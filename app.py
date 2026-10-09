import os
import sqlite3
from functools import wraps
from flask import Flask, request, jsonify, session

app = Flask(__name__)

# Basic configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, "smartmeal.db")

# Secret key for session management and staff PIN for hackathon authentication
app.secret_key = os.environ.get("SECRET_KEY", "smartmeal-hackathon-secret-key-2026")
STAFF_PIN = os.environ.get("STAFF_PIN", "canteen123")


def get_db_connection():
    """
    Establishes a connection to SQLite.
    Enforces foreign keys and enables dictionary-like row access.
    """
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    # Explicitly enforce SQLite foreign key constraints on every connection
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db():
    """
    Initializes the database schema with relational tables:
    1. menu_items: Stores canteen catalog, pricing, availability, and portion limits.
    2. orders: Stores student orders, reference codes, totals, and lifecycle status.
    3. order_items: Stores line items, linking orders to menu items with unit price snapshots.
    """
    conn = get_db_connection()
    try:
        with conn:
            # 1. Menu Items Table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS menu_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    category TEXT NOT NULL,
                    price REAL NOT NULL CHECK(price >= 0),
                    is_available INTEGER NOT NULL DEFAULT 1 CHECK(is_available IN (0, 1)),
                    max_portion_limit INTEGER NOT NULL DEFAULT 5 CHECK(max_portion_limit > 0),
                    allowed_preferences TEXT NOT NULL DEFAULT '[]',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

            # 2. Orders Table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_ref TEXT UNIQUE NOT NULL,
                    student_name TEXT NOT NULL,
                    roll_number TEXT NOT NULL,
                    section TEXT NOT NULL,
                    total_price REAL NOT NULL CHECK(total_price >= 0),
                    status TEXT NOT NULL DEFAULT 'Pending' 
                        CHECK(status IN ('Pending', 'Confirmed', 'Preparing', 'Ready for Pickup', 'Completed', 'Cancelled')),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

            # 3. Order Items Table (with Foreign Keys & Cascade Deletion)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS order_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER NOT NULL,
                    menu_item_id INTEGER NOT NULL,
                    quantity INTEGER NOT NULL CHECK(quantity > 0),
                    unit_price REAL NOT NULL CHECK(unit_price >= 0),
                    cooking_preference TEXT NOT NULL DEFAULT '',
                    special_request TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
                    FOREIGN KEY (menu_item_id) REFERENCES menu_items(id) ON DELETE RESTRICT
                );
                """
            )
    finally:
        conn.close()


# ---------------------------------------------------------
# Staff Authentication Security Layer
# ---------------------------------------------------------
def require_staff_auth(f):
    """
    Decorator to protect staff-only routes.
    Accepts authentication via either:
    1. Flask session cookie (session['is_staff'] == True)
    2. HTTP Header: 'X-Staff-Pin' matching STAFF_PIN
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check active session
        if session.get("is_staff") is True:
            return f(*args, **kwargs)

        # Check API header (for programmatic or testing access)
        provided_pin = request.headers.get("X-Staff-Pin")
        if provided_pin and provided_pin == STAFF_PIN:
            return f(*args, **kwargs)

        return jsonify({
            "status": "error",
            "message": "Unauthorized: Staff authentication required to access this endpoint."
        }), 401

    return decorated_function


# ---------------------------------------------------------
# Milestone 1 Health & Authentication Endpoints
# ---------------------------------------------------------
@app.route("/")
def home():
    """Root info page for Milestone 1."""
    return jsonify({
        "project": "SmartMeal - College Canteen Pre-Ordering System",
        "milestone": "1 - Database Architecture & Backend Foundation",
        "status": "online",
        "demo_staff_pin": "canteen123 (use for staff demo login)"
    }), 200


@app.route("/api/health", methods=["GET"])
def health_check():
    """Verifies SQLite database connectivity and foreign key enforcement."""
    try:
        conn = get_db_connection()
        try:
            # Verify foreign key pragma is active
            fk_status = conn.execute("PRAGMA foreign_keys;").fetchone()[0]
            # Count total registered menu items
            count = conn.execute("SELECT COUNT(*) FROM menu_items;").fetchone()[0]
            return jsonify({
                "status": "healthy",
                "database": "connected",
                "foreign_keys_enabled": bool(fk_status),
                "total_menu_items": count
            }), 200
        finally:
            conn.close()
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": "Health check failed.",
            "details": str(e)
        }), 500


@app.route("/api/staff/login", methods=["POST"])
def staff_login():
    """Authenticates staff using the canteen PIN."""
    data = request.get_json(silent=True) or {}
    pin = data.get("pin", "").strip()

    if pin == STAFF_PIN:
        session["is_staff"] = True
        return jsonify({
            "status": "success",
            "message": "Staff authenticated successfully."
        }), 200

    return jsonify({
        "status": "error",
        "message": "Invalid staff PIN. Access denied."
    }), 401


@app.route("/api/staff/logout", methods=["POST"])
def staff_logout():
    """Logs out staff and clears the session."""
    session.pop("is_staff", None)
    return jsonify({
        "status": "success",
        "message": "Staff logged out successfully."
    }), 200


@app.route("/api/staff/check-auth", methods=["GET"])
@require_staff_auth
def check_staff_auth():
    """Verifies that the current request is authenticated as staff."""
    return jsonify({
        "status": "success",
        "authenticated": True,
        "message": "Staff access confirmed."
    }), 200


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
