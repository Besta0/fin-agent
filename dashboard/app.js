const initialParams = new URLSearchParams(window.location.search);

const state = {
  userId: initialParams.get("user_id") || localStorage.getItem("finAgentDashboardUser") || "chainlit",
  runId: initialParams.get("run_id") || "",
  selectedNode: "coordinator",
  payload: null,
  report: null,
  reportKey: "",
  compare: null,
  compareKey: "",
  watchlist: null,
  watchlistKey: "",
  settings: null,
  settingsOpen: localStorage.getItem("finAgentSettingsOpen") === "true",
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
  settingsToggleBtn: document.getElementById("settingsToggleBtn"),
  queryInput: document.getElementById("queryInput"),
  startRunBtn: document.getElementById("startRunBtn"),
  launchStatus: document.getElementById("launchStatus"),
  settingsPanel: document.getElementById("settingsPanel"),
  settingsCurrentLine: document.getElementById("settingsCurrentLine"),
  settingsStatus: document.getElementById("settingsStatus"),
  settingsProvider: document.getElementById("settingsProvider"),
  settingsModel: document.getElementById("settingsModel"),
  settingsCustomModel: document.getElementById("settingsCustomModel"),
  settingsBaseUrl: document.getElementById("settingsBaseUrl"),
  settingsApiKey: document.getElementById("settingsApiKey"),
  settingsTemperature: document.getElementById("settingsTemperature"),
  settingsTemperatureValue: document.getElementById("settingsTemperatureValue"),
  settingsKeyStatus: document.getElementById("settingsKeyStatus"),
  testSettingsBtn: document.getElementById("testSettingsBtn"),
  saveSettingsBtn: document.getElementById("saveSettingsBtn"),
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
  watchlistStatus: document.getElementById("watchlistStatus"),
  watchlistSummary: document.getElementById("watchlistSummary"),
  watchlistGrid: document.getElementById("watchlistGrid"),
  compareStatus: document.getElementById("compareStatus"),
  compareSummary: document.getElementById("compareSummary"),
  compareTable: document.getElementById("compareTable"),
  reportStatus: document.getElementById("reportStatus"),
  reloadReportBtn: document.getElementById("reloadReportBtn"),
  reportMeta: document.getElementById("reportMeta"),
  reportBody: document.getElementById("reportBody"),
  reportPath: document.getElementById("reportPath"),
  reportLinks: document.getElementById("reportLinks"),
};

async function init() {
  bindEvents();
  await loadUsers();
  await loadSettings();
  await loadPayload();
  state.refreshTimer = window.setInterval(loadPayload, 2500);
}

function bindEvents() {
  els.userSelect.addEventListener("change", async () => {
    state.userId = els.userSelect.value || "chainlit";
    localStorage.setItem("finAgentDashboardUser", state.userId);
    state.runId = "";
    await loadSettings();
    await loadPayload();
  });

  els.runSelect.addEventListener("change", async () => {
    state.runId = els.runSelect.value;
    await loadPayload();
  });

  els.refreshBtn.addEventListener("click", loadPayload);
  els.reloadReportBtn.addEventListener("click", () => loadReport({ force: true }));
  els.settingsToggleBtn.addEventListener("click", toggleSettingsPanel);
  els.settingsProvider.addEventListener("change", handleSettingsProviderChange);
  els.settingsModel.addEventListener("change", handleSettingsModelChange);
  els.settingsCustomModel.addEventListener("input", updateSettingsDraftLine);
  els.settingsBaseUrl.addEventListener("input", updateSettingsDraftLine);
  els.settingsTemperature.addEventListener("input", updateTemperatureLabel);
  els.saveSettingsBtn.addEventListener("click", saveSettings);
  els.testSettingsBtn.addEventListener("click", testSettings);

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

async function loadSettings() {
  const params = new URLSearchParams({ user_id: state.userId || "chainlit" });
  try {
    state.settings = await getJson(`/api/settings?${params.toString()}`);
    renderSettingsPanel();
  } catch (error) {
    state.settings = null;
    setSettingsStatus(`读取失败：${error.message}`);
  }
}

function toggleSettingsPanel() {
  state.settingsOpen = !state.settingsOpen;
  localStorage.setItem("finAgentSettingsOpen", state.settingsOpen ? "true" : "false");
  setSettingsPanelVisibility();
}

function renderSettingsPanel() {
  setSettingsPanelVisibility();
  const providers = state.settings?.providers || [];
  const settings = state.settings?.settings || {};
  if (providers.length === 0) {
    setSettingsStatus("暂无 provider");
    return;
  }

  replaceOptions(
    els.settingsProvider,
    providers.map((provider) => ({
      label: provider.label,
      value: provider.value,
    })),
  );

  const provider = settings.provider || providers[0].value;
  els.settingsProvider.value = provider;
  applyModelOptions(provider, settings.model || providerDefaults(provider)?.default_model || "");
  els.settingsBaseUrl.value = settings.base_url || providerDefaults(provider)?.default_base_url || "";
  els.settingsApiKey.value = "";
  els.settingsTemperature.value = String(settings.temperature ?? 0.2);
  updateTemperatureLabel();

  els.settingsCurrentLine.textContent = `${settings.provider_label || providerLabel(provider)} / ${settings.model || "未选择模型"} / ${settings.base_url || "默认入口"}`;
  els.settingsKeyStatus.textContent = `API Key：${settings.api_key_masked || "未配置"}${settings.api_key_source ? ` / ${settings.api_key_source}` : ""}`;
  setSettingsStatus(settings.updated_at ? `已保存 ${settings.updated_at}` : "使用默认配置");
}

function setSettingsPanelVisibility() {
  els.settingsPanel.classList.toggle("is-hidden", !state.settingsOpen);
  els.settingsToggleBtn.textContent = state.settingsOpen ? "收起设置" : "模型设置";
}

function handleSettingsProviderChange() {
  const provider = els.settingsProvider.value || "openai";
  const defaults = providerDefaults(provider);
  applyModelOptions(provider, defaults?.default_model || "");
  els.settingsBaseUrl.value = defaults?.default_base_url || "";
  updateSettingsDraftLine();
  els.settingsKeyStatus.textContent = "API Key：当前表单尚未保存";
  setSettingsStatus(`已切换到 ${providerLabel(provider)}`);
}

function handleSettingsModelChange() {
  syncCustomModelState();
  updateSettingsDraftLine();
  if (els.settingsModel.value === "__custom__") {
    els.settingsCustomModel.focus();
  }
}

function updateTemperatureLabel() {
  const number = Number(els.settingsTemperature.value || 0);
  els.settingsTemperatureValue.textContent = Number.isFinite(number) ? number.toFixed(2) : "0.20";
}

function applyModelOptions(providerValue, selectedModel) {
  const provider = providerDefaults(providerValue) || {};
  const models = provider.models || [];
  replaceOptions(
    els.settingsModel,
    [
      ...models.map((model) => ({
        label: model.label,
        value: model.value,
      })),
      { label: "自定义模型", value: "__custom__" },
    ],
  );

  const modelValue = selectedModel || provider.default_model || "";
  const known = models.some((model) => model.value === modelValue);
  els.settingsModel.value = known ? modelValue : "__custom__";
  els.settingsCustomModel.value = known ? "" : modelValue;
  syncCustomModelState();
}

function syncCustomModelState() {
  const isCustom = els.settingsModel.value === "__custom__";
  els.settingsCustomModel.disabled = !isCustom;
  els.settingsCustomModel.placeholder = isCustom ? "输入自定义模型名" : "使用上方模型";
}

function updateSettingsDraftLine() {
  const provider = els.settingsProvider.value || "openai";
  const model = els.settingsModel.value === "__custom__"
    ? els.settingsCustomModel.value.trim()
    : els.settingsModel.value;
  const baseUrl = els.settingsBaseUrl.value.trim();
  els.settingsCurrentLine.textContent = `${providerLabel(provider)} / ${model || "未选择模型"} / ${baseUrl || "默认入口"}`;
}

function collectSettingsPayload() {
  const provider = els.settingsProvider.value || "openai";
  const defaults = providerDefaults(provider);
  const selectedModel = els.settingsModel.value === "__custom__"
    ? els.settingsCustomModel.value.trim()
    : els.settingsModel.value;
  return {
    user_id: state.userId || "chainlit",
    provider,
    model: selectedModel || defaults?.default_model || "",
    base_url: els.settingsBaseUrl.value.trim(),
    api_key: els.settingsApiKey.value.trim(),
    temperature: Number(els.settingsTemperature.value || 0.2),
  };
}

async function saveSettings() {
  const payload = collectSettingsPayload();
  setSettingsButtonsDisabled(true);
  setSettingsStatus("保存中");
  try {
    const data = await postJson("/api/settings/save", payload);
    state.settings = {
      ...(state.settings || {}),
      settings: data.settings,
    };
    renderSettingsPanel();
    setSettingsStatus("已保存");
  } catch (error) {
    setSettingsStatus(`保存失败：${error.message}`);
  } finally {
    setSettingsButtonsDisabled(false);
  }
}

async function testSettings() {
  const payload = collectSettingsPayload();
  setSettingsButtonsDisabled(true);
  setSettingsStatus("测试中");
  try {
    const data = await postJson("/api/settings/test", payload);
    const result = data.result || {};
    setSettingsStatus(result.ok ? `连接成功：${result.message || "模型已响应"}` : `连接失败：${result.message || result.status || "未知错误"}`);
  } catch (error) {
    setSettingsStatus(`测试失败：${error.message}`);
  } finally {
    setSettingsButtonsDisabled(false);
  }
}

function setSettingsButtonsDisabled(disabled) {
  els.saveSettingsBtn.disabled = disabled;
  els.testSettingsBtn.disabled = disabled;
}

function setSettingsStatus(message) {
  els.settingsStatus.textContent = message || "等待配置";
}

function providerDefaults(providerValue) {
  return (state.settings?.providers || []).find((provider) => provider.value === providerValue);
}

function providerLabel(providerValue) {
  return providerDefaults(providerValue)?.label || providerValue;
}

function replaceOptions(select, items) {
  select.innerHTML = "";
  for (const item of items) {
    select.append(new Option(item.label, item.value));
  }
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
    await loadSettings();
    return loadPayload();
  }

  renderRunOptions();
  syncUrl();
  renderDashboard();
  await syncWatchlistForCurrentUser();
  await syncCompareForCurrentRun();
  await syncReportForCurrentRun();
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

async function syncReportForCurrentRun() {
  const run = state.payload?.run;
  if (!run || !run.report_path) {
    state.report = null;
    state.reportKey = "";
    renderReportPanel();
    return;
  }

  const reportKey = `${run.run_id}:${run.report_path}`;
  if (state.reportKey === reportKey && state.report) {
    renderReportPanel();
    return;
  }
  await loadReport();
}

async function loadReport({ force = false } = {}) {
  const run = state.payload?.run;
  if (!run) {
    renderReportPanel();
    return;
  }

  if (!force && !run.report_path) {
    state.report = null;
    state.reportKey = "";
    renderReportPanel();
    return;
  }

  const params = new URLSearchParams({ user_id: state.userId });
  if (run.run_id) {
    params.set("run_id", run.run_id);
  }

  els.reloadReportBtn.disabled = true;
  els.reportStatus.textContent = "读取中";
  try {
    const data = await getJson(`/api/report?${params.toString()}`);
    if (!data.ok) {
      state.report = null;
      state.reportKey = "";
      renderReportPanel(data);
      return;
    }
    state.report = data.report;
    state.reportKey = `${run.run_id}:${data.report.path}`;
    renderReportPanel();
  } catch (error) {
    state.report = null;
    state.reportKey = "";
    renderReportPanel({ ok: false, message: `读取报告失败：${error.message}` });
  } finally {
    els.reloadReportBtn.disabled = false;
  }
}

async function syncCompareForCurrentRun() {
  const run = state.payload?.run;
  if (!run || !run.ticker) {
    state.compare = null;
    state.compareKey = "";
    renderComparePanel();
    return;
  }

  const compareKey = `${state.userId}:${run.run_id}:${run.updated_at || ""}:${(run.events || []).length}`;
  if (state.compareKey === compareKey && state.compare) {
    renderComparePanel();
    return;
  }

  const params = new URLSearchParams({ user_id: state.userId });
  if (run.run_id) {
    params.set("run_id", run.run_id);
  }

  try {
    const data = await getJson(`/api/compare?${params.toString()}`);
    if (!data.ok) {
      state.compare = null;
      state.compareKey = "";
      renderComparePanel(data);
      return;
    }
    state.compare = data;
    state.compareKey = compareKey;
    renderComparePanel();
  } catch (error) {
    state.compare = null;
    state.compareKey = "";
    renderComparePanel({ ok: false, message: `读取对比失败：${error.message}` });
  }
}

async function syncWatchlistForCurrentUser() {
  try {
    const data = await getJson(`/api/watchlist?${new URLSearchParams({ user_id: state.userId }).toString()}`);
    if (!data.ok) {
      state.watchlist = null;
      state.watchlistKey = "";
      renderWatchlistPanel(data);
      return;
    }
    const watchlistKey = `${state.userId}:${data.updated_at || ""}:${data.total || 0}`;
    state.watchlist = data;
    state.watchlistKey = watchlistKey;
    renderWatchlistPanel();
  } catch (error) {
    state.watchlist = null;
    state.watchlistKey = "";
    renderWatchlistPanel({ ok: false, message: `读取观察池失败：${error.message}` });
  }
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
    state.report = null;
    state.reportKey = "";
    state.compare = null;
    state.compareKey = "";
    state.watchlist = null;
    state.watchlistKey = "";
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

function syncUrl() {
  const params = new URLSearchParams();
  if (state.userId) {
    params.set("user_id", state.userId);
  }
  if (state.runId) {
    params.set("run_id", state.runId);
  }
  const nextUrl = `${window.location.pathname}${params.toString() ? `?${params.toString()}` : ""}`;
  window.history.replaceState(null, "", nextUrl);
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

function renderWatchlistPanel(payload = null) {
  const watchlist = state.watchlist;
  if (!watchlist) {
    els.watchlistStatus.textContent = "暂无数据";
    els.watchlistSummary.innerHTML = "";
    els.watchlistGrid.innerHTML = `<div class="empty">${escapeHtml(payload?.message || "完成一次研究后，Portfolio Agent 会自动把标的加入观察池。")}</div>`;
    return;
  }

  const items = watchlist.items || [];
  els.watchlistStatus.textContent = `${watchlist.total || 0} tickers / ${watchlist.updated_at || "尚未更新"}`;
  els.watchlistSummary.innerHTML = renderWatchlistSummary(watchlist);
  if (items.length === 0) {
    els.watchlistGrid.innerHTML = `<div class="empty">观察池还是空的。先启动一次研究，系统会自动计算优先级。</div>`;
    return;
  }

  els.watchlistGrid.innerHTML = items
    .slice(0, 8)
    .map((item) => renderWatchlistCard(item))
    .join("");
  document.querySelectorAll("[data-watchlist-query]").forEach((button) => {
    button.addEventListener("click", () => {
      els.queryInput.value = button.getAttribute("data-watchlist-query") || "";
      els.launchStatus.textContent = "已填入复盘问题，可以直接启动研究。";
      els.queryInput.focus();
    });
  });
}

function renderWatchlistSummary(watchlist) {
  const stats = [
    ["标的总数", watchlist.total || 0],
    ["核心跟踪", watchlist.core_count || 0],
    ["高优先级以上", watchlist.high_count || 0],
    ["风险警戒", watchlist.risk_count || 0],
  ];
  return stats
    .map(
      ([label, value]) => `
        <div class="watchlist-stat">
          <span class="metric-label">${escapeHtml(label)}</span>
          <strong>${escapeHtml(value)}</strong>
        </div>
      `,
    )
    .join("");
}

function renderWatchlistCard(item) {
  const ticker = item.ticker || "N/A";
  const query = `帮我重新分析 ${ticker}，重点看估值压力和观点变化`;
  const reason = Array.isArray(item.watch_reasons) && item.watch_reasons.length > 0
    ? item.watch_reasons[0]
    : "暂无明确跟踪理由。";
  return `
    <article class="watchlist-card">
      <header>
        <div>
          <h3>${escapeHtml(ticker)}</h3>
          <p class="muted">${escapeHtml(item.company_name || item.sector || "N/A")}</p>
        </div>
        <span class="watchlist-score">${valueOrNA(item.priority_score)}</span>
      </header>
      <div class="watchlist-meta">
        <div>
          <span class="metric-label">优先级</span>
          <strong>${escapeHtml(item.priority_label || "N/A")}</strong>
        </div>
        <div>
          <span class="metric-label">角色</span>
          <strong>${escapeHtml(item.portfolio_role || "N/A")}</strong>
        </div>
        <div>
          <span class="metric-label">评级</span>
          <strong>${escapeHtml(item.rating || "N/A")} / ${valueOrNA(item.confidence, "%")}</strong>
        </div>
        <div>
          <span class="metric-label">近 1 月</span>
          <strong class="${trendClass(item.return_1m)}">${valueOrNA(item.return_1m, "%")}</strong>
        </div>
      </div>
      <p class="watchlist-reason">${escapeHtml(reason)}</p>
      <button class="watchlist-action" type="button" data-watchlist-query="${escapeAttribute(query)}">复盘</button>
    </article>
  `;
}

function renderComparePanel(payload = null) {
  const run = state.payload?.run;
  const compare = state.compare;

  if (!run) {
    els.compareStatus.textContent = "暂无 run";
    els.compareSummary.innerHTML = `<div class="empty">先启动一次研究，历史对比会自动出现。</div>`;
    els.compareTable.innerHTML = "";
    return;
  }

  if (!compare) {
    els.compareStatus.textContent = run.ticker ? "等待历史" : "等待 ticker";
    els.compareSummary.innerHTML = `<div class="empty">${escapeHtml(payload?.message || "当前 run 暂时没有可对比数据。")}</div>`;
    els.compareTable.innerHTML = "";
    return;
  }

  const current = compare.current || {};
  const previous = compare.previous || {};
  const changes = compare.changes || {};
  els.compareStatus.textContent = `${compare.ticker || run.ticker || "N/A"} / ${compare.runs?.length || 0} runs`;
  els.compareSummary.innerHTML = renderCompareCards(current, previous, changes);
  els.compareTable.innerHTML = renderCompareTable(compare.runs || []);
}

function renderCompareCards(current, previous, changes) {
  if (!changes.has_previous) {
    return `
      <div class="empty">${escapeHtml(changes.summary || "当前标的还没有更早的历史 run。")}</div>
    `;
  }
  return [
    {
      label: "结论变化",
      value: `${previous.rating || "N/A"} -> ${current.rating || "N/A"}`,
      detail: changes.rating_changed ? "投委会观点发生变化" : "投委会观点保持一致",
      trend: changes.rating_changed ? "trend-up" : "trend-flat",
    },
    {
      label: "置信度",
      value: `${valueOrNA(current.confidence, "%")} (${formatDelta(changes.confidence_delta, "点")})`,
      detail: `上一 run：${valueOrNA(previous.confidence, "%")}`,
      trend: trendClass(changes.confidence_delta),
    },
    {
      label: "最新收盘价",
      value: `${valueOrNA(current.last_close)} (${formatDelta(changes.last_close_delta_pct, "%")})`,
      detail: `上一 run：${valueOrNA(previous.last_close)}`,
      trend: trendClass(changes.last_close_delta),
    },
    {
      label: "近 1 月表现",
      value: `${valueOrNA(current.return_1m, "%")} (${formatDelta(changes.return_1m_delta, "点")})`,
      detail: `上一 run：${valueOrNA(previous.return_1m, "%")}`,
      trend: trendClass(changes.return_1m_delta),
    },
  ]
    .map(
      (item) => `
        <div class="compare-card">
          <span class="metric-label">${escapeHtml(item.label)}</span>
          <strong class="${item.trend}">${escapeHtml(item.value)}</strong>
          <p>${escapeHtml(item.detail)}</p>
        </div>
      `,
    )
    .join("");
}

function renderCompareTable(rows) {
  if (!Array.isArray(rows) || rows.length === 0) {
    return `<div class="empty">没有历史 run。</div>`;
  }
  const body = rows
    .map(
      (row) => `
        <tr class="${row.is_current ? "current-run" : ""}">
          <td>
            <a href="/?user_id=${escapeAttribute(state.userId)}&run_id=${escapeAttribute(row.run_id || "")}">${escapeHtml(row.run_id || "N/A")}</a>
            ${row.is_current ? '<span class="badge running">当前</span>' : ""}
          </td>
          <td>${escapeHtml(row.updated_at || "N/A")}</td>
          <td>${escapeHtml(row.rating || "N/A")} / ${valueOrNA(row.confidence, "%")}</td>
          <td>${valueOrNA(row.last_close)}<br><span class="muted">1D ${valueOrNA(row.return_1d, "%")} / 1M ${valueOrNA(row.return_1m, "%")}</span></td>
          <td>${escapeHtml(stripMarkdown(row.bull_summary || row.technical_summary || "N/A"))}</td>
          <td>${escapeHtml(stripMarkdown(row.bear_summary || row.committee_summary || "N/A"))}</td>
          <td>${row.report_path ? "已生成" : "尚未生成"}<br><span class="muted">${escapeHtml(`${row.event_count || 0} events`)}</span></td>
        </tr>
      `,
    )
    .join("");
  return `
    <table>
      <thead>
        <tr>
          <th>Run</th>
          <th>更新时间</th>
          <th>结论 / 置信度</th>
          <th>价格表现</th>
          <th>看多或技术理由</th>
          <th>看空或裁决理由</th>
          <th>报告</th>
        </tr>
      </thead>
      <tbody>${body}</tbody>
    </table>
  `;
}

function renderReportPanel(pendingPayload = null) {
  const run = state.payload?.run;
  const report = state.report;
  els.reloadReportBtn.disabled = !run;

  if (!run) {
    els.reportStatus.textContent = "暂无 run";
    els.reportMeta.innerHTML = "";
    els.reportPath.textContent = "尚未生成";
    els.reportBody.innerHTML = `<div class="empty">先启动一次研究，报告会在分析完成后出现在这里。</div>`;
    els.reportLinks.innerHTML = `<p class="muted">暂无链接。</p>`;
    return;
  }

  if (!report) {
    const message = pendingPayload?.message || (run.report_path ? "报告可读取，点击读取报告。" : "等待 Report / Verifier Agent 生成报告。");
    els.reportStatus.textContent = run.status === "running" ? "生成中" : "待读取";
    els.reportMeta.innerHTML = renderReportMeta({
      ticker: run.ticker || "识别中",
      rating: run.rating || "待投委会",
      confidence: run.confidence ? `${run.confidence}%` : "N/A",
      quality_status: "N/A",
      updated_at: run.updated_at || "N/A",
    });
    els.reportPath.textContent = run.report_path || "尚未生成";
    els.reportBody.innerHTML = `<div class="empty">${escapeHtml(message)}</div>`;
    els.reportLinks.innerHTML = `<p class="muted">报告生成后会自动展示链接。</p>`;
    return;
  }

  els.reportStatus.textContent = `${report.kind || "报告"} / ${report.updated_at || "N/A"}`;
  els.reportMeta.innerHTML = renderReportMeta(report);
  els.reportPath.textContent = report.path || "N/A";
  els.reportBody.innerHTML = markdownToHtml(report.markdown || "");
  els.reportLinks.innerHTML = renderReportLinks(report.links || []);
}

function renderReportMeta(report) {
  const items = [
    ["标题", report.title || report.ticker || "N/A"],
    ["评级", report.rating || "N/A"],
    ["置信度", report.confidence || "N/A"],
    ["周期", report.period || "N/A"],
    ["质检", report.quality_status || "N/A"],
  ];
  return items
    .map(
      ([label, value]) => `
        <div>
          <span class="metric-label">${escapeHtml(label)}</span>
          <strong>${escapeHtml(value)}</strong>
        </div>
      `,
    )
    .join("");
}

function renderReportLinks(links) {
  if (!Array.isArray(links) || links.length === 0) {
    return `<p class="muted">这份报告没有解析到外部链接。</p>`;
  }
  return links
    .map(
      (link) => `
        <div class="report-link">
          <a href="${escapeAttribute(link.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(link.title || link.url)}</a>
          <span>${escapeHtml([link.publisher, link.date].filter((item) => item && item !== "N/A").join(" / ") || "来源信息待补充")}</span>
        </div>
      `,
    )
    .join("");
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

function markdownToHtml(markdown) {
  const lines = String(markdown || "").split(/\r?\n/);
  const html = [];
  let paragraph = [];
  let list = [];
  let listType = "";
  let codeBlock = [];
  let inCode = false;

  const flushParagraph = () => {
    if (paragraph.length === 0) {
      return;
    }
    html.push(`<p>${renderInline(paragraph.join(" "))}</p>`);
    paragraph = [];
  };
  const flushList = () => {
    if (list.length === 0) {
      return;
    }
    const tag = listType === "ol" ? "ol" : "ul";
    html.push(`<${tag}>${list.map((item) => `<li>${renderInline(item)}</li>`).join("")}</${tag}>`);
    list = [];
    listType = "";
  };
  const flushCode = () => {
    if (codeBlock.length === 0) {
      return;
    }
    html.push(`<pre><code>${escapeHtml(codeBlock.join("\n"))}</code></pre>`);
    codeBlock = [];
  };

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    const trimmed = line.trim();

    if (trimmed.startsWith("```")) {
      flushParagraph();
      flushList();
      if (inCode) {
        flushCode();
        inCode = false;
      } else {
        inCode = true;
      }
      continue;
    }
    if (inCode) {
      codeBlock.push(line);
      continue;
    }

    if (!trimmed) {
      flushParagraph();
      flushList();
      continue;
    }

    if (isTableStart(lines, index)) {
      flushParagraph();
      flushList();
      const tableLines = [];
      while (index < lines.length && lines[index].includes("|")) {
        tableLines.push(lines[index]);
        index += 1;
      }
      index -= 1;
      html.push(renderTable(tableLines));
      continue;
    }

    const heading = trimmed.match(/^(#{1,4})\s+(.+)$/);
    if (heading) {
      flushParagraph();
      flushList();
      const level = Math.min(heading[1].length, 4);
      html.push(`<h${level}>${renderInline(heading[2])}</h${level}>`);
      continue;
    }

    const ordered = trimmed.match(/^\d+\.\s+(.+)$/);
    const unordered = trimmed.match(/^[-*]\s+(.+)$/);
    if (ordered || unordered) {
      flushParagraph();
      const nextType = ordered ? "ol" : "ul";
      if (listType && listType !== nextType) {
        flushList();
      }
      listType = nextType;
      list.push((ordered || unordered)[1]);
      continue;
    }

    paragraph.push(trimmed);
  }

  flushParagraph();
  flushList();
  flushCode();
  return html.join("");
}

function isTableStart(lines, index) {
  if (!lines[index]?.includes("|") || !lines[index + 1]?.includes("|")) {
    return false;
  }
  return /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(lines[index + 1]);
}

function renderTable(lines) {
  const rows = lines
    .filter((line) => !/^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(line))
    .map(parseTableRow)
    .filter((row) => row.length > 0);
  if (rows.length === 0) {
    return "";
  }
  const [header, ...body] = rows;
  return `
    <table>
      <thead><tr>${header.map((cell) => `<th>${renderInline(cell)}</th>`).join("")}</tr></thead>
      <tbody>${body.map((row) => `<tr>${row.map((cell) => `<td>${renderInline(cell)}</td>`).join("")}</tr>`).join("")}</tbody>
    </table>
  `;
}

function parseTableRow(line) {
  return line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim());
}

function renderInline(text) {
  const source = String(text || "");
  const linkPattern = /\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g;
  let output = "";
  let lastIndex = 0;
  for (const match of source.matchAll(linkPattern)) {
    output += escapeHtml(source.slice(lastIndex, match.index));
    output += `<a href="${escapeAttribute(match[2])}" target="_blank" rel="noopener noreferrer">${escapeHtml(match[1])}</a>`;
    lastIndex = match.index + match[0].length;
  }
  output += escapeHtml(source.slice(lastIndex));
  return output
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
}

function valueOrNA(value, suffix = "") {
  if (value === null || value === undefined || value === "") {
    return "N/A";
  }
  const number = Number(value);
  if (Number.isFinite(number)) {
    const precision = Math.abs(number) >= 100 ? 2 : 2;
    return `${number.toFixed(precision).replace(/\.00$/, "")}${suffix}`;
  }
  return `${escapeHtml(String(value))}${suffix}`;
}

function formatDelta(value, unit = "") {
  if (value === null || value === undefined || value === "") {
    return "N/A";
  }
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return "N/A";
  }
  const sign = number > 0 ? "+" : "";
  return `${sign}${number.toFixed(2).replace(/\.00$/, "")}${unit}`;
}

function trendClass(value) {
  const number = Number(value);
  if (!Number.isFinite(number) || number === 0) {
    return "trend-flat";
  }
  return number > 0 ? "trend-up" : "trend-down";
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

function escapeAttribute(value) {
  return escapeHtml(value).replaceAll("`", "&#096;");
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
