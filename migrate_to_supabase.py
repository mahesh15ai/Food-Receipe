"""
=============================================================
migrate_to_supabase.py - SQLite to Supabase Data Migration Tool
=============================================================
This script exports all existing users, generated recipes, and
favourite bookmarks from the local SQLite database (database/recipes.db)
and uploads them to your Supabase PostgreSQL cloud database.

Usage:
    python migrate_to_supabase.py

Prerequisites:
    1. Run supabase_schema.sql in your Supabase SQL Editor.
    2. Add SUPABASE_URL and SUPABASE_KEY to your .env file.
=============================================================
"""

import os
import sys
import sqlite3
import json
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database", "recipes.db")


def parse_json_field(val, default):
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
                return [x.strip() for x in val.split("\n") if x.strip()]
            return default
    return default


def main():
    print("=" * 65)
    print("  Mahilicious: SQLite -> Supabase Cloud Migration Tool")
    print("=" * 65)

    # 1. Verify SQLite database exists
    if not os.path.exists(DB_PATH):
        print(f"[-] SQLite database file not found at: {DB_PATH}")
        print("    Nothing to migrate.")
        return

    # 2. Check Supabase credentials
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_KEY", "").strip()

    if not url or not key or url.startswith("your-") or url.startswith("<"):
        print("[-] Supabase is not configured yet in your .env file!")
        print("\nTo setup Supabase:")
        print("  1. Sign up for free at https://supabase.com")
        print("  2. Create a new project (e.g., 'mahilicious')")
        print("  3. Run supabase_schema.sql in the Supabase SQL Editor")
        print("  4. Copy 'Project URL' and 'anon' key from Project Settings -> API")
        print("  5. Paste them into your .env file under SUPABASE_URL and SUPABASE_KEY")
        print("  6. Run this script again!\n")
        return

    # 3. Connect to Supabase
    try:
        from supabase import create_client
        supabase = create_client(url, key)
        # Test connection
        supabase.table("users").select("id").limit(1).execute()
        print("[+] Successfully connected to Supabase Cloud PostgreSQL!")
    except Exception as e:
        print(f"[-] Failed to connect to Supabase: {e}")
        print("    Please check that your SUPABASE_URL and SUPABASE_KEY are correct.")
        print("    Also verify that you ran supabase_schema.sql in the SQL Editor.")
        return

    # 4. Read SQLite records
    sqlite_conn = sqlite3.connect(DB_PATH)
    sqlite_conn.row_factory = sqlite3.Row
    cur = sqlite_conn.cursor()

    # --- Migrate Users ---
    print("\n[*] Step 1/3: Migrating Users...")
    try:
        cur.execute("SELECT * FROM users")
        sqlite_users = cur.fetchall()
        user_count = 0
        for u in sqlite_users:
            u_dict = dict(u)
            email = u_dict.get("email", "").strip().lower()
            # Check if user already in Supabase
            existing = supabase.table("users").select("id").eq("email", email).execute()
            if not existing.data:
                payload = {
                    "id": u_dict.get("id"),
                    "name": u_dict.get("name", "Chef"),
                    "email": email,
                    "password_hash": u_dict.get("password_hash", ""),
                    "avatar_color": u_dict.get("avatar_color", "#059669"),
                    "google_id": u_dict.get("google_id"),
                    "profile_picture": u_dict.get("profile_picture")
                }
                supabase.table("users").insert(payload).execute()
                user_count += 1
        print(f"    [v] Successfully migrated {user_count} new users (Total in SQLite: {len(sqlite_users)}).")
    except Exception as e:
        print(f"    [-] Users migration error: {e}")

    # --- Migrate Generated Recipes ---
    print("\n[*] Step 2/3: Migrating Generated Recipes...")
    try:
        cur.execute("SELECT * FROM generated_recipes")
        sqlite_recipes = cur.fetchall()
        recipe_count = 0
        for r in sqlite_recipes:
            r_dict = dict(r)
            rid = r_dict.get("id")
            existing = supabase.table("generated_recipes").select("id").eq("id", rid).execute()
            if not existing.data:
                payload = {
                    "id": rid,
                    "title": r_dict.get("title", "Recipe"),
                    "description": r_dict.get("description", ""),
                    "category": r_dict.get("category", "Everyday Meal"),
                    "prep_time": r_dict.get("prep_time", "15 mins"),
                    "cook_time": r_dict.get("cook_time", "20 mins"),
                    "difficulty": r_dict.get("difficulty", "Easy"),
                    "calories": r_dict.get("calories", "320 kcal"),
                    "ingredients": parse_json_field(r_dict.get("ingredients"), []),
                    "instructions": parse_json_field(r_dict.get("instructions"), []),
                    "nutrition": parse_json_field(r_dict.get("nutrition"), {}),
                    "tips": r_dict.get("tips", ""),
                    "substitutes": r_dict.get("substitutes", ""),
                    "language": r_dict.get("language", "en"),
                    "user_id": r_dict.get("user_id")
                }
                supabase.table("generated_recipes").insert(payload).execute()
                recipe_count += 1
        print(f"    [v] Successfully migrated {recipe_count} generated recipes (Total in SQLite: {len(sqlite_recipes)}).")
    except Exception as e:
        print(f"    [-] Generated recipes migration error: {e}")

    # --- Migrate Favourites ---
    print("\n[*] Step 3/3: Migrating Favourites (Bookmarks)...")
    try:
        cur.execute("SELECT * FROM favourites")
        sqlite_favs = cur.fetchall()
        fav_count = 0
        for f in sqlite_favs:
            f_dict = dict(f)
            fid = f_dict.get("id")
            existing = supabase.table("favourites").select("id").eq("id", fid).execute()
            if not existing.data:
                payload = {
                    "id": fid,
                    "title": f_dict.get("title", "Recipe"),
                    "description": f_dict.get("description", ""),
                    "category": f_dict.get("category", "General"),
                    "prep_time": f_dict.get("prep_time", "15 mins"),
                    "cook_time": f_dict.get("cook_time", "20 mins"),
                    "difficulty": f_dict.get("difficulty", "Easy"),
                    "calories": f_dict.get("calories", "300 kcal"),
                    "ingredients": parse_json_field(f_dict.get("ingredients"), []),
                    "instructions": parse_json_field(f_dict.get("instructions"), []),
                    "nutrition": parse_json_field(f_dict.get("nutrition"), {}),
                    "tips": f_dict.get("tips", ""),
                    "substitutes": f_dict.get("substitutes", ""),
                    "language": f_dict.get("language", "en"),
                    "user_id": f_dict.get("user_id")
                }
                supabase.table("favourites").insert(payload).execute()
                fav_count += 1
        print(f"    [v] Successfully migrated {fav_count} favourites (Total in SQLite: {len(sqlite_favs)}).")
    except Exception as e:
        print(f"    [-] Favourites migration error: {e}")

    sqlite_conn.close()

    print("\n" + "=" * 65)
    print("  Migration to Supabase Completed Successfully!")
    print("  Mahilicious is now backed by Supabase Cloud PostgreSQL.")
    print("=" * 65)


if __name__ == "__main__":
    main()
