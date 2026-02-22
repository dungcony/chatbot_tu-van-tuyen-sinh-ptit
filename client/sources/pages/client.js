/**
 * Client Chat - Trợ lý Tư vấn Tuyển sinh
 * Cấu trúc: DOM refs → Session → UI helpers → API → Form handler → Init
 */
(function () {
    "use strict";

    // ─── DOM References ─────────────────────────────────────────
    const $ = {
        chat: document.getElementById("chat-container"),
        welcome: document.getElementById("welcome"),
        form: document.getElementById("input-form"),
        input: document.getElementById("message-input"),
        sendBtn: document.getElementById("send-btn"),
    };

    // ─── Session ─────────────────────────────────────────────────
    const sessionId = "sess_" + Math.random().toString(36).slice(2, 11);

    // ─── Format nội dung (Markdown đơn giản) ─────────────────────
    function formatContent(text, isBot) {
        let html = text.replace(/\n/g, "<br>");
        if (isBot) {
            html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
        }
        return html;
    }

    // ─── Build HTML nguồn tham khảo ──────────────────────────────
    function buildSourcesHtml(sources) {
        const links = sources
            .filter((s) => s.source_url || s.source_title)
            .map((s) =>
                s.source_url
                    ? `<a href="${s.source_url}" target="_blank" rel="noopener">${s.source_title || "Xem nguồn"}</a>`
                    : s.source_title
            )
            .filter(Boolean);
        if (links.length === 0) return "";
        return '<div class="sources-title">Nguồn tham khảo:</div>' + links.join(" · ");
    }

    // ─── Thêm tin nhắn vào chat ───────────────────────────────────
    function addMessage(content, role, sources = []) {
        $.welcome.style.display = "none";

        const div = document.createElement("div");
        div.className = "message " + role;
        div.innerHTML = formatContent(content, role === "bot");

        const sourcesHtml = buildSourcesHtml(sources);
        if (sourcesHtml) {
            const srcDiv = document.createElement("div");
            srcDiv.className = "sources";
            srcDiv.innerHTML = sourcesHtml;
            div.appendChild(srcDiv);
        }

        $.chat.appendChild(div);
        $.chat.scrollTop = $.chat.scrollHeight;
    }

    // ─── Typing indicator ────────────────────────────────────────
    function showTyping() {
        const div = document.createElement("div");
        div.className = "message bot typing-indicator";
        div.id = "typing-msg";
        div.innerHTML = '<div class="typing"><span></span><span></span><span></span></div>';
        $.chat.appendChild(div);
        $.chat.scrollTop = $.chat.scrollHeight;
    }

    function hideTyping() {
        document.getElementById("typing-msg")?.remove();
    }

    // ─── API: Gửi tin nhắn ───────────────────────────────────────
    async function sendChat(message) {
        const res = await fetch("/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message, session_id: sessionId }),
        });
        return res.json();
    }

    // ─── Xử lý gửi form ─────────────────────────────────────────
    async function onFormSubmit(e) {
        e.preventDefault();
        const msg = $.input.value.trim();
        if (!msg) return;

        addMessage(msg, "user");
        $.input.value = "";
        $.sendBtn.disabled = true;
        showTyping();

        try {
            const data = await sendChat(msg);
            hideTyping();
            if (data.error) {
                addMessage("Xin lỗi, đã xảy ra lỗi. Vui lòng thử lại.", "bot");
            } else {
                addMessage(data.answer, "bot", data.sources || []);
            }
        } catch (err) {
            hideTyping();
            addMessage("Không thể kết nối. Vui lòng kiểm tra mạng và thử lại.", "bot");
        }
        $.sendBtn.disabled = false;
    }

    // ─── Init ────────────────────────────────────────────────────
    $.form.addEventListener("submit", onFormSubmit);
})();
