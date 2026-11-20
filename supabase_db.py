"""
=============================================================
supabase_db.py - Supabase PostgreSQL Database Adapter for Mahilicious
=============================================================
This module provides a full cloud-native database integration using
Supabase (PostgreSQL + PostgREST REST API) for Mahilicious.

Features:
- Handles user authentication & profiles (including Google OAuth accounts)
- Full CRUD operations for recipes (Create, Read, Update, Delete)
- Favourites / bookmark management
- Native JSONB support for ingredients, instructions, and nutrition
- Automatic fallback handling when offline or unconfigured
=============================================================
"""

import os
import json
import random
from collections import Counter
from dotenv import load_dotenv

# Ensure environment variables from .env are loaded
load_dotenv()

_client = None

AVATAR_COLORS = [
    '#059669',  # Emerald
    '#2563EB',  # Royal Blue
    '#D97706',  # Warm Amber
    '#DC2626',  # Coral Red
    '#7C3AED',  # Purple
    '#DB2777',  # Pink
    '#0D9488',  # Teal
    '#EA580C',  # Flame Orange
]


def get_supabase_client():
    """
    Initializes and returns the Supabase Client singleton.
    Returns None if SUPABASE_URL or SUPABASE_KEY are not configured.
    """
    global _client
    if _client is not None:
        return _client

    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_KEY", "").strip()

    # Reject empty or default placeholder keys
    if not url or not key or url.startswith("your-") or url.startswith("<"):
        return None

    try:
        from supabase import create_client, Client
        _client = create_client(url, key)
        return _client
    except Exception as e:
        print(f"[Supabase Init Warning] Could not initialize Supabase client: {e}")
        return None


def is_connected():
    """
    Checks if Supabase credentials are valid and reachable.
    """
    client = get_supabase_client()
    if not client:
        return False
    try:
        # Lightweight check on the users table
        client.table("users").select("id").limit(1).execute()
        return True
    except Exception as e:
        print(f"[Supabase Connection Check] Connection failed: {e}")
        return False


def _parse_json_field(val, default):
    """
    Safely parses JSON or string data from database columns.
    """
    if val is None:
        return default
    if isinstance(val, (list, dict)):
        return val
    if isinstance(val, str):
        val = val.strip()
        if not val:
            return default
        try:
            return json.loads(val)
        except Exception:
            if isinstance(default, list):
                return [line.strip() for line in val.split("\n") if line.strip()]
            return default
    return default


def _format_supabase_recipe(row):
    """
    Standardizes a Supabase recipe record into the dictionary structure
    expected across all Mahilicious templates and endpoints.
    """
    if not row:
        return None

    recipe = dict(row)
    recipe['id'] = int(recipe['id']) if 'id' in recipe and recipe['id'] is not None else None
    recipe['ingredients'] = _parse_json_field(recipe.get('ingredients'), [])
    recipe['instructions'] = _parse_json_field(recipe.get('instructions'), [])
    recipe['nutrition'] = _parse_json_field(recipe.get('nutrition'), {})

    if 'created_at' in recipe and recipe['created_at']:
        recipe['created_at'] = str(recipe['created_at'])

    return recipe


# ==============================================================================
# User Authentication Helpers
# ==============================================================================

def create_user(name, email, password_hash):
    """
    Creates a new user record in the Supabase users table.
    Returns (user_id, None) on success, or (None, error_message) on failure.
    """
    client = get_supabase_client()
    if not client:
        return None, "Supabase is not configured."

    try:
        clean_name = name.strip()
        clean_email = email.strip().lower()
        color = random.choice(AVATAR_COLORS)

        payload = {
            "name": clean_name,
            "email": clean_email,
            "password_hash": password_hash,
            "avatar_color": color
        }

        res = client.table("users").insert(payload).execute()
        if res.data and len(res.data) > 0:
            return int(res.data[0]["id"]), None
        return None, "Failed to create user record."
    except Exception as e:
        err = str(e)
        if "duplicate key" in err.lower() or "unique constraint" in err.lower() or "idx_users_email" in err.lower() or "23505" in err:
            return None, "An account with this email address already exists."
        return None, f"Registration failed: {err}"


def get_user_by_email(email):
    """
    Fetch a user dictionary by their email address (case-insensitive).
    """
    if not email:
        return None
    client = get_supabase_client()
    if not client:
        return None

    try:
        clean_email = email.strip().lower()
        res = client.table("users").select("*").eq("email", clean_email).limit(1).execute()
        if res.data and len(res.data) > 0:
            user = dict(res.data[0])
            user['id'] = int(user['id'])
            return user
        return None
    except Exception as e:
        print(f"[Supabase get_user_by_email] Error: {e}")
        return None


def get_user_by_id(user_id):
    """
    Fetch a user dictionary by their primary key user_id.
    """
    if not user_id:
        return None
    client = get_supabase_client()
    if not client:
        return None

    try:
        res = client.table("users").select("*").eq("id", int(user_id)).limit(1).execute()
        if res.data and len(res.data) > 0:
            user = dict(res.data[0])
            user['id'] = int(user['id'])
            return user
        return None
    except Exception as e:
        print(f"[Supabase get_user_by_id] Error: {e}")
        return None


def get_or_create_google_user(email, name, google_id=None, profile_picture=None):
    """
    Finds an existing user by email or creates a new user via Google Sign-In.
    Returns the user dict.
    """
    if not email:
        return None

    client = get_supabase_client()
    if not client:
        return None

    clean_email = email.strip().lower()
    existing = get_user_by_email(clean_email)

    if existing:
        updates = {}
        if google_id and not existing.get("google_id"):
            updates["google_id"] = google_id
        if profile_picture and not existing.get("profile_picture"):
            updates["profile_picture"] = profile_picture

        if updates:
            try:
                client.table("users").update(updates).eq("id", existing["id"]).execute()
            except Exception as e:
                print(f"[Supabase Google User Update] Warning: {e}")

        return get_user_by_id(existing["id"])

    # Create new Google user
    color = random.choice(AVATAR_COLORS)
    payload = {
        "name": name.strip(),
        "email": clean_email,
        "password_hash": "oauth_google_account",
        "avatar_color": color,
        "google_id": google_id,
        "profile_picture": profile_picture
    }

    try:
        res = client.table("users").insert(payload).execute()
        if res.data and len(res.data) > 0:
            user = dict(res.data[0])
            user['id'] = int(user['id'])
            return user
    except Exception as e:
        print(f"[Supabase Create Google User Error]: {e}")

    return None


def get_user_stats(user_id):
    """
    Returns dashboard statistics for a specific user:
    - total_saved: count of recipes saved
    - top_category: most frequent recipe category saved
    - joined_at: account creation date
    """
    default_stats = {"total_saved": 0, "top_category": "None", "joined_at": "Unknown"}
    if not user_id:
        return default_stats

    client = get_supabase_client()
    if not client:
        return default_stats

    try:
        uid = int(user_id)
        # Total saved & top category
        fav_res = client.table("favourites").select("id, category", count="exact").eq("user_id", uid).execute()
        total_saved = fav_res.count if fav_res.count is not None else len(fav_res.data or [])

        top_cat = "All"
        if fav_res.data:
            categories = [r.get("category") for r in fav_res.data if r.get("category")]
            if categories:
                top_cat = Counter(categories).most_common(1)[0][0]

        # Joined at
        user_res = client.table("users").select("created_at").eq("id", uid).limit(1).execute()
        joined_at = "Recently"
        if user_res.data and user_res.data[0].get("created_at"):
            joined_at = str(user_res.data[0]["created_at"])[:10]

        return {
            "total_saved": total_saved,
            "top_category": top_cat,
            "joined_at": joined_at
        }
    except Exception as e:
        print(f"[Supabase get_user_stats] Error: {e}")
        return default_stats


# ==============================================================================
# Recipe Operations
# ==============================================================================

def save_generated_recipes(recipes_list, language='en', user_id=None):
    """
    Save the newly generated recipes into Supabase generated_recipes table.
    Returns the list of recipes with their assigned database IDs.
    """
    client = get_supabase_client()
    if not client:
        return recipes_list

    saved_recipes = []
    uid = int(user_id) if user_id else None

    for item in recipes_list:
        ingredients = item.get('ingredients', [])
        if isinstance(ingredients, str):
            ingredients = [i.strip() for i in ingredients.split('\n') if i.strip()]

        instructions = item.get('instructions', [])
        if isinstance(instructions, str):
            instructions = [s.strip() for s in instructions.split('\n') if s.strip()]

        nutrition = item.get('nutrition', {})
        if isinstance(nutrition, str):
            try:
                nutrition = json.loads(nutrition)
            except Exception:
                nutrition = {'calories': item.get('calories', '350 kcal')}

        payload = {
            "title": item.get('title', 'Delicious Dish'),
            "description": item.get('description', ''),
            "category": item.get('category', 'General'),
            "prep_time": item.get('prep_time', '15 mins'),
            "cook_time": item.get('cook_time', '25 mins'),
            "difficulty": item.get('difficulty', 'Medium'),
            "calories": item.get('calories', '350 kcal'),
            "ingredients": ingredients,
            "instructions": instructions,
            "nutrition": nutrition,
            "tips": item.get('tips', ''),
            "substitutes": item.get('substitutes', ''),
            "language": language,
            "user_id": uid
        }

        try:
            res = client.table("generated_recipes").insert(payload).execute()
            if res.data and len(res.data) > 0:
                formatted = _format_supabase_recipe(res.data[0])
                formatted['user_id'] = uid
                formatted['language'] = language
                saved_recipes.append(formatted)
            else:
                copy_item = dict(item)
                copy_item['user_id'] = uid
                copy_item['language'] = language
                saved_recipes.append(copy_item)
        except Exception as e:
            print(f"[Supabase save_generated_recipes item error]: {e}")
            copy_item = dict(item)
            copy_item['user_id'] = uid
            copy_item['language'] = language
            saved_recipes.append(copy_item)

    return saved_recipes


def get_all_recipes(user_id=None, limit=60):
    """
    READ (R): Fetches all active recipes from Supabase generated_recipes.
    If user_id is provided, returns user recipes as well as public ones.
    """
    client = get_supabase_client()
    if not client:
        return []

    try:
        query = client.table("generated_recipes").select("*")
        if user_id:
            uid = int(user_id)
            query = query.or_(f"user_id.eq.{uid},user_id.is.null")
        query = query.order("id", desc=True).limit(limit)

        res = query.execute()
        recipes = [_format_supabase_recipe(row) for row in (res.data or [])]
        for r in recipes:
            r['is_favourite'] = is_favourite(r.get('title', ''), user_id=user_id)
        return recipes
    except Exception as e:
        print(f"[Supabase get_all_recipes] Error: {e}")
        return []


def create_recipe(recipe_data, user_id=None):
    """
    CREATE (C): Inserts a new custom recipe into Supabase.
    Returns the created recipe dictionary.
    """
    client = get_supabase_client()
    if not client:
        return None

    title = recipe_data.get('title', 'My Custom Recipe').strip()
    description = recipe_data.get('description', '').strip()
    category = recipe_data.get('category', 'Everyday Meal').strip()
    prep_time = recipe_data.get('prep_time', '15 mins').strip()
    cook_time = recipe_data.get('cook_time', '20 mins').strip()
    difficulty = recipe_data.get('difficulty', 'Easy').strip()
    calories = recipe_data.get('calories', '320 kcal').strip()
    tips = recipe_data.get('tips', '').strip()
    substitutes = recipe_data.get('substitutes', '').strip()

    ingredients = recipe_data.get('ingredients', [])
    if isinstance(ingredients, str):
        ingredients = [i.strip() for i in ingredients.split('\n') if i.strip()]

    instructions = recipe_data.get('instructions', [])
    if isinstance(instructions, str):
        instructions = [s.strip() for s in instructions.split('\n') if s.strip()]

    nutrition = recipe_data.get('nutrition', {'calories': calories})
    if isinstance(nutrition, str):
        try:
            nutrition = json.loads(nutrition)
        except Exception:
            nutrition = {'calories': calories}

    payload = {
        "title": title,
        "description": description,
        "category": category,
        "prep_time": prep_time,
        "cook_time": cook_time,
        "difficulty": difficulty,
        "calories": calories,
        "ingredients": ingredients,
        "instructions": instructions,
        "nutrition": nutrition,
        "tips": tips,
        "substitutes": substitutes,
        "language": "en",
        "user_id": int(user_id) if user_id else None
    }

    try:
        res = client.table("generated_recipes").insert(payload).execute()
        if res.data and len(res.data) > 0:
            return _format_supabase_recipe(res.data[0])
    except Exception as e:
        print(f"[Supabase create_recipe] Error: {e}")

    return None


def update_recipe(recipe_id, update_data, user_id=None):
    """
    UPDATE (U): Updates an existing recipe's fields in Supabase.
    Returns (True, message) on success, or (False, error) on failure.
    """
    client = get_supabase_client()
    if not client:
        return False, "Supabase is not configured."

    try:
        rid = int(recipe_id)
        # Fetch current record to verify ownership
        check_query = client.table("generated_recipes").select("*").eq("id", rid)
        if user_id:
            uid = int(user_id)
            check_query = check_query.or_(f"user_id.eq.{uid},user_id.is.null")

        res_check = check_query.execute()
        if not res_check.data or len(res_check.data) == 0:
            return False, "Recipe not found or unauthorized."

        existing = res_check.data[0]

        title = update_data.get('title', existing.get('title', '')).strip()
        description = update_data.get('description', existing.get('description', '')).strip()
        category = update_data.get('category', existing.get('category', '')).strip()
        prep_time = update_data.get('prep_time', existing.get('prep_time', '')).strip()
        cook_time = update_data.get('cook_time', existing.get('cook_time', '')).strip()
        difficulty = update_data.get('difficulty', existing.get('difficulty', '')).strip()
        calories = update_data.get('calories', existing.get('calories', '')).strip()
        tips = update_data.get('tips', existing.get('tips', '') or '').strip()
        substitutes = update_data.get('substitutes', existing.get('substitutes', '') or '').strip()

        ingredients = update_data.get('ingredients')
        if ingredients is not None:
            if isinstance(ingredients, str):
                ingredients = [i.strip() for i in ingredients.split('\n') if i.strip()]
        else:
            ingredients = existing.get('ingredients')

        instructions = update_data.get('instructions')
        if instructions is not None:
            if isinstance(instructions, str):
                instructions = [s.strip() for s in instructions.split('\n') if s.strip()]
        else:
            instructions = existing.get('instructions')

        payload = {
            "title": title,
            "description": description,
            "category": category,
            "prep_time": prep_time,
            "cook_time": cook_time,
            "difficulty": difficulty,
            "calories": calories,
            "ingredients": ingredients,
            "instructions": instructions,
            "tips": tips,
            "substitutes": substitutes
        }

        client.table("generated_recipes").update(payload).eq("id", rid).execute()
        return True, "Recipe updated successfully."
    except Exception as e:
        return False, f"Update failed: {str(e)}"


def delete_recipe(recipe_id, user_id=None):
    """
    DELETE (D): Permanently deletes a recipe from Supabase.
    """
    client = get_supabase_client()
    if not client:
        return False

    try:
        rid = int(recipe_id)
        query = client.table("generated_recipes").delete().eq("id", rid)
        if user_id:
            uid = int(user_id)
            query = query.or_(f"user_id.eq.{uid},user_id.is.null")

        res = query.execute()
        return len(res.data or []) > 0
    except Exception as e:
        print(f"[Supabase delete_recipe] Error: {e}")
        return False


def save_favourite(recipe_data, user_id=None):
    """
    Save a recipe to the Supabase favourites table, linked to user_id.
    If the recipe already exists for this user, returns its existing ID.
    """
    client = get_supabase_client()
    if not client:
        return None, False

    title = recipe_data.get('title', '').strip()
    uid = int(user_id) if user_id else None

    try:
        # Check if already favourited by this user
        check_query = client.table("favourites").select("id").eq("title", title)
        if uid:
            check_query = check_query.eq("user_id", uid)
        else:
            check_query = check_query.is_("user_id", "null")

        existing_res = check_query.execute()
        if existing_res.data and len(existing_res.data) > 0:
            return int(existing_res.data[0]['id']), False

        ingredients = recipe_data.get('ingredients', [])
        if isinstance(ingredients, str):
            ingredients = [i.strip() for i in ingredients.split('\n') if i.strip()]

        instructions = recipe_data.get('instructions', [])
        if isinstance(instructions, str):
            instructions = [s.strip() for s in instructions.split('\n') if s.strip()]

        nutrition = recipe_data.get('nutrition', {})
        if isinstance(nutrition, str):
            try:
                nutrition = json.loads(nutrition)
            except Exception:
                nutrition = {'calories': recipe_data.get('calories', '300 kcal')}

        payload = {
            "title": title,
            "description": recipe_data.get('description', ''),
            "category": recipe_data.get('category', 'General'),
            "prep_time": recipe_data.get('prep_time', '15 mins'),
            "cook_time": recipe_data.get('cook_time', '20 mins'),
            "difficulty": recipe_data.get('difficulty', 'Easy'),
            "calories": recipe_data.get('calories', '300 kcal'),
            "ingredients": ingredients,
            "instructions": instructions,
            "nutrition": nutrition,
            "tips": recipe_data.get('tips', ''),
            "substitutes": recipe_data.get('substitutes', ''),
            "language": recipe_data.get('language', 'en'),
            "user_id": uid
        }

        res = client.table("favourites").insert(payload).execute()
        if res.data and len(res.data) > 0:
            return int(res.data[0]['id']), True
        return None, False
    except Exception as e:
        print(f"[Supabase save_favourite] Error: {e}")
        return None, False


def get_all_favourites(user_id=None):
    """
    Retrieve recipes saved in the Supabase favourites table.
    If user_id is provided, returns only recipes for that user; otherwise returns all.
    """
    client = get_supabase_client()
    if not client:
        return []

    try:
        query = client.table("favourites").select("*")
        if user_id:
            query = query.eq("user_id", int(user_id))

        res = query.order("id", desc=True).execute()
        return [_format_supabase_recipe(row) for row in (res.data or [])]
    except Exception as e:
        print(f"[Supabase get_all_favourites] Error: {e}")
        return []


def get_favourite_by_id(fav_id):
    """
    Fetch a single favourite recipe by its ID.
    """
    client = get_supabase_client()
    if not client or not fav_id:
        return None

    try:
        res = client.table("favourites").select("*").eq("id", int(fav_id)).limit(1).execute()
        if res.data and len(res.data) > 0:
            return _format_supabase_recipe(res.data[0])
        return None
    except Exception as e:
        print(f"[Supabase get_favourite_by_id] Error: {e}")
        return None


def delete_favourite(fav_id, user_id=None):
    """
    Remove a recipe from favourites table by ID.
    """
    client = get_supabase_client()
    if not client or not fav_id:
        return False

    try:
        fid = int(fav_id)
        query = client.table("favourites").delete().eq("id", fid)
        if user_id:
            query = query.eq("user_id", int(user_id))

        res = query.execute()
        return len(res.data or []) > 0
    except Exception as e:
        print(f"[Supabase delete_favourite] Error: {e}")
        return False


def is_favourite(title, user_id=None):
    """
    Check if a recipe is in the favourites table by its title for a given user.
    """
    if not title:
        return False
    client = get_supabase_client()
    if not client:
        return False

    try:
        query = client.table("favourites").select("id").eq("title", title.strip())
        if user_id:
            query = query.eq("user_id", int(user_id))
        else:
            query = query.is_("user_id", "null")

        res = query.limit(1).execute()
        return bool(res.data and len(res.data) > 0)
    except Exception as e:
        print(f"[Supabase is_favourite] Error: {e}")
        return False


def get_recipe_by_id(recipe_id):
    """
    Retrieve recipe by ID.
    Checks favourites first, then generated_recipes table.
    """
    client = get_supabase_client()
    if not client or not recipe_id:
        return None

    try:
        rid = int(recipe_id)

        # Check favourites first
        fav_res = client.table("favourites").select("*").eq("id", rid).limit(1).execute()
        if fav_res.data and len(fav_res.data) > 0:
            recipe = _format_supabase_recipe(fav_res.data[0])
            recipe['is_favourite'] = True
            recipe['source'] = 'favourites'
            return recipe

        # Check generated_recipes
        gen_res = client.table("generated_recipes").select("*").eq("id", rid).limit(1).execute()
        if gen_res.data and len(gen_res.data) > 0:
            recipe = _format_supabase_recipe(gen_res.data[0])
            recipe['is_favourite'] = is_favourite(recipe.get('title', ''))
            recipe['source'] = 'generated'
            return recipe

        return None
    except Exception as e:
        print(f"[Supabase get_recipe_by_id] Error: {e}")
        return None
