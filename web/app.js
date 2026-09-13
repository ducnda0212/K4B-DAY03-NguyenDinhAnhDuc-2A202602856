const state = { mode: "agent", busy: false, status: null, tests: [], trace: [] };
const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

function escapeHTML(value = "") {
  return String(value).replace(/[&<>'"]/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"
  })[char]);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
  return payload;
}

function toast(message, type = "success") {
  const region = $("#toastRegion");
  const node = document.createElement("div");
  node.className = `toast ${type === "error" ? "error" : ""}`;
  node.textContent = message;
  region.appendChild(node);
  setTimeout(() => node.remove(), 3400);
}

function setRuntime(status) {
  state.status = status;
  const provider = status.provider || {};
  $("#runtimeBadge").classList.add("online");
  $("#runtimeText").textContent = `${provider.mode === "live" ? "LIVE" : "OFFLINE"} · ${provider.name}`;
  $("#sideStatusDot").classList.add("online");
  $("#sideStatusLabel").textContent = "MCP Server online";
  $("#sideStatusMeta").textContent = status.server?.name || "Connected";
  $("#metricProvider").textContent = provider.name?.replace("Provider", "") || "—";
  $("#metricModel").textContent = provider.model || "Unknown model";
  $("#metricTools").textContent = String(status.tool_count ?? 0).padStart(2, "0");
  $("#metricDocuments").textContent = String(status.document_count ?? 0).padStart(2, "0");
  $("#navToolCount").textContent = status.tool_count ?? 0;
  $("#chatContextModel").textContent = provider.model || provider.name;
}

function renderInventory(documents = []) {
  $("#inventoryGrid").innerHTML = documents.map((doc, index) => {
    const isAvailable = doc.status === "Có sẵn";
    const borrower = doc.borrower_name || "Chưa có người mượn";
    const due = doc.due_date || "—";
    return `
      <article class="document-card">
        <div class="document-top">
          <span class="document-id">${escapeHTML(doc.document_id)}</span>
          <span class="status-pill ${isAvailable ? "available" : "borrowed"}">${escapeHTML(doc.status)}</span>
        </div>
        <div class="book-spine" aria-hidden="true"></div>
        <h4>${escapeHTML(doc.title)}</h4>
        <p class="document-author">${escapeHTML(doc.author)} · ${escapeHTML(doc.category)}</p>
        <div class="document-meta">
          <div><span>Vị trí</span><strong title="${escapeHTML(doc.location)}">${escapeHTML(doc.location)}</strong></div>
          <div><span>Người mượn</span><strong title="${escapeHTML(borrower)}">${escapeHTML(borrower)}</strong></div>
          <div><span>Hạn trả</span><strong>${escapeHTML(due)}</strong></div>
          <div><span>Đặt trước</span><strong>${escapeHTML(doc.reserved_by || "Không có")}</strong></div>
        </div>
      </article>`;
  }).join("");
}

function renderTools(tools = []) {
  $("#toolGrid").innerHTML = tools.map((tool, index) => {
    const properties = tool.parameters?.properties || {};
    const required = new Set(tool.parameters?.required || []);
    const rows = Object.entries(properties).map(([name, schema]) => `
      <div class="schema-row">
        <span class="schema-name">${escapeHTML(name)}</span>
        <span class="schema-type">${escapeHTML(schema.type)}</span>
        <span class="schema-required">${required.has(name) ? "required" : "optional"}</span>
      </div>`).join("");
    return `
      <article class="tool-card">
        <div class="tool-card-head">
          <span class="tool-mark">${index === 0 ? "Q" : "R"}</span>
          <span class="tool-state">● ACTIVE</span>
        </div>
        <div class="tool-copy">
          <h4>${escapeHTML(tool.name)}</h4>
          <p>${escapeHTML(tool.description)}</p>
        </div>
        <div class="schema-list">${rows}</div>
        <div class="tool-footer"><span>JSON Schema</span><span>${Object.keys(properties).length} parameters · MCP</span></div>
      </article>`;
  }).join("");
}

function renderTests(tests = [], results = null) {
  const resultMap = new Map((results || []).map(result => [result.id, result]));
  $("#testList").innerHTML = tests.map(test => {
    const result = resultMap.get(test.id);
    const statusClass = result ? (result.passed ? "passed" : "failed") : "";
    const statusText = result ? (result.passed ? "PASS" : "FAIL") : "PENDING";
    const statusResultClass = result ? (result.passed ? "pass" : "fail") : "";
    return `
      <article class="test-item ${statusClass}">
        <span class="test-id">${escapeHTML(test.id)}</span>
        <div class="test-copy">
          <strong>${escapeHTML(test.question)}</strong>
          <p>${escapeHTML(result?.answer || test.expected_behavior)}</p>
        </div>
        <div class="test-tags">
          <span class="test-tag">${escapeHTML(test.type)}</span>
          <span class="test-tag">${escapeHTML(test.complexity)}</span>
        </div>
        <span class="test-result ${statusResultClass}">${statusText}</span>
      </article>`;
  }).join("");
}

function traceTitle(event) {
  if (event.action_type === "TOOL_EXECUTION") return `Action · ${event.tool_name || "Tool"}`;
  if (event.action_type === "FINAL_ANSWER") return "Final Answer";
  if (event.action_type === "ERROR") return "Execution Error";
  return event.action_type || "Trace Event";
}

function traceDescription(event) {
  if (event.action_type === "TOOL_EXECUTION") return event.thought || "Agent gọi công cụ qua MCP Server.";
  return event.output || event.thought || "Đã hoàn tất bước xử lý.";
}

function renderTrace(trace = [], totalLatency = null) {
  state.trace = trace;
  const toolCalls = trace.filter(event => event.action_type === "TOOL_EXECUTION").length;
  const latency = totalLatency ?? trace.reduce((sum, event) => sum + Number(event.latency_ms || 0), 0);
  $("#traceSteps").textContent = trace.length;
  $("#traceToolCalls").textContent = toolCalls;
  $("#traceLatency").textContent = Math.round(latency);

  if (!trace.length) {
    $("#traceList").innerHTML = `<div class="empty-state compact-empty"><span class="empty-glyph">⌁</span><strong>Chưa có trace</strong><p>Gửi một yêu cầu để quan sát luồng Thought → Action → Observation.</p></div>`;
    return;
  }

  $("#traceList").innerHTML = trace.map(event => {
    const kind = event.action_type === "TOOL_EXECUTION" ? "tool" : event.action_type === "FINAL_ANSWER" ? "final" : "error";
    const symbol = kind === "tool" ? "A" : kind === "final" ? "F" : "!";
    const details = event.action_type === "TOOL_EXECUTION"
      ? `<div class="trace-code">args ${escapeHTML(JSON.stringify(event.arguments || {}))}<br>obs ${escapeHTML(JSON.stringify(event.observation || {}))}</div>`
      : "";
    return `
      <article class="trace-event ${kind}">
        <span class="trace-marker">${symbol}</span>
        <div class="trace-event-header"><strong>${escapeHTML(traceTitle(event))}</strong><span>${Number(event.latency_ms || 0).toFixed(1)} ms</span></div>
        <p>${escapeHTML(traceDescription(event))}</p>
        ${details}
      </article>`;
  }).join("");
}

function appendMessage(role, content, options = {}) {
  const list = $("#messageList");
  const node = document.createElement("div");
  node.className = `message ${role === "user" ? "user-message" : "assistant-message"}`;
  if (options.id) node.id = options.id;
  const safeContent = options.loading
    ? `<div class="thinking-dots"><i></i><i></i><i></i></div>`
    : escapeHTML(content).replace(/\n/g, "<br>");
  node.innerHTML = `
    <div class="message-avatar">${role === "user" ? "U" : "AI"}</div>
    <div class="message-body">
      <div class="message-meta"><strong>${role === "user" ? "Bạn" : state.mode === "agent" ? "Library Agent" : "Chatbot Baseline"}</strong><span>vừa xong</span></div>
      <div class="message-bubble ${options.error ? "error" : ""}">${safeContent}</div>
    </div>`;
  list.appendChild(node);
  list.scrollTop = list.scrollHeight;
}async function sendMessage(query) {
  if (state.busy || !query.trim()) return;
  state.busy = true;
  const input = $("#chatInput");
  const send = $("#sendButton");
  appendMessage("user", query.trim());
  appendMessage("assistant", "", { loading: true, id: "thinkingMessage" });
  input.value = "";
  input.style.height = "auto";
  send.disabled = true;

  try {
    const result = await api("/api/chat", {
      method: "POST",
      body: JSON.stringify({ query: query.trim(), mode: state.mode })
    });
    $("#thinkingMessage")?.remove();
    appendMessage("assistant", result.answer);
    renderTrace(result.trace || [], result.latency_ms);
    if (state.mode === "agent") await loadInventory();
    toast(`${state.mode === "agent" ? "Agent" : "Chatbot"} phản hồi trong ${Math.round(result.latency_ms)} ms`);
  } catch (error) {
    $("#thinkingMessage")?.remove();
    appendMessage("assistant", error.message, { error: true });
    toast(error.message, "error");
  } finally {
    state.busy = false;
    send.disabled = false;
    input.focus();
  }
}

async function runTests() {
  const button = $("#runTestsButton");
  if (state.busy) return;
  state.busy = true;
  button.disabled = true;
  button.innerHTML = `Đang chạy test <span>•••</span>`;
  $("#testStatusLabel").textContent = "RUNNING";
  $("#testStatusTitle").textContent = "Agent đang thực thi test suite";
  $("#testStatusDescription").textContent = "Đang gọi Provider, MCP Server và Tool Backend...";
  $("#testProgressBar").style.width = "42%";

  try {
    const result = await api("/api/run-tests", { method: "POST", body: "{}" });
    const failed = result.total - result.passed;
    const score = result.total ? Math.round(result.passed / result.total * 100) : 0;
    $("#scoreRing").style.setProperty("--score", score);
    $("#scoreValue").textContent = `${result.passed}/${result.total}`;
    $("#testPassed").textContent = result.passed;
    $("#testFailed").textContent = failed;
    $("#testTraceEvents").textContent = result.trace_events;
    $("#testProgressBar").style.width = `${score}%`;
    $("#testStatusLabel").textContent = failed ? "REVIEW REQUIRED" : "ALL SYSTEMS PASS";
    $("#testStatusTitle").textContent = failed ? `${failed} test cần kiểm tra` : "Nghiệm thu Mock Offline thành công";
    $("#testStatusDescription").textContent = `Đã hoàn tất ${result.total} test case và ghi ${result.trace_events} sự kiện Waterfall Trace.`;
    $("#metricTests").textContent = `${result.passed}/${result.total}`;
    $("#metricTestState").textContent = failed ? "Có test cần kiểm tra" : "Tất cả test đã pass";
    renderTests(state.tests, result.results);
    const combined = result.results.flatMap(item => item.trace || []);
    renderTrace(combined);
    await loadInventory();
    toast(`Test Suite hoàn tất: ${result.passed}/${result.total} PASS`, failed ? "error" : "success");
  } catch (error) {
    $("#testStatusLabel").textContent = "EXECUTION ERROR";
    $("#testStatusTitle").textContent = "Không thể chạy Test Suite";
    $("#testStatusDescription").textContent = error.message;
    $("#testProgressBar").style.width = "0%";
    toast(error.message, "error");
  } finally {
    state.busy = false;
    button.disabled = false;
    button.innerHTML = `Chạy toàn bộ 5 tests <span>▶</span>`;
  }
}

async function loadStatus() {
  const status = await api("/api/status");
  setRuntime(status);
}
async function loadInventory() {
  const payload = await api("/api/library");
  renderInventory(payload.documents || []);
}
async function loadTools() {
  const payload = await api("/api/tools");
  renderTools(payload.tools || []);
}
async function loadTests() {
  const payload = await api("/api/tests");
  state.tests = payload.tests || [];
  $("#metricTests").textContent = String(state.tests.length).padStart(2, "0");
  $("#navTestCount").textContent = state.tests.length;
  renderTests(state.tests);
}
async function loadTrace() {
  const payload = await api("/api/trace");
  renderTrace(payload.trace || []);
}

async function refreshAll(showToast = false) {
  try {
    await Promise.all([loadStatus(), loadInventory(), loadTools(), loadTests(), loadTrace()]);
    if (showToast) toast("Đã đồng bộ dữ liệu mới nhất");
  } catch (error) {
    $("#runtimeText").textContent = "Runtime offline";
    $("#sideStatusLabel").textContent = "Mất kết nối";
    $("#sideStatusMeta").textContent = error.message;
    toast(`Không thể kết nối backend: ${error.message}`, "error");
  }
}

function bindEvents() {
  $$(".mode-button").forEach(button => button.addEventListener("click", () => {
    state.mode = button.dataset.mode;
    $$(".mode-button").forEach(item => item.classList.toggle("active", item === button));
    $("#chatContextText").textContent = state.mode === "agent" ? "Agent có quyền gọi MCP Tools" : "Chatbot không có quyền gọi Tool";
    toast(state.mode === "agent" ? "Đã chuyển sang ReAct Agent" : "Đã chuyển sang Chatbot Baseline");
  }));

  $("#chatForm").addEventListener("submit", event => {
    event.preventDefault();
    sendMessage($("#chatInput").value);
  });

  $("#chatInput").addEventListener("keydown", event => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      $("#chatForm").requestSubmit();
    }
  });
  $("#chatInput").addEventListener("input", event => {
    event.target.style.height = "auto";
    event.target.style.height = `${Math.min(event.target.scrollHeight, 110)}px`;
  });

  $$("[data-prompt]").forEach(button => button.addEventListener("click", () => {
    $("#chatInput").value = button.dataset.prompt;
    $("#chatInput").focus();
  }));

  $("#runTestsButton").addEventListener("click", runTests);
  $("#refreshButton").addEventListener("click", () => refreshAll(true));
  $("#resetButton").addEventListener("click", async () => {
    try {
      await api("/api/reset", { method: "POST", body: "{}" });
      await Promise.all([loadInventory(), loadTrace()]);
      toast("Đã khôi phục dữ liệu mock ban đầu");
    } catch (error) { toast(error.message, "error"); }
  });

  const sidebar = $("#sidebar");
  const overlay = $("#mobileOverlay");
  const closeMenu = () => { sidebar.classList.remove("open"); overlay.classList.remove("open"); };
  $("#menuButton").addEventListener("click", () => { sidebar.classList.add("open"); overlay.classList.add("open"); });
  overlay.addEventListener("click", closeMenu);
  $$(".nav-item[href]").forEach(link => link.addEventListener("click", closeMenu));

  document.addEventListener("keydown", event => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      $("#playground").scrollIntoView({ behavior: "smooth" });
      setTimeout(() => $("#chatInput").focus(), 350);
    }
  });

  const sections = $$(".section-anchor");
  const observer = new IntersectionObserver(entries => {
    const visible = entries.filter(entry => entry.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
    if (!visible) return;
    $$(".nav-item[data-section]").forEach(link => link.classList.toggle("active", link.dataset.section === visible.target.id));
  }, { rootMargin: "-20% 0px -60%", threshold: [0.05, 0.2, 0.5] });
  sections.forEach(section => observer.observe(section));
}

document.addEventListener("DOMContentLoaded", () => {
  bindEvents();
  refreshAll();
});