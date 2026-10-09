"""
Milestone 2 Verification Script
Tests student ordering backend:
1. Menu catalog retrieval (GET /api/menu)
2. Order placement with validation, portion limits, preferences (POST /api/orders)
3. Server-authoritative price calculation
4. Order tracking & privacy (GET /api/orders/<ref>)
5. Unknown order references (404)
6. Transaction atomicity (no partial orders on validation error)
"""

from app import app, get_db_connection


def test_menu_retrieval():
    client = app.test_client()
    res = client.get("/api/menu")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    body = res.get_json()
    assert body["status"] == "success"
    items = body["data"]
    assert len(items) > 0, "Menu should contain items"

    first = items[0]
    required_keys = ["id", "name", "category", "price", "is_available", "max_portion_limit", "allowed_preferences"]
    for k in required_keys:
        assert k in first, f"Missing key '{k}' in menu item"
    assert isinstance(first["allowed_preferences"], list), "allowed_preferences should be a list"
    print(f"[PASS] Menu retrieved successfully ({len(items)} available items).")


def test_successful_order_placement_and_tracking():
    client = app.test_client()

    # Place a valid order with two distinct items
    # Masala Dosa (id 1, Rs 40.0) x 2 = Rs 80.0
    # Masala Chai (id 9, Rs 12.0) x 1 = Rs 12.0
    # Expected total = Rs 92.0
    order_data = {
        "student_name": "Arjun Sharma",
        "roll_number": "21BCE1045",
        "section": "CSE-A",
        # Client tries to send an altered total and status (must be ignored/overridden by server)
        "total_price": 5.0,
        "status": "Completed",
        "items": [
            {
                "menu_item_id": 1,
                "quantity": 2,
                "cooking_preference": "Crispy",
                "special_request": "Pack chutney separately"
            },
            {
                "menu_item_id": 9,
                "quantity": 1,
                "cooking_preference": "Less Sugar",
                "special_request": ""
            }
        ]
    }

    res = client.post("/api/orders", json=order_data)
    assert res.status_code == 201, f"Expected 201, got {res.status_code}: {res.get_data(as_text=True)}"
    body = res.get_json()
    assert body["status"] == "success"
    order_ref = body["data"]["order_ref"]
    assert order_ref.startswith("SM-"), f"Unexpected order reference format: {order_ref}"

    # Verify server-authoritative price calculation
    server_total = body["data"]["total_price"]
    assert server_total == 92.0, f"Expected total 92.0, got {server_total}"
    assert body["data"]["status"] == "Pending", "Order status must start as 'Pending'"
    print(f"[PASS] Valid order placed successfully (Ref: {order_ref}, Total: Rs. {server_total}).")

    # Track the order using the reference code
    track_res = client.get(f"/api/orders/{order_ref}")
    assert track_res.status_code == 200, f"Expected 200, got {track_res.status_code}"
    track_body = track_res.get_json()
    data = track_body["data"]
    assert data["order_ref"] == order_ref
    assert data["status"] == "Pending"
    assert data["total_price"] == 92.0
    assert len(data["items"]) == 2

    # Verify student personal identity details are NOT exposed in public tracking
    assert "student_name" not in data, "Student name should not be exposed in order tracking"
    assert "roll_number" not in data, "Roll number should not be exposed in order tracking"
    print(f"[PASS] Order tracking verified with student privacy preserved.")


def test_unknown_order_reference():
    client = app.test_client()
    res = client.get("/api/orders/SM-UNKNOWN999")
    assert res.status_code == 404, f"Expected 404 for unknown order reference, got {res.status_code}"
    print("[PASS] Unknown order reference returned 404 Not Found.")


def test_validation_missing_student_details():
    client = app.test_client()
    valid_items = [{"menu_item_id": 1, "quantity": 1}]

    # Missing student name
    res = client.post("/api/orders", json={"roll_number": "101", "section": "A", "items": valid_items})
    assert res.status_code == 400, "Should reject missing student name"

    # Missing roll number
    res = client.post("/api/orders", json={"student_name": "Rohan", "section": "A", "items": valid_items})
    assert res.status_code == 400, "Should reject missing roll number"

    # Missing section
    res = client.post("/api/orders", json={"student_name": "Rohan", "roll_number": "101", "items": valid_items})
    assert res.status_code == 400, "Should reject missing section"

    print("[PASS] Validation correctly rejected missing student details.")


def test_validation_empty_orders_and_malformed():
    client = app.test_client()

    # Empty items list
    res = client.post("/api/orders", json={"student_name": "Rohan", "roll_number": "101", "section": "A", "items": []})
    assert res.status_code == 400, "Should reject empty items list"

    # Non-json / malformed
    res = client.post("/api/orders", data="not json", content_type="text/plain")
    assert res.status_code == 400, "Should reject non-JSON payload"

    print("[PASS] Empty orders and malformed payloads rejected with 400.")


def test_validation_invalid_quantities():
    client = app.test_client()
    base = {"student_name": "Rohan", "roll_number": "101", "section": "A"}

    # Quantity 0
    res = client.post("/api/orders", json={**base, "items": [{"menu_item_id": 1, "quantity": 0}]})
    assert res.status_code == 400, "Should reject quantity 0"

    # Negative quantity
    res = client.post("/api/orders", json={**base, "items": [{"menu_item_id": 1, "quantity": -3}]})
    assert res.status_code == 400, "Should reject negative quantity"

    # Boolean quantity
    res = client.post("/api/orders", json={**base, "items": [{"menu_item_id": 1, "quantity": True}]})
    assert res.status_code == 400, "Should reject boolean quantity"

    # String quantity
    res = client.post("/api/orders", json={**base, "items": [{"menu_item_id": 1, "quantity": "two"}]})
    assert res.status_code == 400, "Should reject string quantity"

    # Exceeding portion limit (Masala Dosa limit is 4)
    res = client.post("/api/orders", json={**base, "items": [{"menu_item_id": 1, "quantity": 10}]})
    assert res.status_code == 400, "Should reject quantity exceeding portion limit"

    print("[PASS] Invalid quantities and portion limits rejected with 400.")


def test_validation_unavailable_item():
    conn = get_db_connection()
    try:
        # Mark item 2 as unavailable
        conn.execute("UPDATE menu_items SET is_available = 0 WHERE id = 2;")
        conn.commit()

        client = app.test_client()
        res = client.post(
            "/api/orders",
            json={
                "student_name": "Rohan",
                "roll_number": "101",
                "section": "A",
                "items": [{"menu_item_id": 2, "quantity": 1}]
            }
        )
        assert res.status_code == 400, "Should reject order for unavailable item"
        assert "unavailable" in res.get_json()["message"].lower() or "sold out" in res.get_json()["message"].lower()
        print("[PASS] Ordering an unavailable/sold out item correctly rejected with 400.")
    finally:
        # Restore item 2 availability
        conn.execute("UPDATE menu_items SET is_available = 1 WHERE id = 2;")
        conn.commit()
        conn.close()


def test_validation_invalid_preference():
    client = app.test_client()
    res = client.post(
        "/api/orders",
        json={
            "student_name": "Rohan",
            "roll_number": "101",
            "section": "A",
            "items": [
                {
                    "menu_item_id": 1,
                    "quantity": 1,
                    "cooking_preference": "NonExistentCookingStyle123"
                }
            ]
        }
    )
    assert res.status_code == 400, "Should reject invalid cooking preference"
    assert "not supported" in res.get_json()["message"].lower()
    print("[PASS] Invalid cooking preference rejected with 400.")


def test_atomicity_no_partial_records():
    conn = get_db_connection()
    try:
        initial_orders = conn.execute("SELECT COUNT(*) FROM orders;").fetchone()[0]
        initial_order_items = conn.execute("SELECT COUNT(*) FROM order_items;").fetchone()[0]

        client = app.test_client()
        # Item 1 is valid, but item 2 has an invalid quantity exceeding limit
        res = client.post(
            "/api/orders",
            json={
                "student_name": "Test Student",
                "roll_number": "999",
                "section": "X",
                "items": [
                    {"menu_item_id": 1, "quantity": 1},
                    {"menu_item_id": 2, "quantity": 999}  # Will fail validation
                ]
            }
        )
        assert res.status_code == 400

        final_orders = conn.execute("SELECT COUNT(*) FROM orders;").fetchone()[0]
        final_order_items = conn.execute("SELECT COUNT(*) FROM order_items;").fetchone()[0]

        assert initial_orders == final_orders, "Order count changed despite validation error!"
        assert initial_order_items == final_order_items, "Order items count changed despite validation error!"
        print("[PASS] Atomicity confirmed: failed order created 0 database records.")
    finally:
        conn.close()


if __name__ == "__main__":
    print("\n=== Running Milestone 2 Verification Suite ===")
    test_menu_retrieval()
    test_successful_order_placement_and_tracking()
    test_unknown_order_reference()
    test_validation_missing_student_details()
    test_validation_empty_orders_and_malformed()
    test_validation_invalid_quantities()
    test_validation_unavailable_item()
    test_validation_invalid_preference()
    test_atomicity_no_partial_records()
    print("=== All Milestone 2 Checks Passed! ===\n")
