"""
Milestone 4 Verification Script
Tests staff management dashboard backend APIs and business rules:
1. Unauthenticated staff access is rejected (401).
2. Valid and invalid staff PINs for login and logout.
3. Viewing orders and valid status transitions (Pending -> Confirmed -> Preparing -> Ready for Pickup -> Completed).
4. Invalid and backward status transitions are rejected (400).
5. Terminal orders (Completed, Cancelled) cannot be transitioned.
6. Food preparation summary aggregates active orders and excludes Completed and Cancelled orders.
7. Menu availability toggling persists in SQLite.
8. Students cannot order sold-out items.
9. Staff template /staff renders properly.
"""

from app import app, get_db_connection, STAFF_PIN


def test_staff_authentication_and_unauthorized_rejection():
    client = app.test_client()

    # 1. Unauthenticated requests to all staff endpoints should return 401
    endpoints = [
        ("GET", "/api/staff/check-auth", None),
        ("GET", "/api/staff/orders", None),
        ("PATCH", "/api/staff/orders/SM-DUMMY/status", {"status": "Confirmed"}),
        ("GET", "/api/staff/prep-summary", None),
        ("GET", "/api/staff/menu", None),
        ("PATCH", "/api/staff/menu/1/availability", {"is_available": 0}),
    ]

    for method, path, payload in endpoints:
        if method == "GET":
            res = client.get(path)
        else:
            res = client.patch(path, json=payload)
        assert res.status_code == 401, f"Expected 401 for unauthenticated {method} {path}, got {res.status_code}"

    print("[PASS] Unauthenticated access to all staff API endpoints rejected with 401.")

    # 2. Test invalid PIN rejected
    res = client.post("/api/staff/login", json={"pin": "wrong_pin_123"})
    assert res.status_code == 401, f"Expected 401 for wrong PIN, got {res.status_code}"

    # 3. Test valid PIN accepted and establishes session
    res = client.post("/api/staff/login", json={"pin": STAFF_PIN})
    assert res.status_code == 200, f"Expected 200 for valid PIN, got {res.status_code}"
    body = res.get_json()
    assert body["status"] == "success"

    # 4. Session now allows access to protected routes
    res = client.get("/api/staff/check-auth")
    assert res.status_code == 200
    assert res.get_json()["authenticated"] is True

    # 5. Logout clears session
    res = client.post("/api/staff/logout")
    assert res.status_code == 200
    res = client.get("/api/staff/check-auth")
    assert res.status_code == 401

    print("[PASS] Staff PIN authentication, session establishment, and logout verified.")


def test_staff_view_orders_and_valid_status_transitions():
    client = app.test_client()

    # Create an order as a student
    order_payload = {
        "student_name": "Rohan Gupta",
        "roll_number": "21BCE2001",
        "section": "CSE-B",
        "items": [
            {"menu_item_id": 1, "quantity": 2, "cooking_preference": "Crispy", "special_request": "Pack separately"}
        ]
    }
    order_res = client.post("/api/orders", json=order_payload)
    assert order_res.status_code == 201
    order_ref = order_res.get_json()["data"]["order_ref"]

    # Authenticate as staff using header for isolated test calls
    headers = {"X-Staff-Pin": STAFF_PIN}

    # 1. Staff views orders
    res = client.get("/api/staff/orders", headers=headers)
    assert res.status_code == 200
    orders = res.get_json()["data"]
    matched = next((o for o in orders if o["order_ref"] == order_ref), None)
    assert matched is not None, f"Order {order_ref} should appear in staff orders list"
    assert matched["student_name"] == "Rohan Gupta"
    assert matched["roll_number"] == "21BCE2001"
    assert matched["section"] == "CSE-B"
    assert matched["status"] == "Pending"
    assert len(matched["items"]) == 1
    assert matched["items"][0]["item_name"] == "Masala Dosa"
    assert matched["items"][0]["cooking_preference"] == "Crispy"

    print(f"[PASS] Staff orders list retrieved with student metadata and line items (Order: {order_ref}).")

    # 2. Sequential valid transitions: Pending -> Confirmed -> Preparing -> Ready for Pickup -> Completed
    transitions = [
        ("Confirmed", 200),
        ("Preparing", 200),
        ("Ready for Pickup", 200),
        ("Completed", 200)
    ]

    for target_status, expected_code in transitions:
        patch_res = client.patch(
            f"/api/staff/orders/{order_ref}/status",
            headers=headers,
            json={"status": target_status}
        )
        assert patch_res.status_code == expected_code, \
            f"Failed transitioning to {target_status}: {patch_res.get_data(as_text=True)}"
        assert patch_res.get_json()["data"]["status"] == target_status

    print(f"[PASS] Complete valid status lifecycle (Pending -> Confirmed -> Preparing -> Ready for Pickup -> Completed) verified.")


def test_invalid_status_transitions_and_terminal_states():
    client = app.test_client()
    headers = {"X-Staff-Pin": STAFF_PIN}

    # Order 1: Test skipping steps and backward steps
    order_res = client.post("/api/orders", json={
        "student_name": "Anita Roy",
        "roll_number": "22ECE101",
        "section": "ECE-A",
        "items": [{"menu_item_id": 9, "quantity": 1}]
    })
    order_ref = order_res.get_json()["data"]["order_ref"]

    # Invalid jump: Pending -> Completed
    res = client.patch(f"/api/staff/orders/{order_ref}/status", headers=headers, json={"status": "Completed"})
    assert res.status_code == 400, "Should reject skipping to Completed directly from Pending"

    # Invalid jump: Pending -> Ready for Pickup
    res = client.patch(f"/api/staff/orders/{order_ref}/status", headers=headers, json={"status": "Ready for Pickup"})
    assert res.status_code == 400, "Should reject skipping to Ready for Pickup directly from Pending"

    # Move to Confirmed
    res = client.patch(f"/api/staff/orders/{order_ref}/status", headers=headers, json={"status": "Confirmed"})
    assert res.status_code == 200

    # Invalid backward step: Confirmed -> Pending
    res = client.patch(f"/api/staff/orders/{order_ref}/status", headers=headers, json={"status": "Pending"})
    assert res.status_code == 400, "Should reject backward transition to Pending"

    # Move to Preparing
    res = client.patch(f"/api/staff/orders/{order_ref}/status", headers=headers, json={"status": "Preparing"})
    assert res.status_code == 200

    # Move to Ready for Pickup
    res = client.patch(f"/api/staff/orders/{order_ref}/status", headers=headers, json={"status": "Ready for Pickup"})
    assert res.status_code == 200

    # Move to Completed (terminal)
    res = client.patch(f"/api/staff/orders/{order_ref}/status", headers=headers, json={"status": "Completed"})
    assert res.status_code == 200

    # Terminal state rejection: Completed -> Pending or Confirmed
    res = client.patch(f"/api/staff/orders/{order_ref}/status", headers=headers, json={"status": "Pending"})
    assert res.status_code == 400, "Should reject modifying an already Completed order"

    res = client.patch(f"/api/staff/orders/{order_ref}/status", headers=headers, json={"status": "Cancelled"})
    assert res.status_code == 400, "Should reject cancelling an already Completed order"

    # Order 2: Test cancellation and terminal Cancelled state
    order_res2 = client.post("/api/orders", json={
        "student_name": "Dev Patel",
        "roll_number": "22MECH301",
        "section": "MECH-B",
        "items": [{"menu_item_id": 9, "quantity": 1}]
    })
    order_ref2 = order_res2.get_json()["data"]["order_ref"]

    # Cancel pending order
    res = client.patch(f"/api/staff/orders/{order_ref2}/status", headers=headers, json={"status": "Cancelled"})
    assert res.status_code == 200
    assert res.get_json()["data"]["status"] == "Cancelled"

    # Terminal state rejection: Cancelled -> Confirmed
    res = client.patch(f"/api/staff/orders/{order_ref2}/status", headers=headers, json={"status": "Confirmed"})
    assert res.status_code == 400, "Should reject transitioning a Cancelled order"

    print("[PASS] Invalid, backward, and terminal status transitions strictly rejected with 400.")


def test_prep_summary_aggregates_active_orders_and_excludes_terminal():
    client = app.test_client()
    headers = {"X-Staff-Pin": STAFF_PIN}

    # Fetch baseline prep quantity for item 1 (Masala Dosa)
    res = client.get("/api/staff/prep-summary", headers=headers)
    assert res.status_code == 200
    baseline = res.get_json()["data"]
    baseline_dosa = next((i["total_quantity"] for i in baseline if i["item_name"] == "Masala Dosa"), 0)

    # 1. Place Active Order A (2x Masala Dosa) -> status: Pending
    res_a = client.post("/api/orders", json={
        "student_name": "Student A",
        "roll_number": "A101",
        "section": "A",
        "items": [{"menu_item_id": 1, "quantity": 2}]
    })
    ref_a = res_a.get_json()["data"]["order_ref"]

    # 2. Place Order B (3x Masala Dosa) and move to Completed
    res_b = client.post("/api/orders", json={
        "student_name": "Student B",
        "roll_number": "B102",
        "section": "B",
        "items": [{"menu_item_id": 1, "quantity": 3}]
    })
    ref_b = res_b.get_json()["data"]["order_ref"]
    client.patch(f"/api/staff/orders/{ref_b}/status", headers=headers, json={"status": "Confirmed"})
    client.patch(f"/api/staff/orders/{ref_b}/status", headers=headers, json={"status": "Preparing"})
    client.patch(f"/api/staff/orders/{ref_b}/status", headers=headers, json={"status": "Ready for Pickup"})
    client.patch(f"/api/staff/orders/{ref_b}/status", headers=headers, json={"status": "Completed"})

    # 3. Place Order C (4x Masala Dosa) and Cancel it
    res_c = client.post("/api/orders", json={
        "student_name": "Student C",
        "roll_number": "C103",
        "section": "C",
        "items": [{"menu_item_id": 1, "quantity": 4}]
    })
    ref_c = res_c.get_json()["data"]["order_ref"]
    client.patch(f"/api/staff/orders/{ref_c}/status", headers=headers, json={"status": "Cancelled"})

    # 4. Check preparation summary
    res = client.get("/api/staff/prep-summary", headers=headers)
    assert res.status_code == 200
    summary = res.get_json()["data"]
    new_dosa_total = next((i["total_quantity"] for i in summary if i["item_name"] == "Masala Dosa"), 0)

    # Should only increase by 2 (Order A), Order B (Completed) and Order C (Cancelled) must NOT be counted
    assert new_dosa_total == baseline_dosa + 2, \
        f"Expected prep summary to increase by exactly 2 (Order A only), but went from {baseline_dosa} to {new_dosa_total}"

    print(f"[PASS] Preparation summary verified: correctly aggregated active orders and excluded Completed & Cancelled.")


def test_menu_availability_toggling_and_order_prevention():
    client = app.test_client()
    headers = {"X-Staff-Pin": STAFF_PIN}

    # 1. Staff retrieves full menu catalog
    res = client.get("/api/staff/menu", headers=headers)
    assert res.status_code == 200
    catalog = res.get_json()["data"]
    assert len(catalog) >= 10

    # Target item 3 (Chole Bhature)
    target_item_id = 3

    # Ensure item 3 starts as available
    client.patch(f"/api/staff/menu/{target_item_id}/availability", headers=headers, json={"is_available": 1})

    # 2. Staff marks item 3 as Sold Out (is_available = 0)
    toggle_res = client.patch(
        f"/api/staff/menu/{target_item_id}/availability",
        headers=headers,
        json={"is_available": 0}
    )
    assert toggle_res.status_code == 200
    assert toggle_res.get_json()["data"]["is_available"] == 0

    # Verify persistence in database
    conn = get_db_connection()
    try:
        val = conn.execute("SELECT is_available FROM menu_items WHERE id = ?;", (target_item_id,)).fetchone()[0]
        assert val == 0, "Item availability change did not persist in database"
    finally:
        conn.close()

    # 3. Verify public GET /api/menu omits sold out item
    public_menu_res = client.get("/api/menu")
    assert public_menu_res.status_code == 200
    avail_ids = [item["id"] for item in public_menu_res.get_json()["data"]]
    assert target_item_id not in avail_ids, "Sold out item must not be listed in public GET /api/menu"

    # 4. Student attempts to order sold out item -> should be rejected with 400
    order_res = client.post("/api/orders", json={
        "student_name": "Test Student",
        "roll_number": "T101",
        "section": "A",
        "items": [{"menu_item_id": target_item_id, "quantity": 1}]
    })
    assert order_res.status_code == 400, "Student order for sold-out item should be rejected with 400"
    assert "sold out" in order_res.get_json()["message"].lower() or "unavailable" in order_res.get_json()["message"].lower()

    # 5. Restore item 3 availability
    restore_res = client.patch(
        f"/api/staff/menu/{target_item_id}/availability",
        headers=headers,
        json={"is_available": 1}
    )
    assert restore_res.status_code == 200
    assert restore_res.get_json()["data"]["is_available"] == 1

    # Student can now successfully order item 3
    valid_order_res = client.post("/api/orders", json={
        "student_name": "Test Student",
        "roll_number": "T101",
        "section": "A",
        "items": [{"menu_item_id": target_item_id, "quantity": 1}]
    })
    assert valid_order_res.status_code == 201

    print("[PASS] Menu availability toggling persisted and student sold-out order prevention verified.")


def test_staff_dashboard_template_rendered():
    client = app.test_client()
    res = client.get("/staff")
    assert res.status_code == 200
    html = res.get_data(as_text=True)

    # Verify key dashboard template elements
    assert "SmartMeal" in html
    assert "Staff Portal" in html
    assert 'id="staff-pin-input"' in html, "Missing staff pin input element"
    assert 'id="staff-login-btn"' in html, "Missing staff login button"
    assert 'id="staff-orders-grid"' in html, "Missing staff orders grid"
    assert 'id="staff-prep-grid"' in html, "Missing prep summary grid"
    assert 'id="staff-menu-table"' in html, "Missing menu table element"
    assert "static/js/staff.js" in html, "Missing link to staff.js"

    print("[PASS] Staff dashboard HTML (/staff) rendered successfully with all required IDs and scripts.")


if __name__ == "__main__":
    print("\n=== Running Milestone 4 Verification Suite ===")
    test_staff_authentication_and_unauthorized_rejection()
    test_staff_view_orders_and_valid_status_transitions()
    test_invalid_status_transitions_and_terminal_states()
    test_prep_summary_aggregates_active_orders_and_excludes_terminal()
    test_menu_availability_toggling_and_order_prevention()
    test_staff_dashboard_template_rendered()
    print("=== All Milestone 4 Checks Passed! ===\n")
