"""
Milestone 3 Verification Script
Tests student-facing frontend assets, template rendering, and API integration.
"""

from app import app


def test_homepage_and_template_rendering():
    client = app.test_client()
    res = client.get("/")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    html = res.get_data(as_text=True)

    # Verify key template elements
    assert "<title>SmartMeal" in html, "Missing SmartMeal title"
    assert "static/css/style.css" in html, "Missing link to style.css"
    assert "static/js/student.js" in html, "Missing script tag for student.js"
    assert 'id="order-form"' in html, "Missing order form element"
    assert 'id="student-name"' in html, "Missing student name input"
    assert 'id="roll-number"' in html, "Missing roll number input"
    assert 'id="section-name"' in html, "Missing section name input"
    assert 'id="track-order-form"' in html, "Missing track order form"
    assert 'id="order-modal-backdrop"' in html, "Missing confirmation modal"
    print("[PASS] Homepage rendered successfully with all required HTML IDs and assets.")


def test_static_assets_served():
    client = app.test_client()

    css_res = client.get("/static/css/style.css")
    assert css_res.status_code == 200, f"Failed to serve style.css: {css_res.status_code}"
    css_text = css_res.get_data(as_text=True)
    assert "SmartMeal" in css_text
    assert "[hidden]" in css_text, "style.css must respect [hidden] to keep initial dialogs hidden"
    assert ".modal-backdrop[hidden]" in css_text or "display: none !important" in css_text

    js_res = client.get("/static/js/student.js")
    assert js_res.status_code == 200, f"Failed to serve student.js: {js_res.status_code}"
    js_text = js_res.get_data(as_text=True)
    assert "loadMenu" in js_text
    assert "modal-close-btn" in js_text
    assert "modal-track-btn" in js_text
    assert "copy-ref-btn" in js_text

    print("[PASS] Static assets (style.css, student.js) served successfully with HTTP 200 and modal safeguards.")


def test_student_flow_end_to_end():
    client = app.test_client()

    # Step 1: Frontend fetches menu
    menu_res = client.get("/api/menu")
    assert menu_res.status_code == 200
    menu = menu_res.get_json()["data"]
    assert len(menu) >= 2, "Menu should have items"
    item1 = menu[0]
    item2 = menu[1]

    # Step 2: Student builds cart & submits order
    payload = {
        "student_name": "Pooja Reddy",
        "roll_number": "22ECE2014",
        "section": "ECE-B",
        "items": [
            {
                "menu_item_id": item1["id"],
                "quantity": 1,
                "cooking_preference": item1["allowed_preferences"][0] if item1["allowed_preferences"] else "Standard",
                "special_request": "Extra hot"
            },
            {
                "menu_item_id": item2["id"],
                "quantity": 2,
                "cooking_preference": item2["allowed_preferences"][0] if item2["allowed_preferences"] else "Standard",
                "special_request": ""
            }
        ]
    }
    order_res = client.post("/api/orders", json=payload)
    assert order_res.status_code == 201
    order_data = order_res.get_json()["data"]
    ref = order_data["order_ref"]
    assert ref.startswith("SM-")

    expected_total = float(item1["price"] * 1 + item2["price"] * 2)
    assert order_data["total_price"] == expected_total

    # Step 3: Student tracks the order
    track_res = client.get(f"/api/orders/{ref}")
    assert track_res.status_code == 200
    track_data = track_res.get_json()["data"]
    assert track_data["order_ref"] == ref
    assert track_data["status"] == "Pending"
    assert track_data["total_price"] == expected_total
    assert len(track_data["items"]) == 2

    print(f"[PASS] End-to-end student flow verified (Ordered: {item1['name']} + {item2['name']}, Ref: {ref}).")


if __name__ == "__main__":
    print("\n=== Running Milestone 3 Verification Suite ===")
    test_homepage_and_template_rendering()
    test_static_assets_served()
    test_student_flow_end_to_end()
    print("=== All Milestone 3 Checks Passed! ===\n")
