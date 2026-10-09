import json
import os
import sqlite3
import uuid
from functools import wraps
from flask import Flask, request, jsonify, session, render_template

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
# Milestone 1 Health & Staff Authentication Endpoints
# ---------------------------------------------------------
@app.route("/")
def home():
    """Renders student-facing ordering and tracking interface."""
    return render_template("index.html")


@app.route("/api/health", methods=["GET"])
def health_check():
    """Verifies SQLite database connectivity and foreign key enforcement."""
    try:
        conn = get_db_connection()
        try:
            fk_status = conn.execute("PRAGMA foreign_keys;").fetchone()[0]
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


# ---------------------------------------------------------
# Milestone 2: Student Ordering Backend Endpoints
# ---------------------------------------------------------

@app.route("/api/menu", methods=["GET"])
def get_menu():
    """
    Returns available canteen menu items.
    Parses allowed_preferences into a native list for frontend consumption.
    """
    try:
        conn = get_db_connection()
        try:
            # Query all available menu items
            rows = conn.execute(
                """
                SELECT id, name, category, price, is_available, max_portion_limit, allowed_preferences
                FROM menu_items
                WHERE is_available = 1
                ORDER BY category, id;
                """
            ).fetchall()

            menu = []
            for r in rows:
                try:
                    prefs = json.loads(r["allowed_preferences"])
                except Exception:
                    prefs = []

                menu.append({
                    "id": r["id"],
                    "name": r["name"],
                    "category": r["category"],
                    "price": float(r["price"]),
                    "is_available": r["is_available"],
                    "max_portion_limit": r["max_portion_limit"],
                    "allowed_preferences": prefs
                })

            return jsonify({
                "status": "success",
                "count": len(menu),
                "data": menu
            }), 200
        finally:
            conn.close()
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": "Failed to retrieve canteen menu.",
            "details": str(e)
        }), 500


def generate_unique_order_ref(conn):
    """Generates an alphanumeric order reference code and guarantees uniqueness."""
    while True:
        ref = f"SM-{uuid.uuid4().hex[:8].upper()}"
        exists = conn.execute("SELECT 1 FROM orders WHERE order_ref = ?;", (ref,)).fetchone()
        if not exists:
            return ref


@app.route("/api/orders", methods=["POST"])
def place_order():
    """
    Accepts student details and order items.
    Performs server-side validation, looks up database prices,
    calculates order total, and atomically stores order and line items.
    """
    payload = request.get_json(silent=True)
    if not payload or not isinstance(payload, dict):
        return jsonify({
            "status": "error",
            "message": "Invalid request body. Expected a valid JSON object."
        }), 400

    # 1. Validate Student Details
    student_name = payload.get("student_name")
    roll_number = payload.get("roll_number")
    section = payload.get("section")

    if not student_name or not isinstance(student_name, str) or not student_name.strip():
        return jsonify({"status": "error", "message": "Student name is required."}), 400
    if not roll_number or not isinstance(roll_number, str) or not roll_number.strip():
        return jsonify({"status": "error", "message": "Roll number is required."}), 400
    if not section or not isinstance(section, str) or not section.strip():
        return jsonify({"status": "error", "message": "Section is required."}), 400

    student_name = student_name.strip()
    roll_number = roll_number.strip()
    section = section.strip()

    if len(student_name) > 100:
        return jsonify({"status": "error", "message": "Student name cannot exceed 100 characters."}), 400
    if len(roll_number) > 50:
        return jsonify({"status": "error", "message": "Roll number cannot exceed 50 characters."}), 400
    if len(section) > 20:
        return jsonify({"status": "error", "message": "Section cannot exceed 20 characters."}), 400

    # 2. Validate Items List
    raw_items = payload.get("items")
    if not raw_items or not isinstance(raw_items, list) or len(raw_items) == 0:
        return jsonify({
            "status": "error",
            "message": "Order must contain at least one menu item."
        }), 400

    conn = get_db_connection()
    try:
        # Pre-validate each item against database catalog
        validated_items = []
        calculated_total = 0.0

        for idx, item in enumerate(raw_items):
            if not isinstance(item, dict):
                return jsonify({
                    "status": "error",
                    "message": f"Item at index {idx} is invalid. Expected a JSON object."
                }), 400

            menu_item_id = item.get("menu_item_id")
            quantity = item.get("quantity")
            cooking_pref = item.get("cooking_preference", "")
            special_req = item.get("special_request", "")

            # Validate menu_item_id
            if menu_item_id is None or not isinstance(menu_item_id, int):
                return jsonify({
                    "status": "error",
                    "message": f"Item at index {idx} has an invalid or missing 'menu_item_id'."
                }), 400

            # Validate quantity
            if quantity is None or not isinstance(quantity, int) or isinstance(quantity, bool) or quantity <= 0:
                return jsonify({
                    "status": "error",
                    "message": f"Quantity for item ID {menu_item_id} must be a positive integer."
                }), 400

            # Query item details from DB using parameterized query
            db_item = conn.execute(
                """
                SELECT id, name, price, is_available, max_portion_limit, allowed_preferences
                FROM menu_items
                WHERE id = ?;
                """,
                (menu_item_id,)
            ).fetchone()

            if not db_item:
                return jsonify({
                    "status": "error",
                    "message": f"Menu item with ID {menu_item_id} does not exist in the canteen catalog."
                }), 400

            # Check item availability
            if db_item["is_available"] != 1:
                return jsonify({
                    "status": "error",
                    "message": f"'{db_item['name']}' is currently sold out or unavailable."
                }), 400

            # Check portion limit
            if quantity > db_item["max_portion_limit"]:
                return jsonify({
                    "status": "error",
                    "message": f"Quantity {quantity} exceeds the limit of {db_item['max_portion_limit']} for '{db_item['name']}'."
                }), 400

            # Parse and validate cooking preference
            try:
                allowed_prefs = json.loads(db_item["allowed_preferences"])
            except Exception:
                allowed_prefs = []

            cooking_pref_str = str(cooking_pref).strip() if cooking_pref is not None else ""
            if cooking_pref_str:
                if allowed_prefs and cooking_pref_str not in allowed_prefs:
                    return jsonify({
                        "status": "error",
                        "message": f"Cooking preference '{cooking_pref_str}' is not supported for '{db_item['name']}'. Supported options: {allowed_prefs}."
                    }), 400
            else:
                # Default to first allowed preference if available, or 'Standard'
                cooking_pref_str = allowed_prefs[0] if allowed_prefs else "Standard"

            # Validate special request
            special_req_str = str(special_req).strip() if special_req is not None else ""
            if len(special_req_str) > 200:
                return jsonify({
                    "status": "error",
                    "message": f"Special request for '{db_item['name']}' exceeds 200 characters."
                }), 400

            # Calculate server-authoritative line price
            unit_price = float(db_item["price"])
            line_total = unit_price * quantity
            calculated_total += line_total

            validated_items.append({
                "menu_item_id": db_item["id"],
                "item_name": db_item["name"],
                "quantity": quantity,
                "unit_price": unit_price,
                "cooking_preference": cooking_pref_str,
                "special_request": special_req_str
            })

        # Atomic database transaction: Insert order and all line items
        with conn:
            order_ref = generate_unique_order_ref(conn)
            cursor = conn.cursor()

            # Insert order record
            cursor.execute(
                """
                INSERT INTO orders (order_ref, student_name, roll_number, section, total_price, status)
                VALUES (?, ?, ?, ?, ?, 'Pending');
                """,
                (order_ref, student_name, roll_number, section, calculated_total)
            )
            order_id = cursor.lastrowid

            # Insert line item records
            for v_item in validated_items:
                cursor.execute(
                    """
                    INSERT INTO order_items (
                        order_id, menu_item_id, quantity, unit_price, cooking_preference, special_request
                    ) VALUES (?, ?, ?, ?, ?, ?);
                    """,
                    (
                        order_id,
                        v_item["menu_item_id"],
                        v_item["quantity"],
                        v_item["unit_price"],
                        v_item["cooking_preference"],
                        v_item["special_request"]
                    )
                )

        return jsonify({
            "status": "success",
            "message": "Order placed successfully!",
            "data": {
                "order_ref": order_ref,
                "total_price": round(calculated_total, 2),
                "status": "Pending",
                "item_count": len(validated_items)
            }
        }), 201

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": "Failed to place order due to a server error.",
            "details": str(e)
        }), 500
    finally:
        conn.close()


@app.route("/api/orders/<order_ref>", methods=["GET"])
def get_order_status(order_ref):
    """
    Retrieves the order status and item summary by order reference.
    Protects student privacy by omitting sensitive personal data.
    """
    ref = order_ref.strip().upper()
    try:
        conn = get_db_connection()
        try:
            # Look up order
            order = conn.execute(
                """
                SELECT id, order_ref, total_price, status, created_at
                FROM orders
                WHERE order_ref = ?;
                """,
                (ref,)
            ).fetchone()

            if not order:
                return jsonify({
                    "status": "error",
                    "message": f"Order reference '{ref}' not found."
                }), 404

            # Look up order line items
            line_items = conn.execute(
                """
                SELECT 
                    oi.quantity,
                    oi.unit_price,
                    oi.cooking_preference,
                    oi.special_request,
                    mi.name AS item_name,
                    mi.category
                FROM order_items oi
                JOIN menu_items mi ON oi.menu_item_id = mi.id
                WHERE oi.order_id = ?
                ORDER BY oi.id ASC;
                """,
                (order["id"],)
            ).fetchall()

            items = [
                {
                    "item_name": li["item_name"],
                    "category": li["category"],
                    "quantity": li["quantity"],
                    "unit_price": float(li["unit_price"]),
                    "line_total": round(float(li["unit_price"]) * li["quantity"], 2),
                    "cooking_preference": li["cooking_preference"],
                    "special_request": li["special_request"]
                }
                for li in line_items
            ]

            return jsonify({
                "status": "success",
                "data": {
                    "order_ref": order["order_ref"],
                    "status": order["status"],
                    "total_price": float(order["total_price"]),
                    "created_at": order["created_at"],
                    "items": items
                }
            }), 200
        finally:
            conn.close()
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": "Failed to retrieve order status.",
            "details": str(e)
        }), 500


# ---------------------------------------------------------
# Milestone 4: Staff Dashboard Endpoints
# ---------------------------------------------------------

@app.route("/staff")
def staff_dashboard():
    """Renders the staff management dashboard."""
    return render_template("staff.html")


@app.route("/api/staff/orders", methods=["GET"])
@require_staff_auth
def get_staff_orders():
    """
    Returns canteen orders with complete student identity and line items for staff fulfillment.
    Supports optional status filtering and search query.
    """
    status_filter = request.args.get("status", "").strip()
    search_query = request.args.get("search", "").strip()

    try:
        conn = get_db_connection()
        try:
            sql = """
                SELECT id, order_ref, student_name, roll_number, section, total_price, status, created_at, updated_at
                FROM orders
                WHERE 1=1
            """
            params = []
            if status_filter and status_filter.lower() != "all":
                sql += " AND LOWER(status) = LOWER(?)"
                params.append(status_filter)

            if search_query:
                sql += " AND (order_ref LIKE ? OR roll_number LIKE ? OR student_name LIKE ?)"
                like_term = f"%{search_query}%"
                params.extend([like_term, like_term, like_term])

            sql += " ORDER BY id DESC"
            order_rows = conn.execute(sql, params).fetchall()

            orders = []
            for o in order_rows:
                items_rows = conn.execute(
                    """
                    SELECT oi.id, oi.quantity, oi.unit_price, oi.cooking_preference, oi.special_request,
                           mi.name AS item_name, mi.category
                    FROM order_items oi
                    JOIN menu_items mi ON oi.menu_item_id = mi.id
                    WHERE oi.order_id = ?
                    ORDER BY oi.id ASC;
                    """,
                    (o["id"],)
                ).fetchall()

                items = [
                    {
                        "item_name": ir["item_name"],
                        "category": ir["category"],
                        "quantity": ir["quantity"],
                        "unit_price": float(ir["unit_price"]),
                        "line_total": round(float(ir["unit_price"]) * ir["quantity"], 2),
                        "cooking_preference": ir["cooking_preference"],
                        "special_request": ir["special_request"]
                    }
                    for ir in items_rows
                ]

                orders.append({
                    "id": o["id"],
                    "order_ref": o["order_ref"],
                    "student_name": o["student_name"],
                    "roll_number": o["roll_number"],
                    "section": o["section"],
                    "total_price": float(o["total_price"]),
                    "status": o["status"],
                    "created_at": o["created_at"],
                    "updated_at": o["updated_at"],
                    "items": items
                })

            return jsonify({
                "status": "success",
                "count": len(orders),
                "data": orders
            }), 200
        finally:
            conn.close()
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": "Failed to retrieve orders.",
            "details": str(e)
        }), 500


# Allowed status lifecycle transitions
VALID_TRANSITIONS = {
    "Pending": ["Confirmed", "Cancelled"],
    "Confirmed": ["Preparing", "Cancelled"],
    "Preparing": ["Ready for Pickup", "Cancelled"],
    "Ready for Pickup": ["Completed", "Cancelled"],
    "Completed": [],
    "Cancelled": []
}


@app.route("/api/staff/orders/<order_ref>/status", methods=["PATCH", "POST"])
@require_staff_auth
def update_order_status(order_ref):
    """
    Updates the lifecycle status of an order according to allowed workflow transitions:
    Pending -> Confirmed -> Preparing -> Ready for Pickup -> Completed (or Cancelled).
    Terminal statuses (Completed, Cancelled) cannot be modified.
    """
    ref = order_ref.strip().upper()
    payload = request.get_json(silent=True) or {}
    new_status = payload.get("status", "").strip()

    if not new_status:
        return jsonify({
            "status": "error",
            "message": "Target status is required."
        }), 400

    conn = get_db_connection()
    try:
        order = conn.execute("SELECT id, status FROM orders WHERE order_ref = ?;", (ref,)).fetchone()
        if not order:
            return jsonify({
                "status": "error",
                "message": f"Order reference '{ref}' not found."
            }), 404

        current_status = order["status"]
        allowed_next = VALID_TRANSITIONS.get(current_status, [])
        if new_status not in allowed_next:
            return jsonify({
                "status": "error",
                "message": f"Invalid status transition from '{current_status}' to '{new_status}'. Allowed next statuses: {allowed_next}."
            }), 400

        with conn:
            conn.execute(
                """
                UPDATE orders
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (new_status, order["id"])
            )

        return jsonify({
            "status": "success",
            "message": f"Order {ref} status updated from '{current_status}' to '{new_status}'.",
            "data": {
                "order_ref": ref,
                "previous_status": current_status,
                "status": new_status
            }
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": "Failed to update order status.",
            "details": str(e)
        }), 500
    finally:
        conn.close()


@app.route("/api/staff/stats", methods=["GET"])
@require_staff_auth
def get_staff_stats():
    """
    Calculates live dashboard statistics directly from SQLite:
    - total_orders: Count of all orders placed in the system.
    - pending_orders: Count of orders currently in 'Pending' status.
    - completed_orders: Count of orders currently in 'Completed' status.
    - today_sales: Sum of total_price for orders placed today (server local date), excluding 'Cancelled' orders.
      Note: This represents gross order value, not confirmed payment gateway revenue, as online payments are not implemented.
    - server_date: Current local date of the server (YYYY-MM-DD).
    - sales_disclaimer: Clarification regarding order value vs payment gateway revenue.
    """
    try:
        conn = get_db_connection()
        try:
            row = conn.execute(
                """
                SELECT
                    COUNT(*) AS total_orders,
                    COALESCE(SUM(CASE WHEN status = 'Pending' THEN 1 ELSE 0 END), 0) AS pending_orders,
                    COALESCE(SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END), 0) AS completed_orders,
                    COALESCE(SUM(CASE WHEN DATE(created_at, 'localtime') = DATE('now', 'localtime') AND status != 'Cancelled' THEN total_price ELSE 0.0 END), 0.0) AS today_sales
                FROM orders;
                """
            ).fetchone()

            server_date = conn.execute("SELECT DATE('now', 'localtime');").fetchone()[0]

            return jsonify({
                "status": "success",
                "data": {
                    "total_orders": int(row["total_orders"]),
                    "pending_orders": int(row["pending_orders"]),
                    "completed_orders": int(row["completed_orders"]),
                    "today_sales": round(float(row["today_sales"]), 2),
                    "server_date": server_date,
                    "sales_disclaimer": "Order value based on non-cancelled orders placed today. Online payment gateway is not integrated."
                }
            }), 200
        finally:
            conn.close()
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": "Failed to calculate staff statistics.",
            "details": str(e)
        }), 500


@app.route("/api/staff/prep-summary", methods=["GET"])
@require_staff_auth
def get_prep_summary():
    """
    Returns aggregated quantities for each dish across all active orders.
    Orders in terminal statuses ('Completed', 'Cancelled') are strictly excluded.
    """
    try:
        conn = get_db_connection()
        try:
            rows = conn.execute(
                """
                SELECT mi.id, mi.name, mi.category, SUM(oi.quantity) as total_quantity
                FROM order_items oi
                JOIN orders o ON oi.order_id = o.id
                JOIN menu_items mi ON oi.menu_item_id = mi.id
                WHERE o.status NOT IN ('Completed', 'Cancelled')
                GROUP BY mi.id, mi.name, mi.category
                ORDER BY total_quantity DESC, mi.name ASC;
                """
            ).fetchall()

            summary = [
                {
                    "item_id": r["id"],
                    "item_name": r["name"],
                    "category": r["category"],
                    "total_quantity": r["total_quantity"]
                }
                for r in rows
            ]

            return jsonify({
                "status": "success",
                "count": len(summary),
                "data": summary
            }), 200
        finally:
            conn.close()
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": "Failed to retrieve preparation summary.",
            "details": str(e)
        }), 500


@app.route("/api/staff/menu", methods=["GET"])
@require_staff_auth
def get_staff_menu():
    """
    Returns complete menu catalog (both available and unavailable items) for staff management.
    """
    try:
        conn = get_db_connection()
        try:
            rows = conn.execute(
                """
                SELECT id, name, category, price, is_available, max_portion_limit, allowed_preferences
                FROM menu_items
                ORDER BY category, id;
                """
            ).fetchall()

            catalog = []
            for r in rows:
                try:
                    prefs = json.loads(r["allowed_preferences"])
                except Exception:
                    prefs = []

                catalog.append({
                    "id": r["id"],
                    "name": r["name"],
                    "category": r["category"],
                    "price": float(r["price"]),
                    "is_available": r["is_available"],
                    "max_portion_limit": r["max_portion_limit"],
                    "allowed_preferences": prefs
                })

            return jsonify({
                "status": "success",
                "count": len(catalog),
                "data": catalog
            }), 200
        finally:
            conn.close()
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": "Failed to retrieve menu catalog.",
            "details": str(e)
        }), 500


@app.route("/api/staff/menu/<int:item_id>/availability", methods=["PATCH", "POST"])
@require_staff_auth
def update_item_availability(item_id):
    """
    Toggles or sets the availability flag for a menu item (1 = Available, 0 = Sold Out).
    """
    payload = request.get_json(silent=True) or {}
    raw_val = payload.get("is_available")

    if raw_val is None:
        return jsonify({
            "status": "error",
            "message": "Field 'is_available' (0 or 1, or boolean) is required."
        }), 400

    if isinstance(raw_val, bool):
        val = 1 if raw_val else 0
    elif isinstance(raw_val, int) and raw_val in (0, 1):
        val = raw_val
    else:
        return jsonify({
            "status": "error",
            "message": "Field 'is_available' must be 0, 1, true, or false."
        }), 400

    conn = get_db_connection()
    try:
        item = conn.execute("SELECT id, name FROM menu_items WHERE id = ?;", (item_id,)).fetchone()
        if not item:
            return jsonify({
                "status": "error",
                "message": f"Menu item with ID {item_id} not found."
            }), 404

        with conn:
            conn.execute("UPDATE menu_items SET is_available = ? WHERE id = ?;", (val, item_id))

        status_str = "Available" if val == 1 else "Sold Out"
        return jsonify({
            "status": "success",
            "message": f"'{item['name']}' is now marked as {status_str}.",
            "data": {
                "id": item_id,
                "name": item["name"],
                "is_available": val
            }
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": "Failed to update item availability.",
            "details": str(e)
        }), 500
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
