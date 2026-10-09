/**
 * SmartMeal - Client-Side Application Logic
 * Handles food submission, API communication, and dynamic list rendering.
 */

document.addEventListener("DOMContentLoaded", () => {
    // DOM Element References
    const foodForm = document.getElementById("add-food-form");
    const foodNameInput = document.getElementById("food-name");
    const quantityInput = document.getElementById("quantity");
    const locationInput = document.getElementById("location");
    const submitBtn = document.getElementById("submit-btn");
    const btnText = document.getElementById("btn-text");
    const btnSpinner = document.getElementById("btn-spinner");
    const formStatus = document.getElementById("form-status");

    const foodListContainer = document.getElementById("food-list");
    const refreshBtn = document.getElementById("refresh-btn");
    const feedStatus = document.getElementById("feed-status");

    /**
     * Escapes untrusted text to prevent Cross-Site Scripting (XSS).
     * @param {string} str - Raw input text.
     * @returns {string} - Escaped safe HTML string.
     */
    function sanitize(str) {
        if (!str) return "";
        const div = document.createElement("div");
        div.textContent = str;
        return div.innerHTML;
    }

    /**
     * Shows a status message banner (success or error).
     * @param {HTMLElement} bannerElement - The banner element to show.
     * @param {string} message - Text message to display.
     * @param {string} type - 'success' or 'error'.
     */
    function showBanner(bannerElement, message, type) {
        bannerElement.textContent = message;
        bannerElement.className = `status-banner ${type}`;
        bannerElement.hidden = false;
    }

    /**
     * Hides a status message banner.
     * @param {HTMLElement} bannerElement - The banner element to hide.
     */
    function hideBanner(bannerElement) {
        bannerElement.textContent = "";
        bannerElement.className = "status-banner";
        bannerElement.hidden = true;
    }

    /**
     * Formats an ISO or SQLite timestamp into a user-friendly local date/time string.
     * @param {string} dateString - SQLite timestamp string.
     * @returns {string} - Human-readable time.
     */
    function formatDateTime(dateString) {
        if (!dateString) return "Just now";
        // SQLite CURRENT_TIMESTAMP is in UTC "YYYY-MM-DD HH:MM:SS"
        const utcDate = new Date(dateString.replace(" ", "T") + "Z");
        if (isNaN(utcDate.getTime())) {
            return dateString;
        }
        return utcDate.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) +
               ", " + utcDate.toLocaleDateString([], { month: "short", day: "numeric" });
    }

    /**
     * Fetches all available food items from GET /api/food and renders them.
     */
    async function loadFoodItems() {
        hideBanner(feedStatus);
        foodListContainer.innerHTML = `
            <div class="empty-state">
                <p class="empty-state-text">Loading available food...</p>
            </div>
        `;

        try {
            const response = await fetch("/api/food", {
                method: "GET",
                headers: {
                    "Accept": "application/json"
                }
            });

            const result = await response.json();

            if (!response.ok) {
                const errorMsg = result.message || "Failed to load food items from server.";
                showBanner(feedStatus, errorMsg, "error");
                foodListContainer.innerHTML = "";
                return;
            }

            const items = result.data || [];
            renderFoodList(items);
        } catch (error) {
            console.error("Error fetching food items:", error);
            showBanner(
                feedStatus,
                "Unable to connect to the server. Please check your internet or server connection.",
                "error"
            );
            foodListContainer.innerHTML = "";
        }
    }

    /**
     * Renders an array of food item objects into the list container.
     * @param {Array} items - List of food records.
     */
    function renderFoodList(items) {
        if (!items || items.length === 0) {
            foodListContainer.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon" aria-hidden="true">🍽️</div>
                    <p class="empty-state-text">No surplus food listed right now.<br>Check back later or share extra food from the form!</p>
                </div>
            `;
            return;
        }

        // Build HTML for each food card
        const cardsHtml = items.map(item => {
            const safeName = sanitize(item.food_name);
            const safeQuantity = sanitize(item.quantity);
            const safeLocation = sanitize(item.location);
            const safeTime = sanitize(formatDateTime(item.created_at));

            return `
                <article class="food-item-card">
                    <div class="food-item-header">
                        <h3 class="food-item-name">${safeName}</h3>
                        <span class="quantity-badge">${safeQuantity}</span>
                    </div>
                    <div class="food-item-location">
                        <span aria-hidden="true">📍</span>
                        <span>${safeLocation}</span>
                    </div>
                    <div class="food-item-timestamp">
                        <span>Posted: ${safeTime}</span>
                    </div>
                </article>
            `;
        }).join("");

        foodListContainer.innerHTML = cardsHtml;
    }

    /**
     * Handles the surplus food form submission.
     * @param {Event} e - Form submit event.
     */
    async function handleFoodSubmit(e) {
        e.preventDefault();
        hideBanner(formStatus);

        const foodName = foodNameInput.value.trim();
        const quantity = quantityInput.value.trim();
        const location = locationInput.value.trim();

        // Client-side quick validation for instant feedback
        if (!foodName) {
            showBanner(formStatus, "Please enter a food name.", "error");
            foodNameInput.focus();
            return;
        }

        if (!quantity) {
            showBanner(formStatus, "Please enter the quantity (e.g., 3 plates).", "error");
            quantityInput.focus();
            return;
        }

        if (!location) {
            showBanner(formStatus, "Please enter the pickup location (e.g., Room 204).", "error");
            locationInput.focus();
            return;
        }

        // Set button loading state
        submitBtn.disabled = true;
        btnText.textContent = "Posting...";
        btnSpinner.hidden = false;

        try {
            const response = await fetch("/api/food", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                },
                body: JSON.stringify({
                    food_name: foodName,
                    quantity: quantity,
                    location: location
                })
            });

            const result = await response.json();

            if (!response.ok) {
                // Server validation or operational error
                const errorMsg = result.message || "Failed to post food item. Please check your inputs.";
                showBanner(formStatus, errorMsg, "error");
            } else {
                // Success: show message, reset inputs, and refresh the food list
                showBanner(formStatus, "Surplus food shared successfully! Thank you for reducing waste.", "success");
                foodForm.reset();
                loadFoodItems();
            }
        } catch (error) {
            console.error("Error submitting food:", error);
            showBanner(
                formStatus,
                "Network error: Unable to reach the server. Please try again.",
                "error"
            );
        } finally {
            // Restore button state
            submitBtn.disabled = false;
            btnText.textContent = "Share Food Now";
            btnSpinner.hidden = true;
        }
    }

    // Event Listeners
    foodForm.addEventListener("submit", handleFoodSubmit);
    refreshBtn.addEventListener("click", () => {
        loadFoodItems();
    });

    // Initial load when page opens
    loadFoodItems();
});
