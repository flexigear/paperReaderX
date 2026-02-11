/* Paper X-ray Web - Frontend Logic */

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

let state = {
  currentPaper: null,  // { id, title, page_count, ... }
  currentPage: 0,
  currentLang: "en",
  papers: [],
};

// === Tab Navigation ===

$$(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    $$(".tab").forEach((b) => b.classList.remove("active"));
    $$(".tab-content").forEach((c) => c.classList.remove("active"));
    btn.classList.add("active");
    $(`#tab-${btn.dataset.tab}`).classList.add("active");
  });
});

// === File Upload ===

const dropZone = $("#drop-zone");
const fileInput = $("#file-input");
const uploadStatus = $("#upload-status");

dropZone.addEventListener("click", () => fileInput.click());
dropZone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropZone.classList.add("dragover");
});
dropZone.addEventListener("dragleave", () => dropZone.classList.remove("dragover"));
dropZone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropZone.classList.remove("dragover");
  const files = e.dataTransfer.files;
  if (files.length > 0) uploadFile(files[0]);
});
fileInput.addEventListener("change", () => {
  if (fileInput.files.length > 0) uploadFile(fileInput.files[0]);
});

async function uploadFile(file) {
  if (!file.name.toLowerCase().endsWith(".pdf")) {
    showStatus(uploadStatus, "Only PDF files accepted", "error");
    return;
  }
  showStatus(uploadStatus, '<span class="spinner"></span>Uploading...', "info");

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch("/api/upload", { method: "POST", body: formData });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Upload failed");

    if (data.is_duplicate) {
      showStatus(uploadStatus, `Already exists: "${data.title}"`, "info");
    } else {
      showStatus(uploadStatus, `Uploaded: "${data.title}" - Analysis started`, "success");
    }
    await loadPapers();
    selectPaper(data.paper_id);
  } catch (err) {
    showStatus(uploadStatus, `Error: ${err.message}`, "error");
  }
}

function showStatus(el, html, type) {
  el.innerHTML = html;
  el.className = `status-msg ${type}`;
  el.hidden = false;
}

// === Paper List (UPLOAD tab) ===

async function loadPapers() {
  try {
    const res = await fetch("/api/papers");
    state.papers = await res.json();
    renderPaperList();
  } catch (err) {
    console.error("Failed to load papers:", err);
  }
}

function renderPaperList() {
  const list = $("#paper-list");
  if (state.papers.length === 0) {
    list.innerHTML = '<div class="empty-state">No papers uploaded yet</div>';
    return;
  }
  list.innerHTML = state.papers.map((p) => {
    const selected = state.currentPaper?.id === p.id ? "selected" : "";
    const date = new Date(p.created_at).toLocaleDateString();
    return `
      <div class="paper-item ${selected}" data-id="${p.id}">
        <span class="title">${esc(p.title || p.filename)}</span>
        <div style="display:flex;align-items:center">
          <span class="meta">${date}</span>
          <button class="delete-btn" data-id="${p.id}" title="Delete"><svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M2 3h10M5 3V2h4v1M3 3v9h8V3M6 5.5v4.5M8 5.5v4.5"/></svg></button>
        </div>
      </div>`;
  }).join("");

  $$(".paper-item").forEach((el) => {
    el.addEventListener("click", (e) => {
      if (e.target.closest(".delete-btn")) return;
      selectPaper(el.dataset.id);
    });
  });

  $$(".delete-btn").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      deletePaper(btn.dataset.id);
    });
  });
}

async function deletePaper(paperId) {
  if (!confirm("Delete this paper and all its analysis results?")) return;
  try {
    const res = await fetch(`/api/papers/${paperId}`, { method: "DELETE" });
    if (!res.ok) throw new Error("Delete failed");
    if (state.currentPaper?.id === paperId) {
      state.currentPaper = null;
      $("#no-paper-msg").hidden = false;
      $("#pdf-controls").hidden = true;
      $("#pdf-page-img").src = "";
      $("#no-result-msg").hidden = false;
      $("#results-panel").hidden = true;
    }
    await loadPapers();
  } catch (err) {
    console.error("Failed to delete paper:", err);
  }
}

// === Select Paper ===

async function selectPaper(paperId) {
  try {
    const res = await fetch(`/api/papers/${paperId}`);
    if (!res.ok) return;
    state.currentPaper = await res.json();
    state.currentPage = 0;
    onPaperSelected();
  } catch (err) {
    console.error("Failed to select paper:", err);
  }
}

function onPaperSelected() {
  // Update paper list selection
  $$(".paper-item").forEach((el) => {
    el.classList.toggle("selected", el.dataset.id === state.currentPaper.id);
  });

  // Load PDF in PAPER tab
  $("#no-paper-msg").hidden = true;
  $("#pdf-controls").hidden = false;
  loadPage(0);

  // Show results panel
  $("#no-result-msg").hidden = true;
  $("#results-panel").hidden = false;
  $("#detail-title").textContent = state.currentPaper.title || "Untitled";
  loadResult(state.currentLang);
  loadChatHistory();
}

// === PDF Viewer ===

function loadPage(pageNum) {
  const paper = state.currentPaper;
  if (!paper) return;
  state.currentPage = pageNum;
  const img = $("#pdf-page-img");
  img.src = `/api/papers/${paper.id}/page/${pageNum}`;
  $("#page-info").textContent = `${pageNum + 1} / ${paper.page_count}`;
  $("#prev-page").disabled = pageNum <= 0;
  $("#next-page").disabled = pageNum >= paper.page_count - 1;
}

$("#prev-page").addEventListener("click", () => {
  if (state.currentPage > 0) loadPage(state.currentPage - 1);
});
$("#next-page").addEventListener("click", () => {
  if (state.currentPaper && state.currentPage < state.currentPaper.page_count - 1)
    loadPage(state.currentPage + 1);
});

// === Results ===

let resultEventSource = null;

$$(".lang-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    $$(".lang-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    state.currentLang = btn.dataset.lang;
    loadResult(state.currentLang);
  });
});

async function loadResult(lang) {
  const paper = state.currentPaper;
  if (!paper) return;

  if (resultEventSource) {
    resultEventSource.close();
    resultEventSource = null;
  }

  const statusEl = $("#result-status");
  const contentEl = $("#result-content");
  contentEl.innerHTML = "";
  showStatus(statusEl, '<span class="spinner"></span>Loading...', "info");

  try {
    const res = await fetch(`/api/papers/${paper.id}/result?lang=${lang}`);
    const contentType = res.headers.get("content-type") || "";

    if (contentType.includes("application/json")) {
      const data = await res.json();
      if (data.type === "complete") {
        contentEl.innerHTML = marked.parse(data.content);
        statusEl.hidden = true;
      } else if (data.type === "error") {
        showStatus(statusEl, data.message || "Analysis failed", "error");
      }
      return;
    }

    showStatus(statusEl, '<span class="spinner"></span>Analyzing...', "info");
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let accumulated = "";
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const lines = buffer.split("\n");
      buffer = lines.pop();

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        try {
          const data = JSON.parse(line.slice(6));
          if (data.type === "chunk") {
            accumulated += data.content;
            contentEl.innerHTML = marked.parse(accumulated);
          } else if (data.type === "status") {
            if (data.status === "done") {
              statusEl.hidden = true;
            } else if (data.status === "error") {
              showStatus(statusEl, "Analysis failed", "error");
            }
          }
        } catch {}
      }
    }

    if (accumulated) {
      statusEl.hidden = true;
    } else {
      showStatus(statusEl, "No content yet, analysis may still be starting...", "info");
    }
  } catch (err) {
    showStatus(statusEl, `Error: ${err.message}`, "error");
  }
}

// === Chat ===

const chatInput = $("#chat-input");
const chatSend = $("#chat-send");
const chatMessages = $("#chat-messages");

chatSend.addEventListener("click", sendChat);
chatInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendChat();
  }
});

async function loadChatHistory() {
  chatMessages.innerHTML = "";
}

async function sendChat() {
  const paper = state.currentPaper;
  if (!paper) return;

  const message = chatInput.value.trim();
  if (!message) return;

  chatInput.value = "";
  chatSend.disabled = true;

  appendChatMsg("user", message);
  const assistantEl = appendChatMsg("assistant", '<span class="spinner"></span>');

  try {
    const res = await fetch(`/api/papers/${paper.id}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let accumulated = "";
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const lines = buffer.split("\n");
      buffer = lines.pop();

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        try {
          const data = JSON.parse(line.slice(6));
          if (data.type === "chunk") {
            accumulated += data.content;
            assistantEl.innerHTML = marked.parse(accumulated);
          }
        } catch {}
      }
    }

    if (!accumulated) {
      assistantEl.textContent = "(No response)";
    }
  } catch (err) {
    assistantEl.textContent = `Error: ${err.message}`;
  }

  chatSend.disabled = false;
  chatInput.focus();
}

function appendChatMsg(role, html) {
  const div = document.createElement("div");
  div.className = `chat-msg ${role}`;
  div.innerHTML = html;
  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return div;
}

// === Utilities ===

function esc(str) {
  const d = document.createElement("div");
  d.textContent = str || "";
  return d.innerHTML;
}

// === Auto-refresh paper list ===

let refreshInterval = null;

function startAutoRefresh() {
  if (refreshInterval) return;
  refreshInterval = setInterval(loadPapers, 5000);
}

// === Init ===

loadPapers();
startAutoRefresh();
