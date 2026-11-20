"""
=============================================================
database.py - Database Management & Master Adapter for Mahilicious
=============================================================
This module acts as the unified database layer for Mahilicious.
It supports both:
1. Supabase (Cloud PostgreSQL) - production/cloud-native backend
2. SQLite (Local database/recipes.db) - offline/development fallback

Dual-Engine Architecture:
- If SUPABASE_URL and SUPABASE_KEY are provided in .env, all operations
  route transparently to Supabase Cloud PostgreSQL.
- If not configured or offline, the app seamlessly falls back to
  SQLite with zero configuration and zero downtime.

Tables / Entities:
1. users: User authentication, passwords, profiles & Google OAuth.
2. favourites: Bookmarked user recipes with nutrition & tips.
3. generated_recipes: Persisted AI & custom CRUD recipes.
=============================================================
"""

import os
import sqlite3
import json
import random
from dotenv import load_dotenv

# Import the Supabase database module
import supabase_db

load_dotenv()

# Define paths for local SQLite storage
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, "database")
DB_PATH = os.path.join(DB_DIR, "recipes.db")


# ==============================================================================
# Database Engine Detection
# ==============================================================================

def is_supabase_enabled():
    """
    Returns True if Supabase credentials are configured in .env.
    """
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_KEY", "").strip()
    if not url or not key:
        return False
    if url.startswith("your-") or url.startswith("<"):
        return False
    return True


def get_database_type():
    """
    Returns a human-readable string of the active database backend.
    Used for dashboard status, health checks, and viva presentations.
    """
    if is_supabase_enabled():
        return "Supabase (Cloud PostgreSQL)"
    return "SQLite (Local Database)"


# ==============================================================================
# Local SQLite Initialization & Connection
# ==============================================================================

def get_db_connection():
    """
    Establish and return a connection to the local SQLite database.
    """
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """
    Initialize local database tables if they do not already exist.
    Called once when Flask starts up.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Table 1: Users table for Authentication
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            avatar_color TEXT DEFAULT '#059669',
            google_id TEXT DEFAULT NULL,
            profile_picture TEXT DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Table 2: Favourites table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS favourites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            category TEXT,
            prep_time TEXT,
            cook_time TEXT,
            difficulty TEXT,
            calories TEXT,
            ingredients TEXT,
            instructions TEXT,
            nutrition TEXT,
            tips TEXT,
            substitutes TEXT,
            language TEXT DEFAULT 'en',
            user_id INTEGER DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    """)

    # Check and add missing columns to favourites if needed
    cursor.execute("PRAGMA table_info(favourites)")
    columns = [col['name'] for col in cursor.fetchall()]
    if 'user_id' not in columns:
        try:
            cursor.execute("ALTER TABLE favourites ADD COLUMN user_id INTEGER DEFAULT NULL")
        except Exception:
            pass

    # Check and add missing columns to users if needed
    cursor.execute("PRAGMA table_info(users)")
    user_columns = [col['name'] for col in cursor.fetchall()]
    if 'google_id' not in user_columns:
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN google_id TEXT DEFAULT NULL")
        except Exception:
            pass
    if 'profile_picture' not in user_columns:
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN profile_picture TEXT DEFAULT NULL")
        except Exception:
            pass

    # Table 3: Generated recipes table (persists generated & custom recipes)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS generated_recipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            category TEXT,
            prep_time TEXT,
            cook_time TEXT,
            difficulty TEXT,
            calories TEXT,
            ingredients TEXT,
            instructions TEXT,
            nutrition TEXT,
            tips TEXT,
            substitutes TEXT,
            language TEXT DEFAULT 'en',
            user_id INTEGER DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
        )
    """)

    cursor.execute("PRAGMA table_info(generated_recipes)")
    gen_columns = [col['name'] for col in cursor.fetchall()]
    if 'user_id' not in gen_columns:
        try:
            cursor.execute("ALTER TABLE generated_recipes ADD COLUMN user_id INTEGER DEFAULT NULL")
        except Exception:
            pass

    conn.commit()
    conn.close()

    if is_supabase_enabled():
        print(f"[Database] Primary Engine: Supabase Cloud PostgreSQL (Active)")
        print(f"[Database] Fallback Engine: SQLite ({DB_PATH})")
    else:
        print(f"[Database] Primary Engine: SQLite ({DB_PATH})")
        print(f"[Database] Tip: Add SUPABASE_URL & SUPABASE_KEY to .env to enable Supabase Cloud PostgreSQL!")


# ==============================================================================
# User Authentication Helpers
# ==============================================================================

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


def create_user(name, email, password_hash):
    """
    Creates a new user record.
    Routes to Supabase if configured, otherwise uses local SQLite.
    Returns (user_id, None) on success, or (None, error_message) on failure.
    """
    if is_supabase_enabled():
        res = supabase_db.create_user(name, email, password_hash)
        if res[0] is not None or "already exists" in str(res[1]):
            return res

    # SQLite implementation / fallback
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        color = random.choice(AVATAR_COLORS)
        cursor.execute("""
            INSERT INTO users (name, email, password_hash, avatar_color)
            VALUES (?, ?, ?, ?)
        """, (name.strip(), email.strip().lower(), password_hash, color))
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return user_id, None
    except sqlite3.IntegrityError:
        conn.close()
        return None, "An account with this email address already exists."
    except Exception as e:
        conn.close()
        return None, f"Registration failed: {str(e)}"


def get_user_by_email(email):
    """
    Fetch a user dictionary by email address (case-insensitive).
    """
    if not email:
        return None

    if is_supabase_enabled():
        user = supabase_db.get_user_by_email(email)
        if user is not None:
            return user

    # SQLite implementation / fallback
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE LOWER(email) = ?", (email.strip().lower(),))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_id(user_id):
    """
    Fetch a user dictionary by primary key user_id.
    """
    if not user_id:
        return None

    if is_supabase_enabled():
        user = supabase_db.get_user_by_id(user_id)
        if user is not None:
            return user

    # SQLite implementation / fallback
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (int(user_id),))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_or_create_google_user(email, name, google_id=None, profile_picture=None):
    """
    Finds an existing user by email or creates a new user via Google Sign-In.
    Returns the user dict.
    """
    if not email:
        return None

    if is_supabase_enabled():
        user = supabase_db.get_or_create_google_user(email, name, google_id, profile_picture)
        if user is not None:
            return user

    # SQLite implementation / fallback
    clean_email = email.strip().lower()
    existing = get_user_by_email(clean_email)

    conn = get_db_connection()
    cursor = conn.cursor()

    if existing:
        cursor.execute("""
            UPDATE users SET 
                google_id = COALESCE(google_id, ?),
                profile_picture = COALESCE(?, profile_picture)
            WHERE id = ?
        """, (google_id, profile_picture, existing["id"]))
        conn.commit()
        conn.close()
        return get_user_by_id(existing["id"])

    color = random.choice(AVATAR_COLORS)
    cursor.execute("""
        INSERT INTO users (name, email, password_hash, avatar_color, google_id, profile_picture)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (name.strip(), clean_email, "oauth_google_account", color, google_id, profile_picture))
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return get_user_by_id(new_id)


def get_user_stats(user_id):
    """
    Returns dashboard statistics for a specific user:
    - total_saved: count of recipes saved
    - top_category: most frequent recipe category saved
    - joined_at: account creation date
    """
    if not user_id:
        return {"total_saved": 0, "top_category": "None", "joined_at": "Unknown"}

    if is_supabase_enabled():
        stats = supabase_db.get_user_stats(user_id)
        if stats and stats.get("joined_at") != "Unknown":
            return stats

    # SQLite implementation / fallback
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as cnt FROM favourites WHERE user_id = ?", (user_id,))
    total_saved = cursor.fetchone()['cnt']

    cursor.execute("""
        SELECT category, COUNT(*) as cat_cnt 
        FROM favourites 
        WHERE user_id = ? 
        GROUP BY category 
        ORDER BY cat_cnt DESC 
        LIMIT 1
    """, (user_id,))
    cat_row = cursor.fetchone()
    top_cat = cat_row['category'] if cat_row and cat_row['category'] else "All"

    cursor.execute("SELECT created_at FROM users WHERE id = ?", (user_id,))
    user_row = cursor.fetchone()
    joined_at = str(user_row['created_at'])[:10] if user_row and user_row['created_at'] else "Recently"

    conn.close()
    return {
        "total_saved": total_saved,
        "top_category": top_cat,
        "joined_at": joined_at
    }


# ==============================================================================
# Recipe Formatting Helpers
# ==============================================================================

def _format_recipe_row(row):
    """
    Helper function to convert a SQLite sqlite3.Row into a clean Python dictionary,
    parsing JSON strings (ingredients, instructions, nutrition) back into lists/dicts.
    """
    if not row:
        return None

    recipe = dict(row)

    for field in ['ingredients', 'instructions', 'nutrition']:
        if field in recipe and recipe[field]:
            try:
                recipe[field] = json.loads(recipe[field])
            except (json.JSONDecodeError, TypeError):
                if isinstance(recipe[field], str):
                    recipe[field] = [line.strip() for line in recipe[field].split('\n') if line.strip()]

    return recipe


# ==============================================================================
# Recipe Operations
# ==============================================================================

def save_generated_recipes(recipes_list, language='en', user_id=None):
    """
    Save the newly generated recipes into the database linked to user_id.
    Returns the list of recipes with their assigned database IDs.
    """
    if is_supabase_enabled():
        saved = supabase_db.save_generated_recipes(recipes_list, language=language, user_id=user_id)
        if saved:
            return saved

    # SQLite implementation / fallback
    conn = get_db_connection()
    cursor = conn.cursor()
    saved_recipes = []

    for item in recipes_list:
        ingredients_json = json.dumps(item.get('ingredients', []), ensure_ascii=False)
        instructions_json = json.dumps(item.get('instructions', []), ensure_ascii=False)
        nutrition_json = json.dumps(item.get('nutrition', {}), ensure_ascii=False)

        cursor.execute("""
            INSERT INTO generated_recipes (
                title, description, category, prep_time, cook_time,
                difficulty, calories, ingredients, instructions,
                nutrition, tips, substitutes, language, user_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            item.get('title', 'Delicious Dish'),
            item.get('description', ''),
            item.get('category', 'General'),
            item.get('prep_time', '15 mins'),
            item.get('cook_time', '25 mins'),
            item.get('difficulty', 'Medium'),
            item.get('calories', '350 kcal'),
            ingredients_json,
            instructions_json,
            nutrition_json,
            item.get('tips', ''),
            item.get('substitutes', ''),
            language,
            user_id
        ))

        new_id = cursor.lastrowid
        recipe_copy = dict(item)
        recipe_copy['id'] = new_id
        recipe_copy['user_id'] = user_id
        recipe_copy['language'] = language
        saved_recipes.append(recipe_copy)

    conn.commit()
    conn.close()
    return saved_recipes


# ------------------------------------------------------------------------------
# Full Recipe CRUD Operations (Create, Read, Update, Delete)
# ------------------------------------------------------------------------------

def get_all_recipes(user_id=None, limit=60):
    """
    READ (R): Fetches all active recipes.
    If user_id is provided, returns recipes for that user (and public ones).
    """
    if is_supabase_enabled():
        recipes = supabase_db.get_all_recipes(user_id=user_id, limit=limit)
        if recipes is not None:
            return recipes

    # SQLite implementation / fallback
    conn = get_db_connection()
    cursor = conn.cursor()

    if user_id:
        cursor.execute("""
            SELECT * FROM generated_recipes 
            WHERE user_id = ? OR user_id IS NULL 
            ORDER BY id DESC LIMIT ?
        """, (int(user_id), limit))
    else:
        cursor.execute("SELECT * FROM generated_recipes ORDER BY id DESC LIMIT ?", (limit,))

    rows = cursor.fetchall()
    conn.close()

    recipes = [_format_recipe_row(row) for row in rows]
    for r in recipes:
        r['is_favourite'] = is_favourite(r.get('title', ''), user_id=user_id)
    return recipes


def create_recipe(recipe_data, user_id=None):
    """
    CREATE (C): Inserts a new custom recipe.
    Returns the created recipe dictionary.
    """
    if is_supabase_enabled():
        created = supabase_db.create_recipe(recipe_data, user_id=user_id)
        if created:
            return created

    # SQLite implementation / fallback
    conn = get_db_connection()
    cursor = conn.cursor()

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
    ingredients_json = json.dumps(ingredients, ensure_ascii=False)

    instructions = recipe_data.get('instructions', [])
    if isinstance(instructions, str):
        instructions = [s.strip() for s in instructions.split('\n') if s.strip()]
    instructions_json = json.dumps(instructions, ensure_ascii=False)

    nutrition = recipe_data.get('nutrition', {'calories': calories})
    nutrition_json = json.dumps(nutrition, ensure_ascii=False)

    cursor.execute("""
        INSERT INTO generated_recipes (
            title, description, category, prep_time, cook_time,
            difficulty, calories, ingredients, instructions,
            nutrition, tips, substitutes, language, user_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'en', ?)
    """, (
        title, description, category, prep_time, cook_time,
        difficulty, calories, ingredients_json, instructions_json,
        nutrition_json, tips, substitutes, user_id
    ))

    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return get_recipe_by_id(new_id)


def update_recipe(recipe_id, update_data, user_id=None):
    """
    UPDATE (U): Updates an existing recipe's fields.
    Returns (True, message) on success, or (False, error) on failure.
    """
    if is_supabase_enabled():
        res = supabase_db.update_recipe(recipe_id, update_data, user_id=user_id)
        if res[0]:
            return res

    # SQLite implementation / fallback
    conn = get_db_connection()
    cursor = conn.cursor()

    if user_id:
        cursor.execute("SELECT * FROM generated_recipes WHERE id = ? AND (user_id = ? OR user_id IS NULL)", (recipe_id, user_id))
    else:
        cursor.execute("SELECT * FROM generated_recipes WHERE id = ?", (recipe_id,))

    row = cursor.fetchone()
    if not row:
        conn.close()
        return False, "Recipe not found or unauthorized."

    title = update_data.get('title', row['title']).strip()
    description = update_data.get('description', row['description']).strip()
    category = update_data.get('category', row['category']).strip()
    prep_time = update_data.get('prep_time', row['prep_time']).strip()
    cook_time = update_data.get('cook_time', row['cook_time']).strip()
    difficulty = update_data.get('difficulty', row['difficulty']).strip()
    calories = update_data.get('calories', row['calories']).strip()
    tips = update_data.get('tips', row['tips'] or '').strip()
    substitutes = update_data.get('substitutes', row['substitutes'] or '').strip()

    ingredients = update_data.get('ingredients')
    if ingredients is not None:
        if isinstance(ingredients, str):
            ingredients = [i.strip() for i in ingredients.split('\n') if i.strip()]
        ingredients_json = json.dumps(ingredients, ensure_ascii=False)
    else:
        ingredients_json = row['ingredients']

    instructions = update_data.get('instructions')
    if instructions is not None:
        if isinstance(instructions, str):
            instructions = [s.strip() for s in instructions.split('\n') if s.strip()]
        instructions_json = json.dumps(instructions, ensure_ascii=False)
    else:
        instructions_json = row['instructions']

    cursor.execute("""
        UPDATE generated_recipes SET
            title = ?,
            description = ?,
            category = ?,
            prep_time = ?,
            cook_time = ?,
            difficulty = ?,
            calories = ?,
            ingredients = ?,
            instructions = ?,
            tips = ?,
            substitutes = ?
        WHERE id = ?
    """, (
        title, description, category, prep_time, cook_time,
        difficulty, calories, ingredients_json, instructions_json,
        tips, substitutes, recipe_id
    ))

    conn.commit()
    conn.close()
    return True, "Recipe updated successfully."


def delete_recipe(recipe_id, user_id=None):
    """
    DELETE (D): Permanently deletes a recipe.
    """
    if is_supabase_enabled():
        deleted = supabase_db.delete_recipe(recipe_id, user_id=user_id)
        if deleted:
            return True

    # SQLite implementation / fallback
    conn = get_db_connection()
    cursor = conn.cursor()

    if user_id:
        cursor.execute("DELETE FROM generated_recipes WHERE id = ? AND (user_id = ? OR user_id IS NULL)", (recipe_id, user_id))
    else:
        cursor.execute("DELETE FROM generated_recipes WHERE id = ?", (recipe_id,))

    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def save_favourite(recipe_data, user_id=None):
    """
    Save a recipe to the favourites table, linked to user_id.
    """
    if is_supabase_enabled():
        fav_id, is_new = supabase_db.save_favourite(recipe_data, user_id=user_id)
        if fav_id is not None:
            return fav_id, is_new

    # SQLite implementation / fallback
    conn = get_db_connection()
    cursor = conn.cursor()

    title = recipe_data.get('title', '').strip()

    if user_id:
        cursor.execute("SELECT id FROM favourites WHERE title = ? AND user_id = ?", (title, user_id))
    else:
        cursor.execute("SELECT id FROM favourites WHERE title = ? AND user_id IS NULL", (title,))

    existing = cursor.fetchone()
    if existing:
        conn.close()
        return existing['id'], False

    ingredients = recipe_data.get('ingredients', [])
    if isinstance(ingredients, (list, dict)):
        ingredients_json = json.dumps(ingredients, ensure_ascii=False)
    else:
        ingredients_json = json.dumps([str(ingredients)], ensure_ascii=False)

    instructions = recipe_data.get('instructions', [])
    if isinstance(instructions, (list, dict)):
        instructions_json = json.dumps(instructions, ensure_ascii=False)
    else:
        instructions_json = json.dumps([str(instructions)], ensure_ascii=False)

    nutrition = recipe_data.get('nutrition', {})
    if isinstance(nutrition, (list, dict)):
        nutrition_json = json.dumps(nutrition, ensure_ascii=False)
    else:
        nutrition_json = json.dumps({'info': str(nutrition)}, ensure_ascii=False)

    cursor.execute("""
        INSERT INTO favourites (
            title, description, category, prep_time, cook_time,
            difficulty, calories, ingredients, instructions,
            nutrition, tips, substitutes, language, user_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        title,
        recipe_data.get('description', ''),
        recipe_data.get('category', 'General'),
        recipe_data.get('prep_time', '15 mins'),
        recipe_data.get('cook_time', '20 mins'),
        recipe_data.get('difficulty', 'Easy'),
        recipe_data.get('calories', '300 kcal'),
        ingredients_json,
        instructions_json,
        nutrition_json,
        recipe_data.get('tips', ''),
        recipe_data.get('substitutes', ''),
        recipe_data.get('language', 'en'),
        user_id
    ))

    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return new_id, True


def get_all_favourites(user_id=None):
    """
    Retrieve recipes saved in favourites.
    """
    if is_supabase_enabled():
        favs = supabase_db.get_all_favourites(user_id=user_id)
        if favs is not None:
            return favs

    # SQLite implementation / fallback
    conn = get_db_connection()
    cursor = conn.cursor()

    if user_id:
        cursor.execute("SELECT * FROM favourites WHERE user_id = ? ORDER BY id DESC", (user_id,))
    else:
        cursor.execute("SELECT * FROM favourites ORDER BY id DESC")

    rows = cursor.fetchall()
    conn.close()

    return [_format_recipe_row(row) for row in rows]


def get_favourite_by_id(fav_id):
    """
    Fetch a single favourite recipe by its ID.
    """
    if is_supabase_enabled():
        fav = supabase_db.get_favourite_by_id(fav_id)
        if fav is not None:
            return fav

    # SQLite implementation / fallback
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM favourites WHERE id = ?", (fav_id,))
    row = cursor.fetchone()
    conn.close()

    return _format_recipe_row(row)


def delete_favourite(fav_id, user_id=None):
    """
    Remove a recipe from favourites table by ID.
    """
    if is_supabase_enabled():
        deleted = supabase_db.delete_favourite(fav_id, user_id=user_id)
        if deleted:
            return True

    # SQLite implementation / fallback
    conn = get_db_connection()
    cursor = conn.cursor()
    if user_id:
        cursor.execute("DELETE FROM favourites WHERE id = ? AND user_id = ?", (fav_id, user_id))
    else:
        cursor.execute("DELETE FROM favourites WHERE id = ?", (fav_id,))

    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def is_favourite(title, user_id=None):
    """
    Check if a recipe is in favourites by its title for a given user.
    """
    if not title:
        return False

    if is_supabase_enabled():
        return supabase_db.is_favourite(title, user_id=user_id)

    # SQLite implementation / fallback
    conn = get_db_connection()
    cursor = conn.cursor()
    if user_id:
        cursor.execute("SELECT id FROM favourites WHERE title = ? AND user_id = ?", (title.strip(), user_id))
    else:
        cursor.execute("SELECT id FROM favourites WHERE title = ? AND user_id IS NULL", (title.strip(),))
    row = cursor.fetchone()
    conn.close()
    return row is not None


def get_recipe_by_id(recipe_id):
    """
    Retrieve recipe by ID.
    Checks favourites first, then generated_recipes.
    """
    if is_supabase_enabled():
        recipe = supabase_db.get_recipe_by_id(recipe_id)
        if recipe is not None:
            return recipe

    # SQLite implementation / fallback
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM favourites WHERE id = ?", (recipe_id,))
    row = cursor.fetchone()
    if row:
        conn.close()
        recipe = _format_recipe_row(row)
        recipe['is_favourite'] = True
        recipe['source'] = 'favourites'
        return recipe

    cursor.execute("SELECT * FROM generated_recipes WHERE id = ?", (recipe_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        recipe = _format_recipe_row(row)
        recipe['is_favourite'] = is_favourite(recipe.get('title', ''))
        recipe['source'] = 'generated'
        return recipe

    return None
