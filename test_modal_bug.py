"""
Bug Verification & Regression Test Suite
Tests for:
1. Confirmation modal does NOT show automatically on page load.
2. Confirmation modal buttons correctly close or track the order.
3. Order reference and total are populated from real API response, not placeholder SM-00000000 / Rs. 0.00.
4. "Order More Items" closes the modal.
5. "Track This Order Now" closes the modal, switches to tracking tab, and populates the tracking input.
6. "Copy Code" functions properly.
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
from app import app, init_db


class ServerThread(threading.Thread):
    def __init__(self, app_instance, host="127.0.0.1", port=5055):
        super().__init__()
        self.server = make_server(host, port, app_instance)
        self.ctx = app_instance.app_context()
        self.ctx.push()

    def run(self):
        self.server.serve_forever()

    def shutdown(self):
        self.server.shutdown()


class ModalBugTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.port = 5055
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        cls.server_thread = ServerThread(app, port=cls.port)
        cls.server_thread.start()
        time.sleep(1)  # Allow server to bind and start

        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--window-size=1280,900")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        cls.driver = webdriver.Chrome(options=options)
        cls.driver.implicitly_wait(5)

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()
        cls.server_thread.shutdown()

    def test_modal_hidden_on_initial_load(self):
        """Task 1: Verify confirmation modal is NOT displayed automatically on initial page load."""
        self.driver.get(self.base_url)
        WebDriverWait(self.driver, 5).until(
            EC.presence_of_element_located((By.ID, "order-modal-backdrop"))
        )

        modal = self.driver.find_element(By.ID, "order-modal-backdrop")
        computed_display = modal.value_of_css_property("display")

        self.assertEqual(
            computed_display, "none",
            f"Expected modal computed display to be 'none' on page load, but got '{computed_display}'."
        )
        self.assertFalse(
            modal.is_displayed(),
            "Modal should not be visible to the user on initial page load."
        )

    def test_full_order_flow_modal_population_and_buttons(self):
        """Tasks 2-5: Test placing order, populating real ref & total, copy code, close, and track buttons."""
        self.driver.get(self.base_url)

        # 1. Wait for menu to load
        WebDriverWait(self.driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-action='add-to-cart']"))
        )

        # 2. Add first item to cart
        add_btn = self.driver.find_element(By.CSS_SELECTOR, "[data-action='add-to-cart']")
        add_btn.click()

        # 3. Fill in student information
        name_input = self.driver.find_element(By.ID, "student-name")
        name_input.clear()
        name_input.send_keys("Pooja Sharma")

        roll_input = self.driver.find_element(By.ID, "roll-number")
        roll_input.clear()
        roll_input.send_keys("23BCE999")

        section_input = self.driver.find_element(By.ID, "section-name")
        section_input.clear()
        section_input.send_keys("CSE-C")

        # 4. Submit order
        place_order_btn = self.driver.find_element(By.ID, "place-order-btn")
        self.assertTrue(place_order_btn.is_enabled(), "Place order button should be enabled after adding items")
        place_order_btn.click()

        # 5. Wait for confirmation modal to become visible
        modal = self.driver.find_element(By.ID, "order-modal-backdrop")
        WebDriverWait(self.driver, 5).until(
            lambda d: modal.is_displayed()
        )

        ref_code_el = self.driver.find_element(By.ID, "confirmed-ref-code")
        WebDriverWait(self.driver, 5).until(
            lambda d: ref_code_el.text.strip().startswith("SM-")
        )

        # 6. Verify real API values are populated (not placeholder defaults)
        total_amount_el = self.driver.find_element(By.ID, "confirmed-total-amount")
        status_pill_el = self.driver.find_element(By.ID, "confirmed-status-pill")

        order_ref = ref_code_el.text.strip()
        total_text = total_amount_el.text.strip()
        status_text = status_pill_el.text.strip()

        self.assertTrue(
            order_ref.startswith("SM-"),
            f"Expected order reference to start with 'SM-', got '{order_ref}'"
        )
        self.assertNotEqual(
            order_ref, "SM-00000000",
            "Order reference should be the actual generated reference, not the placeholder SM-00000000."
        )
        self.assertNotEqual(
            total_text, "Rs. 0.00",
            "Total amount should be populated with the actual order total, not Rs. 0.00."
        )
        self.assertEqual(status_text.upper(), "PENDING")

        # 7. Test "Copy Code" button
        copy_btn = self.driver.find_element(By.ID, "copy-ref-btn")
        copy_btn.click()
        time.sleep(0.3)
        self.assertIn("Copied", copy_btn.text)

        # 8. Test "Order More Items" button closes the modal
        close_btn = WebDriverWait(self.driver, 5).until(
            EC.element_to_be_clickable((By.ID, "modal-close-btn"))
        )
        close_btn.click()
        WebDriverWait(self.driver, 5).until(
            lambda d: not modal.is_displayed()
        )
        self.assertFalse(modal.is_displayed(), "Modal should be closed after clicking 'Order More Items'.")

        # 9. Test "Track This Order Now" workflow
        # Re-open modal by placing another item or checking track button
        add_btn = self.driver.find_element(By.CSS_SELECTOR, "[data-action='add-to-cart']")
        add_btn.click()
        place_order_btn.click()
        WebDriverWait(self.driver, 5).until(
            lambda d: modal.is_displayed()
        )
        WebDriverWait(self.driver, 5).until(
            lambda d: ref_code_el.text.strip().startswith("SM-")
        )

        new_ref = ref_code_el.text.strip()
        track_btn = WebDriverWait(self.driver, 5).until(
            EC.element_to_be_clickable((By.ID, "modal-track-btn"))
        )
        track_btn.click()

        # Modal must close
        WebDriverWait(self.driver, 5).until(
            lambda d: not modal.is_displayed()
        )
        self.assertFalse(modal.is_displayed(), "Modal should be closed after clicking 'Track This Order Now'.")

        # Tracking view should be active and tracking input filled with new_ref
        tracking_view = self.driver.find_element(By.ID, "tracking-view")
        self.assertTrue(tracking_view.is_displayed(), "Tracking view should be visible after tracking order.")

        track_input = self.driver.find_element(By.ID, "track-ref-input")
        self.assertEqual(track_input.get_attribute("value").strip(), new_ref)

        # Track result container should be rendered
        WebDriverWait(self.driver, 5).until(
            lambda d: self.driver.find_element(By.ID, "track-result-container").is_displayed()
        )
        track_result = self.driver.find_element(By.ID, "track-result-container")
        self.assertIn(new_ref, track_result.text)


if __name__ == "__main__":
    unittest.main()
