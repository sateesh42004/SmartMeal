import json
import sqlite3
from app import get_db_connection, init_db

# Realistic college canteen menu catalog
SAMPLE_MENU_ITEMS = [
    {
        "name": "Masala Dosa",
        "category": "Breakfast",
        "price": 40.0,
        "is_available": 1,
        "max_portion_limit": 4,
        "allowed_preferences": ["Standard", "Crispy", "Less Spicy", "No Onion"]
    },
    {
        "name": "Idli Vada Combo",
        "category": "Breakfast",
        "price": 35.0,
        "is_available": 1,
        "max_portion_limit": 5,
        "allowed_preferences": ["Standard", "Extra Sambar", "Less Spicy"]
    },
    {
        "name": "Poori Masala (2 pcs)",
        "category": "Breakfast",
        "price": 45.0,
        "is_available": 1,
        "max_portion_limit": 4,
        "allowed_preferences": ["Standard", "Extra Potato Bhaji"]
    },
    {
        "name": "Veg Fried Rice",
        "category": "Lunch",
        "price": 60.0,
        "is_available": 1,
        "max_portion_limit": 4,
        "allowed_preferences": ["Standard", "Less Spicy", "No Onion", "Extra Gravy"]
    },
    {
        "name": "South Indian Mini Thali",
        "category": "Lunch",
        "price": 75.0,
        "is_available": 1,
        "max_portion_limit": 3,
        "allowed_preferences": ["Standard", "No Curd", "Extra Rasam"]
    },
    {
        "name": "Paneer Butter Masala Combo",
        "category": "Lunch",
        "price": 85.0,
        "is_available": 1,
        "max_portion_limit": 4,
        "allowed_preferences": ["Standard", "Mild", "Less Spicy"]
    },
    {
        "name": "Veg Samosa (2 pcs)",
        "category": "Snacks",
        "price": 25.0,
        "is_available": 1,
        "max_portion_limit": 6,
        "allowed_preferences": ["Standard", "Extra Green Chutney", "Extra Sweet Chutney"]
    },
    {
        "name": "Aloo Tikki Burger",
        "category": "Snacks",
        "price": 45.0,
        "is_available": 1,
        "max_portion_limit": 4,
        "allowed_preferences": ["Standard", "Extra Mayo", "No Onion", "Mild"]
    },
    {
        "name": "Masala Chai",
        "category": "Beverages",
        "price": 12.0,
        "is_available": 1,
        "max_portion_limit": 5,
        "allowed_preferences": ["Standard", "Less Sugar", "No Sugar", "Strong"]
    },
    {
        "name": "Cold Coffee",
        "category": "Beverages",
        "price": 30.0,
        "is_available": 1,
        "max_portion_limit": 4,
        "allowed_preferences": ["Standard", "Less Sugar", "Extra Chocolate"]
    }
]


def seed_database():
    """
    Initializes tables and seeds sample menu items.
    Safe to run repeatedly: uses UPSERT on item name to prevent duplicates.
    """
    # Ensure tables exist first
    init_db()

    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            for item in SAMPLE_MENU_ITEMS:
                # Upsert query: if the item name already exists, update its details
                cursor.execute(
                    """
                    INSERT INTO menu_items (
                        name, category, price, is_available, max_portion_limit, allowed_preferences
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(name) DO UPDATE SET
                        category = excluded.category,
                        price = excluded.price,
                        is_available = excluded.is_available,
                        max_portion_limit = excluded.max_portion_limit,
                        allowed_preferences = excluded.allowed_preferences;
                    """,
                    (
                        item["name"],
                        item["category"],
                        item["price"],
                        item["is_available"],
                        item["max_portion_limit"],
                        json.dumps(item["allowed_preferences"])
                    )
                )

        print("[OK] Seeding complete.")
        # Query and display current table content for verification
        rows = conn.execute("SELECT id, name, category, price, max_portion_limit, is_available FROM menu_items ORDER BY id;").fetchall()
        print(f"\n--- Current Menu Items ({len(rows)} items) ---")
        for r in rows:
            status = "Available" if r["is_available"] == 1 else "Sold Out"
            print(f"[{r['id']:2d}] {r['name']:<28} | {r['category']:<10} | Rs.{r['price']:<5.1f} | Limit: {r['max_portion_limit']} | {status}")

    finally:
        conn.close()


if __name__ == "__main__":
    seed_database()
