"""
Milestone 5A Verification Script
Tests automatic student order-status updates:
1. Status progression API contract (Pending -> Confirmed -> Preparing -> Ready for Pickup -> Completed, and Cancelled).
2. Terminal order states (Completed, Cancelled) and non-existent reference handling.
3. Frontend code contract (5-second polling interval, overlap prevention, progression steps, graceful error handling).
4. Headless Chrome End-to-End Test:
   - Student opens order tracking.
   - Stepper progression is visually rendered.
   - Background staff status transitions are picked up automatically by polling without page reloads.
   - Polling stops when order reaches terminal status (Completed/Cancelled) or when switching tabs.
"""

import threading
import time
import unittest
from werkzeug.serving import make_server
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from app import app, init_db, STAFF_PIN


class ServerThread(threading.Thread):
    def __init__(self, app_instance, host="127.0.0.1", port=5066):
        super().__init__()
        self.server = make_server(host, port, app_instance)
        self.ctx = app_instance.app_context()
        self.ctx.push()

    def run(self):
        self.server.serve_forever()

    def shutdown(self):
        self.server.shutdown()


def test_order_status_progression_api_contract():
    client = app.test_client()
    staff_headers = {"X-Staff-Pin": STAFF_PIN}

    # 1. Place a new order
    order_res = client.post("/api/orders", json={
        "student_name": "Kavita Nair",
        "roll_number": "23ECE001",
        "section": "ECE-A",
        "items": [{"menu_item_id": 9, "quantity": 1}]
    })
    assert order_res.status_code == 201
    order_ref = order_res.get_json()["data"]["order_ref"]

    # 2. Check initial tracking response (Pending)
    track_res = client.get(f"/api/orders/{order_ref}")
    assert track_res.status_code == 200
    assert track_res.get_json()["data"]["status"] == "Pending"

    # 3. Simulate progression through lifecycle and verify tracking API returns each status
    expected_statuses = ["Confirmed", "Preparing", "Ready for Pickup", "Completed"]
    for status in expected_statuses:
        patch_res = client.patch(
            f"/api/staff/orders/{order_ref}/status",
            headers=staff_headers,
            json={"status": status}
        )
        assert patch_res.status_code == 200

        # Student polling endpoint must return updated status immediately
        poll_res = client.get(f"/api/orders/{order_ref}")
        assert poll_res.status_code == 200
        assert poll_res.get_json()["data"]["status"] == status

    # 4. Check terminal state and 404 for unknown order
    not_found_res = client.get("/api/orders/SM-NONEXISTENT")
    assert not_found_res.status_code == 404

    # 5. Check Cancelled status
    order_res2 = client.post("/api/orders", json={
        "student_name": "Siddharth Verma",
        "roll_number": "23MECH102",
        "section": "MECH-A",
        "items": [{"menu_item_id": 9, "quantity": 1}]
    })
    order_ref2 = order_res2.get_json()["data"]["order_ref"]
    client.patch(f"/api/staff/orders/{order_ref2}/status", headers=staff_headers, json={"status": "Cancelled"})
    cancel_poll = client.get(f"/api/orders/{order_ref2}")
    assert cancel_poll.status_code == 200
    assert cancel_poll.get_json()["data"]["status"] == "Cancelled"

    print("[PASS] Order tracking API status progression and terminal states verified.")


def test_frontend_code_contract():
    client = app.test_client()

    # Verify student.js contains polling safeguards and progression stepper logic
    js_res = client.get("/static/js/student.js")
    assert js_res.status_code == 200
    js_code = js_res.get_data(as_text=True)

    assert "TRACKING_POLL_INTERVAL_MS = 5000" in js_code, "Polling interval must be 5000ms (5 seconds)"
    assert "startTrackingPolling" in js_code, "Missing startTrackingPolling function"
    assert "stopTrackingPolling" in js_code, "Missing stopTrackingPolling function"
    assert "isPollingInProgress" in js_code, "Must guard against overlapping requests"
    assert "ORDER_STATUS_STEPS" in js_code, "Missing status steps array"
    assert "Completed" in js_code and "Cancelled" in js_code

    # Verify style.css includes stepper styles
    css_res = client.get("/static/css/style.css")
    assert css_res.status_code == 200
    css_code = css_res.get_data(as_text=True)
    assert ".order-progress-bar" in css_code
    assert ".progress-step" in css_code
    assert ".auto-refresh-indicator" in css_code

    print("[PASS] Frontend JavaScript and CSS contract for 5s polling and progression stepper verified.")


class Milestone5ABrowserTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.port = 5066
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        cls.server_thread = ServerThread(app, port=cls.port)
        cls.server_thread.start()
        time.sleep(1)

        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--window-size=1280,900")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        cls.driver = webdriver.Chrome(options=options)
        cls.driver.implicitly_wait(5)
        cls.client = app.test_client()

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()
        cls.server_thread.shutdown()

    def test_automatic_polling_updates_ui_on_status_change(self):
        """End-to-End: Verifies browser polls every 5s and updates stepper from Pending -> Confirmed -> Preparing -> Ready -> Completed."""
        # 1. Create a test order
        res = self.client.post("/api/orders", json={
            "student_name": "Meera Joshi",
            "roll_number": "22BCE345",
            "section": "CSE-A",
            "items": [{"menu_item_id": 9, "quantity": 1}]
        })
        self.assertEqual(res.status_code, 201)
        order_ref = res.get_json()["data"]["order_ref"]

        # 2. Open Student Portal in browser and navigate to tracking tab
        self.driver.get(self.base_url)
        track_tab_btn = self.driver.find_element(By.ID, "tab-track-btn")
        track_tab_btn.click()

        # 3. Enter order reference and submit
        track_input = self.driver.find_element(By.ID, "track-ref-input")
        track_input.clear()
        track_input.send_keys(order_ref)
        self.driver.find_element(By.ID, "track-btn").click()

        # 4. Wait for initial tracking results (status: Pending)
        WebDriverWait(self.driver, 5).until(
            lambda d: d.find_element(By.ID, "track-result-container").is_displayed()
        )
        status_pill = self.driver.find_element(By.CSS_SELECTOR, "#track-result-container .status-pill")
        self.assertEqual(status_pill.text.strip().upper(), "PENDING")

        # Verify progression bar is rendered
        progress_bar = self.driver.find_element(By.CLASS_NAME, "order-progress-bar")
        self.assertTrue(progress_bar.is_displayed(), "Order progression bar should be displayed")

        # Verify live auto-refresh indicator
        indicator = self.driver.find_element(By.CLASS_NAME, "auto-refresh-indicator")
        self.assertIn("Auto-refreshing every 5s", indicator.text)

        # 5. Staff updates status to "Confirmed" in the background
        staff_headers = {"X-Staff-Pin": STAFF_PIN}
        self.client.patch(f"/api/staff/orders/{order_ref}/status", headers=staff_headers, json={"status": "Confirmed"})

        # Browser should automatically poll and update status without user interaction within ~6s
        WebDriverWait(self.driver, 8).until(
            lambda d: d.find_element(By.CSS_SELECTOR, "#track-result-container .status-pill").text.strip().upper() == "CONFIRMED"
        )
        # Verify stepper shows Confirmed as current/completed
        confirmed_step = self.driver.find_element(By.CSS_SELECTOR, ".progress-step.current .step-label")
        self.assertEqual(confirmed_step.text.strip().upper(), "CONFIRMED")

        # 6. Staff updates status to "Preparing"
        self.client.patch(f"/api/staff/orders/{order_ref}/status", headers=staff_headers, json={"status": "Preparing"})
        WebDriverWait(self.driver, 8).until(
            lambda d: d.find_element(By.CSS_SELECTOR, "#track-result-container .status-pill").text.strip().upper() == "PREPARING"
        )

        # 7. Staff updates status to "Ready for Pickup"
        self.client.patch(f"/api/staff/orders/{order_ref}/status", headers=staff_headers, json={"status": "Ready for Pickup"})
        WebDriverWait(self.driver, 8).until(
            lambda d: d.find_element(By.CSS_SELECTOR, "#track-result-container .status-pill").text.strip().upper() == "READY FOR PICKUP"
        )

        # 8. Staff completes order -> reaches terminal state
        self.client.patch(f"/api/staff/orders/{order_ref}/status", headers=staff_headers, json={"status": "Completed"})
        WebDriverWait(self.driver, 8).until(
            lambda d: d.find_element(By.CSS_SELECTOR, "#track-result-container .status-pill").text.strip().upper() == "COMPLETED"
        )

        # Polling stopped indicator should be displayed
        final_indicator = self.driver.find_element(By.CLASS_NAME, "auto-refresh-indicator")
        self.assertIn("stopped", final_indicator.text.lower())

        # 9. Verify switching tabs stops tracking
        order_tab_btn = self.driver.find_element(By.ID, "tab-order-btn")
        order_tab_btn.click()
        tracking_view = self.driver.find_element(By.ID, "tracking-view")
        self.assertFalse(tracking_view.is_displayed(), "Tracking view should be closed when switching tabs")


if __name__ == "__main__":
    print("\n=== Running Milestone 5A Verification Suite ===")
    test_order_status_progression_api_contract()
    test_frontend_code_contract()
    unittest.main()
