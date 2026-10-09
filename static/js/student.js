/**
 * SmartMeal - Student Frontend Application Logic
 * Handles menu retrieval, cart state, client-side validation,
 * order submission to POST /api/orders, and order tracking via GET /api/orders/<ref>.
 */

document.addEventListener("DOMContentLoaded", () => {
    // -------------------------------------------------------------
    // Application State
    // -------------------------------------------------------------
    let menuCatalog = [];          // Fetched dynamically from GET /api/menu
    let activeCategory = "All";    // Current category filter
    let searchQuery = "";          // Current search filter
    const cart = new Map();        // Map of menu_item_id -> cartItem object

    // Milestone 5A Tracking Polling State
    let currentTrackedRef = null;
    let trackingPollTimer = null;
    let isPollingInProgress = false;
    const TRACKING_POLL_INTERVAL_MS = 5000;
    const ORDER_STATUS_STEPS = ["Pending", "Confirmed", "Preparing", "Ready for Pickup", "Completed"];

    // -------------------------------------------------------------
    // DOM Element References
    // -------------------------------------------------------------
    // Navigation Tabs & Views
    const tabOrderBtn = document.getElementById("tab-order-btn");
    const tabTrackBtn = document.getElementById("tab-track-btn");
    const orderingView = document.getElementById("ordering-view");
    const trackingView = document.getElementById("tracking-view");
    const cartCountBadge = document.getElementById("cart-count-badge");

    // Menu Elements
    const categoryFiltersContainer = document.getElementById("category-filters");
    const menuSearchInput = document.getElementById("menu-search-input");
    const menuGrid = document.getElementById("menu-grid");
    const menuStatus = document.getElementById("menu-status");

    // Order & Cart Form Elements
    const orderForm = document.getElementById("order-form");
    const studentNameInput = document.getElementById("student-name");
    const rollNumberInput = document.getElementById("roll-number");
    const sectionNameInput = document.getElementById("section-name");
    const cartItemsContainer = document.getElementById("cart-items-container");
    const clearCartBtn = document.getElementById("clear-cart-btn");
    const summaryItemsCount = document.getElementById("summary-items-count");
    const summaryEstimatedTotal = document.getElementById("summary-estimated-total");
    const orderFormStatus = document.getElementById("order-form-status");
    const placeOrderBtn = document.getElementById("place-order-btn");
    const placeOrderBtnText = document.getElementById("place-order-btn-text");
    const placeOrderSpinner = document.getElementById("place-order-spinner");

    // Order Tracking Elements
    const trackOrderForm = document.getElementById("track-order-form");
    const trackRefInput = document.getElementById("track-ref-input");
    const trackBtn = document.getElementById("track-btn");
    const trackBtnText = document.getElementById("track-btn-text");
    const trackSpinner = document.getElementById("track-spinner");
    const trackStatusAlert = document.getElementById("track-status-alert");
    const trackResultContainer = document.getElementById("track-result-container");

    // Confirmation Modal Elements
    const orderModalBackdrop = document.getElementById("order-modal-backdrop");
    const confirmedRefCode = document.getElementById("confirmed-ref-code");
    const confirmedStatusPill = document.getElementById("confirmed-status-pill");
    const confirmedTotalAmount = document.getElementById("confirmed-total-amount");
    const copyRefBtn = document.getElementById("copy-ref-btn");
    const modalTrackBtn = document.getElementById("modal-track-btn");
    const modalCloseBtn = document.getElementById("modal-close-btn");

    // -------------------------------------------------------------
    // Utility Helpers
    // -------------------------------------------------------------
    function sanitize(str) {
        if (!str) return "";
        const div = document.createElement("div");
        div.textContent = str;
        return div.innerHTML;
    }

    function formatCurrency(amount) {
        return `Rs. ${Number(amount).toFixed(2)}`;
    }

    function showAlert(element, message, type = "error") {
        element.textContent = message;
        element.className = `alert-banner ${type}`;
        element.hidden = false;
    }

    function hideAlert(element) {
        element.textContent = "";
        element.className = "alert-banner";
        element.hidden = true;
    }

    function getCategoryEmoji(category) {
        switch ((category || "").toLowerCase()) {
            case "breakfast": return "🥞";
            case "lunch": return "🍛";
            case "snacks": return "🥪";
            case "beverages": return "☕";
            default: return "🍲";
        }
    }

    function getStatusClass(status) {
        switch ((status || "").toLowerCase()) {
            case "pending": return "status-pending";
            case "confirmed": return "status-confirmed";
            case "preparing": return "status-preparing";
            case "ready for pickup": return "status-ready";
            case "completed": return "status-completed";
            case "cancelled": return "status-cancelled";
            default: return "status-pending";
        }
    }

    // -------------------------------------------------------------
    // Navigation Tab Switching
    // -------------------------------------------------------------
    function switchTab(viewName) {
        if (viewName === "track") {
            orderingView.classList.remove("active");
            orderingView.hidden = true;
            trackingView.classList.add("active");
            trackingView.hidden = false;
            tabTrackBtn.classList.add("active");
            tabOrderBtn.classList.remove("active");
            tabTrackBtn.setAttribute("aria-selected", "true");
            tabOrderBtn.setAttribute("aria-selected", "false");

            // Resume polling if an active order is currently on screen
            if (currentTrackedRef && !trackResultContainer.hidden) {
                startTrackingPolling(currentTrackedRef);
            }
        } else {
            trackingView.classList.remove("active");
            trackingView.hidden = true;
            orderingView.classList.add("active");
            orderingView.hidden = false;
            tabOrderBtn.classList.add("active");
            tabTrackBtn.classList.remove("active");
            tabOrderBtn.setAttribute("aria-selected", "true");
            tabTrackBtn.setAttribute("aria-selected", "false");

            // Stop automatic polling when tracking view is closed
            stopTrackingPolling();
        }
    }

    tabOrderBtn.addEventListener("click", () => switchTab("order"));
    tabTrackBtn.addEventListener("click", () => switchTab("track"));

    // -------------------------------------------------------------
    // 1. Menu Catalog Fetching & Rendering (GET /api/menu)
    // -------------------------------------------------------------
    async function loadMenu() {
        hideAlert(menuStatus);
        menuGrid.innerHTML = `
            <div class="loading-state">
                <div class="spinner"></div>
                <p>Loading fresh canteen menu...</p>
            </div>
        `;

        try {
            const response = await fetch("/api/menu", {
                method: "GET",
                headers: { "Accept": "application/json" }
            });

            const result = await response.json();

            if (!response.ok) {
                showAlert(menuStatus, result.message || "Failed to load canteen menu.", "error");
                menuGrid.innerHTML = "";
                return;
            }

            menuCatalog = result.data || [];
            renderMenuGrid();
        } catch (err) {
            console.error("Error loading menu:", err);
            showAlert(menuStatus, "Unable to connect to canteen server. Please check your network or try refreshing.", "error");
            menuGrid.innerHTML = `
                <div class="loading-state">
                    <p>Failed to load menu items.</p>
                    <button type="button" class="btn btn-secondary btn-sm" onclick="location.reload()">Retry</button>
                </div>
            `;
        }
    }

    function renderMenuGrid() {
        // Filter catalog based on active category and search term
        const filtered = menuCatalog.filter(item => {
            const matchesCat = activeCategory === "All" || item.category === activeCategory;
            const matchesSearch = !searchQuery || item.name.toLowerCase().includes(searchQuery.toLowerCase());
            return matchesCat && matchesSearch;
        });

        if (filtered.length === 0) {
            menuGrid.innerHTML = `
                <div class="loading-state">
                    <p>No dishes match your selected filter or search.</p>
                </div>
            `;
            return;
        }

        menuGrid.innerHTML = filtered.map(item => {
            const isInCart = cart.has(item.id);
            const emoji = getCategoryEmoji(item.category);
            const safeName = sanitize(item.name);
            const safeCategory = sanitize(item.category);
            const prefsCount = (item.allowed_preferences || []).length;
            const prefsNotice = prefsCount > 0 ? `${prefsCount} customizable option${prefsCount > 1 ? 's' : ''}` : "Standard prep";

            return `
                <article class="menu-card" data-item-id="${item.id}">
                    <div>
                        <div class="menu-card-header">
                            <h3 class="menu-card-title">${emoji} ${safeName}</h3>
                            <span class="category-tag">${safeCategory}</span>
                        </div>
                        <div class="menu-card-meta">
                            <span>Max portion: ${item.max_portion_limit}</span> &bull; 
                            <span>${prefsNotice}</span>
                        </div>
                    </div>
                    <div class="menu-card-footer">
                        <span class="menu-card-price">${formatCurrency(item.price)}</span>
                        <button 
                            type="button" 
                            class="btn-add ${isInCart ? 'in-cart' : ''}" 
                            data-action="add-to-cart" 
                            data-id="${item.id}"
                        >
                            ${isInCart ? '✓ Added' : '+ Add'}
                        </button>
                    </div>
                </article>
            `;
        }).join("");
    }

    // Category Filter Clicks
    categoryFiltersContainer.addEventListener("click", (e) => {
        const pill = e.target.closest(".filter-pill");
        if (!pill) return;

        categoryFiltersContainer.querySelectorAll(".filter-pill").forEach(p => p.classList.remove("active"));
        pill.classList.add("active");
        activeCategory = pill.dataset.category;
        renderMenuGrid();
    });

    // Real-Time Search Input
    menuSearchInput.addEventListener("input", (e) => {
        searchQuery = e.target.value.trim();
        renderMenuGrid();
    });

    // Delegated Add-To-Cart from Menu Cards
    menuGrid.addEventListener("click", (e) => {
        const addBtn = e.target.closest("[data-action='add-to-cart']");
        if (!addBtn) return;

        const itemId = parseInt(addBtn.dataset.id, 10);
        const item = menuCatalog.find(m => m.id === itemId);
        if (!item) return;

        if (!cart.has(itemId)) {
            // Add initial entry
            const defaultPref = (item.allowed_preferences && item.allowed_preferences.length > 0)
                ? item.allowed_preferences[0]
                : "Standard";

            cart.set(itemId, {
                item: item,
                quantity: 1,
                cooking_preference: defaultPref,
                special_request: ""
            });
        } else {
            // If already in cart, increment quantity if within portion limit
            const current = cart.get(itemId);
            if (current.quantity < item.max_portion_limit) {
                current.quantity += 1;
            } else {
                showAlert(orderFormStatus, `Limit of ${item.max_portion_limit} portions reached for ${item.name}.`, "info");
            }
        }

        updateCartUI();
        renderMenuGrid();
    });

    // -------------------------------------------------------------
    // 2. Cart Management & Live Estimation
    // -------------------------------------------------------------
    function updateCartUI() {
        const items = Array.from(cart.values());
        cartCountBadge.textContent = items.reduce((acc, c) => acc + c.quantity, 0);

        if (items.length === 0) {
            cartItemsContainer.innerHTML = `
                <div class="empty-cart-state">
                    <span class="empty-cart-icon">🍽️</span>
                    <p>Your cart is empty.</p>
                    <small>Pick items from the menu on the left to start your order.</small>
                </div>
            `;
            summaryItemsCount.textContent = "0";
            summaryEstimatedTotal.textContent = "Rs. 0.00";
            placeOrderBtn.disabled = true;
            return;
        }

        // Render Cart Item Rows
        cartItemsContainer.innerHTML = items.map(({ item, quantity, cooking_preference, special_request }) => {
            const safeName = sanitize(item.name);
            const allowedPrefs = item.allowed_preferences || [];

            // Preferences dropdown options
            const prefOptionsHtml = allowedPrefs.length > 0
                ? allowedPrefs.map(pref => {
                    const selected = pref === cooking_preference ? "selected" : "";
                    return `<option value="${sanitize(pref)}" ${selected}>${sanitize(pref)}</option>`;
                }).join("")
                : `<option value="Standard" selected>Standard Prep</option>`;

            return `
                <div class="cart-item-row" data-id="${item.id}">
                    <div class="cart-item-top">
                        <span class="cart-item-title">${safeName}</span>
                        <div style="display:flex; align-items:center; gap:0.5rem;">
                            <span class="cart-item-price">${formatCurrency(item.price * quantity)}</span>
                            <button type="button" class="btn-remove-item" data-action="remove" data-id="${item.id}" title="Remove item">&times;</button>
                        </div>
                    </div>

                    <div class="cart-item-controls">
                        <small style="color:var(--text-muted);">Max: ${item.max_portion_limit}</small>
                        <div class="quantity-stepper">
                            <button type="button" class="stepper-btn" data-action="decrease" data-id="${item.id}">-</button>
                            <span class="stepper-val">${quantity}</span>
                            <button type="button" class="stepper-btn" data-action="increase" data-id="${item.id}">+</button>
                        </div>
                    </div>

                    <div class="cart-customization-row">
                        <select data-action="set-preference" data-id="${item.id}" aria-label="Cooking Preference for ${safeName}">
                            ${prefOptionsHtml}
                        </select>
                        <input 
                            type="text" 
                            data-action="set-special-request" 
                            data-id="${item.id}" 
                            placeholder="Special note (e.g. less spicy)..." 
                            maxlength="200" 
                            value="${sanitize(special_request)}"
                            aria-label="Special request for ${safeName}"
                        >
                    </div>
                </div>
            `;
        }).join("");

        // Compute Live Estimated Total
        const totalPortions = items.reduce((acc, c) => acc + c.quantity, 0);
        const estimatedTotal = items.reduce((acc, c) => acc + (c.item.price * c.quantity), 0);

        summaryItemsCount.textContent = totalPortions;
        summaryEstimatedTotal.textContent = formatCurrency(estimatedTotal);
        placeOrderBtn.disabled = false;
    }

    // Delegated Cart Interactions (stepper, remove, preferences)
    cartItemsContainer.addEventListener("click", (e) => {
        const actionBtn = e.target.closest("[data-action]");
        if (!actionBtn) return;

        const action = actionBtn.dataset.action;
        const itemId = parseInt(actionBtn.dataset.id, 10);
        const entry = cart.get(itemId);
        if (!entry) return;

        if (action === "increase") {
            if (entry.quantity < entry.item.max_portion_limit) {
                entry.quantity += 1;
                updateCartUI();
            } else {
                showAlert(orderFormStatus, `Limit of ${entry.item.max_portion_limit} reached for ${entry.item.name}.`, "info");
            }
        } else if (action === "decrease") {
            if (entry.quantity > 1) {
                entry.quantity -= 1;
                updateCartUI();
            } else {
                cart.delete(itemId);
                updateCartUI();
                renderMenuGrid();
            }
        } else if (action === "remove") {
            cart.delete(itemId);
            updateCartUI();
            renderMenuGrid();
        }
    });

    // Customization inputs change
    cartItemsContainer.addEventListener("change", (e) => {
        const target = e.target;
        const itemId = parseInt(target.dataset.id, 10);
        const entry = cart.get(itemId);
        if (!entry) return;

        if (target.dataset.action === "set-preference") {
            entry.cooking_preference = target.value;
        }
    });

    cartItemsContainer.addEventListener("input", (e) => {
        const target = e.target;
        const itemId = parseInt(target.dataset.id, 10);
        const entry = cart.get(itemId);
        if (!entry) return;

        if (target.dataset.action === "set-special-request") {
            entry.special_request = target.value;
        }
    });

    // Clear Cart Button
    clearCartBtn.addEventListener("click", () => {
        cart.clear();
        hideAlert(orderFormStatus);
        updateCartUI();
        renderMenuGrid();
    });

    // -------------------------------------------------------------
    // 3. Order Submission (POST /api/orders)
    // -------------------------------------------------------------
    orderForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        hideAlert(orderFormStatus);

        const studentName = studentNameInput.value.trim();
        const rollNumber = rollNumberInput.value.trim();
        const sectionName = sectionNameInput.value.trim();

        // 1. Client-side input validation
        if (!studentName) {
            showAlert(orderFormStatus, "Please enter your full name.");
            studentNameInput.focus();
            return;
        }

        if (!rollNumber) {
            showAlert(orderFormStatus, "Please enter your student roll number.");
            rollNumberInput.focus();
            return;
        }

        if (!sectionName) {
            showAlert(orderFormStatus, "Please enter your section/class.");
            sectionNameInput.focus();
            return;
        }

        if (cart.size === 0) {
            showAlert(orderFormStatus, "Please select at least one dish from the menu.");
            return;
        }

        // 2. Prepare payload conforming to API contract
        const itemsPayload = Array.from(cart.values()).map(({ item, quantity, cooking_preference, special_request }) => ({
            menu_item_id: item.id,
            quantity: quantity,
            cooking_preference: cooking_preference || "Standard",
            special_request: (special_request || "").trim()
        }));

        const orderPayload = {
            student_name: studentName,
            roll_number: rollNumber,
            section: sectionName,
            items: itemsPayload
        };

        // 3. UI Loading State
        placeOrderBtn.disabled = true;
        placeOrderBtnText.textContent = "Placing Order...";
        placeOrderSpinner.hidden = false;

        try {
            const response = await fetch("/api/orders", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                },
                body: JSON.stringify(orderPayload)
            });

            const result = await response.json();

            if (!response.ok) {
                showAlert(orderFormStatus, result.message || "Failed to place order. Please review your selections.");
                return;
            }

            // Success: Display confirmation modal with reference code
            const orderData = result.data || {};
            confirmedRefCode.textContent = orderData.order_ref || "SM-XXXXXXXX";
            confirmedTotalAmount.textContent = formatCurrency(orderData.total_price);
            confirmedStatusPill.textContent = orderData.status || "Pending";
            confirmedStatusPill.className = `status-pill ${getStatusClass(orderData.status)}`;

            orderModalBackdrop.hidden = false;

            // Clear Cart and form
            cart.clear();
            updateCartUI();
            renderMenuGrid();

        } catch (err) {
            console.error("Order submission error:", err);
            showAlert(orderFormStatus, "Network error: Unable to connect to canteen server. Please try again.");
        } finally {
            placeOrderBtn.disabled = cart.size === 0;
            placeOrderBtnText.textContent = "Confirm & Place Order";
            placeOrderSpinner.hidden = true;
        }
    });

    // Utility: Copy text to clipboard with fallback
    function copyTextToClipboard(text, onSuccess, onError) {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text).then(onSuccess).catch(() => {
                fallbackCopy(text, onSuccess, onError);
            });
        } else {
            fallbackCopy(text, onSuccess, onError);
        }
    }

    function fallbackCopy(text, onSuccess, onError) {
        try {
            const textarea = document.createElement("textarea");
            textarea.value = text;
            textarea.setAttribute("readonly", "");
            textarea.style.position = "absolute";
            textarea.style.left = "-9999px";
            document.body.appendChild(textarea);
            textarea.select();
            const successful = document.execCommand("copy");
            document.body.removeChild(textarea);
            if (successful) {
                if (onSuccess) onSuccess();
            } else {
                if (onError) onError();
            }
        } catch (err) {
            if (onError) onError();
        }
    }

    // Copy Order Reference Code
    copyRefBtn.addEventListener("click", () => {
        const code = confirmedRefCode.textContent.trim();
        copyTextToClipboard(
            code,
            () => {
                copyRefBtn.textContent = "✓ Copied!";
                setTimeout(() => { copyRefBtn.textContent = "📋 Copy Code"; }, 2000);
            },
            () => {
                copyRefBtn.textContent = code;
            }
        );
    });

    // Close Modal Button ("Order More Items")
    modalCloseBtn.addEventListener("click", () => {
        orderModalBackdrop.hidden = true;
    });

    // Modal "Track This Order Now" Button
    modalTrackBtn.addEventListener("click", () => {
        const code = confirmedRefCode.textContent.trim();
        orderModalBackdrop.hidden = true;
        trackRefInput.value = code;
        switchTab("track");
        fetchOrderStatus(code);
    });

    // Close modal when clicking outside of modal card (backdrop click)
    orderModalBackdrop.addEventListener("click", (e) => {
        if (e.target === orderModalBackdrop) {
            orderModalBackdrop.hidden = true;
        }
    });

    // Close modal on Escape key press
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && !orderModalBackdrop.hidden) {
            orderModalBackdrop.hidden = true;
        }
    });

    // -------------------------------------------------------------
    // 4. Order Status Tracking (GET /api/orders/<order_ref>)
    // -------------------------------------------------------------
    trackOrderForm.addEventListener("submit", (e) => {
        e.preventDefault();
        const ref = trackRefInput.value.trim().toUpperCase();
        if (!ref) {
            showAlert(trackStatusAlert, "Please enter an order reference code.");
            trackRefInput.focus();
            return;
        }
        fetchOrderStatus(ref, false);
    });

    function startTrackingPolling(ref) {
        stopTrackingPolling();
        currentTrackedRef = ref;
        trackingPollTimer = setInterval(() => {
            // Stop if tracking view was hidden or ref was cleared
            if (trackingView.hidden || !currentTrackedRef) {
                stopTrackingPolling();
                return;
            }
            fetchOrderStatus(currentTrackedRef, true);
        }, TRACKING_POLL_INTERVAL_MS);
    }

    function stopTrackingPolling() {
        if (trackingPollTimer) {
            clearInterval(trackingPollTimer);
            trackingPollTimer = null;
        }
    }

    async function fetchOrderStatus(orderRef, isAutoRefresh = false) {
        // Prevent overlapping requests
        if (isPollingInProgress) return;
        isPollingInProgress = true;

        if (!isAutoRefresh) {
            hideAlert(trackStatusAlert);
            trackResultContainer.hidden = true;
            trackBtn.disabled = true;
            trackBtnText.textContent = "Checking...";
            trackSpinner.hidden = false;
        }

        try {
            const response = await fetch(`/api/orders/${encodeURIComponent(orderRef)}`, {
                method: "GET",
                headers: { "Accept": "application/json" }
            });

            const result = await response.json();

            if (!response.ok) {
                if (!isAutoRefresh) {
                    showAlert(trackStatusAlert, result.message || `No order found with reference '${orderRef}'.`, "error");
                    stopTrackingPolling();
                    currentTrackedRef = null;
                }
                return;
            }

            const data = result.data;
            currentTrackedRef = data.order_ref;
            renderTrackResult(data);

            // Stop polling when reaching terminal statuses (Completed or Cancelled)
            if (data.status === "Completed" || data.status === "Cancelled") {
                stopTrackingPolling();
            } else {
                // Ensure polling continues every 5s while tracking is open
                if (!trackingView.hidden && !trackingPollTimer) {
                    startTrackingPolling(data.order_ref);
                }
            }
        } catch (err) {
            console.error("Tracking error:", err);
            if (!isAutoRefresh) {
                showAlert(trackStatusAlert, "Network error: Unable to reach canteen server.", "error");
                stopTrackingPolling();
                currentTrackedRef = null;
            } else {
                // Background poll failed gracefully without breaking visible view
                const timeEl = document.getElementById("last-updated-timestamp");
                if (timeEl) {
                    timeEl.textContent = "Connection issue, retrying in 5s...";
                    timeEl.style.color = "#ef4444";
                }
            }
        } finally {
            isPollingInProgress = false;
            if (!isAutoRefresh) {
                trackBtn.disabled = false;
                trackBtnText.textContent = "Check Status";
                trackSpinner.hidden = true;
            }
        }
    }

    function renderTrackResult(data) {
        const safeRef = sanitize(data.order_ref);
        const safeStatus = sanitize(data.status);
        const statusClass = getStatusClass(data.status);
        const formattedDate = new Date(data.created_at ? data.created_at.replace(" ", "T") + "Z" : Date.now())
            .toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });

        const isTerminal = data.status === "Completed" || data.status === "Cancelled";
        const isCancelled = data.status === "Cancelled";

        // Step progression visualization
        let progressionHtml = "";
        if (isCancelled) {
            progressionHtml = `
                <div class="cancelled-order-banner">
                    <span style="font-size:1.3rem;">🛑</span>
                    <div>
                        <strong>Order Cancelled</strong>
                        <div style="font-size:0.8rem; font-weight:400; opacity:0.9;">
                            This order was cancelled by canteen staff or student. Automatic updates stopped.
                        </div>
                    </div>
                </div>
            `;
        } else {
            const stepIcons = {
                "Pending": "📝",
                "Confirmed": "👍",
                "Preparing": "🍳",
                "Ready for Pickup": "🔔",
                "Completed": "🎉"
            };

            const currentIdx = ORDER_STATUS_STEPS.indexOf(data.status);
            const activeIdx = currentIdx >= 0 ? currentIdx : 0;
            const fillPercent = Math.max(0, Math.min(100, (activeIdx / (ORDER_STATUS_STEPS.length - 1)) * 100));

            const stepsHtml = ORDER_STATUS_STEPS.map((step, idx) => {
                let stateClass = "upcoming";
                let bubbleContent = stepIcons[step] || (idx + 1);

                if (idx < activeIdx) {
                    stateClass = "completed";
                    bubbleContent = "✓";
                } else if (idx === activeIdx) {
                    stateClass = "current";
                    if (step === "Completed") bubbleContent = "🎉";
                }

                return `
                    <div class="progress-step ${stateClass}">
                        <div class="step-bubble">${bubbleContent}</div>
                        <span class="step-label">${step}</span>
                    </div>
                `;
            }).join("");

            progressionHtml = `
                <div class="order-progress-bar" aria-label="Order Status Progression">
                    <div class="progress-steps-wrapper">
                        <div class="progress-connector">
                            <div class="progress-connector-fill" style="width: ${fillPercent}%;"></div>
                        </div>
                        <div class="progress-steps">
                            ${stepsHtml}
                        </div>
                    </div>
                    <div class="auto-refresh-indicator">
                        <span>
                            ${isTerminal 
                                ? '🎉 <strong>Order Completed & Collected!</strong> Automatic polling stopped.' 
                                : '<span class="refresh-pulse"></span>Live Status: Auto-refreshing every 5s'}
                        </span>
                        <span id="last-updated-timestamp">Updated: ${new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</span>
                    </div>
                </div>
            `;
        }

        const itemsRowsHtml = (data.items || []).map(item => {
            const safeItemName = sanitize(item.item_name);
            const safePref = item.cooking_preference ? `Pref: ${sanitize(item.cooking_preference)}` : "";
            const safeReq = item.special_request ? ` &bull; Note: ${sanitize(item.special_request)}` : "";

            return `
                <tr>
                    <td>
                        <strong>${safeItemName}</strong>
                        ${(safePref || safeReq) ? `<span class="track-item-pref">${safePref}${safeReq}</span>` : ""}
                    </td>
                    <td>${item.quantity}</td>
                    <td>${formatCurrency(item.unit_price)}</td>
                    <td><strong>${formatCurrency(item.line_total)}</strong></td>
                </tr>
            `;
        }).join("");

        trackResultContainer.innerHTML = `
            <div class="track-result-header">
                <div>
                    <span style="font-size:0.75rem; color:var(--text-muted); text-transform:uppercase; font-weight:700;">Order Reference</span>
                    <h3 class="track-ref-title">${safeRef}</h3>
                </div>
                <span class="status-pill ${statusClass}">${safeStatus}</span>
            </div>

            <!-- Progression Stepper (Pending -> Confirmed -> Preparing -> Ready for Pickup -> Completed) -->
            ${progressionHtml}

            <div class="track-result-meta">
                <span>Placed on: ${formattedDate}</span>
                <span>Items: ${data.items ? data.items.length : 0}</span>
            </div>

            <table class="track-items-table">
                <thead>
                    <tr>
                        <th>Dish</th>
                        <th>Qty</th>
                        <th>Unit Price</th>
                        <th>Total</th>
                    </tr>
                </thead>
                <tbody>
                    ${itemsRowsHtml}
                </tbody>
            </table>

            <div class="track-total-box">
                <span>Verified Order Total</span>
                <span>${formatCurrency(data.total_price)}</span>
            </div>
        `;

        trackResultContainer.hidden = false;
    }

    // -------------------------------------------------------------
    // Initial Load
    // -------------------------------------------------------------
    loadMenu();
});
