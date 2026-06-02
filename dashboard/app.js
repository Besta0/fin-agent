const state = {
  userId: localStorage.getItem("finAgentDashboardUser") || "chainlit",
  runId: "",
  selectedNode: "coordinator",
  payload: null,
  refreshTimer: null,
};

const statusLabels = {
  running: "运行中",
  completed: "已完成",
  stopped: "已早停",
  failed: "出错",
};

const statusClasses = {
  "已完成": "done",
  "工作中": "running",
  "等待中": "waiting",
  "未运行": "waiting",
  "出错": "failed",
};

const els = {
  userSelect: document.getElementById("userSelect"),
  runSelect: document.getElementById("runSelect"),
  refreshBtn: document.getElementById("refreshBtn"),
  queryInput: document.getElementById("queryInput"),
  startRunBtn: document.getElementById("startRunBtn"),
  launchStatus: document.getElementById("launchStatus"),
  tickerMetric: document.getElementById("tickerMetric"),
  statusMetric: document.getElementById("statusMetric"),
  ratingMetric: document.getElementById("ratingMetric"),
  confidenceMetric: document.getElementById("confidenceMetric"),
  progressMetric: document.getElementById("progressMetric"),
  queryText: document.getElementById("queryText"),
  runIdText: document.getElementById("runIdText"),
  updatedText: document.getElementById("updatedText"),
  agentCount: document.getElementById("agentCount"),
  agentGrid: document.getElementById("agentGrid"),
  detailTitle: document.getElementById("detailTitle"),
  detailStatus: document.getElementById("detailStatus"),
  detailMission: document.getElementById("detailMission"),
  detailContent: document.getElementById("detailContent"),
  eventCount: document.getElementById("eventCount"),
  timeline: document.getElementById("timeline"),
  debateStatus: document.getElementById("debateStatus"),
  bullSummary: document.getElementById("bullSummary"),
  bullArgs: document.getElementById("bullArgs"),
  bearSummary: document.getElementById("bearSummary"),
  bearArgs: document.getElementById("bearArgs"),
  committeeSummary: document.getElementById("committeeSummary"),
  committeeArgs: document.getElementById("committeeArgs"),
};

async function init() {
  bindEvents();
  await loadUsers();
  await loadPayload();
  state.refreshTimer = window.setInterval(loadPayload, 2500);
}

function bindEvents() {
  els.userSelect.addEventListener("change", async () => {
    state.userId = els.userSelect.value || "chainlit";
    localStorage.setItem("finAgentDashboardUser", state.userId);
    state.runId = "";
    await loadPayload();
  });

  els.runSelect.addEventListener("change", async () => {
    state.runId = els.runSelect.value;
    await loadPayload();
  });

  els.refreshBtn.addEventListener("click", loadPayload);

  els.startRunBtn.addEventListener("click", startRun);
  els.queryInput.addEventListener("keydown", async (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
      event.preventDefault();
      await startRun();
    }
  });
}

async function loadUsers() {
  const data = await getJson("/api/users");
  const users = data.users || [];
  if (users.length > 0 && !users.some((user) => user.user_id === state.userId)) {
    state.userId = users[0].user_id;
  }

  els.userSelect.innerHTML = "";
  if (users.length === 0) {
    els.userSelect.append(new Option("chainlit", "chainlit"));
    return;
  }
  for (const user of users) {
    const label = `${user.user_id} (${user.run_count})`;
    els.userSelect.append(new Option(label, user.user_id));
  }
  els.userSelect.value = state.userId;
}

async function loadPayload() {
  const params = new URLSearchParams({ user_id: state.userId });
  if (state.runId) {
    params.set("run_id", state.runId);
  }

  state.payload = await getJson(`/api/run?${params.toString()}`);
  if (!state.payload.run && !state.runId && (state.payload.users || []).length > 0) {
    state.userId = state.payload.users[0].user_id;
    localStorage.setItem("finAgentDashboardUser", state.userId);
    await loadUsers();
    return loadPayload();
  }

  renderRunOptions();
  renderDashboard();
}

async function getJson(url) {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || `Request failed: ${response.status}`);
  }
  return data;
}

async function startRun() {
  const query = els.queryInput.value.trim();
  if (!query) {
    els.launchStatus.textContent = "请输入一个股票研究问题。";
    return;
  }

  els.startRunBtn.disabled = true;
  els.startRunBtn.textContent = "启动中";
  els.launchStatus.textContent = "正在创建 run，并启动多 Agent 工作流...";
  try {
    const data = await postJson("/api/run/start", {
      user_id: state.userId || "chainlit",
      query,
    });
    state.userId = data.user_id;
    state.runId = data.run_id;
    localStorage.setItem("finAgentDashboardUser", state.userId);
    els.queryInput.value = "";
    els.launchStatus.textContent = `已启动 run ${data.run_id}，看板会自动刷新。`;
    await loadUsers();
    await loadPayload();
  } catch (error) {
    els.launchStatus.textContent = `启动失败：${error.message}`;
  } finally {
    els.startRunBtn.disabled = false;
    els.startRunBtn.textContent = "启动研究";
  }
}

function renderRunOptions() {
  const runs = state.payload?.runs || [];
  const currentRunId = state.payload?.run?.run_id || state.runId || "";
  els.runSelect.innerHTML = "";
  if (runs.length === 0) {
    els.runSelect.append(new Option("暂无 run", ""));
    return;
  }

  for (const run of runs) {
    const label = `${run.ticker || "识别中"} / ${run.rating || "待结论"} / ${run.updated_at || run.run_id}`;
    els.runSelect.append(new Option(label, run.run_id));
  }
  els.runSelect.value = currentRunId || runs[0].run_id;
  state.runId = els.runSelect.value;
}

function renderDashboard() {
  const run = state.payload?.run;
  const flow = state.payload?.agent_flow || [];

  if (!run) {
    renderEmpty(flow);
    return;
  }

  const events = run.events || [];
  const eventByNode = Object.fromEntries(events.map((event) => [event.node, event]));
  const completeCount = events.length;

  els.tickerMetric.textContent = run.ticker || "识别中";
  els.statusMetric.textContent = statusLabels[run.status] || run.status || "N/A";
  els.ratingMetric.textContent = run.rating || "待投委会";
  els.confidenceMetric.textContent = run.confidence ? `${run.confidence}%` : "N/A";
  els.progressMetric.textContent = `${completeCount}/${flow.length || 14}`;
  els.queryText.textContent = run.user_query || "N/A";
  els.runIdText.textContent = run.run_id || "N/A";
  els.updatedText.textContent = run.updated_at || "N/A";
  els.agentCount.textContent = `${flow.length} agents`;
  els.eventCount.textContent = `${completeCount} events`;

  renderAgents(flow, run, eventByNode);
  renderDetails(flow, run, eventByNode);
  renderTimeline(events);
  renderDebate(eventByNode, run);
}

function renderEmpty(flow) {
  els.tickerMetric.textContent = "N/A";
  els.statusMetric.textContent = "暂无 run";
  els.ratingMetric.textContent = "待投委会";
  els.confidenceMetric.textContent = "N/A";
  els.progressMetric.textContent = `0/${flow.length || 14}`;
  els.queryText.textContent = "还没有运行记录。可以在上方输入研究问题并启动一次多 Agent 分析。";
  els.runIdText.textContent = "N/A";
  els.updatedText.textContent = "N/A";
  els.agentGrid.innerHTML = `<div class="empty">暂无 Agent 运行记录。</div>`;
  els.detailContent.innerHTML = `<div class="empty">完成一次分析后，这里会展示每个 Agent 的结构化输出。</div>`;
  els.timeline.innerHTML = `<div class="empty">等待运行事件。</div>`;
  renderDebate({}, {});
}

function renderAgents(flow, run, eventByNode) {
  els.agentGrid.innerHTML = "";
  for (const agent of flow) {
    const event = eventByNode[agent.node];
    const status = statusForNode(run, agent.node, event);
    const card = document.createElement("button");
    card.type = "button";
    card.className = `agent-card ${state.selectedNode === agent.node ? "selected" : ""}`;
    card.innerHTML = `
      <h3>${escapeHtml(agent.name)}</h3>
      <div class="agent-role">${escapeHtml(agent.role)}</div>
      <p class="agent-summary">${escapeHtml(stripMarkdown(event?.summary || agent.mission))}</p>
      <span class="badge ${statusClasses[status] || "waiting"}">${status}</span>
    `;
    card.addEventListener("click", () => {
      state.selectedNode = agent.node;
      renderDashboard();
    });
    els.agentGrid.append(card);
  }
}

function renderDetails(flow, run, eventByNode) {
  const selected = flow.find((agent) => agent.node === state.selectedNode) || flow[0];
  if (!selected) {
    return;
  }

  const event = eventByNode[selected.node];
  const status = statusForNode(run, selected.node, event);
  els.detailTitle.textContent = `${selected.name} / ${selected.role}`;
  els.detailStatus.textContent = status;
  els.detailMission.textContent = selected.mission;

  if (!event) {
    els.detailContent.innerHTML = `<div class="empty">这个 Agent 尚未输出。分析运行到对应阶段后会自动更新。</div>`;
    return;
  }

  els.detailContent.innerHTML = `
    <div class="kv-row">
      <div class="kv-key">完成时间</div>
      <div class="kv-value">${escapeHtml(event.finished_at || "N/A")}</div>
    </div>
    <div class="kv-row">
      <div class="kv-key">摘要</div>
      <div class="kv-value">${escapeHtml(stripMarkdown(event.summary || "N/A"))}</div>
    </div>
    ${renderObject(event.output)}
  `;
}

function renderTimeline(events) {
  if (!events || events.length === 0) {
    els.timeline.innerHTML = `<div class="empty">等待第一个 Agent 输出。</div>`;
    return;
  }
  els.timeline.innerHTML = events
    .map(
      (event) => `
        <div class="timeline-item">
          <strong>${event.index}. ${escapeHtml(event.agent_name || event.node)}</strong>
          <p>${escapeHtml(stripMarkdown(event.summary || ""))}</p>
          <p>${escapeHtml(event.finished_at || "")}</p>
        </div>
      `,
    )
    .join("");
}

function renderDebate(eventByNode, run) {
  const bull = eventByNode.bull?.output || {};
  const bear = eventByNode.bear?.output || {};
  const committee = eventByNode.committee?.output || {};

  els.debateStatus.textContent = committee.rating
    ? `${committee.rating} / ${committee.confidence || run.confidence || "N/A"}%`
    : "等待 Bull / Bear / Committee";

  els.bullSummary.textContent = bull.summary || "暂无看多观点。";
  els.bullArgs.innerHTML = renderList("核心论据", bull.arguments, "薄弱点", bull.weak_points);

  els.bearSummary.textContent = bear.summary || "暂无看空观点。";
  els.bearArgs.innerHTML = renderList("核心论据", bear.arguments, "反驳点", bear.rebuttals);

  els.committeeSummary.textContent = committee.rating
    ? `${committee.rating}，置信度 ${committee.confidence || "N/A"}%。`
    : "等待投委会裁决。";
  els.committeeArgs.innerHTML = renderList("关键依据", committee.key_reasons, "不确定性", committee.uncertainty ? [committee.uncertainty] : []);
}

function renderList(titleA, listA, titleB, listB) {
  const first = Array.isArray(listA) && listA.length > 0
    ? `<p class="metric-label">${escapeHtml(titleA)}</p><ol class="list-block">${listA
        .slice(0, 5)
        .map((item) => `<li>${escapeHtml(String(item))}</li>`)
        .join("")}</ol>`
    : "";
  const second = Array.isArray(listB) && listB.length > 0
    ? `<p class="metric-label">${escapeHtml(titleB)}</p><ol class="list-block">${listB
        .slice(0, 5)
        .map((item) => `<li>${escapeHtml(String(item))}</li>`)
        .join("")}</ol>`
    : "";
  return first || second ? `${first}${second}` : `<p class="muted">暂无结构化要点。</p>`;
}

function renderObject(value) {
  if (!value || typeof value !== "object") {
    return `<div class="kv-row"><div class="kv-key">输出</div><div class="kv-value">${escapeHtml(String(value || "N/A"))}</div></div>`;
  }

  return Object.entries(value)
    .map(([key, item]) => {
      return `
        <div class="kv-row">
          <div class="kv-key">${escapeHtml(key)}</div>
          <div class="kv-value">${formatValue(item)}</div>
        </div>
      `;
    })
    .join("");
}

function formatValue(value) {
  if (value === null || value === undefined || value === "") {
    return "N/A";
  }
  if (Array.isArray(value)) {
    if (value.length === 0) {
      return "暂无";
    }
    return `<ol class="list-block">${value
      .slice(0, 8)
      .map((item) => `<li>${escapeHtml(formatPlain(item))}</li>`)
      .join("")}</ol>`;
  }
  if (typeof value === "object") {
    return `<code>${escapeHtml(JSON.stringify(value, null, 2))}</code>`;
  }
  return escapeHtml(String(value));
}

function formatPlain(value) {
  if (value === null || value === undefined) {
    return "N/A";
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

function statusForNode(run, node, event) {
  if (event) {
    return "已完成";
  }
  if (run.status === "failed" && run.current_node === node) {
    return "出错";
  }
  if (run.status === "running" && run.current_node === node) {
    return "工作中";
  }
  if (["completed", "stopped", "failed"].includes(run.status)) {
    return "未运行";
  }
  return "等待中";
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function stripMarkdown(value) {
  return String(value ?? "")
    .replace(/\*\*/g, "")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/#{1,6}\s*/g, "")
    .replace(/\[(.*?)\]\((.*?)\)/g, "$1")
    .trim();
}

init().catch((error) => {
  console.error(error);
  document.body.innerHTML = `<div class="app-shell"><div class="empty">Dashboard 加载失败：${escapeHtml(error.message)}</div></div>`;
});
