/**
 * SmartMeal - Staff Portal Frontend Logic (Milestone 4)
 * Handles staff PIN authentication, orders management, lifecycle transitions,
 * kitchen preparation summaries, and menu stock availability toggling.
 */

document.addEventListener("DOMContentLoaded", () => {
    // -------------------------------------------------------------
    // Application State
    // -------------------------------------------------------------
    let isAuthenticated = false;
    let activeTab = "orders";
    let ordersList = [];
    let activeStatusFilter = "All";
    let searchQuery = "";
    let prepSummaryList = [];
    let menuCatalog = [];

    // -------------------------------------------------------------
    // DOM Element References
    // -------------------------------------------------------------
    // Auth Views & Form
    const staffAuthView = document.getElementById("staff-auth-view");
    const staffPortalView = document.getElementById("staff-portal-view");
    const staffLoginForm = document.getElementById("staff-login-form");
    const staffPinInput = document.getElementById("staff-pin-input");
    const staffLoginAlert = document.getElementById("staff-login-alert");
    const staffLoginBtn = document.getElementById("staff-login-btn");
    const staffLoginBtnText = document.getElementById("staff-login-btn-text");
    const staffLoginSpinner = document.getElementById("staff-login-spinner");
    const staffLogoutBtn = document.getElementById("staff-logout-btn");

    // Portal Navigation & Controls
    const activeOrdersCountBadge = document.getElementById("active-orders-count-badge");
    const staffRefreshBtn = document.getElementById("staff-refresh-btn");
    const staffActionAlert = document.getElementById("staff-action-alert");

    // Milestone 5B: Statistics Cards
    const statTotalOrders = document.getElementById("stat-total-orders");
    const statPendingOrders = document.getElementById("stat-pending-orders");
    const statCompletedOrders = document.getElementById("stat-completed-orders");
    const statTodaySales = document.getElementById("stat-today-sales");
    const statServerDate = document.getElementById("stat-server-date");
    const statSalesDisclaimer = document.getElementById("stat-sales-disclaimer");

    // Tabs
    const tabBtnOrders = document.getElementById("tab-btn-orders");
    const tabBtnPrep = document.getElementById("tab-btn-prep");
    const tabBtnMenu = document.getElementById("tab-btn-menu");
    const sectionOrders = document.getElementById("section-orders");
    const sectionPrep = document.getElementById("section-prep");
    const sectionMenu = document.getElementById("section-menu");
    const tabOrdersCount = document.getElementById("tab-orders-count");
    const tabPrepCount = document.getElementById("tab-prep-count");

    // Orders Panel
    const staffStatusFilters = document.getElementById("staff-status-filters");
    const staffSearchInput = document.getElementById("staff-search-input");
    const staffOrdersGrid = document.getElementById("staff-orders-grid");

    // Prep Panel
    const staffPrepGrid = document.getElementById("staff-prep-grid");

    // Menu Panel
    const staffMenuTbody = document.getElementById("staff-menu-tbody");

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

    function formatDate(dateStr) {
        if (!dateStr) return "Just now";
        try {
            const d = new Date(dateStr.replace(" ", "T") + "Z");
            return d.toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
        } catch {
            return dateStr;
        }
    }

    // -------------------------------------------------------------
    // Tab Switching
    // -------------------------------------------------------------
    function switchTab(tabName) {
        activeTab = tabName;
        const tabs = [
            { name: "orders", btn: tabBtnOrders, section: sectionOrders },
            { name: "prep", btn: tabBtnPrep, section: sectionPrep },
            { name: "menu", btn: tabBtnMenu, section: sectionMenu }
        ];

        tabs.forEach(t => {
            if (t.name === tabName) {
                t.btn.classList.add("active");
                t.btn.setAttribute("aria-selected", "true");
                t.section.hidden = false;
            } else {
                t.btn.classList.remove("active");
                t.btn.setAttribute("aria-selected", "false");
                t.section.hidden = true;
            }
        });

        if (tabName === "prep") loadPrepSummary();
        if (tabName === "menu") loadMenuCatalog();
    }

    tabBtnOrders.addEventListener("click", () => switchTab("orders"));
    tabBtnPrep.addEventListener("click", () => switchTab("prep"));
    tabBtnMenu.addEventListener("click", () => switchTab("menu"));

    // -------------------------------------------------------------
    // Authentication Flow (Session-based)
    // -------------------------------------------------------------
    async function checkAuth() {
        try {
            const res = await fetch("/api/staff/check-auth", {
                method: "GET",
                headers: { "Accept": "application/json" }
            });

            if (res.ok) {
                setAuthenticatedView(true);
                refreshAll();
            } else {
                setAuthenticatedView(false);
            }
        } catch {
            setAuthenticatedView(false);
        }
    }

    function setAuthenticatedView(authed) {
        isAuthenticated = authed;
        if (authed) {
            staffAuthView.hidden = true;
            staffPortalView.hidden = false;
            staffLogoutBtn.hidden = false;
        } else {
            staffAuthView.hidden = false;
            staffPortalView.hidden = true;
            staffLogoutBtn.hidden = true;
        }
    }

    staffLoginForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        hideAlert(staffLoginAlert);

        const pin = staffPinInput.value.trim();
        if (!pin) {
            showAlert(staffLoginAlert, "Please enter your staff PIN.");
            staffPinInput.focus();
            return;
        }

        staffLoginBtn.disabled = true;
        staffLoginBtnText.textContent = "Authenticating...";
        staffLoginSpinner.hidden = false;

        try {
            const res = await fetch("/api/staff/login", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                },
                body: JSON.stringify({ pin: pin })
            });

            const data = await res.json();
            if (!res.ok) {
                showAlert(staffLoginAlert, data.message || "Invalid staff PIN. Access denied.");
                staffPinInput.value = "";
                staffPinInput.focus();
                return;
            }

            // Authentication succeeded
            staffPinInput.value = "";
            setAuthenticatedView(true);
            refreshAll();
        } catch (err) {
            showAlert(staffLoginAlert, "Network error: Unable to reach the server.");
        } finally {
            staffLoginBtn.disabled = false;
            staffLoginBtnText.textContent = "Authenticate & Enter";
            staffLoginSpinner.hidden = true;
        }
    });

    staffLogoutBtn.addEventListener("click", async () => {
        try {
            await fetch("/api/staff/logout", {
                method: "POST",
                headers: { "Accept": "application/json" }
            });
        } catch {
            // Proceed to clear state locally regardless
        }
        setAuthenticatedView(false);
        ordersList = [];
        prepSummaryList = [];
        menuCatalog = [];
        if (statTotalOrders) statTotalOrders.textContent = "0";
        if (statPendingOrders) statPendingOrders.textContent = "0";
        if (statCompletedOrders) statCompletedOrders.textContent = "0";
        if (statTodaySales) statTodaySales.textContent = "Rs. 0.00";
    });

    // -------------------------------------------------------------
    // Data Loading & Refresh
    // -------------------------------------------------------------
    async function refreshAll() {
        hideAlert(staffActionAlert);
        await Promise.all([
            loadStats(),
            loadOrders(),
            loadPrepSummary(),
            loadMenuCatalog()
        ]);
    }

    staffRefreshBtn.addEventListener("click", () => {
        refreshAll();
    });

    // -------------------------------------------------------------
    // 1. Orders Board Operations
    // -------------------------------------------------------------
    async function loadOrders() {
        staffOrdersGrid.innerHTML = `
            <div class="loading-state">
                <div class="spinner"></div>
                <p>Loading canteen orders...</p>
            </div>
        `;

        try {
            const res = await fetch("/api/staff/orders", {
                method: "GET",
                headers: { "Accept": "application/json" }
            });

            const result = await res.json();
            if (!res.ok) {
                staffOrdersGrid.innerHTML = `
                    <div class="loading-state">
                        <p style="color:#ef4444;">${sanitize(result.message || "Failed to load orders.")}</p>
                    </div>
                `;
                return;
            }

            ordersList = result.data || [];

            // Compute active orders count (excluding Completed & Cancelled)
            const activeCount = ordersList.filter(o => 
                o.status !== "Completed" && o.status !== "Cancelled"
            ).length;

            activeOrdersCountBadge.textContent = `${activeCount} Active Order${activeCount === 1 ? '' : 's'}`;
            tabOrdersCount.textContent = ordersList.length;

            renderOrders();
        } catch (err) {
            console.error("Orders fetch error:", err);
            staffOrdersGrid.innerHTML = `
                <div class="loading-state">
                    <p style="color:#ef4444;">Unable to connect to server.</p>
                </div>
            `;
        }
    }

    function renderOrders() {
        const filtered = ordersList.filter(order => {
            const matchStatus = activeStatusFilter === "All" || order.status.toLowerCase() === activeStatusFilter.toLowerCase();
            const term = searchQuery.toLowerCase();
            const matchSearch = !term || 
                order.order_ref.toLowerCase().includes(term) ||
                order.roll_number.toLowerCase().includes(term) ||
                order.student_name.toLowerCase().includes(term);

            return matchStatus && matchSearch;
        });

        if (filtered.length === 0) {
            staffOrdersGrid.innerHTML = `
                <div class="loading-state">
                    <p>No orders match the current filter or search criteria.</p>
                </div>
            `;
            return;
        }

        staffOrdersGrid.innerHTML = filtered.map(order => {
            const safeRef = sanitize(order.order_ref);
            const safeName = sanitize(order.student_name);
            const safeRoll = sanitize(order.roll_number);
            const safeSection = sanitize(order.section);
            const statusClass = getStatusClass(order.status);
            const safeStatus = sanitize(order.status);
            const safeDate = formatDate(order.created_at);

            // Render items list
            const itemsHtml = (order.items || []).map(item => {
                const safeDish = sanitize(item.item_name);
                const safePref = item.cooking_preference ? `[${sanitize(item.cooking_preference)}]` : "";
                const safeNote = item.special_request ? `Note: "${sanitize(item.special_request)}"` : "";
                const notesHtml = (safePref || safeNote) ? `<span class="staff-item-notes">${safePref} ${safeNote}</span>` : "";

                return `
                    <div class="staff-order-item-row">
                        <div class="staff-item-name-group">
                            <strong>${item.quantity}x ${safeDish}</strong>
                            ${notesHtml}
                        </div>
                        <span>${formatCurrency(item.line_total)}</span>
                    </div>
                `;
            }).join("");

            // Determine appropriate lifecycle buttons
            let actionButtonsHtml = "";
            switch (order.status) {
                case "Pending":
                    actionButtonsHtml = `
                        <button type="button" class="btn-status-next" data-action="update-status" data-ref="${safeRef}" data-target="Confirmed">
                            ✓ Confirm Order
                        </button>
                        <button type="button" class="btn-status-cancel" data-action="update-status" data-ref="${safeRef}" data-target="Cancelled">
                            ✕ Cancel
                        </button>
                    `;
                    break;
                case "Confirmed":
                    actionButtonsHtml = `
                        <button type="button" class="btn-status-next" data-action="update-status" data-ref="${safeRef}" data-target="Preparing">
                            🍳 Start Preparing
                        </button>
                        <button type="button" class="btn-status-cancel" data-action="update-status" data-ref="${safeRef}" data-target="Cancelled">
                            ✕ Cancel
                        </button>
                    `;
                    break;
                case "Preparing":
                    actionButtonsHtml = `
                        <button type="button" class="btn-status-next" data-action="update-status" data-ref="${safeRef}" data-target="Ready for Pickup">
                            🔔 Ready for Pickup
                        </button>
                        <button type="button" class="btn-status-cancel" data-action="update-status" data-ref="${safeRef}" data-target="Cancelled">
                            ✕ Cancel
                        </button>
                    `;
                    break;
                case "Ready for Pickup":
                    actionButtonsHtml = `
                        <button type="button" class="btn-status-next" data-action="update-status" data-ref="${safeRef}" data-target="Completed">
                            🎉 Complete Order
                        </button>
                        <button type="button" class="btn-status-cancel" data-action="update-status" data-ref="${safeRef}" data-target="Cancelled">
                            ✕ Cancel
                        </button>
                    `;
                    break;
                case "Completed":
                    actionButtonsHtml = `
                        <span style="font-size:0.8rem; font-weight:700; color:#166534; padding:0.35rem 0;">
                            ✓ Order Fulfilled
                        </span>
                    `;
                    break;
                case "Cancelled":
                    actionButtonsHtml = `
                        <span style="font-size:0.8rem; font-weight:700; color:#991b1b; padding:0.35rem 0;">
                            ✕ Order Cancelled
                        </span>
                    `;
                    break;
            }

            return `
                <article class="staff-order-card" data-order-ref="${safeRef}">
                    <div>
                        <div class="staff-order-header">
                            <div>
                                <span style="font-size:0.7rem; color:var(--text-muted); text-transform:uppercase; font-weight:700; display:block;">Reference</span>
                                <span class="staff-order-ref">${safeRef}</span>
                            </div>
                            <span class="status-pill ${statusClass}">${safeStatus}</span>
                        </div>

                        <div class="staff-student-info">
                            <span class="staff-student-name">${safeName}</span>
                            <span class="staff-student-details">Roll: ${safeRoll} &bull; Section: ${safeSection}</span>
                            <div style="font-size:0.75rem; color:var(--text-muted); margin-top:0.25rem;">
                                Placed: ${safeDate}
                            </div>
                        </div>

                        <div class="staff-order-items-list">
                            ${itemsHtml}
                        </div>
                    </div>

                    <div>
                        <div class="staff-order-total">
                            <span>Total Due:</span>
                            <span>${formatCurrency(order.total_price)}</span>
                        </div>

                        <div class="staff-order-actions">
                            ${actionButtonsHtml}
                        </div>
                    </div>
                </article>
            `;
        }).join("");
    }

    // Status Filters
    staffStatusFilters.addEventListener("click", (e) => {
        const pill = e.target.closest(".staff-filter-pill");
        if (!pill) return;

        staffStatusFilters.querySelectorAll(".staff-filter-pill").forEach(p => p.classList.remove("active"));
        pill.classList.add("active");
        activeStatusFilter = pill.dataset.status;
        renderOrders();
    });

    // Real-Time Search
    staffSearchInput.addEventListener("input", (e) => {
        searchQuery = e.target.value.trim();
        renderOrders();
    });

    // Delegated Order Status Transitions
    staffOrdersGrid.addEventListener("click", async (e) => {
        const btn = e.target.closest("[data-action='update-status']");
        if (!btn) return;

        const orderRef = btn.dataset.ref;
        const targetStatus = btn.dataset.target;
        if (!orderRef || !targetStatus) return;

        btn.disabled = true;
        const originalText = btn.textContent;
        btn.textContent = "Updating...";

        try {
            const res = await fetch(`/api/staff/orders/${encodeURIComponent(orderRef)}/status`, {
                method: "PATCH",
                headers: {
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                },
                body: JSON.stringify({ status: targetStatus })
            });

            const result = await res.json();
            if (!res.ok) {
                showAlert(staffActionAlert, result.message || "Failed to update order status.", "error");
                btn.disabled = false;
                btn.textContent = originalText;
                return;
            }

            // Success feedback
            showAlert(staffActionAlert, `Order ${orderRef} updated to '${targetStatus}'.`, "success");
            setTimeout(() => hideAlert(staffActionAlert), 3000);

            // Refresh state to update board, active counter, prep summary, and statistics
            await Promise.all([
                loadStats(),
                loadOrders(),
                loadPrepSummary()
            ]);
        } catch (err) {
            console.error("Status update error:", err);
            showAlert(staffActionAlert, "Network error updating order status.", "error");
            btn.disabled = false;
            btn.textContent = originalText;
        }
    });

    // -------------------------------------------------------------
    // 1B. Staff Dashboard Statistics (Milestone 5B)
    // -------------------------------------------------------------
    async function loadStats() {
        try {
            const res = await fetch("/api/staff/stats", {
                method: "GET",
                headers: { "Accept": "application/json" }
            });

            if (!res.ok) {
                console.error("Failed to fetch staff statistics: HTTP", res.status);
                return;
            }

            const result = await res.json();
            const stats = result.data || {};

            if (statTotalOrders) statTotalOrders.textContent = (stats.total_orders ?? 0).toLocaleString();
            if (statPendingOrders) statPendingOrders.textContent = (stats.pending_orders ?? 0).toLocaleString();
            if (statCompletedOrders) statCompletedOrders.textContent = (stats.completed_orders ?? 0).toLocaleString();
            if (statTodaySales) statTodaySales.textContent = formatCurrency(stats.today_sales ?? 0);
            if (statServerDate && stats.server_date) statServerDate.textContent = stats.server_date;
            if (statSalesDisclaimer && stats.sales_disclaimer) {
                statSalesDisclaimer.title = stats.sales_disclaimer;
            }
        } catch (err) {
            console.error("Staff stats fetch error:", err);
            if (statTotalOrders && !statTotalOrders.textContent) statTotalOrders.textContent = "0";
            if (statPendingOrders && !statPendingOrders.textContent) statPendingOrders.textContent = "0";
            if (statCompletedOrders && !statCompletedOrders.textContent) statCompletedOrders.textContent = "0";
            if (statTodaySales && !statTodaySales.textContent) statTodaySales.textContent = "Rs. 0.00";
        }
    }

    // -------------------------------------------------------------
    // 2. Kitchen Preparation Summary
    // -------------------------------------------------------------
    async function loadPrepSummary() {
        try {
            const res = await fetch("/api/staff/prep-summary", {
                method: "GET",
                headers: { "Accept": "application/json" }
            });

            const result = await res.json();
            if (!res.ok) return;

            prepSummaryList = result.data || [];
            tabPrepCount.textContent = prepSummaryList.reduce((acc, p) => acc + p.total_quantity, 0);

            if (prepSummaryList.length === 0) {
                staffPrepGrid.innerHTML = `
                    <div class="loading-state">
                        <p>No pending kitchen orders! All active food preparation is complete.</p>
                    </div>
                `;
                return;
            }

            staffPrepGrid.innerHTML = prepSummaryList.map(item => {
                const safeName = sanitize(item.item_name);
                const safeCat = sanitize(item.category);

                return `
                    <div class="prep-summary-card">
                        <div>
                            <span class="prep-dish-category">${safeCat}</span>
                            <div class="prep-dish-name">${safeName}</div>
                        </div>
                        <div class="prep-qty-badge" title="Total active portions needed">
                            ${item.total_quantity}
                        </div>
                    </div>
                `;
            }).join("");

        } catch (err) {
            console.error("Prep summary error:", err);
        }
    }

    // -------------------------------------------------------------
    // 3. Menu Availability Management
    // -------------------------------------------------------------
    async function loadMenuCatalog() {
        try {
            const res = await fetch("/api/staff/menu", {
                method: "GET",
                headers: { "Accept": "application/json" }
            });

            const result = await res.json();
            if (!res.ok) {
                staffMenuTbody.innerHTML = `
                    <tr><td colspan="6" style="text-align:center; color:#ef4444;">Failed to load catalog.</td></tr>
                `;
                return;
            }

            menuCatalog = result.data || [];

            staffMenuTbody.innerHTML = menuCatalog.map(item => {
                const safeName = sanitize(item.name);
                const safeCat = sanitize(item.category);
                const isAvail = item.is_available === 1;

                const statusBadge = isAvail
                    ? `<span class="status-badge-available">Available</span>`
                    : `<span class="status-badge-soldout">Sold Out</span>`;

                const toggleBtn = isAvail
                    ? `<button type="button" class="btn-toggle-availability btn-toggle-soldout" data-action="toggle-stock" data-id="${item.id}" data-current="1">
                           Mark Sold Out
                       </button>`
                    : `<button type="button" class="btn-toggle-availability btn-toggle-available" data-action="toggle-stock" data-id="${item.id}" data-current="0">
                           Mark Available
                       </button>`;

                return `
                    <tr>
                        <td><strong>${safeName}</strong></td>
                        <td>${safeCat}</td>
                        <td>${formatCurrency(item.price)}</td>
                        <td>${item.max_portion_limit} max/order</td>
                        <td>${statusBadge}</td>
                        <td style="text-align:right;">${toggleBtn}</td>
                    </tr>
                `;
            }).join("");

        } catch (err) {
            console.error("Menu catalog fetch error:", err);
        }
    }

    staffMenuTbody.addEventListener("click", async (e) => {
        const btn = e.target.closest("[data-action='toggle-stock']");
        if (!btn) return;

        const itemId = parseInt(btn.dataset.id, 10);
        const currentVal = parseInt(btn.dataset.current, 10);
        const newVal = currentVal === 1 ? 0 : 1;

        btn.disabled = true;
        btn.textContent = "Updating...";

        try {
            const res = await fetch(`/api/staff/menu/${itemId}/availability`, {
                method: "PATCH",
                headers: {
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                },
                body: JSON.stringify({ is_available: newVal })
            });

            const result = await res.json();
            if (!res.ok) {
                showAlert(staffActionAlert, result.message || "Failed to update item availability.", "error");
                return;
            }

            showAlert(staffActionAlert, result.message || "Stock availability updated.", "success");
            setTimeout(() => hideAlert(staffActionAlert), 3000);

            loadMenuCatalog();
        } catch (err) {
            console.error("Toggle availability error:", err);
            showAlert(staffActionAlert, "Network error updating availability.", "error");
        }
    });

    // Initial Auth Check
    checkAuth();
});
