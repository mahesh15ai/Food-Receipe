"""
=============================================================
app.py - Main Flask Application for AI Food Recipe Generator
=============================================================
This is the main entry point for the application.
It defines all the URL routes, handles form submissions,
coordinates with SQLite (database.py) and Gemini AI (ai_engine.py),
and renders HTML templates.

Routes:
- GET  /                     : Home page with ingredient input & guide
- POST /generate             : Processes ingredients & generates 3 AI recipes
- GET  /recipes              : Displays current generated recipes
- GET  /recipe/<int:id>      : Displays full recipe details with print option
- GET  /chatbot              : Interactive Chef AI Chatbot page
- POST /api/chat             : JSON endpoint for chatbot messages
- GET  /favourites           : Displays saved favourite recipes from SQLite
- POST /api/favourites/add   : Saves a recipe to SQLite favourites
- POST /api/favourites/remove/<int:id> : Removes a favourite recipe
- GET  /api/status           : System health check (API key & DB status)
"""

import os
from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash
import database
import ai_engine

# Initialize Flask App
app = Flask(__name__)

# Secret key for secure session cookies
app.secret_key = os.getenv("SECRET_KEY", "recipe_secret_key_2026")

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
    - fav_count: Total number of saved favourite recipes in SQLite
    """
    try:
        favs = database.get_all_favourites()
        fav_count = len(favs)
    except Exception:
        fav_count = 0

    return {
        "api_ready": ai_engine.is_api_key_configured(),
        "gemini_model": os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
        "fav_count": fav_count
    }


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
def generate():
    """
    Handles recipe generation request:
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
        # Pass error to recipes page
        return render_template(
            "recipes.html",
            error_message=result.get("message"),
            ingredients_input=ingredients,
            category=category,
            language=language,
            recipes=[]
        )

    # Save generated recipes into SQLite so they can be viewed individually
    raw_recipes = result.get("recipes", [])
    saved_recipes = database.save_generated_recipes(raw_recipes, language=language)

    # Store IDs in user session for this generation round
    session["latest_recipe_ids"] = [r["id"] for r in saved_recipes]
    session["last_ingredients"] = ingredients
    session["last_category"] = category
    session["last_language"] = language

    return redirect(url_for("recipes"))


# -----------------------------------------------------------
# Route 3: View Generated Recipes (GET)
# -----------------------------------------------------------
@app.route("/recipes")
def recipes():
    """
    Displays the generated recipes.
    Fetches the recipes from SQLite using the IDs stored in session.
    """
    recipe_ids = session.get("latest_recipe_ids", [])
    recipe_list = []

    for r_id in recipe_ids:
        r = database.get_recipe_by_id(r_id)
        if r:
            recipe_list.append(r)

    return render_template(
        "recipes.html",
        recipes=recipe_list,
        ingredients_input=session.get("last_ingredients", ""),
        category=session.get("last_category", "All"),
        language=session.get("last_language", "en"),
        error_message=None
    )


# -----------------------------------------------------------
# Route 4: Recipe Details View
# -----------------------------------------------------------
@app.route("/recipe/<int:recipe_id>")
def recipe_details(recipe_id):
    """
    Detailed recipe view:
    Shows full ingredients list, step-by-step numbered cooking instructions,
    nutritional info, chef's tips, substitutes, and print button.
    """
    recipe = database.get_recipe_by_id(recipe_id)

    if not recipe:
        flash("Recipe not found.", "danger")
        return redirect(url_for("index"))

    return render_template("recipe_details.html", recipe=recipe)


# -----------------------------------------------------------
# Route 5: Chef AI Chatbot Page
# -----------------------------------------------------------
@app.route("/chatbot")
def chatbot():
    """
    Renders the interactive cooking assistant chatbot page.
    """
    return render_template("chatbot.html")


# -----------------------------------------------------------
# Route 6: Chatbot API Endpoint (POST JSON)
# -----------------------------------------------------------
@app.route("/api/chat", methods=["POST"])
def api_chat():
    """
    Accepts JSON payload: {"message": "...", "language": "en"}
    Returns genuine Gemini AI reply as JSON.
    """
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
    """
    fav_recipes = database.get_all_favourites()
    return render_template("favourites.html", favourites=fav_recipes)


# -----------------------------------------------------------
# Route 8: Add to Favourites (POST API)
# -----------------------------------------------------------
@app.route("/api/favourites/add", methods=["POST"])
def api_add_favourite():
    """
    Adds a recipe to favourites in SQLite database.
    Can accept either a recipe_id or a raw recipe JSON object.
    """
    data = request.get_json() or {}
    recipe_id = data.get("recipe_id")

    if recipe_id:
        recipe = database.get_recipe_by_id(int(recipe_id))
        if not recipe:
            return jsonify({"success": False, "message": "Recipe not found."}), 404
        new_id, is_new = database.save_favourite(recipe)
    else:
        # Save raw recipe dict
        new_id, is_new = database.save_favourite(data)

    if is_new:
        message = "Recipe saved to your favourites! ❤️"
    else:
        message = "Recipe is already in your favourites! ⭐️"

    return jsonify({"success": True, "message": message, "id": new_id})


# -----------------------------------------------------------
# Route 9: Remove from Favourites (POST API)
# -----------------------------------------------------------
@app.route("/api/favourites/remove/<int:fav_id>", methods=["POST"])
def api_remove_favourite(fav_id):
    """
    Deletes a recipe from the favourites table in SQLite.
    """
    deleted = database.delete_favourite(fav_id)
    if deleted:
        flash("Recipe removed from favourites.", "info")
        return jsonify({"success": True, "message": "Removed from favourites."})
    return jsonify({"success": False, "message": "Recipe not found."}), 404


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
        db_status = "Connected (SQLite)"
        total_favs = len(favs)
    except Exception as e:
        db_status = f"Error: {str(e)}"
        total_favs = 0

    return jsonify({
        "project": "AI Food Recipe Generator",
        "api_configured": api_ready,
        "gemini_model": os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
        "database": db_status,
        "total_saved_favourites": total_favs,
        "supported_languages": ["en (English)", "hi (Hindi)", "mr (Marathi)"]
    })


# -----------------------------------------------------------
# Route 11: Shopping List Generator
# -----------------------------------------------------------
@app.route("/api/shopping-list/<int:recipe_id>")
def api_shopping_list(recipe_id):
    """
    Returns the ingredients of a recipe as a plain shopping list (JSON).
    """
    recipe = database.get_recipe_by_id(recipe_id)
    if not recipe:
        return jsonify({"success": False, "message": "Recipe not found."}), 404

    ingredients = recipe.get("ingredients", [])
    if isinstance(ingredients, str):
        ingredients = [ingredients]

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
        "🧄 Always sauté garlic on medium heat — high heat turns it bitter in seconds!",
        "🍳 Let your pan heat up fully before adding oil — it prevents sticking.",
        "🧂 Salt pasta water generously — it should taste like the sea!",
        "🥚 For fluffier scrambled eggs, whisk in a splash of cold water, not milk.",
        "🍅 Add a pinch of sugar to tomato-based sauces to balance acidity.",
        "🧅 Refrigerate onions for 15 minutes before cutting to avoid teary eyes!",
        "🍚 Rinse rice 2-3 times before cooking to remove excess starch.",
        "🫒 Add olive oil after cooking, not before — it preserves its flavor.",
        "🌶️ Remove seeds from chili for less heat but full flavor.",
        "🥦 Steam vegetables instead of boiling to retain more nutrients.",
        "🍋 Squeeze lemon at the END of cooking to keep its bright fresh flavor.",
        "🧈 Brown butter (not just melt it!) adds a rich nutty depth to any dish.",
    ]
    import random
    return jsonify({"success": True, "tip": random.choice(tips)})


# -----------------------------------------------------------
# Run Application
# -----------------------------------------------------------
if __name__ == "__main__":
    # Run local server on port 5000 with debug enabled
    print("==================================================")
    print("  🍲 AI Food Recipe Generator Starting...        ")
    print("  Open your browser at: http://127.0.0.1:5000    ")
    print("==================================================")
    app.run(host="127.0.0.1", port=5000, debug=True)
