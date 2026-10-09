"""
Milestone 1 Verification Script
Tests database schema, foreign key enforcement, idempotent seeding, and staff authentication.
"""

import sqlite3
from app import app, get_db_connection, STAFF_PIN


def test_schema_and_tables():
    conn = get_db_connection()
    try:
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
        assert "menu_items" in tables, "menu_items table missing"
        assert "orders" in tables, "orders table missing"
        assert "order_items" in tables, "order_items table missing"
        print("[PASS] All 3 tables (menu_items, orders, order_items) exist.")
    finally:
        conn.close()


def test_foreign_key_enforcement():
    conn = get_db_connection()
    try:
        # Check PRAGMA foreign_keys is 1
        fk_status = conn.execute("PRAGMA foreign_keys;").fetchone()[0]
        assert fk_status == 1, "Foreign keys are not enabled"
        print("[PASS] SQLite PRAGMA foreign_keys is active (1).")

        # Test FK violation by inserting into order_items with a non-existent order_id
        violation_caught = False
        try:
            conn.execute(
                """
                INSERT INTO order_items (order_id, menu_item_id, quantity, unit_price)
                VALUES (99999, 1, 2, 40.0);
                """
            )
            conn.commit()
        except sqlite3.IntegrityError:
            violation_caught = True

        assert violation_caught, "Foreign key constraint failed to trigger an IntegrityError on invalid order_id!"
        print("[PASS] Foreign key constraint successfully rejected invalid reference (IntegrityError raised).")
    finally:
        conn.close()


def test_menu_items_count():
    conn = get_db_connection()
    try:
        count = conn.execute("SELECT COUNT(*) FROM menu_items;").fetchone()[0]
        assert count == 10, f"Expected 10 seeded menu items, found {count}"
        print(f"[PASS] Exact expected menu item count confirmed: {count} items.")
    finally:
        conn.close()


def test_staff_auth():
    client = app.test_client()

    # 1. Unauthenticated request to staff route should return 401
    res = client.get("/api/staff/check-auth")
    assert res.status_code == 401, f"Expected 401 for unauthenticated request, got {res.status_code}"
    print("[PASS] Unauthenticated access to staff endpoint blocked with 401.")

    # 2. Header-based authentication with correct PIN
    res = client.get("/api/staff/check-auth", headers={"X-Staff-Pin": STAFF_PIN})
    assert res.status_code == 200, f"Expected 200 with X-Staff-Pin header, got {res.status_code}"
    print("[PASS] Header-based staff authentication (X-Staff-Pin) succeeded with 200.")

    # 3. Bad login PIN should return 401
    res = client.post("/api/staff/login", json={"pin": "wrong_pin"})
    assert res.status_code == 401, f"Expected 401 for wrong PIN, got {res.status_code}"
    print("[PASS] Incorrect staff PIN rejected with 401.")

    # 4. Correct login PIN establishes session
    res = client.post("/api/staff/login", json={"pin": STAFF_PIN})
    assert res.status_code == 200, f"Expected 200 for valid PIN, got {res.status_code}"

    # Check that session cookie now allows access to protected route
    res = client.get("/api/staff/check-auth")
    assert res.status_code == 200, f"Expected 200 for session-authenticated staff, got {res.status_code}"
    print("[PASS] Session-based staff login and authenticated access verified.")


if __name__ == "__main__":
    print("\n=== Running Milestone 1 Verification Suite ===")
    test_schema_and_tables()
    test_foreign_key_enforcement()
    test_menu_items_count()
    test_staff_auth()
    print("=== All Milestone 1 Checks Passed! ===\n")
