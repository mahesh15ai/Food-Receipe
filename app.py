"""
=============================================================
app.py - Main Flask Application for Mahilicious
=============================================================
This is the main entry point for the Mahilicious application.
It defines all the URL routes, handles user authentication,
coordinates with SQLite (database.py) and Gemini AI (ai_engine.py),
and renders HTML templates.

Routes:
- GET  /                     : Home page with ingredient input & guide
- POST /generate             : Processes ingredients & generates 3 AI recipes
- GET  /recipes              : Displays current generated recipes
- GET  /recipe/<int:id>      : Displays full recipe details with print option
- GET  /chatbot              : Interactive Chef AI Chatbot page
- POST /api/chat             : JSON endpoint for chatbot messages
- GET & POST /register       : User registration / sign-up
- GET & POST /login          : User sign-in with sessions
- GET  /logout               : Sign out and clear session
- GET  /profile              : User account dashboard & statistics
- GET  /favourites           : Displays saved favourite recipes from SQLite
- POST /api/favourites/add   : Saves a recipe to SQLite favourites (user-linked)
- POST /api/favourites/remove/<int:id> : Removes a favourite recipe
- GET  /api/shopping-list/<int:id>    : Formats shopping list for clipboard
- GET  /api/random-tip       : Returns a random cooking tip
- GET  /api/status           : System health check (API key & DB status)
"""

import os
import re
import secrets
import urllib.parse
from functools import wraps
import requests
from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import database
import ai_engine

# Initialize Flask App
app = Flask(__name__)

# Secret key for secure session cookies
app.secret_key = os.getenv("SECRET_KEY", "mahilicious_recipe_secret_key_2026")

# Ensure database tables exist at startup
database.init_db()


# -----------------------------------------------------------
# Context Processor (makes common variables available in all templates)
# -----------------------------------------------------------
@app.context_processor
def inject_globals():
    """
    Injects global variables into every Jinja2 template:
    - api_ready: True if GEMINI_API_KEY is configured
    - fav_count: Total number of saved favourite recipes for the current user
    - current_user: Current logged-in user dict (or None if guest)
    """
    user_id = session.get("user_id")
    current_user = database.get_user_by_id(user_id) if user_id else None

    try:
        favs = database.get_all_favourites(user_id=user_id)
        fav_count = len(favs)
    except Exception:
        fav_count = 0

    return {
        "api_ready": ai_engine.is_api_key_configured(),
        "gemini_model": os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
        "fav_count": fav_count,
        "current_user": current_user
    }


# -----------------------------------------------------------
# Login Required Decorator
# -----------------------------------------------------------
def login_required(f):
    """
    Ensures that a user is signed in before accessing protected routes.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session or not database.get_user_by_id(session["user_id"]):
            flash("You must be signed in to create and generate recipes. Please sign in or create an account.", "info")
            next_url = request.url if request.method == "GET" else url_for("index")
            return redirect(url_for("login", next=next_url))
        return f(*args, **kwargs)
    return decorated_function


# -----------------------------------------------------------
# Route: User Registration (Sign Up)
# -----------------------------------------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    """
    User registration route.
    Handles new account creation with secure password hashing.
    """
    if "user_id" in session and database.get_user_by_id(session["user_id"]):
        return redirect(url_for("index"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        # Form Validations
        if not name or not email or not password:
            flash("Please fill in all required fields.", "danger")
            return render_template("register.html", name=name, email=email)

        # Basic email validation
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            flash("Please enter a valid email address.", "danger")
            return render_template("register.html", name=name, email=email)

        if len(password) < 6:
            flash("Password must be at least 6 characters long.", "danger")
            return render_template("register.html", name=name, email=email)

        if password != confirm_password:
            flash("Passwords do not match. Please re-enter.", "danger")
            return render_template("register.html", name=name, email=email)

        # Hash password and create user in SQLite
        password_hash = generate_password_hash(password)
        user_id, error = database.create_user(name, email, password_hash)

        if error:
            flash(error, "danger")
            return render_template("register.html", name=name, email=email)

        # Log in automatically upon registration
        session["user_id"] = user_id
        session["user_name"] = name
        session["user_email"] = email

        flash(f"Welcome to Mahilicious, {name}! Your account has been created successfully.", "success")
        return redirect(url_for("index"))

    return render_template("register.html")


# -----------------------------------------------------------
# Route: User Login (Sign In)
# -----------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    """
    User sign-in route.
    Verifies credentials and initiates a secure session.
    """
    if "user_id" in session and database.get_user_by_id(session["user_id"]):
        return redirect(url_for("index"))

    next_page = request.args.get("next")

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Please provide both email and password.", "danger")
            return render_template("login.html", email=email, next=next_page)

        user = database.get_user_by_email(email)

        if not user or not check_password_hash(user["password_hash"], password):
            flash("Invalid email or password. Please try again.", "danger")
            return render_template("login.html", email=email, next=next_page)

        # Login successful
        session["user_id"] = user["id"]
        session["user_name"] = user["name"]
        session["user_email"] = user["email"]

        flash(f"Welcome back, {user['name']}!", "success")
        if next_page and next_page.startswith("/"):
            return redirect(next_page)
        return redirect(url_for("index"))

    return render_template("login.html", next=next_page)


# -----------------------------------------------------------
# Route: User Logout (Sign Out)
# -----------------------------------------------------------
@app.route("/logout")
def logout():
    """
    Clears session and logs out user.
    """
    user_name = session.get("user_name")
    session.clear()
    flash(f"You have been signed out. See you next time!", "info")
    return redirect(url_for("index"))


# -----------------------------------------------------------
# Route: Google OAuth 2.0 Sign-In Initiator
# -----------------------------------------------------------
@app.route("/login/google")
def login_google():
    """
    Initiates Google OAuth 2.0 flow.
    If GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are configured in .env,
    redirects directly to accounts.google.com.
    If credentials are not yet set, opens a helpful setup & instant demo page.
    """
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()

    if not client_id or not client_secret:
        return render_template(
            "google_auth_demo.html",
            has_credentials=False,
            redirect_uri=url_for("login_google_callback", _external=True)
        )

    # Generate CSRF state token to prevent cross-site request forgery
    state = secrets.token_urlsafe(16)
    session["oauth_state"] = state

    redirect_uri = url_for("login_google_callback", _external=True)
    google_auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        + urllib.parse.urlencode({
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "offline",
            "prompt": "select_account"
        })
    )
    return redirect(google_auth_url)


# -----------------------------------------------------------
# Route: Google OAuth 2.0 Callback
# -----------------------------------------------------------
@app.route("/login/google/callback")
def login_google_callback():
    """
    Callback handler for Google OAuth 2.0.
    Exchanges code for access token and retrieves verified Google profile.
    """
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
    code = request.args.get("code")
    state = request.args.get("state")

    # Verify CSRF state token
    expected_state = session.get("oauth_state")
    if not state or state != expected_state:
        flash("Invalid Google login session state. Please try again.", "danger")
        return redirect(url_for("login"))

    session.pop("oauth_state", None)

    if not code:
        flash("Google sign-in was cancelled or encountered an error.", "warning")
        return redirect(url_for("login"))

    redirect_uri = url_for("login_google_callback", _external=True)
    token_url = "https://oauth2.googleapis.com/token"
    token_data = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code"
    }

    try:
        token_res = requests.post(token_url, data=token_data, timeout=10)
        token_json = token_res.json()
        access_token = token_json.get("access_token")

        if not access_token:
            error_msg = token_json.get("error_description", "Unable to retrieve access token from Google.")
            flash(f"Google authorization failed: {error_msg}", "danger")
            return redirect(url_for("login"))

        # Fetch Google user profile
        userinfo_res = requests.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10
        )
        profile_data = userinfo_res.json()

        email = profile_data.get("email")
        name = profile_data.get("name") or (email.split("@")[0] if email else "Google User")
        google_id = profile_data.get("sub")
        picture = profile_data.get("picture")

        if not email:
            flash("Google account email could not be verified.", "danger")
            return redirect(url_for("login"))

        # Create or update user in SQLite
        user = database.get_or_create_google_user(email, name, google_id=google_id, profile_picture=picture)

        session["user_id"] = user["id"]
        session["user_name"] = user["name"]
        session["user_email"] = user["email"]

        flash(f"Successfully signed in with Google! Welcome, {user['name']}.", "success")
        return redirect(url_for("index"))

    except Exception as e:
        flash(f"Google Sign-In connection error: {str(e)}", "danger")
        return redirect(url_for("login"))


# -----------------------------------------------------------
# Route: Quick Demo Google Sign-In (For offline/viva testing)
# -----------------------------------------------------------
@app.route("/login/google/demo", methods=["POST"])
def login_google_demo():
    """
    Provides an instant 1-click Google authentication demo.
    Allows presentation/viva evaluators to test the Google Sign-In experience
    without waiting for Google Cloud Console OAuth verification.
    """
    demo_email = request.form.get("email", "mahi.google@gmail.com").strip().lower()
    demo_name = request.form.get("name", "Mahi Kangule").strip()

    if not demo_email or "@" not in demo_email:
        demo_email = "mahi.google@gmail.com"
    if not demo_name:
        demo_name = "Mahi Kangule"

    user = database.get_or_create_google_user(
        demo_email,
        demo_name,
        google_id="google_oauth_demo_1001",
        profile_picture="https://lh3.googleusercontent.com/a/default-user=s96-c"
    )

    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    session["user_email"] = user["email"]

    flash(f"Signed in successfully via Google account ({demo_email})! Welcome, {user['name']}.", "success")
    return redirect(url_for("index"))


# -----------------------------------------------------------
# Route: User Profile Dashboard
# -----------------------------------------------------------
@app.route("/profile")
@login_required
def profile():
    """
    User account profile page with personal statistics.
    """
    user_id = session.get("user_id")
    user = database.get_user_by_id(user_id)
    stats = database.get_user_stats(user_id)
    recent_favs = database.get_all_favourites(user_id=user_id)[:3]

    return render_template("profile.html", user=user, stats=stats, recent_favs=recent_favs)


# -----------------------------------------------------------
# Route 1: Home Page
# -----------------------------------------------------------
@app.route("/")
def index():
    """
    Home page route.
    Displays project hero banner, ingredient input box,
    category pills, language selector, and 'How to Use' guide.
    """
    return render_template("index.html")


# -----------------------------------------------------------
# Route 2: Generate Recipes (POST)
# -----------------------------------------------------------
@app.route("/generate", methods=["POST"])
@login_required
def generate():
    """
    Handles recipe generation request:
    Requires user to be signed in.
    1. Extracts ingredients, category, and language from form.
    2. Calls ai_engine.generate_recipes().
    3. Saves generated recipes into SQLite database.
    4. Redirects to /recipes to view the result cards.
    """
    ingredients = request.form.get("ingredients", "").strip()
    category = request.form.get("category", "All").strip()
    language = request.form.get("language", "en").strip()

    if not ingredients:
        flash("Please enter at least one ingredient to generate recipes.", "warning")
        return redirect(url_for("index"))

    # Call Gemini AI
    result = ai_engine.generate_recipes(ingredients, category=category, language=language)

    if not result.get("success"):
        return render_template(
            "recipes.html",
            error_message=result.get("message", "Could not generate recipes. Please try again."),
            ingredients_input=ingredients,
            category=category,
            language=language
        )

    # Save generated recipes into SQLite
    user_id = session.get("user_id")
    raw_recipes = result.get("recipes", [])
    saved_recipes = database.save_generated_recipes(raw_recipes, language=language, user_id=user_id)

    # Store current batch in user session for viewing
    session["current_recipes"] = saved_recipes
    session["ingredients_input"] = ingredients
    session["category_input"] = category
    session["language_input"] = language

    return redirect(url_for("recipes"))


# -----------------------------------------------------------
# Route 3: View Generated Recipes (Read from SQLite Database)
# -----------------------------------------------------------
@app.route("/recipes")
@login_required
def recipes():
    """
    Displays live recipes from the SQLite database (no static data).
    All recipes are persisted in database/recipes.db with full CRUD support.
    """
    user_id = session.get("user_id")
    recipes_list = database.get_all_recipes(user_id=user_id)
    ingredients_input = session.get("ingredients_input", "")
    category = session.get("category_input", "All")
    language = session.get("language_input", "en")

    return render_template(
        "recipes.html",
        recipes=recipes_list,
        ingredients_input=ingredients_input,
        category=category,
        language=language
    )


# -----------------------------------------------------------
# Route: Create Recipe Manually (POST API - CRUD: Create)
# -----------------------------------------------------------
@app.route("/api/recipes/create", methods=["POST"])
@login_required
def api_create_recipe():
    """
    CRUD - CREATE (C):
    Adds a new custom recipe created manually by the user into SQLite.
    """
    user_id = session.get("user_id")
    data = request.get_json() or {}

    title = data.get("title", "").strip()
    if not title:
        return jsonify({"success": False, "message": "Recipe title is required."}), 400

    new_recipe = database.create_recipe(data, user_id=user_id)
    return jsonify({
        "success": True,
        "message": f"Recipe '{title}' created successfully!",
        "recipe": new_recipe
    })


# -----------------------------------------------------------
# Route: Get Recipe Details JSON (GET API for edit form)
# -----------------------------------------------------------
@app.route("/api/recipes/<int:recipe_id>", methods=["GET"])
@login_required
def api_get_recipe(recipe_id):
    """
    CRUD - READ (R):
    Returns raw recipe JSON for pre-populating the edit modal.
    """
    recipe = database.get_recipe_by_id(recipe_id)
    if not recipe:
        return jsonify({"success": False, "message": "Recipe not found."}), 404
    return jsonify({"success": True, "recipe": recipe})


# -----------------------------------------------------------
# Route: Update Recipe (POST API - CRUD: Update)
# -----------------------------------------------------------
@app.route("/api/recipes/update/<int:recipe_id>", methods=["POST"])
@login_required
def api_update_recipe(recipe_id):
    """
    CRUD - UPDATE (U):
    Updates recipe fields in SQLite database.
    """
    user_id = session.get("user_id")
    data = request.get_json() or {}

    success, message = database.update_recipe(recipe_id, data, user_id=user_id)
    if success:
        updated_recipe = database.get_recipe_by_id(recipe_id)
        return jsonify({
            "success": True,
            "message": "Recipe updated successfully!",
            "recipe": updated_recipe
        })
    return jsonify({"success": False, "message": message}), 400


# -----------------------------------------------------------
# Route: Delete Recipe (POST API - CRUD: Delete)
# -----------------------------------------------------------
@app.route("/api/recipes/delete/<int:recipe_id>", methods=["POST"])
@login_required
def api_delete_recipe(recipe_id):
    """
    CRUD - DELETE (D):
    Deletes a recipe from SQLite database.
    """
    user_id = session.get("user_id")
    deleted = database.delete_recipe(recipe_id, user_id=user_id)
    if deleted:
        return jsonify({"success": True, "message": "Recipe deleted successfully."})
    return jsonify({"success": False, "message": "Recipe not found or permission denied."}), 404


# -----------------------------------------------------------
# Route 4: Recipe Details (Step-by-step & Print View)
# -----------------------------------------------------------
@app.route("/recipe/<int:recipe_id>")
def recipe_details(recipe_id):
    """
    Displays full details of a specific recipe:
    Ingredients checklist, step-by-step directions, tips, substitutes,
    and nutritional breakdown.
    """
    recipe = database.get_recipe_by_id(recipe_id)

    if not recipe:
        flash("Recipe not found.", "danger")
        return redirect(url_for("recipes"))

    return render_template("recipe_details.html", recipe=recipe)


# -----------------------------------------------------------
# Route 5: Chef AI Chatbot Page
# -----------------------------------------------------------
@app.route("/chatbot")
def chatbot():
    """
    Renders the interactive Chef AI Chatbot page.
    """
    return render_template("chatbot.html")


# -----------------------------------------------------------
# Route 6: Chef AI Chat JSON API Endpoint
# -----------------------------------------------------------
@app.route("/api/chat", methods=["POST"])
def api_chat():
    """
    Accepts JSON payload: {"message": "...", "language": "en"}
    Requires user to be signed in.
    Returns genuine Gemini AI reply as JSON.
    """
    user_id = session.get("user_id")
    if not user_id or not database.get_user_by_id(user_id):
        return jsonify({
            "success": False,
            "auth_required": True,
            "reply": "🔒 Sign-in required: Please sign in or create an account to chat with Chef AI."
        }), 401

    data = request.get_json() or {}
    user_message = data.get("message", "").strip()
    language = data.get("language", "en")

    if not user_message:
        return jsonify({"success": False, "reply": "Please enter a question for Chef AI."}), 400

    result = ai_engine.ask_chef_chatbot(user_message, language=language)
    return jsonify(result)


# -----------------------------------------------------------
# Route 7: Favourites Page
# -----------------------------------------------------------
@app.route("/favourites")
def favourites():
    """
    Displays all saved favourite recipes stored in the SQLite database.
    If user is signed in, loads their personalized saved favourites.
    """
    user_id = session.get("user_id")
    fav_recipes = database.get_all_favourites(user_id=user_id)
    return render_template("favourites.html", favourites=fav_recipes)


# -----------------------------------------------------------
# Route 8: Add to Favourites (POST API)
# -----------------------------------------------------------
@app.route("/api/favourites/add", methods=["POST"])
def api_add_favourite():
    """
    Adds a recipe to favourites in SQLite database, linked to current user.
    """
    user_id = session.get("user_id")
    data = request.get_json() or {}
    recipe_id = data.get("recipe_id")

    if recipe_id:
        recipe = database.get_recipe_by_id(int(recipe_id))
        if not recipe:
            return jsonify({"success": False, "message": "Recipe not found."}), 404
        new_id, is_new = database.save_favourite(recipe, user_id=user_id)
    else:
        new_id, is_new = database.save_favourite(data, user_id=user_id)

    if is_new:
        message = "Recipe saved to your favourites!"
    else:
        message = "Recipe is already in your favourites!"

    return jsonify({"success": True, "message": message, "id": new_id})


# -----------------------------------------------------------
# Route 9: Remove from Favourites (POST API)
# -----------------------------------------------------------
@app.route("/api/favourites/remove/<int:fav_id>", methods=["POST"])
def api_remove_favourite(fav_id):
    """
    Deletes a recipe from the favourites table in SQLite for this user.
    """
    user_id = session.get("user_id")
    deleted = database.delete_favourite(fav_id, user_id=user_id)
    if deleted:
        flash("Recipe removed from favourites.", "info")
        return jsonify({"success": True, "message": "Removed from favourites."})
    return jsonify({"success": False, "message": "Recipe not found or unauthorized."}), 404


# -----------------------------------------------------------
# Route 10: System Status / Health Check
# -----------------------------------------------------------
@app.route("/api/status")
def api_status():
    """
    Health check route for presentation/viva demonstration.
    Reports API key status, model in use, and database connection.
    """
    api_ready = ai_engine.is_api_key_configured()
    try:
        favs = database.get_all_favourites()
        db_type = database.get_database_type()
        db_status = f"Connected ({db_type})"
        total_favs = len(favs)
    except Exception as e:
        db_status = f"Error: {str(e)}"
        total_favs = 0

    return jsonify({
        "project": "Mahilicious - AI Food Recipe Generator",
        "api_configured": api_ready,
        "gemini_model": os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite"),
        "database": db_status,
        "database_type": database.get_database_type(),
        "total_saved_favourites": total_favs,
        "supported_languages": ["en (English)", "hi (Hindi)", "mr (Marathi)"]
    })


# -----------------------------------------------------------
# Route 11: Export Shopping List API
# -----------------------------------------------------------
@app.route("/api/shopping-list/<int:recipe_id>")
def api_shopping_list(recipe_id):
    """
    Returns clean ingredients list for easy clipboard copying.
    """
    recipe = database.get_recipe_by_id(recipe_id)
    if not recipe:
        return jsonify({"success": False, "message": "Recipe not found."}), 404

    ingredients = recipe.get("ingredients", [])
    if isinstance(ingredients, str):
        ingredients = [i.strip() for i in ingredients.split("\n") if i.strip()]

    return jsonify({
        "success": True,
        "title": recipe.get("title", "Recipe"),
        "shopping_list": ingredients
    })


# -----------------------------------------------------------
# Route 12: Random Quick Recipe Suggestion
# -----------------------------------------------------------
@app.route("/api/random-tip")
def api_random_tip():
    """
    Returns a quick random cooking tip from Chef AI.
    """
    tips = [
        "Always sauté garlic on medium heat — high heat turns it bitter in seconds!",
        "Let your pan heat up fully before adding oil — it prevents sticking.",
        "Salt pasta water generously — it should taste like the sea!",
        "For fluffier scrambled eggs, whisk in a splash of cold water, not milk.",
        "Add a pinch of sugar to tomato-based sauces to balance acidity.",
        "Refrigerate onions for 15 minutes before cutting to avoid teary eyes!",
        "Rinse rice 2-3 times before cooking to remove excess starch.",
        "Add olive oil after cooking, not before — it preserves its rich flavor.",
        "Remove seeds from chili for less heat but full pepper aroma.",
        "Steam vegetables instead of boiling to retain more nutrients.",
        "Squeeze lemon at the END of cooking to keep its bright fresh flavor.",
        "Brown butter (not just melt it!) adds a rich nutty depth to any dish.",
    ]
    import random
    return jsonify({"success": True, "tip": random.choice(tips)})


# -----------------------------------------------------------
# Run Application
# -----------------------------------------------------------
if __name__ == "__main__":
    print("==================================================")
    print("  🍲 Mahilicious - AI Food Recipe Generator Starting... ")
    print("  Open your browser at: http://127.0.0.1:5000    ")
    print("==================================================")
    app.run(host="127.0.0.1", port=5000, debug=True)
