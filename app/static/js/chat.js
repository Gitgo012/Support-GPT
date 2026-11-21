const API_URL = "/api/chat";
const HEALTH_URL = "/api/health";
const STORAGE_KEY = "supportgpt_conversations";
const ACTIVE_CONVERSATION_KEY = "supportgpt_active_conversation";
const THEME_KEY = "supportgpt_theme";
const MAX_MESSAGE_LENGTH = 2000;

const chatForm = document.getElementById("chatForm");
const messageInput = document.getElementById("messageInput");
const sendBtn = document.getElementById("sendBtn");
const messagesContainer = document.getElementById("messagesContainer");
const welcomeScreen = document.getElementById("welcomeScreen");
const newChatBtn = document.getElementById("newChatBtn");
const clearConversationsBtn = document.getElementById("clearConversationsBtn");
const clearChatBtn = document.getElementById("clearChatBtn");
const conversationList = document.getElementById("conversationList");
const sidebar = document.getElementById("sidebar");
const sidebarScrim = document.getElementById("sidebarScrim");
const mobileMenuBtn = document.getElementById("mobileMenuBtn");
const themeToggle = document.getElementById("themeToggle");
const characterCount = document.getElementById("characterCount");
const toastRegion = document.getElementById("toastRegion");
const onlineBadge = document.getElementById("onlineBadge");
const sidebarServiceStatus = document.getElementById("sidebarServiceStatus");

function loadSavedConversations() {
    try {
        const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
        if (!Array.isArray(saved)) {
            return [];
        }

        return saved
            .filter(item => item && typeof item === "object" && Array.isArray(item.messages))
            .map(item => ({
                id: typeof item.id === "string" ? item.id : crypto.randomUUID(),
                sessionId: typeof item.sessionId === "string" ? item.sessionId : null,
                title: typeof item.title === "string" ? item.title : "New conversation",
                messages: item.messages
                    .filter(message => message
                        && ["user", "assistant"].includes(message.role)
                        && typeof message.content === "string")
                    .map(message => ({
                        role: message.role,
                        content: message.content,
                        timestamp: validTimestamp(message.timestamp),
                        ...(message.error ? { error: true } : {})
                    })),
                draft: typeof item.draft === "string" ? item.draft : "",
                createdAt: validTimestamp(item.createdAt),
                updatedAt: validTimestamp(item.updatedAt || item.createdAt)
            }));
    } catch (error) {
        console.error("Could not load saved conversations:", error);
        return [];
    }
}

function validTimestamp(value) {
    return typeof value === "string" && !Number.isNaN(Date.parse(value))
        ? value
        : new Date().toISOString();
}

let conversations = loadSavedConversations();
let activeConversationId = null;
let storageWarningShown = false;
const pendingConversationIds = new Set();

try {
    activeConversationId = localStorage.getItem(ACTIVE_CONVERSATION_KEY);
} catch (error) {
    console.error("Could not restore the active conversation:", error);
}

function showToast(message) {
    const toast = document.createElement("div");
    toast.className = "toast";
    toast.textContent = message;
    toastRegion.appendChild(toast);
    window.setTimeout(() => toast.remove(), 3000);
}

function saveConversations() {
    try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
        if (activeConversationId) {
            localStorage.setItem(ACTIVE_CONVERSATION_KEY, activeConversationId);
        } else {
            localStorage.removeItem(ACTIVE_CONVERSATION_KEY);
        }
    } catch (error) {
        console.error("Could not save conversations:", error);
        if (!storageWarningShown) {
            storageWarningShown = true;
            showToast("Your browser could not save this conversation.");
        }
    }
}

function getActiveConversation() {
    return conversations.find(item => item.id === activeConversationId) || null;
}

function createConversation() {
    const now = new Date().toISOString();
    const conversation = {
        id: crypto.randomUUID(),
        sessionId: null,
        title: "New conversation",
        messages: [],
        draft: "",
        createdAt: now,
        updatedAt: now
    };

    conversations.unshift(conversation);
    activeConversationId = conversation.id;
    saveConversations();
    renderConversationList();
    renderMessages();
    return conversation;
}

function updateConversationTimestamp(conversation) {
    conversation.updatedAt = new Date().toISOString();
}

function relativeDate(value) {
    const date = new Date(value);
    const elapsedSeconds = Math.round((date.getTime() - Date.now()) / 1000);
    const elapsedDays = Math.round(elapsedSeconds / 86400);
    if (Math.abs(elapsedDays) >= 7) {
        return date.toLocaleDateString([], { month: "short", day: "numeric" });
    }
    const formatter = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
    if (Math.abs(elapsedSeconds) < 60) return "just now";
    if (Math.abs(elapsedSeconds) < 3600) return formatter.format(
        Math.round(elapsedSeconds / 60), "minute");
    if (Math.abs(elapsedSeconds) < 86400) return formatter.format(
        Math.round(elapsedSeconds / 3600), "hour");
    return formatter.format(elapsedDays, "day");
}

function renderConversationList() {
    conversationList.replaceChildren();
    clearConversationsBtn.hidden = conversations.length === 0;

    if (conversations.length === 0) {
        const empty = document.createElement("p");
        empty.className = "empty-history";
        empty.textContent = "Your saved conversations will appear here.";
        conversationList.appendChild(empty);
        return;
    }

    [...conversations]
        .sort((left, right) => Date.parse(right.updatedAt) - Date.parse(left.updatedAt))
        .forEach(conversation => {
            const wrapper = document.createElement("div");
            wrapper.className = "conversation-item-wrapper";
            if (conversation.id === activeConversationId) {
                wrapper.classList.add("active");
            }

            const selectButton = document.createElement("button");
            selectButton.className = "conversation-item";
            selectButton.type = "button";
            selectButton.setAttribute("aria-current",
                conversation.id === activeConversationId ? "page" : "false");
            selectButton.addEventListener("click", () => switchConversation(conversation.id));

            const title = document.createElement("span");
            title.className = "conversation-title";
            title.textContent = conversation.title;
            selectButton.title = conversation.title;

            const date = document.createElement("span");
            date.className = "conversation-date";
            date.textContent = relativeDate(conversation.updatedAt);
            date.title = new Date(conversation.updatedAt).toLocaleString();
            selectButton.append(title, date);

            const deleteButton = document.createElement("button");
            deleteButton.className = "delete-conversation-btn";
            deleteButton.type = "button";
            deleteButton.textContent = "×";
            deleteButton.title = `Delete ${conversation.title}`;
            deleteButton.setAttribute("aria-label", `Delete conversation: ${conversation.title}`);
            deleteButton.addEventListener("click", () => deleteConversation(conversation.id));

            wrapper.append(selectButton, deleteButton);
            conversationList.appendChild(wrapper);
        });
}

function switchConversation(conversationId) {
    if (!conversations.some(item => item.id === conversationId)) return;
    saveDraft();
    activeConversationId = conversationId;
    saveConversations();
    renderConversationList();
    renderMessages();
    messageInput.value = getActiveConversation().draft;
    resizeInput();
    updateComposerState();
    closeSidebar();
}

function startNewChat() {
    const current = getActiveConversation();
    if (current && current.messages.length === 0 && !current.draft.trim()) {
        messageInput.focus();
        closeSidebar();
        return;
    }

    const conversation = createConversation();
    messageInput.value = conversation.draft;
    updateComposerState();
    messageInput.focus();
    closeSidebar();
}

function deleteConversation(conversationId) {
    const conversation = conversations.find(item => item.id === conversationId);
    if (!conversation) return;

    const confirmed = window.confirm(`Delete "${conversation.title}"? This cannot be undone.`);
    if (!confirmed) return;

    conversations = conversations.filter(item => item.id !== conversationId);
    if (activeConversationId === conversationId) {
        const next = [...conversations].sort(
            (left, right) => Date.parse(right.updatedAt) - Date.parse(left.updatedAt)
        )[0];
        activeConversationId = next ? next.id : null;
    }

    saveConversations();
    renderConversationList();
    renderMessages();
    const active = getActiveConversation();
    messageInput.value = active ? active.draft : "";
    updateComposerState();
    showToast("Conversation deleted.");
}

function clearAllConversations() {
    if (conversations.length === 0) return;
    if (!window.confirm("Clear all saved conversations? This cannot be undone.")) return;

    conversations = [];
    activeConversationId = null;
    saveConversations();
    renderConversationList();
    renderMessages();
    messageInput.value = "";
    updateComposerState();
    showToast("All conversations cleared.");
}

function clearActiveConversation() {
    const conversation = getActiveConversation();
    if (!conversation || conversation.messages.length === 0
        || pendingConversationIds.has(conversation.id)) return;
    if (!window.confirm("Clear messages in this conversation? This cannot be undone.")) return;

    conversation.messages = [];
    conversation.sessionId = null;
    conversation.title = "New conversation";
    conversation.draft = "";
    updateConversationTimestamp(conversation);
    saveConversations();
    renderConversationList();
    renderMessages();
    messageInput.value = "";
    updateComposerState();
    showToast("Chat cleared.");
}

function formatTime(timestamp) {
    const date = new Date(timestamp);
    return {
        short: date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        full: date.toLocaleString()
    };
}

function renderMessages() {
    const conversation = getActiveConversation();
    messagesContainer.replaceChildren();

    const messages = conversation ? conversation.messages : [];
    welcomeScreen.hidden = messages.length > 0;
    clearChatBtn.hidden = messages.length === 0;
    clearChatBtn.disabled = Boolean(
        conversation && pendingConversationIds.has(conversation.id)
    );

    messages.forEach((message, index) => {
        messagesContainer.appendChild(createMessageElement(
            message, index, messages.length, conversation
        ));
    });

    if (conversation && pendingConversationIds.has(conversation.id)) {
        messagesContainer.appendChild(createTypingIndicator());
    }

    updateComposerState();
    scrollToBottom("instant");
}

function createMessageElement(message, index, total, conversation) {
    const row = document.createElement("article");
    row.className = `message-row ${message.role}`;

    const avatar = document.createElement("div");
    avatar.className = "message-avatar";
    avatar.setAttribute("aria-hidden", "true");
    avatar.textContent = message.role === "user" ? "Y" : "S";

    const content = document.createElement("div");
    content.className = "message-content";

    const header = document.createElement("div");
    header.className = "message-header";

    const name = document.createElement("span");
    name.className = "message-name";
    name.textContent = message.role === "user" ? "You" : "SupportGPT";

    const timestamp = formatTime(message.timestamp);
    const time = document.createElement("time");
    time.className = "message-time";
    time.dateTime = message.timestamp;
    time.title = timestamp.full;
    time.textContent = timestamp.short;
    header.append(name, time);

    const bubble = document.createElement("div");
    bubble.className = "message-bubble";
    if (message.role === "assistant") {
        renderMarkdown(message.content, bubble);
    } else {
        bubble.textContent = message.content;
    }

    content.append(header, bubble);

    if (message.role === "assistant") {
        const actions = document.createElement("div");
        actions.className = "message-actions";
        const copyButton = createMessageAction("Copy", "Copy response");
        copyButton.addEventListener("click", () => copyMessage(message.content, copyButton));
        actions.appendChild(copyButton);

        if (index === total - 1) {
            const retryButton = createMessageAction(
                message.error ? "Try again" : "Regenerate",
                message.error ? "Retry response" : "Regenerate response"
            );
            retryButton.addEventListener("click", () => regenerateResponse(conversation));
            actions.appendChild(retryButton);
        }
        content.appendChild(actions);
    }

    row.append(avatar, content);
    return row;
}

function createMessageAction(text, label) {
    const button = document.createElement("button");
    button.className = "message-action-btn";
    button.type = "button";
    button.textContent = text;
    button.setAttribute("aria-label", label);
    return button;
}

function createTypingIndicator() {
    const row = document.createElement("div");
    row.className = "message-row assistant";
    row.id = "typingIndicator";
    row.setAttribute("role", "status");
    row.setAttribute("aria-label", "SupportGPT is typing");

    const avatar = document.createElement("div");
    avatar.className = "message-avatar";
    avatar.setAttribute("aria-hidden", "true");
    avatar.textContent = "S";

    const content = document.createElement("div");
    content.className = "message-content";
    const name = document.createElement("div");
    name.className = "message-name";
    name.textContent = "SupportGPT is typing";

    const indicator = document.createElement("div");
    indicator.className = "typing-indicator";
    indicator.setAttribute("aria-hidden", "true");
    for (let index = 0; index < 3; index += 1) {
        indicator.appendChild(document.createElement("span"));
    }

    content.append(name, indicator);
    row.append(avatar, content);
    return row;
}

async function copyMessage(text, button) {
    try {
        await navigator.clipboard.writeText(text);
        button.textContent = "Copied!";
        showToast("Response copied to clipboard.");
        window.setTimeout(() => { button.textContent = "Copy"; }, 1600);
    } catch (error) {
        console.error("Could not copy response:", error);
        showToast("Copy is unavailable in this browser.");
    }
}

function appendInlineMarkdown(parent, text) {
    const tokenPattern = /(\[[^\]]+\]\((?:[^()]|\([^()]*\))*\)|\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*|https?:\/\/[^\s<>]+)/g;
    let cursor = 0;

    for (const match of text.matchAll(tokenPattern)) {
        const token = match[0];
        const start = match.index;
        if (start > cursor) {
            parent.appendChild(document.createTextNode(text.slice(cursor, start)));
        }

        if (token.startsWith("[") && token.includes("](")) {
            const linkMatch = token.match(/^\[([^\]]+)\]\((.*)\)$/);
            if (linkMatch) {
                appendSafeLink(parent, linkMatch[1], linkMatch[2]);
            } else {
                parent.appendChild(document.createTextNode(token));
            }
        } else if (token.startsWith("**")) {
            const strong = document.createElement("strong");
            strong.textContent = token.slice(2, -2);
            parent.appendChild(strong);
        } else if (token.startsWith("*")) {
            const emphasis = document.createElement("em");
            emphasis.textContent = token.slice(1, -1);
            parent.appendChild(emphasis);
        } else if (token.startsWith("`")) {
            const code = document.createElement("code");
            code.textContent = token.slice(1, -1);
            parent.appendChild(code);
        } else {
            appendSafeLink(parent, token, token);
        }
        cursor = start + token.length;
    }

    if (cursor < text.length) {
        parent.appendChild(document.createTextNode(text.slice(cursor)));
    }
}

function appendSafeLink(parent, label, href) {
    let parsed;
    try {
        parsed = new URL(href);
    } catch {
        parent.appendChild(document.createTextNode(label));
        return;
    }

    if (!["http:", "https:"].includes(parsed.protocol)) {
        parent.appendChild(document.createTextNode(label));
        return;
    }

    const link = document.createElement("a");
    link.href = parsed.href;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = label;
    parent.appendChild(link);
}

function renderMarkdown(source, container) {
    const lines = source.replace(/\r\n?/g, "\n").split("\n");
    let paragraph = [];
    let list = null;

    const flushParagraph = () => {
        if (paragraph.length === 0) return;
        const element = document.createElement("p");
        paragraph.forEach((line, index) => {
            if (index > 0) element.appendChild(document.createElement("br"));
            appendInlineMarkdown(element, line);
        });
        container.appendChild(element);
        paragraph = [];
    };

    const flushList = () => {
        if (list) container.appendChild(list.element);
        list = null;
    };

    for (let index = 0; index < lines.length; index += 1) {
        const line = lines[index];
        if (line.trim().startsWith("```")) {
            flushParagraph();
            flushList();
            const codeLines = [];
            index += 1;
            while (index < lines.length && !lines[index].trim().startsWith("```")) {
                codeLines.push(lines[index]);
                index += 1;
            }
            const pre = document.createElement("pre");
            const code = document.createElement("code");
            code.textContent = codeLines.join("\n");
            pre.appendChild(code);
            container.appendChild(pre);
            continue;
        }

        const headingMatch = line.match(/^(#{1,3})\s+(.+)$/);
        if (headingMatch) {
            flushParagraph();
            flushList();
            const heading = document.createElement(`h${headingMatch[1].length + 1}`);
            appendInlineMarkdown(heading, headingMatch[2]);
            container.appendChild(heading);
            continue;
        }

        const listMatch = line.match(/^\s*(?:([-*+])|(\d+)[.)])\s+(.+)$/);
        if (listMatch) {
            flushParagraph();
            const type = listMatch[2] ? "ol" : "ul";
            if (!list || list.type !== type) {
                flushList();
                list = { type, element: document.createElement(type) };
                if (type === "ol" && Number(listMatch[2]) > 1) {
                    list.element.start = Number(listMatch[2]);
                }
            }
            const item = document.createElement("li");
            appendInlineMarkdown(item, listMatch[3]);
            list.element.appendChild(item);
            continue;
        }

        if (!line.trim()) {
            flushParagraph();
            flushList();
            continue;
        }

        flushList();
        paragraph.push(line);
    }
    flushParagraph();
    flushList();
}

function saveDraft() {
    const conversation = getActiveConversation();
    if (!conversation) return;
    conversation.draft = messageInput.value;
    saveConversations();
}

function resizeInput() {
    messageInput.style.height = "auto";
    messageInput.style.height = `${Math.min(messageInput.scrollHeight, 128)}px`;
}

function updateComposerState() {
    const isPending = activeConversationId
        ? pendingConversationIds.has(activeConversationId)
        : false;
    const hasText = Boolean(messageInput.value.trim());
    sendBtn.disabled = isPending || !hasText;
    sendBtn.classList.toggle("is-loading", isPending);
    sendBtn.setAttribute("aria-label", isPending ? "SupportGPT is responding" : "Send message");
    messageInput.setAttribute("aria-busy", String(isPending));
    characterCount.textContent = `${messageInput.value.length} / ${MAX_MESSAGE_LENGTH}`;
    characterCount.classList.toggle(
        "near-limit",
        messageInput.value.length >= MAX_MESSAGE_LENGTH * 0.9
    );
}

async function sendMessage(rawMessage) {
    const message = rawMessage.trim();
    if (!message || message.length > MAX_MESSAGE_LENGTH) return;

    let conversation = getActiveConversation();
    if (!conversation) conversation = createConversation();
    if (pendingConversationIds.has(conversation.id)) return;

    const userMessage = {
        role: "user",
        content: message,
        timestamp: new Date().toISOString()
    };
    conversation.messages.push(userMessage);
    if (conversation.messages.filter(item => item.role === "user").length === 1) {
        conversation.title = message.length > 36
            ? `${message.slice(0, 36).trimEnd()}…`
            : message;
    }
    conversation.draft = "";
    updateConversationTimestamp(conversation);
    saveConversations();
    renderConversationList();
    messageInput.value = "";
    resizeInput();
    updateComposerState();
    if (activeConversationId === conversation.id) renderMessages();

    await requestAssistantResponse(conversation, message);
}

async function requestAssistantResponse(conversation, message) {
    if (pendingConversationIds.has(conversation.id)) return;
    pendingConversationIds.add(conversation.id);
    if (activeConversationId === conversation.id) renderMessages();

    try {
        const payload = { message };
        if (conversation.sessionId) payload.session_id = conversation.sessionId;

        const response = await fetch(API_URL, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            let detail = "";
            try {
                const errorData = await response.json();
                detail = typeof errorData.detail === "string" ? errorData.detail : "";
            } catch {
                detail = "";
            }
            throw new Error(detail || `Support service returned ${response.status}`);
        }

        const data = await response.json();
        if (typeof data.response !== "string" || !data.response.trim()) {
            throw new Error("Support service returned an empty response.");
        }

        conversation.sessionId = typeof data.session_id === "string"
            ? data.session_id
            : conversation.sessionId;
        conversation.messages.push({
            role: "assistant",
            content: data.response,
            timestamp: new Date().toISOString()
        });
        updateConversationTimestamp(conversation);
    } catch (error) {
        console.error("SupportGPT request failed:", error);
        conversation.messages.push({
            role: "assistant",
            content: "I couldn’t reach SupportGPT just now. Check your connection and try again.",
            timestamp: new Date().toISOString(),
            error: true
        });
        updateConversationTimestamp(conversation);
        showToast("SupportGPT is temporarily unavailable. Your message is saved.");
    } finally {
        pendingConversationIds.delete(conversation.id);
        saveConversations();
        renderConversationList();
        if (activeConversationId === conversation.id) {
            renderMessages();
            messageInput.focus();
        } else {
            updateComposerState();
        }
    }
}

async function regenerateResponse(conversation) {
    if (!conversation || pendingConversationIds.has(conversation.id)) return;
    const lastMessage = conversation.messages[conversation.messages.length - 1];
    if (!lastMessage || lastMessage.role !== "assistant") return;
    const previousUserMessage = [...conversation.messages]
        .reverse()
        .find(message => message.role === "user");
    if (!previousUserMessage) return;

    conversation.messages.pop();
    saveConversations();
    if (activeConversationId === conversation.id) renderMessages();
    await requestAssistantResponse(conversation, previousUserMessage.content);
}

function scrollToBottom(behavior = "smooth") {
    const chatArea = document.getElementById("chatArea");
    chatArea.scrollTo({ top: chatArea.scrollHeight, behavior });
}

function setSidebarOpen(isOpen) {
    sidebar.classList.toggle("open", isOpen);
    sidebarScrim.hidden = !isOpen;
    mobileMenuBtn.setAttribute("aria-expanded", String(isOpen));
    mobileMenuBtn.setAttribute("aria-label",
        isOpen ? "Close conversation menu" : "Open conversation menu");
}

function closeSidebar() {
    setSidebarOpen(false);
}

function applyTheme(theme) {
    const isDark = theme === "dark";
    document.body.classList.toggle("theme-dark", isDark);
    themeToggle.querySelector(".theme-icon").textContent = isDark ? "☀" : "☾";
    themeToggle.querySelector(".theme-label").textContent =
        isDark ? "Light mode" : "Dark mode";
    themeToggle.setAttribute("aria-label",
        isDark ? "Switch to light mode" : "Switch to dark mode");
}

function toggleTheme() {
    const nextTheme = document.body.classList.contains("theme-dark") ? "light" : "dark";
    applyTheme(nextTheme);
    try {
        localStorage.setItem(THEME_KEY, nextTheme);
    } catch (error) {
        console.error("Could not save theme preference:", error);
        showToast("Theme preference could not be saved.");
    }
}

function updateConnectionStatus(isOnline) {
    const state = isOnline ? "online" : "offline";
    const label = isOnline ? "SupportGPT is online" : "SupportGPT is unavailable";
    [onlineBadge, sidebarServiceStatus].forEach(element => {
        element.dataset.state = state;
        element.querySelector(".status-label").textContent = label;
    });
}

async function checkConnection() {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 5000);
    try {
        const response = await fetch(HEALTH_URL, {
            headers: { "Accept": "application/json" },
            signal: controller.signal
        });
        if (!response.ok) throw new Error(`Health check returned ${response.status}`);
        const health = await response.json();
        updateConnectionStatus(health.status === "healthy" && health.model_loaded === true);
    } catch (error) {
        updateConnectionStatus(false);
    } finally {
        window.clearTimeout(timeout);
    }
}

chatForm.addEventListener("submit", event => {
    event.preventDefault();
    if (!sendBtn.disabled) sendMessage(messageInput.value);
});

messageInput.addEventListener("input", () => {
    resizeInput();
    updateComposerState();
    saveDraft();
});

messageInput.addEventListener("keydown", event => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
        event.preventDefault();
        chatForm.requestSubmit();
    }
});

newChatBtn.addEventListener("click", startNewChat);
clearConversationsBtn.addEventListener("click", clearAllConversations);
clearChatBtn.addEventListener("click", clearActiveConversation);
mobileMenuBtn.addEventListener("click", () => {
    setSidebarOpen(!sidebar.classList.contains("open"));
});
sidebarScrim.addEventListener("click", closeSidebar);
themeToggle.addEventListener("click", toggleTheme);
document.querySelectorAll(".suggestion-card").forEach(card => {
    card.addEventListener("click", () => {
        const message = card.dataset.message;
        if (message) sendMessage(message);
    });
});
document.addEventListener("keydown", event => {
    if (event.key === "Escape" && sidebar.classList.contains("open")) {
        closeSidebar();
        mobileMenuBtn.focus();
    }
});

function initializeApp() {
    if (!conversations.some(item => item.id === activeConversationId)) {
        const mostRecent = [...conversations].sort(
            (left, right) => Date.parse(right.updatedAt) - Date.parse(left.updatedAt)
        )[0];
        activeConversationId = mostRecent ? mostRecent.id : null;
    }

    let savedTheme = "light";
    try {
        savedTheme = localStorage.getItem(THEME_KEY) === "dark" ? "dark" : "light";
    } catch (error) {
        console.error("Could not restore theme preference:", error);
    }
    applyTheme(savedTheme);

    renderConversationList();
    renderMessages();
    const conversation = getActiveConversation();
    messageInput.value = conversation ? conversation.draft : "";
    resizeInput();
    updateComposerState();
    checkConnection();
    window.setInterval(checkConnection, 30000);
}

initializeApp();
