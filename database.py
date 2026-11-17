"""
=============================================================
database.py - SQLite Database Management for Recipe Generator
=============================================================
This file manages the SQLite database for the recipe generator application.
SQLite is a lightweight, serverless database that stores all
records in a single file ('database/recipes.db').

Tables:
1. favourites: Stores user's bookmarked / favourite recipes.
2. generated_recipes: Stores recently generated AI recipes so
   users can view their full details, instructions, and print them.
"""

import os
import sqlite3
import json

# Define the path to our SQLite database file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, "database")
DB_PATH = os.path.join(DB_DIR, "recipes.db")


def get_db_connection():
    """
    Establish and return a connection to the SQLite database.
    row_factory = sqlite3.Row allows accessing columns by name (e.g., row['title']).
    """
    # Ensure the database directory exists
    os.makedirs(DB_DIR, exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """
    Initialize the database tables if they do not already exist.
    Called once when the Flask server starts.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Table 1: Favourites table
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Table 2: Generated recipes table (persists generated recipes for detail view)
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()
    print("Database initialized successfully at:", DB_PATH)


def _format_recipe_row(row):
    """
    Helper function to convert a database sqlite3.Row into a clean Python dictionary,
    parsing JSON strings (ingredients, instructions, nutrition) back into lists/dicts.
    """
    if not row:
        return None

    recipe = dict(row)

    # Safely parse JSON fields
    for field in ['ingredients', 'instructions', 'nutrition']:
        if field in recipe and recipe[field]:
            try:
                recipe[field] = json.loads(recipe[field])
            except (json.JSONDecodeError, TypeError):
                # If it's already a plain string, split by newlines
                if isinstance(recipe[field], str):
                    recipe[field] = [line.strip() for line in recipe[field].split('\n') if line.strip()]

    return recipe


def save_generated_recipes(recipes_list, language='en'):
    """
    Save the newly generated recipes into the database.
    Returns the list of recipes with their assigned database IDs.
    """
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
                nutrition, tips, substitutes, language
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            language
        ))

        new_id = cursor.lastrowid
        recipe_copy = dict(item)
        recipe_copy['id'] = new_id
        recipe_copy['language'] = language
        saved_recipes.append(recipe_copy)

    conn.commit()
    conn.close()
    return saved_recipes


def save_favourite(recipe_data):
    """
    Save a recipe to the favourites table.
    If the recipe already exists by title, returns its existing ID.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    title = recipe_data.get('title', '').strip()

    # Check if already favourited
    cursor.execute("SELECT id FROM favourites WHERE title = ?", (title,))
    existing = cursor.fetchone()
    if existing:
        conn.close()
        return existing['id'], False  # ID, is_new=False

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
            nutrition, tips, substitutes, language
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        recipe_data.get('language', 'en')
    ))

    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return new_id, True


def get_all_favourites():
    """
    Retrieve all recipes saved in the favourites table,
    ordered with the newest saved recipe first.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM favourites ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()

    return [_format_recipe_row(row) for row in rows]


def get_favourite_by_id(fav_id):
    """
    Fetch a single favourite recipe by its ID.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM favourites WHERE id = ?", (fav_id,))
    row = cursor.fetchone()
    conn.close()

    return _format_recipe_row(row)


def delete_favourite(fav_id):
    """
    Remove a recipe from favourites table by ID.
    Returns True if deleted, False otherwise.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM favourites WHERE id = ?", (fav_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def is_favourite(title):
    """
    Check if a recipe is already in the favourites table by its title.
    """
    if not title:
        return False
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM favourites WHERE title = ?", (title.strip(),))
    row = cursor.fetchone()
    conn.close()
    return row is not None


def get_recipe_by_id(recipe_id):
    """
    Retrieve recipe by ID.
    First checks the favourites table, then the generated_recipes table.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Check favourites first
    cursor.execute("SELECT * FROM favourites WHERE id = ?", (recipe_id,))
    row = cursor.fetchone()
    if row:
        conn.close()
        recipe = _format_recipe_row(row)
        recipe['is_favourite'] = True
        recipe['source'] = 'favourites'
        return recipe

    # Check generated_recipes
    cursor.execute("SELECT * FROM generated_recipes WHERE id = ?", (recipe_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        recipe = _format_recipe_row(row)
        recipe['is_favourite'] = is_favourite(recipe.get('title', ''))
        recipe['source'] = 'generated'
        return recipe

    return None
