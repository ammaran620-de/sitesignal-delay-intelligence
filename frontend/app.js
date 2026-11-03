let accessToken = null;
let currentUser = null;
let toastTimer = null;
let cachedOverview = null;
const $ = (id) => document.getElementById(id);

function showToast(message, isError = false) {
  const el = $("toast");
  el.textContent = message;
  el.className = `toast${isError ? " error" : ""}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.add("hidden"), 3600);
}

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  if (options.body) headers["Content-Type"] = "application/json";
  const response = await fetch(path, { ...options, headers });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || `Request failed (${response.status})`);
  return body;
}

function appendInlineMarkdown(parent, source) {
  // Render a deliberately small Markdown subset using DOM nodes only.
  // Model output is never assigned to innerHTML, preventing HTML/script injection.
  const pattern = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*\n]+\*)/g;
  let cursor = 0;
  let match;

  while ((match = pattern.exec(source)) !== null) {
    if (match.index > cursor) {
      parent.appendChild(document.createTextNode(source.slice(cursor, match.index)));
    }

    const token = match[0];
    let node;
    if (token.startsWith("**")) {
      node = document.createElement("strong");
      node.textContent = token.slice(2, -2);
    } else if (token.startsWith("`")) {
      node = document.createElement("code");
      node.textContent = token.slice(1, -1);
    } else {
      node = document.createElement("em");
      node.textContent = token.slice(1, -1);
    }
    parent.appendChild(node);
    cursor = pattern.lastIndex;
  }

  if (cursor < source.length) {
    parent.appendChild(document.createTextNode(source.slice(cursor)));
  }
}

function renderMarkdown(container, markdown) {
  const lines = String(markdown || "")
    .replace(/\\([#*_`])/g, "$1")
    .split(/\r?\n/);

  let paragraph = [];
  let list = null;
  let listType = null;

  const flushParagraph = () => {
    if (!paragraph.length) return;
    const p = document.createElement("p");
    paragraph.forEach((line, index) => {
      if (index) p.appendChild(document.createElement("br"));
      appendInlineMarkdown(p, line);
    });
    container.appendChild(p);
    paragraph = [];
  };

  const flushList = () => {
    if (list) container.appendChild(list);
    list = null;
    listType = null;
  };

  for (const rawLine of lines) {
    const line = rawLine.trim();

    if (!line) {
      flushParagraph();
      flushList();
      continue;
    }

    const heading = line.match(/^(#{1,4})\s+(.+)$/);
    if (heading) {
      flushParagraph();
      flushList();
      const level = Math.min(heading[1].length + 1, 6);
      const node = document.createElement(`h${level}`);
      appendInlineMarkdown(node, heading[2]);
      container.appendChild(node);
      continue;
    }

    if (/^---+$/.test(line)) {
      flushParagraph();
      flushList();
      container.appendChild(document.createElement("hr"));
      continue;
    }

    const bullet = line.match(/^[-*]\s+(.+)$/);
    const numbered = line.match(/^\d+[.)]\s+(.+)$/);
    if (bullet || numbered) {
      flushParagraph();
      const nextType = bullet ? "ul" : "ol";
      if (!list || listType !== nextType) {
        flushList();
        list = document.createElement(nextType);
        listType = nextType;
      }
      const item = document.createElement("li");
      appendInlineMarkdown(item, (bullet || numbered)[1]);
      list.appendChild(item);
      continue;
    }

    flushList();
    paragraph.push(line);
  }

  flushParagraph();
  flushList();
}

function addMessage(text, role = "assistant") {
  const container = $("chatMessages");
  const outer = document.createElement("div");
  outer.className = `message ${role === "user" ? "user-message" : "assistant-message"}`;
  const avatar = document.createElement("div");
  avatar.className = "bot-avatar";
  avatar.textContent = role === "user" ? "YOU" : "SS";
  const wrap = document.createElement("div");
  wrap.className = "bubble-wrap";
  const label = document.createElement("span");
  label.className = "message-label";
  label.textContent = role === "user" ? "YOU" : "SITESIGNAL · GEMINI";
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  renderMarkdown(bubble, text);
  wrap.append(label, bubble);
  outer.append(avatar, wrap);
  container.appendChild(outer);
  container.scrollTop = container.scrollHeight;
}

function roleLabel(role) {
  return role === "manager" ? "Project manager" : role === "technician" ? "Project delivery user" : "Restricted user";
}

async function loadOverview() {
  const [data, health] = await Promise.all([
    api("/api/construction/overview"),
    fetch("/api/health").then(r => r.json()),
  ]);
  cachedOverview = data;
  $("projectName").textContent = data.project.name;
  $("statBaseline").textContent = `${data.metrics.baseline_duration_days} days`;
  $("statBaselineDate").textContent = `Finish ${data.metrics.baseline_finish_date}`;
  $("statForecast").textContent = `${data.metrics.forecast_duration_days} days`;
  $("statForecastDate").textContent = `Forecast ${data.metrics.forecast_finish_date}`;
  $("statDelay").textContent = `+${data.metrics.completion_delay_days} days`;
  $("statEvidence").textContent = data.metrics.evidence_files_available;
  $("statEvents").textContent = `${data.metrics.delay_events} linked delay events`;
  $("modelStatus").textContent = !health.gemini_configured
    ? "API key not configured"
    : (health.construction_rag_ready
      ? `API configured · ${health.construction_rag_chunks} RAG chunks indexed`
      : "API configured · RAG index pending");
  const agentBadge = $("agentStatusBadge");
  if (agentBadge) {
    const label = !health.gemini_configured
      ? "SETUP REQUIRED"
      : (health.construction_rag_ready ? "CONFIGURED · LIVE TEST AVAILABLE" : "INDEX REQUIRED");
    agentBadge.innerHTML = `<i></i> ${label}`;
    agentBadge.classList.toggle("needs-setup", !health.gemini_configured || !health.construction_rag_ready);
  }
  renderSchedule(data);
}

function renderSchedule(data) {
  const baseRows = data.baseline.activities;
  const impactedById = Object.fromEntries(data.impact.impacted_schedule.activities.map(x => [x.id, x]));
  $("criticalPathCount").textContent = `${data.baseline.critical_activities.length} zero-float activities`;
  $("scheduleSummary").textContent = `Baseline finish: ${data.metrics.baseline_finish_date}. Event-adjusted forecast: ${data.metrics.forecast_finish_date} (+${data.metrics.completion_delay_days} calendar days). Critical path: ${data.baseline.critical_path.join(" → ")}.`;
  const body = $("activityRows");
  body.replaceChildren();
  for (const row of baseRows) {
    const tr = document.createElement("tr");
    const impacted = impactedById[row.id];
    const values = [row.id, row.name, `${row.duration_days} d`, `${row.total_float_days} d`, row.is_critical ? "Yes" : "No", row.early_start_date || `Day ${row.early_start_day}`];
    values.forEach((value, index) => {
      const td = document.createElement("td");
      td.textContent = value;
      if (index === 4 && row.is_critical) td.className = "critical-cell";
      if (index === 1 && impacted && impacted.early_start_day > row.early_start_day) td.title = `Event-adjusted start shifted by ${impacted.early_start_day - row.early_start_day} calendar day(s)`;
      tr.appendChild(td);
    });
    body.appendChild(tr);
  }
}

function renderToolEvents(events = []) {
  const target = $("toolEvents");
  target.replaceChildren();
  if (!events.length) {
    target.className = "tool-events empty-state";
    target.textContent = "No tools executed for the latest request.";
    return;
  }
  target.className = "tool-events-list";
  for (const event of events) {
    const chip = document.createElement("div");
    chip.className = "tool-chip";
    const title = document.createElement("strong");
    title.textContent = `${event.status === "success" ? "✓" : "!"} ${event.name}`;
    const detail = document.createElement("span");
    const result = event.result || {};
    if (event.name === "get_project_schedule") detail.textContent = `Baseline ${result.metrics?.baseline_duration_days ?? "—"}d · Forecast ${result.metrics?.forecast_duration_days ?? "—"}d`;
    else if (event.name === "investigate_delay_event") detail.textContent = `${result.event?.id || event.arguments?.event_id || "Event"} · evidence returned`;
    else if (event.name === "simulate_recovery_scenario") detail.textContent = `Recovered ${result.simulation?.days_recovered_vs_delayed_schedule ?? "—"} day(s)`;
    else if (event.name === "search_project_evidence") detail.textContent = `${result.matches?.length ?? 0} evidence passage(s)`;
    else detail.textContent = result.error || "Tool completed";
    chip.append(title, detail);
    target.appendChild(chip);
  }
}

async function sendMessage(message) {
  if (!message.trim()) return;
  addMessage(message, "user");
  $("chatInput").value = "";
  $("sendBtn").disabled = true;
  $("sendBtn").textContent = "…";
  try {
    const result = await api("/api/chat", { method: "POST", body: JSON.stringify({ message }) });
    addMessage(result.answer || "No response returned.", "assistant");
    renderToolEvents(result.tool_events || []);
    await loadOverview();
  } catch (error) {
    addMessage(`The request failed: ${error.message}`, "assistant");
    showToast(error.message, true);
  } finally {
    $("sendBtn").disabled = false;
    $("sendBtn").textContent = "↑";
  }
}

function emptyState(container, text) {
  container.replaceChildren();
  const el = document.createElement("div");
  el.className = "empty-list";
  el.textContent = text;
  container.appendChild(el);
}

async function loadEvidence() {
  const result = await api("/api/construction/evidence");
  const container = $("evidenceList");
  container.replaceChildren();
  $("evidenceCount").textContent = `${result.items.length} sources`;
  for (const item of result.items) {
    const row = document.createElement("div");
    row.className = "data-row evidence-row";
    const info = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = item.title;
    const details = document.createElement("small");
    details.textContent = `${item.source} · ${item.excerpt}`;
    info.append(title, details);
    const badge = document.createElement("span");
    badge.className = "count-pill";
    badge.textContent = item.synthetic ? "SYNTHETIC" : "SOURCE";
    row.append(info, badge);
    container.appendChild(row);
  }
  if (!result.items.length) emptyState(container, "No evidence files found.");
}

async function runRecovery() {
  const button = $("simulateBtn");
  button.disabled = true;
  button.textContent = "Simulating…";
  try {
    const result = await api("/api/construction/recovery/REC-001", { method: "POST" });
    const sim = result.simulation;
    $("recoveryResult").textContent = `Delayed: ${sim.delayed_duration_days} days (${sim.delay_vs_baseline_days}d over baseline). Recovered: ${sim.recovered_duration_days} days. Days recovered: ${sim.days_recovered_vs_delayed_schedule}. ${sim.feasibility_warning}`;
    showToast("Schedule-only recovery simulation completed. No schedule was changed.");
    if (currentUser.role === "manager") await loadAudit();
  } catch (error) { showToast(error.message, true); }
  finally { button.disabled = false; button.textContent = "Simulate recovery"; }
}

async function loadAudit() {
  const result = await api("/api/audit");
  const container = $("auditList");
  container.replaceChildren();
  if (!result.items.length) return emptyState(container, "No audit events yet.");
  for (const item of result.items) {
    const row = document.createElement("div");
    row.className = "data-row";
    const info = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = `${item.action} · ${item.outcome}`;
    const details = document.createElement("small");
    details.textContent = `${item.actor_name} · ${item.resource_type}${item.resource_id ? ` #${item.resource_id}` : ""} · ${item.created_at}${item.details ? ` · ${item.details}` : ""}`;
    info.append(title, details);
    row.append(info);
    container.appendChild(row);
  }
}

const DEMO_CHECKS = ["schedule", "critical", "float", "evidence", "recovery"];

function setDemoStep(step, state, label) {
  const card = document.querySelector(`[data-demo-step="${step}"]`);
  if (!card) return;
  card.classList.remove("running", "passed", "failed");
  if (state) card.classList.add(state);
  const badge = card.querySelector(".demo-step-state");
  if (badge) badge.textContent = label;
}

function addDemoResult(title, detail, ok = true) {
  const container = $("demoResults");
  if (container.querySelector(".empty-list")) container.replaceChildren();
  const card = document.createElement("article");
  card.className = "demo-result";
  const top = document.createElement("div");
  top.className = "demo-result-top";
  const heading = document.createElement("strong");
  heading.textContent = title;
  const state = document.createElement("span");
  state.textContent = ok ? "PASS" : "FAIL";
  state.style.color = ok ? "#248264" : "#a84d42";
  const body = document.createElement("p");
  body.textContent = detail;
  top.append(heading, state);
  card.append(top, body);
  container.appendChild(card);
}

function addDemoNote(title, detail) {
  const container = $("demoResults");
  if (container.querySelector(".empty-list")) container.replaceChildren();

  const card = document.createElement("article");
  card.className = "demo-result";
  const top = document.createElement("div");
  top.className = "demo-result-top";

  const heading = document.createElement("strong");
  heading.textContent = title;

  const state = document.createElement("span");
  state.textContent = "MANUAL";
  state.style.color = "#8a6d32";

  const body = document.createElement("p");
  body.textContent = detail;

  top.append(heading, state);
  card.append(top, body);
  container.appendChild(card);
}

function updateDemoCount(passed) {
  $("demoRunCount").textContent = `${passed} / ${DEMO_CHECKS.length} automated checks`;
}

function resetGuidedDemo() {
  DEMO_CHECKS.forEach(step => setDemoStep(step, "", "Not run"));
  setDemoStep("technician", "", "Manual sign-in");
  setDemoStep("sales", "", "Manual sign-in");
  $("demoRunStatus").textContent = "Ready to run";
  updateDemoCount(0);
  $("demoResults").innerHTML = '<div class="empty-list">Run the guided demo to populate live API results. Role boundaries require separate manual sign-ins.</div>';
}

async function runGuidedDemo() {
  if (!currentUser || currentUser.role !== "manager") {
    showToast("Sign in as the project manager to run the full guided demo.", true);
    return;
  }
  const button = $("runGuidedDemoBtn");
  button.disabled = true;
  button.textContent = "Running walkthrough…";
  resetGuidedDemo();
  $("demoRunStatus").textContent = "Running live API checks…";
  let passed = 0;
  const execute = async (step, title, operation, describe) => {
    setDemoStep(step, "running", "Running…");
    try {
      const result = await operation();
      const detail = describe(result);
      setDemoStep(step, "passed", "Passed");
      addDemoResult(title, detail, true);
      passed += 1;
      updateDemoCount(passed);
      return result;
    } catch (error) {
      setDemoStep(step, "failed", "Failed");
      addDemoResult(title, error.message, false);
      throw error;
    }
  };
  try {
    const overview = await execute(
      "schedule", "1 · Deterministic schedule analysis",
      () => api("/api/construction/overview"),
      data => `Baseline: ${data.metrics.baseline_duration_days} days, finishing ${data.metrics.baseline_finish_date}. Event-adjusted: ${data.metrics.forecast_duration_days} days, finishing ${data.metrics.forecast_finish_date} (+${data.metrics.completion_delay_days} days). Critical path: ${data.baseline.critical_path.join(" → ")}.`
    );
    const critical = await execute(
      "critical", "2 · Critical-path incident EV-001",
      () => api("/api/construction/events/EV-001"),
      data => `Source: ${data.evidence.source}. Event: ${data.event.summary}. Calculated completion impact when applied alone: +${data.schedule_impact.project_completion_delta_if_applied_alone_days} days. Evidence is explicitly marked synthetic: ${data.evidence.synthetic}.`
    );
    const nonCritical = await execute(
      "float", "3 · Float-absorbed incident EV-002",
      () => api("/api/construction/events/EV-002"),
      data => `Source: ${data.evidence.source}. Event: ${data.event.summary}. Calculated completion impact when applied alone: +${data.schedule_impact.project_completion_delta_if_applied_alone_days} days. Baseline activity critical: ${data.schedule_impact.baseline_activity_was_critical}.`
    );
    const evidence = await execute(
      "evidence", "4 · Evidence register",
      () => api("/api/construction/evidence"),
      data => `${data.items.length} synthetic source records returned: ${data.items.map(item => item.source).join(", ")}.`
    );
    const recovery = await execute(
      "recovery", "5 · Recovery what-if simulation",
      () => api("/api/construction/recovery/REC-001", { method: "POST" }),
      data => `Delayed schedule: ${data.simulation.delayed_duration_days} days. Recovered schedule: ${data.simulation.recovered_duration_days} days. Improvement: ${data.simulation.days_recovered_vs_delayed_schedule} day(s). Approval required: ${data.approval_required}. ${data.simulation.feasibility_warning}`
    );
    setDemoStep("technician", "", "Manual sign-in");
    addDemoNote(
      "6 · Technician permission boundary",
      "Manual verification: sign out, sign in as technician, confirm schedule access, then confirm recovery simulation is denied. The browser walkthrough does not embed or reuse account passwords."
    );
    setDemoStep("sales", "", "Manual sign-in");
    addDemoNote(
      "7 · Restricted-user boundary",
      "Manual verification: sign out, sign in as sales, and confirm construction project data is denied. The browser walkthrough does not embed or reuse account passwords."
    );
    const allPassed = passed === DEMO_CHECKS.length;
    $("demoRunStatus").textContent = allPassed ? "Automated checks passed · role checks manual" : "Walkthrough completed with issues";
    addDemoResult("Walkthrough summary", `${passed}/${DEMO_CHECKS.length} automated API checks passed. Two role-boundary checks are marked for separate manual sign-in. No approved baseline or real project data was changed.`, allPassed);
    if (currentUser.role === "manager") await loadAudit();
    showToast(allPassed ? "Guided demo completed: all 5 automated checks passed. Role checks remain manual." : "Guided demo completed with failed checks.", !allPassed);
  } catch (error) {
    $("demoRunStatus").textContent = `Stopped: ${error.message}`;
    showToast(`Guided demo stopped: ${error.message}`, true);
  } finally {
    button.disabled = false;
    button.innerHTML = 'Run full walkthrough <span>→</span>';
  }
}

async function runGeminiDemo() {
  if (!currentUser || currentUser.role !== "manager") {
    showToast("Sign in as the project manager to run the Gemini demonstration.", true);
    return;
  }
  const health = await fetch("/api/health").then(response => response.json());
  if (!health.gemini_configured) {
    showToast("Gemini is not configured. Add GEMINI_API_KEY to the local .env file.", true);
    return;
  }
  if (!health.construction_rag_ready) {
    showToast("Construction RAG is not indexed. Run: python -m app.ingest_construction", true);
    return;
  }
  await showPanel("assistant");
  const prompt = "Investigate EV-001 and compare it with EV-002. Use the deterministic schedule and evidence retrieval tools. Separate recorded facts, calculated results, assumptions and unknowns. Cite the source filenames, explain the float effect, and do not propose or execute a real-world action.";
  await sendMessage(prompt);
}

async function showPanel(panel) {
  const panels = { demo: "demoPanel", assistant: "assistantPanel", schedule: "schedulePanel", evidence: "evidencePanel", audit: "auditPanel" };
  for (const [key, id] of Object.entries(panels)) $(id).classList.toggle("hidden", key !== panel);
  document.querySelectorAll(".nav-item").forEach(el => el.classList.toggle("active", el.dataset.panel === panel));
  const titles = { demo: "Overview & walkthrough", assistant: "AI investigator", schedule: "Schedule & recovery", evidence: "Evidence library", audit: "Security & audit" };
  $("pageTitle").textContent = titles[panel];
  try {
    if (panel === "schedule" && !cachedOverview) await loadOverview();
    if (panel === "evidence") await loadEvidence();
    if (panel === "audit") await loadAudit();
  } catch (error) { showToast(error.message, true); }
}

async function enterWorkspace(loginResult) {
  accessToken = loginResult.access_token;
  currentUser = loginResult.user;
  $("loginView").classList.add("hidden");
  $("appView").classList.remove("hidden");
  $("userName").textContent = currentUser.full_name;
  $("userRole").textContent = roleLabel(currentUser.role);
  $("avatarInitials").textContent = currentUser.full_name.split(" ").map(x => x[0]).slice(0, 2).join("").toUpperCase();
  $("greeting").textContent = `Welcome, ${currentUser.full_name.split(" ")[0]}.`;
  $("auditNav").classList.toggle("hidden", currentUser.role !== "manager");
  $("simulateBtn").classList.toggle("hidden", currentUser.role !== "manager");
  // The sales role can authenticate, but must not see project content.
  // Protected API endpoints independently enforce HTTP 403 on this role.
  document.querySelectorAll(".nav-item").forEach(el => el.classList.remove("hidden"));
  if (currentUser.role === "sales") {
    document.querySelectorAll(".nav-item").forEach(el => el.classList.add("hidden"));
    $("auditNav").classList.add("hidden");
    $("restrictedAccessPanel").classList.remove("hidden");
    $("pageTitle").textContent = "Access restricted";
    $("welcomeRow").classList.add("hidden");
    return;
  }

  $("restrictedAccessPanel").classList.add("hidden");
  $("welcomeRow").classList.remove("hidden");
  await loadOverview();
  await showPanel("demo");
}

$("loginForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  $("loginError").textContent = "";
  try {
    const result = await fetch("/api/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username: $("username").value, password: $("password").value }) });
    const body = await result.json();
    if (!result.ok) throw new Error(body.detail || "Login failed.");
    try { await enterWorkspace(body); } catch (error) { $("loginError").textContent = error.message; }
  } catch (error) { $("loginError").textContent = error.message; }
});

$("chatForm").addEventListener("submit", (event) => { event.preventDefault(); sendMessage($("chatInput").value); });
$("chatInput").addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); sendMessage($("chatInput").value); }
});
document.querySelectorAll(".suggestion").forEach(button => button.addEventListener("click", () => sendMessage(button.dataset.prompt)));
document.querySelectorAll(".nav-item").forEach(button => button.addEventListener("click", () => showPanel(button.dataset.panel)));
$("simulateBtn").addEventListener("click", runRecovery);
$("restrictedLogoutBtn").addEventListener("click", () => $("logoutBtn").click());

$("logoutBtn").addEventListener("click", async () => {
  try { await api("/api/logout", { method: "POST" }); } catch (_) {}
  accessToken = null;
  currentUser = null;
  cachedOverview = null;

  // Clear project-specific content so a later restricted login cannot
  // see data left in the previous user's browser session.
  $("password").value = "";
  $("loginError").textContent = "";
  $("chatInput").value = "";
  $("chatMessages").replaceChildren();
  $("evidenceList").replaceChildren();
  $("auditList").replaceChildren();
  $("activityRows").replaceChildren();
  $("projectName").textContent = "—";
  $("statBaseline").textContent = "—";
  $("statBaselineDate").textContent = "Original schedule";
  $("statForecast").textContent = "—";
  $("statForecastDate").textContent = "Event-adjusted schedule";
  $("statDelay").textContent = "—";
  $("statEvidence").textContent = "—";
  $("statEvents").textContent = "Linked delay events";
  $("scheduleSummary").textContent = "Sign in to load project schedule.";
  $("toolEvents").replaceChildren();
  $("toolEvents").className = "tool-events empty-state";
  $("toolEvents").textContent = "No tools executed yet.";
  $("recoveryResult").textContent = "Run the scenario to view calculated impact.";
  $("restrictedAccessPanel").classList.add("hidden");
  $("welcomeRow").classList.remove("hidden");
  document.querySelectorAll(".nav-item").forEach(el => el.classList.remove("hidden"));
  resetGuidedDemo();

  $("appView").classList.add("hidden");
  $("loginView").classList.remove("hidden");
});

$("runGuidedDemoBtn").addEventListener("click", runGuidedDemo);
$("runGeminiDemoBtn").addEventListener("click", runGeminiDemo);
$("resetGuidedDemoBtn").addEventListener("click", resetGuidedDemo);
$("openAuditFromDemoBtn").addEventListener("click", () => showPanel("audit"));
