const API = "/api";
const DEMO_EMAIL = "alex.morgan@example.com";
const CUSTOMER_KEY = "novamart_customer";
const BAG_KEY = "novamart_bag";
const CATEGORIES = ["All", "Everyday", "Home", "Travel"];

const state = {
    products: [],
    category: "All",
    search: "",
    customer: null,
    orders: [],
    bag: readStorage(BAG_KEY, []),
    conversations: [],
    activeConversationId: null,
    busy: false
};

const byId = id => document.getElementById(id);
const chatForm = byId("chatForm");
const messageInput = byId("messageInput");

function readStorage(key, fallback) {
    try {
        const value = JSON.parse(localStorage.getItem(key) || "null");
        return value ?? fallback;
    } catch (error) {
        console.error(`Could not read ${key}:`, error);
        return fallback;
    }
}

function writeStorage(key, value) {
    try {
        localStorage.setItem(key, JSON.stringify(value));
    } catch (error) {
        console.error(`Could not save ${key}:`, error);
        showToast("Your browser could not save this demo data.");
    }
}

function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, character => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[character]);
}

async function api(path, options = {}) {
    const response = await fetch(`${API}${path}`, {
        headers: { "Content-Type": "application/json", ...(options.headers || {}) },
        ...options
    });
    let data;
    try {
        data = await response.json();
    } catch (error) {
        if (response.ok) {
            throw new Error("The server returned a response we couldn't read.");
        }
        data = {};
    }
    if (!response.ok) {
        throw new Error(data.detail || `The request failed (${response.status}). Please try again.`);
    }
    return data;
}

function money(value) {
    return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
}

function showToast(message) {
    const toast = document.createElement("div");
    toast.className = "toast";
    toast.textContent = message;
    byId("toastRegion").appendChild(toast);
    window.setTimeout(() => toast.remove(), 3200);
}

function navigate(view) {
    document.querySelectorAll(".view").forEach(section => {
        const active = section.id === `${view}View`;
        section.classList.toggle("active", active);
        section.hidden = !active;
    });
    document.querySelectorAll(".nav-link").forEach(button => {
        button.classList.toggle("active", button.dataset.view === view);
    });
    byId("mainNav").classList.remove("open");
    if (view === "account" && state.customer) loadAccount();
    if (view === "support") {
        refreshOrderSelector();
        renderChat();
        loadConversationHistory();
    }
    window.scrollTo({ top: 0, behavior: "smooth" });
}

function renderCategories() {
    byId("categoryFilters").replaceChildren();
    CATEGORIES.forEach(category => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = `category-chip${state.category === category ? " active" : ""}`;
        button.textContent = category;
        button.addEventListener("click", () => {
            state.category = category;
            renderCategories();
            renderProducts();
        });
        byId("categoryFilters").appendChild(button);
    });
}

function renderProducts() {
    const grid = byId("productGrid");
    const matches = state.products.filter(product => {
        const categoryMatch = state.category === "All" || product.category === state.category;
        const query = state.search.toLowerCase();
        const textMatch = !query || `${product.name} ${product.description} ${product.category}`.toLowerCase().includes(query);
        return categoryMatch && textMatch;
    });
    grid.replaceChildren();
    byId("emptyProducts").hidden = matches.length > 0;
    matches.forEach(product => {
        const card = document.createElement("article");
        card.className = "product-card";
        card.innerHTML = `
            <div class="product-visual" style="--product-color:${escapeHtml(product.color)}">
                <span class="product-badge">${escapeHtml(product.badge)}</span>
                <span class="product-icon" aria-hidden="true">${escapeHtml(product.icon)}</span>
                <button class="product-action" type="button" aria-label="Add ${escapeHtml(product.name)} to bag">Add to bag <span aria-hidden="true">＋</span></button>
            </div>
            <div class="product-info">
                <div><p class="product-category">${escapeHtml(product.category)}</p><h3 class="product-name">${escapeHtml(product.name)}</h3><p class="product-desc">${escapeHtml(product.description)}</p></div>
                <p class="product-price">${money(product.price)}</p>
            </div>`;
        card.querySelector(".product-action").addEventListener("click", () => addToBag(product.id));
        grid.appendChild(card);
    });
}

function addToBag(productId) {
    const existing = state.bag.find(item => item.product_id === productId);
    if (existing) existing.quantity = Math.min(existing.quantity + 1, 5);
    else state.bag.push({ product_id: productId, quantity: 1 });
    writeStorage(BAG_KEY, state.bag);
    renderBag();
    showToast("Added to your bag.");
}

function renderBag() {
    const bagCount = state.bag.reduce((sum, item) => sum + item.quantity, 0);
    byId("bagCount").textContent = bagCount;
    byId("drawerBagCount").textContent = `(${bagCount})`;
    const bagItems = byId("bagItems");
    bagItems.replaceChildren();
    let total = 0;
    if (state.bag.length === 0) {
        const empty = document.createElement("p");
        empty.className = "bag-empty";
        empty.textContent = "Your bag is taking a little breather.";
        bagItems.appendChild(empty);
    }
    state.bag.forEach(item => {
        const product = state.products.find(entry => entry.id === item.product_id);
        if (!product) return;
        total += product.price * item.quantity;
        const row = document.createElement("div");
        row.className = "bag-line";
        row.innerHTML = `
            <div class="order-thumb" style="--product-color:${escapeHtml(product.color)}">${escapeHtml(product.icon)}</div>
            <div><h3>${escapeHtml(product.name)}</h3><p>${money(product.price)}</p>
                <div class="quantity-control"><button type="button" data-quantity="-1" aria-label="Remove one">−</button><span>${item.quantity}</span><button type="button" data-quantity="1" aria-label="Add one">＋</button><button type="button" data-remove="true" class="text-button">Remove</button></div>
            </div>
            <span class="bag-line-price">${money(product.price * item.quantity)}</span>`;
        row.querySelectorAll("[data-quantity]").forEach(button => {
            button.addEventListener("click", () => changeQuantity(product.id, Number(button.dataset.quantity)));
        });
        row.querySelector("[data-remove]").addEventListener("click", () => removeFromBag(product.id));
        bagItems.appendChild(row);
    });
    byId("bagTotal").textContent = money(total);
    byId("checkoutButton").disabled = bagCount === 0;
}

function changeQuantity(productId, delta) {
    const item = state.bag.find(entry => entry.product_id === productId);
    if (!item) return;
    item.quantity += delta;
    if (item.quantity <= 0) state.bag = state.bag.filter(entry => entry.product_id !== productId);
    else item.quantity = Math.min(item.quantity, 5);
    writeStorage(BAG_KEY, state.bag);
    renderBag();
}

function removeFromBag(productId) {
    state.bag = state.bag.filter(item => item.product_id !== productId);
    writeStorage(BAG_KEY, state.bag);
    renderBag();
}

function openBag() {
    renderBag();
    byId("bagOverlay").hidden = false;
    byId("closeBag").focus();
}

function closeBag() {
    byId("bagOverlay").hidden = true;
    byId("bagButton").focus();
}

async function checkout() {
    if (!state.customer) {
        closeBag();
        navigate("account");
        showToast("Add your demo email first, then your bag will be ready.");
        return;
    }
    byId("checkoutButton").disabled = true;
    try {
        const created = [];
        for (const item of state.bag) {
            created.push(await api("/orders", {
                method: "POST",
                body: JSON.stringify({
                    email: state.customer.email,
                    product_id: item.product_id,
                    quantity: item.quantity
                })
            }));
        }
        state.bag = [];
        writeStorage(BAG_KEY, state.bag);
        renderBag();
        closeBag();
        await loadAccount();
        navigate("account");
        showToast(`${created.length} demo order${created.length === 1 ? "" : "s"} placed. No payment was taken.`);
    } catch (error) {
        showToast(error.message);
    } finally {
        byId("checkoutButton").disabled = state.bag.length === 0;
    }
}

async function connectAccount(name, email) {
    const result = await api("/customers", {
        method: "POST",
        body: JSON.stringify({ name: name.trim(), email: email.trim() })
    });
    state.customer = result.customer;
    writeStorage(CUSTOMER_KEY, state.customer);
    updateHeaderAccount();
    await loadAccount();
}

async function useDemoAccount() {
    try {
        await connectAccount("Alex Morgan", DEMO_EMAIL);
        showToast("You're in. The sample order is ready to explore.");
    } catch (error) {
        showToast(error.message);
    }
}

function updateHeaderAccount() {
    const name = state.customer?.name || "Account";
    byId("accountLabel").textContent = state.customer ? name.split(" ")[0] : "Account";
    byId("accountAvatar").textContent = state.customer ? name.charAt(0).toUpperCase() : "A";
    byId("profileContent").innerHTML = state.customer ? `
        <div class="profile-summary"><div class="profile-avatar">${escapeHtml(name.charAt(0).toUpperCase())}</div><div><h2>${escapeHtml(name)}</h2><p>${escapeHtml(state.customer.email)}</p></div></div>
        <div class="profile-facts"><span>Account type<strong>Demo shopper</strong></span><span>Member since<strong>${new Date(state.customer.created_at).toLocaleDateString(undefined, { month: "short", year: "numeric" })}</strong></span></div>
        <div class="account-signed-in"><button class="text-button" id="switchAccount" type="button">Use a different email</button></div>` : "";
    byId("accountForm").hidden = Boolean(state.customer);
    const switchButton = byId("switchAccount");
    if (switchButton) {
        switchButton.addEventListener("click", () => {
            state.customer = null;
            state.orders = [];
            localStorage.removeItem(CUSTOMER_KEY);
            updateHeaderAccount();
            renderOrders();
            refreshOrderSelector();
        });
    }
}

async function loadAccount() {
    if (!state.customer) return;
    try {
        const customer = await api(`/customers/${encodeURIComponent(state.customer.email)}`);
        state.customer = customer;
        writeStorage(CUSTOMER_KEY, customer);
        state.orders = await api(`/customers/${encodeURIComponent(customer.email)}/orders`);
        updateHeaderAccount();
        renderOrders();
        refreshOrderSelector();
    } catch (error) {
        showToast(error.message);
    }
}

function renderOrders() {
    const list = byId("ordersList");
    byId("orderCount").textContent = state.orders.length;
    list.replaceChildren();
    if (!state.customer || state.orders.length === 0) {
        const empty = document.createElement("div");
        empty.className = "empty-orders";
        empty.innerHTML = '<span>✳</span><p>Your next favorite is one good find away.</p><button class="text-button" data-view="store" type="button">Browse the collection →</button>';
        empty.querySelector("button").addEventListener("click", () => navigate("store"));
        list.appendChild(empty);
        return;
    }
    state.orders.forEach(order => {
        const product = state.products.find(item => order.items.some(line => line.product_id === item.id));
        const mainItem = order.items[0];
        const article = document.createElement("article");
        article.className = "order-card";
        article.innerHTML = `
            <div class="order-thumb" style="--product-color:${escapeHtml(mainItem?.color || "#e7e8df")}">${escapeHtml(mainItem?.icon || "✳")}</div>
            <div class="order-meta"><p class="order-id">${escapeHtml(order.id)} · ${new Date(order.placed_at).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}</p><h3>${escapeHtml(product?.name || mainItem?.name || "NovaMart order")}${order.items.length > 1 ? ` + ${order.items.length - 1} more` : ""}</h3><p>${order.items.reduce((sum, item) => sum + item.quantity, 0)} item${order.items.length === 1 && mainItem?.quantity === 1 ? "" : "s"} · ${escapeHtml(order.latest_update)}</p></div>
            <div class="order-aside"><span class="status-pill">${escapeHtml(order.status)}</span><strong>${money(order.total)}</strong>
                <details><summary class="invoice-link">Order & invoice</summary><div class="order-details"><p><strong>Estimated delivery</strong><br>${escapeHtml(order.estimated_delivery)}</p><p><strong>Latest update</strong><br>${escapeHtml(order.latest_update)}</p><p><strong>Invoice</strong><br>${escapeHtml(order.invoice_id)} · Demo invoice</p></div></details>
            </div>`;
        list.appendChild(article);
    });
}

function refreshOrderSelector() {
    const select = byId("supportOrder");
    if (!select) return;
    const previous = select.value;
    select.replaceChildren(new Option("Choose an order (optional)", ""));
    state.orders.forEach(order => {
        const item = order.items[0];
        const option = new Option(`${order.id} · ${item?.name || "Order"} · ${order.status}`, order.id);
        select.appendChild(option);
    });
    if (state.orders.some(order => order.id === previous)) select.value = previous;
}

function refreshProductSelector() {
    const select = byId("supportProduct");
    if (!select) return;
    const previous = select.value;
    select.replaceChildren(new Option("Choose a product (optional)", ""));
    state.products.forEach(product => {
        select.appendChild(new Option(`${product.name} · ${money(product.price)}`, product.id));
    });
    if (state.products.some(product => product.id === previous)) select.value = previous;
}

function activeConversation() {
    return state.conversations.find(conversation => conversation.id === state.activeConversationId);
}

function createConversation() {
    const conversation = {
        id: crypto.randomUUID(),
        title: "New conversation",
        messages: [],
        updated_at: new Date().toISOString()
    };
    state.conversations.unshift(conversation);
    state.activeConversationId = conversation.id;
    renderConversationList();
    renderChat();
    return conversation;
}

function persistConversations() {
    const email = state.customer?.email || "guest";
    writeStorage(`novamart_chats_${email}`, state.conversations);
}

async function loadConversationHistory() {
    if (!state.customer) return;
    try {
        const summaries = await api(`/customers/${encodeURIComponent(state.customer.email)}/conversations`);
        for (const summary of summaries) {
            if (state.conversations.some(item => item.id === summary.id)) continue;
            const messages = await api(`/conversations/${encodeURIComponent(summary.id)}?email=${encodeURIComponent(state.customer.email)}`);
            state.conversations.push({
                id: summary.id,
                title: summary.preview?.slice(0, 38) || "Support conversation",
                updated_at: summary.updated_at,
                messages: messages.map(message => ({ role: message.role, content: message.content, created_at: message.created_at }))
            });
        }
        state.conversations.sort((a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at));
        if (!activeConversation() && state.conversations.length) state.activeConversationId = state.conversations[0].id;
        renderConversationList();
        renderChat();
    } catch (error) {
        showToast(error.message);
    }
}

function renderConversationList() {
    const list = byId("conversationList");
    list.replaceChildren();
    if (!state.conversations.length) {
        const empty = document.createElement("p");
        empty.className = "history-empty";
        empty.textContent = "Your chats will show up here.";
        list.appendChild(empty);
        return;
    }
    state.conversations.forEach(conversation => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = `history-item${conversation.id === state.activeConversationId ? " active" : ""}`;
        const title = document.createElement("span");
        title.textContent = conversation.title;
        const date = document.createElement("small");
        date.textContent = new Date(conversation.updated_at).toLocaleDateString(undefined, { month: "short", day: "numeric" });
        button.append(title, date);
        button.addEventListener("click", () => {
            state.activeConversationId = conversation.id;
            renderConversationList();
            renderChat();
        });
        list.appendChild(button);
    });
}

function renderChat() {
    const box = byId("chatMessages");
    box.replaceChildren();
    const conversation = activeConversation();
    if (!conversation || conversation.messages.length === 0) {
        const welcome = document.createElement("div");
        welcome.className = "chat-welcome";
        welcome.innerHTML = "<strong>A little help, right this way.</strong>I'm here for order updates, product questions, and friendly guidance. Select one of your orders if you'd like me to look at its simulated status.";
        box.appendChild(welcome);
    } else {
        conversation.messages.forEach(message => {
            const article = document.createElement("article");
            article.className = `chat-message ${message.role}`;
            const label = document.createElement("small");
            label.textContent = message.role === "user" ? "YOU" : "SUPPORTGPT";
            const content = document.createElement("div");
            content.textContent = message.content;
            article.append(label, content);
            box.appendChild(article);
        });
    }
    if (state.busy) {
        const typing = document.createElement("div");
        typing.className = "chat-message assistant";
        typing.textContent = "SupportGPT is thinking…";
        box.appendChild(typing);
    }
    byId("quickPrompts").hidden = Boolean(conversation?.messages.length);
    byId("sendButton").disabled = state.busy;
    box.scrollTop = box.scrollHeight;
}

async function sendMessage(message) {
    const text = message.trim();
    if (!text || state.busy) return;
    let conversation = activeConversation();
    if (!conversation) conversation = createConversation();
    const userMessage = { role: "user", content: text, created_at: new Date().toISOString() };
    conversation.messages.push(userMessage);
    if (conversation.title === "New conversation") conversation.title = text.slice(0, 38);
    conversation.updated_at = new Date().toISOString();
    messageInput.value = "";
    state.busy = true;
    renderConversationList();
    renderChat();
    try {
        const payload = { message: text, session_id: conversation.id };
        if (state.customer) {
            payload.customer_email = state.customer.email;
            if (byId("supportOrder").value) payload.order_id = byId("supportOrder").value;
        }
        if (byId("supportProduct").value) payload.product_id = byId("supportProduct").value;
        const result = await api("/chat", { method: "POST", body: JSON.stringify(payload) });
        conversation.messages.push({ role: "assistant", content: result.response, created_at: new Date().toISOString() });
        conversation.updated_at = new Date().toISOString();
        persistConversations();
    } catch (error) {
        conversation.messages.pop();
        showToast(error.message);
    } finally {
        state.busy = false;
        renderConversationList();
        renderChat();
    }
}

async function createTicket(event) {
    event.preventDefault();
    const form = event.currentTarget;
    if (!state.customer) {
        navigate("account");
        showToast("Add your email to create a support ticket.");
        return;
    }
    const submit = form.querySelector("button[type=submit]");
    submit.disabled = true;
    try {
        const ticket = await api("/tickets", {
            method: "POST",
            body: JSON.stringify({
                email: state.customer.email,
                order_id: byId("supportOrder").value || null,
                subject: byId("ticketSubject").value.trim(),
                message: byId("ticketMessage").value.trim()
            })
        });
        form.reset();
        showToast(`Demo ticket ${ticket.id} created. Our sample support queue has it.`);
    } catch (error) {
        showToast(error.message);
    } finally {
        submit.disabled = false;
    }
}

async function initialize() {
    state.customer = readStorage(CUSTOMER_KEY, null);
    updateHeaderAccount();
    renderBag();
    renderCategories();
    document.querySelectorAll(".nav-link").forEach(button => {
        button.addEventListener("click", () => navigate(button.dataset.view));
    });
    document.querySelectorAll("[data-view]:not(.nav-link)").forEach(button => {
        button.addEventListener("click", () => navigate(button.dataset.view));
    });
    byId("accountShortcut").addEventListener("click", () => navigate("account"));
    byId("menuButton").addEventListener("click", () => byId("mainNav").classList.toggle("open"));
    byId("exploreButton").addEventListener("click", () => byId("collection").scrollIntoView({ behavior: "smooth" }));
    byId("searchInput").addEventListener("input", event => {
        state.search = event.target.value;
        renderProducts();
    });
    byId("bagButton").addEventListener("click", openBag);
    byId("closeBag").addEventListener("click", closeBag);
    byId("closeBagScrim").addEventListener("click", closeBag);
    byId("checkoutButton").addEventListener("click", checkout);
    byId("accountForm").addEventListener("submit", async event => {
        event.preventDefault();
        const formData = new FormData(event.currentTarget);
        try {
            await connectAccount(formData.get("name"), formData.get("email"));
            showToast("Your demo account is ready.");
        } catch (error) {
            showToast(error.message);
        }
    });
    byId("demoAccountButton").addEventListener("click", useDemoAccount);
    byId("newConversation").addEventListener("click", () => {
        createConversation();
        persistConversations();
        messageInput.focus();
    });
    chatForm.addEventListener("submit", event => {
        event.preventDefault();
        sendMessage(messageInput.value);
    });
    document.querySelectorAll("[data-prompt]").forEach(button => {
        button.addEventListener("click", () => sendMessage(button.dataset.prompt));
    });
    byId("ticketForm").addEventListener("submit", createTicket);
    document.addEventListener("keydown", event => {
        if (event.key === "Escape" && !byId("bagOverlay").hidden) closeBag();
    });

    try {
        state.products = await api("/products");
        renderProducts();
        renderBag();
        refreshProductSelector();
        if (state.customer) {
            await loadAccount();
            state.conversations = readStorage(`novamart_chats_${state.customer.email}`, []);
            if (state.conversations.length) state.activeConversationId = state.conversations[0].id;
        } else {
            state.conversations = readStorage("novamart_chats_guest", []);
        }
        if (!state.activeConversationId && state.conversations.length) {
            state.activeConversationId = state.conversations[0].id;
        }
        renderConversationList();
        renderChat();
    } catch (error) {
        showToast(error.message);
    }
}

initialize();
