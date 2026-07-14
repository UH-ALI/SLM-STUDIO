(function () {
  "use strict";
  // document.currentScript only reliably points at this <script> tag while it
  // is executing synchronously during initial parse — it becomes null if the
  // tag has async/defer, or if a CMS/tag-manager/page-builder injects it
  // dynamically (very common for "paste this snippet anywhere" embeds, and
  // something page owners often do deliberately so a chat widget doesn't
  // block their page load). Falling back to a selector match on the
  // data-deploy-key attribute means the widget finds itself correctly
  // regardless of how the host page chose to load it.
  const scriptTag =
    document.currentScript ||
    document.querySelector('script[data-deploy-key][src*="widget.js"]');
  if (!scriptTag) {
    console.error("[SLM Widget] Could not locate the widget's own <script> tag.");
    return;
  }
  const deployKey = scriptTag.getAttribute("data-deploy-key");
  const apiBase = new URL(scriptTag.src, window.location.href).origin;

  if (!deployKey) {
    console.error("[SLM Widget] Missing data-deploy-key attribute.");
    return;
  }

  /* ───── State ───── */
  let config = {
    title: "Assistant",
    greeting: "Hi! Ask me anything.",
    primaryColor: "#4F46E5",
    bodyColor: "#FFFFFF",
    dotsColor: "#9CA3AF",
    botMessageColor: "#2A3441",
    userMessageColor: "#4F46E5",
    chatInputColor: "#FFFFFF",
    position: "bottom-right",
  };
  let isOpen = false;
  let messages = [];
  let isStreaming = false;

  /* ───── Host + Shadow DOM ───── */
  const host = document.createElement("div");
  host.id = "slm-widget-host";
  document.body.appendChild(host);
  const shadow = host.attachShadow({ mode: "open" });

  /* ───── Color Helpers ───── */
  function hexToHSL(hex) {
    hex = hex.replace("#", "");
    const r = parseInt(hex.substring(0, 2), 16) / 255;
    const g = parseInt(hex.substring(2, 4), 16) / 255;
    const b = parseInt(hex.substring(4, 6), 16) / 255;
    const max = Math.max(r, g, b), min = Math.min(r, g, b);
    let h, s, l = (max + min) / 2;
    if (max === min) { h = s = 0; }
    else {
      const d = max - min;
      s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
      if (max === r) h = ((g - b) / d + (g < b ? 6 : 0)) / 6;
      else if (max === g) h = ((b - r) / d + 2) / 6;
      else h = ((r - g) / d + 4) / 6;
    }
    return { h: Math.round(h * 360), s: Math.round(s * 100), l: Math.round(l * 100) };
  }

  function darken(hex, amount) {
    const hsl = hexToHSL(hex);
    return `hsl(${hsl.h}, ${hsl.s}%, ${Math.max(0, hsl.l - amount)}%)`;
  }

  function getContrastColor(hex) {
    if (!hex || !/^#[0-9A-Fa-f]{6}$/i.test(hex)) return '#FFFFFF';
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
    return luminance > 0.5 ? '#111827' : '#FFFFFF';
  }

  /* ───── SVG Icons ───── */
  const chatSVG = `<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>`;
  const closeSVG = `<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>`;
  const sendSVG = `<svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>`;
  const botSVG = `<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="10" opacity="0.15"/><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 15h-2v-2h2v2zm0-4h-2V7h2v6zm4 4h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg>`;

  /* ───── Render ───── */
  function render() {
    const side = config.position === "bottom-left" ? "left: 20px;" : "right: 20px;";
    const panelSide = config.position === "bottom-left" ? "left: 20px;" : "right: 20px;";
    const pc = config.primaryColor;
    const pcDark = darken(pc, 12);

    const bodyC = config.bodyColor || "#FFFFFF";
    const dotsC = config.dotsColor || "#9CA3AF";
    const botMsgC = config.botMessageColor || "#2A3441";
    const userMsgC = config.userMessageColor || pc;
    const inputC = config.chatInputColor || "#FFFFFF";

    const headerTextC = getContrastColor(pc);
    const bodyTextC = getContrastColor(bodyC);
    const botMsgTextC = getContrastColor(botMsgC);
    const userMsgTextC = getContrastColor(userMsgC);
    const inputBgC = inputC === "transparent" ? "transparent" : inputC;
    const inputTextC = getContrastColor(inputC);

    shadow.innerHTML = `
      <style>
        :host { all: initial; font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; }
        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

        .bubble {
          position: fixed; bottom: 20px; ${side}
          width: 60px; height: 60px; border-radius: 50%;
          background: linear-gradient(135deg, ${pc}, ${pcDark});
          color: ${headerTextC}; display: flex; align-items: center; justify-content: center;
          cursor: pointer; z-index: 999999;
          box-shadow: 0 4px 20px rgba(0,0,0,0.25), 0 0 0 0 ${pc}40;
          transition: transform 0.2s ease, box-shadow 0.2s ease;
        }
        .bubble:hover { transform: scale(1.08); box-shadow: 0 6px 28px rgba(0,0,0,0.3); }

        .panel {
          position: fixed; bottom: 92px; ${panelSide}
          width: 380px; min-width: 300px; max-width: calc(100vw - 24px);
          height: 520px; min-height: 380px; max-height: calc(100vh - 120px);
          background: ${bodyC}; border-radius: 16px;
          box-shadow: 0 12px 48px rgba(0,0,0,0.2), 0 2px 8px rgba(0,0,0,0.08);
          display: flex; flex-direction: column; overflow: hidden;
          resize: both;
          z-index: 999999;
          transform: translateY(${isOpen ? "0" : "20px"});
          opacity: ${isOpen ? "1" : "0"};
          pointer-events: ${isOpen ? "auto" : "none"};
          transition: transform 0.3s cubic-bezier(0.4,0,0.2,1), opacity 0.3s cubic-bezier(0.4,0,0.2,1);
        }

        .header {
          background: linear-gradient(135deg, ${pc}, ${pcDark});
          color: ${headerTextC}; padding: 16px 18px;
          font-weight: 600; font-size: 15px;
          display: flex; align-items: center; gap: 10px;
          flex-shrink: 0;
        }
        .header-icon {
          width: 32px; height: 32px; border-radius: 50%;
          background: rgba(255,255,255,0.2); display: flex;
          align-items: center; justify-content: center; flex-shrink: 0;
        }

        .body {
          flex: 1; overflow-y: auto; padding: 16px;
          background: ${bodyC};
          scroll-behavior: smooth;
        }
        .body::-webkit-scrollbar { width: 5px; }
        .body::-webkit-scrollbar-thumb { background: #d0d0d0; border-radius: 4px; }

        .welcome {
          text-align: center; color: ${bodyTextC}; opacity: 0.6; font-size: 14px;
          margin-top: 60px; line-height: 1.6;
        }

        .msg-row { display: flex; margin-bottom: 12px; gap: 8px; align-items: flex-end; }
        .msg-row.user { flex-direction: row-reverse; }

        .msg-avatar {
          width: 28px; height: 28px; border-radius: 50%; flex-shrink: 0;
          background: ${pc}18; color: ${pc};
          display: flex; align-items: center; justify-content: center;
        }
        .msg-row.user .msg-avatar { display: none; }

        .msg-bubble {
          max-width: 78%; padding: 10px 14px; font-size: 14px;
          line-height: 1.55; word-break: break-word;
          border-radius: 14px;
        }
        .msg-row.bot .msg-bubble {
          background: ${botMsgC}; color: ${botMsgTextC};
          border: 1px solid ${botMsgC.toLowerCase() === "#ffffff" ? "#e8e8e8" : darken(botMsgC, 10)};
          border-bottom-left-radius: 4px;
        }
        .msg-row.user .msg-bubble {
          background: ${userMsgC};
          color: ${userMsgTextC};
          border-bottom-right-radius: 4px;
        }

        .citations {
          font-size: 11px; color: #999; margin-top: 6px;
          padding-left: 36px;
        }
        .citations span {
          background: #f0f0f0; padding: 2px 6px; border-radius: 4px;
          margin-right: 4px; display: inline-block; margin-bottom: 2px;
        }

        .typing { display: flex; align-items: center; gap: 4px; padding: 10px 14px; background: ${botMsgC}; border: 1px solid ${botMsgC.toLowerCase() === "#ffffff" ? "#e8e8e8" : darken(botMsgC, 10)}; border-radius: 14px; border-bottom-left-radius: 4px; }
        .typing-dot {
          width: 6px; height: 6px; border-radius: 50%;
          background: ${dotsC};
          animation: typingBounce 1.2s ease-in-out infinite;
          opacity: 0.7;
        }
        .typing-dot:nth-child(2) { animation-delay: 0.15s; }
        .typing-dot:nth-child(3) { animation-delay: 0.3s; }
        @keyframes typingBounce {
          0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
          30% { transform: translateY(-6px); opacity: 1; }
        }

        .input-row {
          display: flex; align-items: center;
          border-top: 1px solid ${darken(bodyC, 8)}; background: ${bodyC};
          padding: 8px 12px; gap: 8px; flex-shrink: 0;
        }
        .input-row input {
          flex: 1; border: 1px solid ${darken(bodyC, 15)}; border-radius: 24px;
          padding: 10px 16px; font-size: 14px; outline: none;
          font-family: inherit; background: ${inputBgC}; color: ${inputTextC};
          transition: border-color 0.2s;
        }
        .input-row input:focus { border-color: ${pc}; }
        .input-row input::placeholder { color: #bbb; }

        .send-btn {
          width: 40px; height: 40px; border-radius: 50%;
          background: linear-gradient(135deg, ${pc}, ${pcDark});
          color: ${headerTextC}; border: none; cursor: pointer;
          display: flex; align-items: center; justify-content: center;
          transition: transform 0.15s ease, opacity 0.15s;
          flex-shrink: 0;
        }
        .send-btn:hover { transform: scale(1.06); }
        .send-btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }

        .footer {
          text-align: center; padding: 6px; font-size: 10px; color: #bbb;
          background: #fff; border-top: 1px solid #f0f0f0;
          flex-shrink: 0;
        }
        .footer a { color: #aaa; text-decoration: none; }
        .footer a:hover { color: ${pc}; }
      </style>

      <div class="bubble" id="slm-bubble">${isOpen ? closeSVG : chatSVG}</div>
      <div class="panel" id="slm-panel">
        <div class="header">
          <div class="header-icon">${botSVG}</div>
          <span>${escapeHtml(config.title || "")}</span>
        </div>
        <div class="body" id="slm-body"></div>
        <div class="input-row">
          <input id="slm-input" type="text" placeholder="Type a message..." ${isStreaming ? "disabled" : ""} />
          <button class="send-btn" id="slm-send" ${isStreaming ? "disabled" : ""}>${sendSVG}</button>
        </div>
        <div class="footer">Powered by <a href="#" onclick="return false;">SLM Studio</a></div>
      </div>
    `;

    renderMessages();
    bindEvents();
  }

  function renderMessages() {
    const body = shadow.getElementById("slm-body");
    if (!body) return;

    if (messages.length === 0) {
      body.innerHTML = `<div class="welcome">${escapeHtml(config.greeting)}</div>`;
      return;
    }

    let html = "";
    for (const m of messages) {
      if (m.role === "bot" && !m.text && isStreaming) continue;
      html += `<div class="msg-row ${m.role}">`;
      if (m.role === "bot") html += `<div class="msg-avatar">${botSVG}</div>`;
      const cleanText = (m.text || "").replace(/\[?[Ss]ources?:?\s*(\[.*?\]|[^.\n\]]+\]?)/g, "").trim();
      html += `<div class="msg-bubble">${escapeHtml(cleanText)}</div>`;
      html += `</div>`;
    }

    const lastMsg = messages[messages.length - 1];
    const showTyping = isStreaming && (!lastMsg || lastMsg.role !== "bot" || !lastMsg.text);
    if (showTyping) {
      html += `<div class="msg-row bot"><div class="msg-avatar">${botSVG}</div><div class="typing"><div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div></div></div>`;
    }

    body.innerHTML = html;
    body.scrollTop = body.scrollHeight;
  }

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  function bindEvents() {
    const bubble = shadow.getElementById("slm-bubble");
    const sendBtn = shadow.getElementById("slm-send");
    const input = shadow.getElementById("slm-input");

    if (bubble) bubble.onclick = () => { isOpen = !isOpen; render(); if (isOpen && input) input.focus(); };
    if (sendBtn) sendBtn.onclick = sendMessage;
    if (input) input.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); } });
  }

  /* ───── Send Message (SSE Streaming) ───── */
  async function sendMessage() {
    const input = shadow.getElementById("slm-input");
    if (!input) return;
    const text = input.value.trim();
    if (!text || isStreaming) return;

    input.value = "";
    messages.push({ role: "user", text });
    isStreaming = true;
    renderMessages();

    let botText = "";
    let citations = [];

    try {
      const res = await fetch(`${apiBase}/deploy/${deployKey}/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Error ${res.status}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      // Add placeholder bot message
      messages.push({ role: "bot", text: "", citations: [] });

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const event = JSON.parse(line.slice(6));
            if (event.token) {
              botText += event.token;
              messages[messages.length - 1].text = botText;
              renderMessages();
            }
            if (event.citations) {
              citations = event.citations;
            }
            if (event.error) {
              botText = "Sorry, something went wrong. Please try again.";
              messages[messages.length - 1].text = botText;
            }
          } catch (e) { /* skip malformed lines */ }
        }
      }

      messages[messages.length - 1].citations = citations;

    } catch (e) {
      if (botText === "") {
        messages.push({ role: "bot", text: "Sorry, something went wrong. Please try again.", citations: [] });
      } else {
        // Stream started and some tokens already arrived, then the connection
        // dropped mid-response. Without this branch the partial message was
        // left permanently as-is with no indication anything went wrong —
        // the user would see the bot appear to just stop talking.
        messages[messages.length - 1].text = botText + "\n\n[Connection interrupted]";
      }
    }

    isStreaming = false;
    renderMessages();
    const input2 = shadow.getElementById("slm-input");
    if (input2) input2.focus();
  }

  /* ───── Init: Fetch Config & Render ───── */
  fetch(`${apiBase}/deploy/${deployKey}/config`)
    .then(r => { if (!r.ok) throw new Error(); return r.json(); })
    .then(cfg => { config = { ...config, ...cfg }; render(); })
    .catch(() => render());
})();
