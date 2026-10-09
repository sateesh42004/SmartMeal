"""
Milestone 5B Verification Script
Tests staff dashboard statistics cards:
1. Unauthenticated staff access to /api/staff/stats is rejected (401).
2. Authenticated access via X-Staff-Pin and session cookie succeeds (200).
3. Empty database calculations return 0 orders and 0.0 sales gracefully.
4. Live calculations from SQLite:
   - Total Orders (all-time placed orders)
   - Pending Orders (orders in 'Pending' status)
   - Completed Orders (orders in 'Completed' status)
   - Today's Sales (sum of order totals placed on server local date, excluding Cancelled orders)
5. Server local date consistency and sales disclaimer explanation.
6. Dynamic updates when orders are placed or status transitions occur.
7. Staff HTML (/staff), CSS, and JS integration contract checks.
"""

import os
import sqlite3
import tempfile
import datetime
from app import app, STAFF_PIN


def test_stats_authentication_protection():
    client = app.test_client()

    # 1. Unauthenticated request must return 401
    res = client.get("/api/staff/stats")
    assert res.status_code == 401, f"Expected 401 for unauthenticated GET /api/staff/stats, got {res.status_code}"
    body = res.get_json()
    assert body["status"] == "error"

    # 2. Invalid PIN in header must return 401
    res = client.get("/api/staff/stats", headers={"X-Staff-Pin": "invalid_pin_xyz"})
    assert res.status_code == 401, f"Expected 401 for invalid PIN, got {res.status_code}"

    # 3. Valid PIN in header must return 200
    res = client.get("/api/staff/stats", headers={"X-Staff-Pin": STAFF_PIN})
    assert res.status_code == 200, f"Expected 200 for valid PIN, got {res.status_code}"
    data = res.get_json()["data"]
    assert "total_orders" in data
    assert "pending_orders" in data
    assert "completed_orders" in data
    assert "today_sales" in data
    assert "server_date" in data
    assert "sales_disclaimer" in data

    # 4. Session cookie authentication must return 200
    with client.session_transaction() as sess:
        sess["is_staff"] = True

    res_session = client.get("/api/staff/stats")
    assert res_session.status_code == 200
    assert res_session.get_json()["status"] == "success"

    print("[PASS] Staff statistics endpoint authentication and authorization protected (401 & 200).")


def test_empty_database_and_zero_handling():
    # Use isolated temporary SQLite database to test empty state
    temp_fd, temp_db_path = tempfile.mkstemp(suffix=".db")
    os.close(temp_fd)

    try:
        conn = sqlite3.connect(temp_db_path)
        conn.row_factory = sqlite3.Row
        with conn:
            conn.execute("""
                CREATE TABLE orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_ref TEXT UNIQUE NOT NULL,
                    student_name TEXT NOT NULL,
                    roll_number TEXT NOT NULL,
                    section TEXT NOT NULL,
                    total_price REAL NOT NULL CHECK(total_price >= 0),
                    status TEXT NOT NULL DEFAULT 'Pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
        conn.close()

        # Temporarily point app's DATABASE_PATH to empty db
        import app as app_module
        orig_db = app_module.DATABASE_PATH
        app_module.DATABASE_PATH = temp_db_path

        try:
            client = app.test_client()
            res = client.get("/api/staff/stats", headers={"X-Staff-Pin": STAFF_PIN})
            assert res.status_code == 200
            data = res.get_json()["data"]
            assert data["total_orders"] == 0, f"Expected 0 total orders, got {data['total_orders']}"
            assert data["pending_orders"] == 0, f"Expected 0 pending orders, got {data['pending_orders']}"
            assert data["completed_orders"] == 0, f"Expected 0 completed orders, got {data['completed_orders']}"
            assert data["today_sales"] == 0.0, f"Expected 0.0 today sales, got {data['today_sales']}"
            assert data["server_date"] == datetime.date.today().isoformat()
            assert "payment" in data["sales_disclaimer"].lower() or "order value" in data["sales_disclaimer"].lower()
        finally:
            app_module.DATABASE_PATH = orig_db

        print("[PASS] Empty database returns all zeros gracefully without errors.")
    finally:
        if os.path.exists(temp_db_path):
            os.remove(temp_db_path)


def test_statistics_calculation_filtering_and_lifecycle():
    # Use isolated temporary SQLite database to test exact math and lifecycle
    temp_fd, temp_db_path = tempfile.mkstemp(suffix=".db")
    os.close(temp_fd)

    try:
        conn = sqlite3.connect(temp_db_path)
        conn.row_factory = sqlite3.Row
        with conn:
            conn.execute("""
                CREATE TABLE orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_ref TEXT UNIQUE NOT NULL,
                    student_name TEXT NOT NULL,
                    roll_number TEXT NOT NULL,
                    section TEXT NOT NULL,
                    total_price REAL NOT NULL CHECK(total_price >= 0),
                    status TEXT NOT NULL DEFAULT 'Pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 1. Order today: Pending (Total: 120.0) -> counts in total, pending, today_sales
            conn.execute("""
                INSERT INTO orders (order_ref, student_name, roll_number, section, total_price, status)
                VALUES ('SM-TEST01', 'Student A', '20BCE001', 'A', 120.0, 'Pending');
            """)

            # 2. Order today: Completed (Total: 250.50) -> counts in total, completed, today_sales
            conn.execute("""
                INSERT INTO orders (order_ref, student_name, roll_number, section, total_price, status)
                VALUES ('SM-TEST02', 'Student B', '20BCE002', 'A', 250.50, 'Completed');
            """)

            # 3. Order today: Preparing (Total: 80.0) -> counts in total, today_sales (not pending, not completed)
            conn.execute("""
                INSERT INTO orders (order_ref, student_name, roll_number, section, total_price, status)
                VALUES ('SM-TEST03', 'Student C', '20BCE003', 'B', 80.0, 'Preparing');
            """)

            # 4. Order today: Cancelled (Total: 65.0) -> counts in total, but EXCLUDED from today_sales!
            conn.execute("""
                INSERT INTO orders (order_ref, student_name, roll_number, section, total_price, status)
                VALUES ('SM-TEST04', 'Student D', '20BCE004', 'B', 65.0, 'Cancelled');
            """)

            # 5. Order yesterday: Completed (Total: 300.0) -> counts in total, completed, but EXCLUDED from today_sales!
            conn.execute("""
                INSERT INTO orders (order_ref, student_name, roll_number, section, total_price, status, created_at)
                VALUES ('SM-TEST05', 'Student E', '20BCE005', 'C', 300.0, 'Completed', datetime('now', '-1 day'));
            """)

            # 6. Order yesterday: Cancelled (Total: 50.0) -> counts in total, EXCLUDED from today_sales
            conn.execute("""
                INSERT INTO orders (order_ref, student_name, roll_number, section, total_price, status, created_at)
                VALUES ('SM-TEST06', 'Student F', '20BCE006', 'C', 50.0, 'Cancelled', datetime('now', '-2 days'));
            """)
        conn.close()

        import app as app_module
        orig_db = app_module.DATABASE_PATH
        app_module.DATABASE_PATH = temp_db_path

        try:
            client = app.test_client()
            res = client.get("/api/staff/stats", headers={"X-Staff-Pin": STAFF_PIN})
            assert res.status_code == 200
            data = res.get_json()["data"]

            # Expected:
            # Total orders: 6
            # Pending orders: 1 (SM-TEST01)
            # Completed orders: 2 (SM-TEST02 today + SM-TEST05 yesterday)
            # Today's sales: 120.0 + 250.50 + 80.0 = 450.50 (cancelled 65.0 and yesterday 300.0/50.0 excluded)
            assert data["total_orders"] == 6, f"Expected 6, got {data['total_orders']}"
            assert data["pending_orders"] == 1, f"Expected 1, got {data['pending_orders']}"
            assert data["completed_orders"] == 2, f"Expected 2, got {data['completed_orders']}"
            assert round(data["today_sales"], 2) == 450.50, f"Expected 450.50, got {data['today_sales']}"

            # Verify server local date is consistent
            assert data["server_date"] == datetime.date.today().isoformat()

            # Now simulate lifecycle: update SM-TEST01 (Pending, 120.0) -> Completed
            conn = sqlite3.connect(temp_db_path)
            with conn:
                conn.execute("UPDATE orders SET status = 'Completed' WHERE order_ref = 'SM-TEST01';")
            conn.close()

            res2 = client.get("/api/staff/stats", headers={"X-Staff-Pin": STAFF_PIN})
            data2 = res2.get_json()["data"]
            assert data2["pending_orders"] == 0, f"Expected 0 pending, got {data2['pending_orders']}"
            assert data2["completed_orders"] == 3, f"Expected 3 completed, got {data2['completed_orders']}"
            assert round(data2["today_sales"], 2) == 450.50

            # Now simulate cancel: update SM-TEST03 (Preparing, 80.0) -> Cancelled
            conn = sqlite3.connect(temp_db_path)
            with conn:
                conn.execute("UPDATE orders SET status = 'Cancelled' WHERE order_ref = 'SM-TEST03';")
            conn.close()

            res3 = client.get("/api/staff/stats", headers={"X-Staff-Pin": STAFF_PIN})
            data3 = res3.get_json()["data"]
            # Today's sales should decrease by 80.0: 450.50 - 80.0 = 370.50
            assert round(data3["today_sales"], 2) == 370.50, f"Expected 370.50, got {data3['today_sales']}"

        finally:
            app_module.DATABASE_PATH = orig_db

        print("[PASS] Accurate calculations, server local date filtering, and Cancelled order exclusions verified.")
    finally:
        if os.path.exists(temp_db_path):
            os.remove(temp_db_path)


def test_staff_dashboard_ui_and_frontend_contract():
    client = app.test_client()

    # 1. Staff dashboard page /staff renders
    res = client.get("/staff")
    assert res.status_code == 200
    html = res.get_data(as_text=True)

    required_element_ids = [
        "stat-total-orders",
        "stat-pending-orders",
        "stat-completed-orders",
        "stat-today-sales",
        "stat-server-date",
        "staff-refresh-btn"
    ]
    for el_id in required_element_ids:
        assert f'id="{el_id}"' in html, f"Missing required element id='{el_id}' in templates/staff.html"

    # 2. Check CSS file contains stats styling
    css_res = client.get("/static/css/style.css")
    assert css_res.status_code == 200
    css_text = css_res.get_data(as_text=True)
    assert ".staff-stats-grid" in css_text, "Missing .staff-stats-grid in style.css"
    assert ".stat-card" in css_text, "Missing .stat-card in style.css"

    # 3. Check JS file contains loadStats and endpoint reference
    js_res = client.get("/static/js/staff.js")
    assert js_res.status_code == 200
    js_text = js_res.get_data(as_text=True)
    assert "loadStats" in js_text, "Missing loadStats in static/js/staff.js"
    assert "/api/staff/stats" in js_text, "Missing /api/staff/stats endpoint call in static/js/staff.js"

    print("[PASS] Staff UI contract, required element IDs, and CSS/JS integrations verified.")


if __name__ == "__main__":
    print("\n=== Running Milestone 5B Verification Suite ===")
    test_stats_authentication_protection()
    test_empty_database_and_zero_handling()
    test_statistics_calculation_filtering_and_lifecycle()
    test_staff_dashboard_ui_and_frontend_contract()
    print("=== All Milestone 5B Checks Passed! ===\n")
