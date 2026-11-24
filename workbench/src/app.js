/* 合同工作台 · UI 逻辑 */
(function (root) {
  const WB = (root.WB = root.WB || {});
  const $ = (sel, el) => (el || document).querySelector(sel);
  const $$ = (sel, el) => Array.from((el || document).querySelectorAll(sel));
  const esc = WB.escapeHtml;

  const ICONS = {
    home: '<path d="M3 11.5 12 4l9 7.5"/><path d="M5 10v10h14V10"/><path d="M9 20v-6h6v6"/>',
    review: '<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4"/><circle cx="11" cy="13" r="3"/><path d="M13.2 15.2 16 18"/>',
    ledger: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 10h18M9 10v10M15 10v10"/>',
    clause: '<path d="M6 3h12v18l-6-4-6 4z"/>',
    rules: '<path d="M9 6h11M9 12h11M9 18h11"/><path d="m3 6 1.5 1.5L7 5"/><path d="m3 12 1.5 1.5L7 11"/><path d="m3 18 1.5 1.5L7 17"/>',
    settings: '<path d="M4 7h16M4 12h16M4 17h16"/><circle cx="9" cy="7" r="2"/><circle cx="15" cy="12" r="2"/><circle cx="8" cy="17" r="2"/>',
    export: '<path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M4 20h16"/>',
    upload: '<path d="M12 16V4"/><path d="m7 9 5-5 5 5"/><path d="M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3"/>',
    search: '<circle cx="11" cy="11" r="7"/><path d="m16.5 16.5 4 4"/>',
    calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M8 3v4M16 3v4M3 10h18"/>',
    clock: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
    wallet: '<path d="M4 7.5A2.5 2.5 0 0 1 6.5 5H18a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H6.5A2.5 2.5 0 0 1 4 16.5z"/><path d="M4 8.5h16"/><circle cx="16" cy="13.5" r="1.2"/>',
    edit: '<path d="M4 20h4l10-10-4-4L4 16z"/><path d="m13.5 5.5 4 4"/>',
    trash: '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/><path d="M10 11v5M14 11v5"/>',
  };

  const STEPS = [
    { n: 1, label: "抽取" },
    { n: 2, label: "法条" },
    { n: 3, label: "评估" },
    { n: 4, label: "复核" },
    { n: 5, label: "报告" },
  ];

  const RUNNING_TITLES = {
    1: "正在读取合同条款……",
    2: "正在匹配法条……",
    3: "正在逐条评估风险……",
    4: "正在复核分析质量……",
    5: "正在生成报告……",
  };

  const TYPE_KEYWORDS = {
    房屋租赁合同: ["租赁", "出租", "承租", "押金", "房东", "房租", "房屋"],
    劳动合同: ["劳动合同", "用人单位", "劳动者", "试用期", "工资", "社保", "竞业限制"],
    买卖合同: ["买卖合同", "买方", "卖方", "交货", "验收", "货款", "定金"],
    服务合同: ["服务合同", "委托方", "服务方", "服务费", "交付物", "验收标准"],
    合作协议: ["合作协议", "合作方", "利润分配", "分成", "退出", "出资"],
    借款合同: ["借款", "出借", "借款人", "利息", "利率", "还款", "担保"],
  };

  const LEVEL_RANK = { 高: 3, 中: 2, 低: 1 };
  const LEVEL_MARK = { 高: "mark-square", 中: "mark-diamond", 低: "mark-ring" };
  const LEVEL_CLS = { 高: "high", 中: "mid", 低: "low" };

  const state = {
    settings: null,
    lastResult: null,
    lastContractText: "",
    running: false,
    parsingFile: false,
    abort: null,
    clauseFilter: "房屋租赁合同",
    reportTab: "list",
    hintTimer: null,
    recommendTimer: null,
    history: [],
    historyQuery: "",
    homeTab: "reviews",
    ledger: [],
    ledgerStatus: "全部",
    ledgerType: "全部类型",
    editingLedgerId: null,
    lastReviewId: null,
    ruleFilter: "全部",
    ruleStatus: "全部状态",
    ruleQuery: "",
  };

  const ui = {};
  let beamMark = null;
  let beamResizeTimer = null;

  document.addEventListener("DOMContentLoaded", init);

  async function init() {
    cacheUI();
    injectIcons();
    state.settings = await WB.loadSettings();
    const [history, ledger] = await Promise.all([WB.listReviews(), WB.listLedger()]);
    state.history = history;
    state.ledger = ledger;
    if (WB.RuleStore) {
      try { await WB.RuleStore.load(); } catch (e) { /* 保留内置默认规则 */ }
      WB.RuleStore.onRemoteChange = refreshRulesFromStorage;
    }
    populateTypes();
    populateProviders();
    populateLedgerOptions();
    populateRuleOptions();
    renderRuleMeta();
    renderSamples();
    renderClauseFilters();
    renderClauses();
    bindEvents();
    updateModelStatus();

    const saved = await WB.loadCurrent();
    if (saved && saved.result && saved.contractText) {
      state.lastReviewId = saved.reviewId || null;
      ui.input.value = saved.contractText;
      updateCharCount();
      if (saved.contractType) setType(saved.contractType, false);
      showResult(saved.result, saved.contractText);
      toast("已恢复上次审查结果");
    } else {
      showEmpty();
    }
    root.__WB_READY__ = true;
  }

  function cacheUI() {
    ui.typeSelect = $("#contract-type");
    ui.stanceSelect = $("#review-stance");
    ui.stanceHint = $("#stance-hint");
    ui.modelStatus = $("#model-status");
    ui.modelStatusText = $("#model-status-text");
    ui.input = $("#contract-input");
    ui.charCount = $("#char-count");
    ui.typeHint = $("#type-hint");
    ui.fileBtn = $("#btn-file");
    ui.fileInput = $("#file-input");
    ui.fileStatus = $("#file-status");
    ui.sampleRow = $("#sample-row");
    ui.empty = $("#review-empty");
    ui.running = $("#review-running");
    ui.result = $("#review-result");
    ui.error = $("#review-error");
    ui.runningTitle = $("#running-title");
    ui.runningDetail = $("#running-detail");
    ui.pipeline = $("#pipeline");
    ui.pipelineResult = $("#pipeline-result");
    ui.resultStats = $("#result-stats");
    ui.contractView = $("#contract-view");
    ui.riskList = $("#risk-list");
    ui.riskCount = $("#risk-count");
    ui.reportView = $("#report-view");
    ui.clauseFilters = $("#clause-filters");
    ui.clauseList = $("#clause-list");
    ui.ruleFilters = $("#rule-filters");
    ui.ruleList = $("#rule-list");
    ui.ruleSummary = $("#rule-summary");
    ui.ruleMeta = $("#rules-law-meta");
    ui.ruleSearch = $("#rule-search");
    ui.ruleStatusFilter = $("#rule-status-filter");
    ui.ruleType = $("#rule-type");
    ui.ruleLevel = $("#rule-level");
    ui.ruleName = $("#rule-name");
    ui.ruleKeywords = $("#rule-keywords");
    ui.ruleCondition = $("#rule-condition");
    ui.ruleBasis = $("#rule-basis");
    ui.ruleAdvice = $("#rule-advice");
    ui.ruleId = $("#rule-id");
    ui.ruleForm = $("#rule-form");
    ui.ruleFormTitle = $("#rule-form-title");
    ui.ruleFormNote = $("#rule-form-note");
    ui.ruleDrawer = $("#rule-drawer");
    ui.ruleBackdrop = $("#rule-backdrop");
    ui.ruleAdd = $("#btn-rule-add");
    ui.ruleReset = $("#btn-rule-reset");
    ui.topbar = $("#topbar");
    ui.homeStats = $("#home-stats");
    ui.homeGreetingBlock = $("#home-greeting-block");
    ui.homeGreeting = $("#home-greeting");
    ui.homeSub = $("#home-sub");
    ui.sidebarSearch = $("#sidebar-search");
    ui.sidebarSearchClear = $("#sidebar-search-clear");
    ui.homeIcs = $("#btn-home-ics");
    ui.homeTabs = $$(".home-tab");
    ui.homeReviewTools = $("#home-review-tools");
    ui.homeContractTools = $("#home-contract-tools");
    ui.homeReviewsPane = $("#home-reviews-pane");
    ui.homeContractsPane = $("#home-contracts-pane");
    ui.homeContractsList = $("#home-contracts-list");
    ui.homeLedgerAll = $("#btn-home-ledger-all");
    ui.contractsSearch = $("#contracts-search");
    ui.historyList = $("#history-list");
    ui.historySearch = $("#history-search");
    ui.historyClear = $("#btn-history-clear");
    ui.homeReview = $("#btn-home-review");
    ui.homeLedger = $("#btn-home-ledger");
    ui.homeReminders = $("#home-reminder-list");
    ui.ledgerList = $("#ledger-list");
    ui.ledgerFilters = $("#ledger-filters");
    ui.ledgerSearch = $("#ledger-search");
    ui.ledgerTypeFilter = $("#ledger-type-filter");
    ui.ledgerSummary = $("#ledger-summary");
    ui.ledgerTableCount = $("#ledger-table-count");
    ui.ledgerDatesSub = $("#ledger-dates-sub");
    ui.ledgerDatesList = $("#ledger-dates-list");
    ui.ledgerAdd = $("#btn-ledger-add");
    ui.ledgerIcs = $("#btn-ledger-ics");
    ui.ledgerCsv = $("#btn-ledger-csv");
    ui.ledgerDrawer = $("#ledger-drawer");
    ui.ledgerBackdrop = $("#ledger-backdrop");
    ui.ledgerForm = $("#ledger-form");
    ui.ledgerFormTitle = $("#ledger-form-title");
    ui.ledgerTitle = $("#ledger-title");
    ui.ledgerType = $("#ledger-type");
    ui.ledgerStatus = $("#ledger-status");
    ui.ledgerCounterparty = $("#ledger-counterparty");
    ui.ledgerAmount = $("#ledger-amount");
    ui.ledgerStart = $("#ledger-start");
    ui.ledgerEnd = $("#ledger-end");
    ui.ledgerPaymentDate = $("#ledger-payment-date");
    ui.ledgerPaymentAmount = $("#ledger-payment-amount");
    ui.ledgerNote = $("#ledger-note");
    ui.ledgerReviewId = $("#ledger-review-id");
    ui.drawer = $("#settings-drawer");
    ui.backdrop = $("#settings-backdrop");
    ui.toast = $("#toast");
    ui.errorTitle = $("#error-title");
    ui.errorDetail = $("#error-detail");
  }

  function iconSvg(name) {
    const paths = ICONS[name];
    if (!paths) return "";
    return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths}</svg>`;
  }

  function injectIcons() {
    $$("[data-icon]").forEach((el) => {
      const svg = iconSvg(el.dataset.icon);
      if (!svg) return;
      el.innerHTML = svg;
      el.classList.add("icon");
    });
  }

  // ═════════════ 初始化数据 ═════════════

  function populateTypes() {
    ui.typeSelect.innerHTML = WB.CONTRACT_TYPES.map(
      (t) => `<option value="${esc(t)}">${esc(t)}</option>`
    ).join("");
    setType(state.settings.contractType || WB.CONTRACT_TYPES[0], false);
  }

  function populateStances(type) {
    const t = type || state.settings.contractType;
    if (!ui.stanceSelect) return;
    const roles = Object.prototype.hasOwnProperty.call(WB.STANCES, t) ? WB.STANCES[t] : [];
    const options = [{ key: "neutral", label: "中立（双方）" }].concat(roles);
    const current = state.settings.stance || "neutral";
    const valid = options.some((r) => r.key === current);
    const value = valid ? current : "neutral";
    ui.stanceSelect.innerHTML = options
      .map((r) => `<option value="${esc(r.key)}">${esc(r.label)}</option>`)
      .join("");
    ui.stanceSelect.value = value;
    state.settings.stance = value;
    updateStanceHint(t);
  }

  function updateStanceHint(type) {
    if (!ui.stanceHint) return;
    const label = WB.stanceLabel(type || state.settings.contractType, state.settings.stance);
    ui.stanceHint.textContent =
      state.settings.stance === "neutral"
        ? "按双方公平性审查，不偏向任何一方"
        : `站在${label}一侧，优先看对我方不利的条款`;
  }

  function setType(type, persist) {
    if (!WB.CONTRACT_TYPES.includes(type)) return;
    ui.typeSelect.value = type;
    state.settings.contractType = type;
    populateStances(type);
    if (persist !== false) WB.saveSettings(state.settings).catch(() => {});
  }

  function populateLedgerOptions() {
    const types = WB.CONTRACT_TYPES.concat(["其他"]);
    ui.ledgerType.innerHTML = types
      .map((t) => `<option value="${esc(t)}">${esc(t)}</option>`)
      .join("");
    ui.ledgerStatus.innerHTML = WB.Ledger.STATUSES
      .map((s) => `<option value="${esc(s)}">${esc(s)}</option>`)
      .join("");
    if (ui.ledgerTypeFilter) {
      ui.ledgerTypeFilter.innerHTML = ["全部类型"]
        .concat(types)
        .map((t) => `<option value="${esc(t)}">${esc(t)}</option>`)
        .join("");
      ui.ledgerTypeFilter.value = state.ledgerType;
    }
  }

  function populateProviders() {
    const sel = $("#set-provider");
    sel.innerHTML = Object.keys(WB.PROVIDERS).map((k) => {
      const p = WB.PROVIDERS[k];
      return `<option value="${esc(k)}">${esc(p.label)}</option>`;
    }).join("");
  }

  function populateRuleOptions() {
    const types = ["通用"].concat(WB.CONTRACT_TYPES);
    ui.ruleType.innerHTML = types
      .map((t) => `<option value="${esc(t)}">${esc(t)}</option>`)
      .join("");
  }

  function renderSamples() {
    ui.sampleRow.innerHTML = (WB.SAMPLES || []).map(
      (s) => `<button class="sample-chip" type="button" data-sample="${esc(s.key)}">${esc(s.name)}</button>`
    ).join("");
  }

  function renderClauseFilters() {
    const types = WB.CONTRACT_TYPES.concat(["通用"]);
    ui.clauseFilters.innerHTML = types.map((t) => {
      const label = t === "通用" ? "通用" : t.replace("合同", "");
      const active = t === state.clauseFilter ? " active" : "";
      return `<button class="filter-chip${active}" type="button" data-type="${esc(t)}">${esc(label)}</button>`;
    }).join("");
  }

  function renderClauses() {
    const rules = (WB.RULES || [])
      .filter((r) => r.contractType === state.clauseFilter)
      .sort((a, b) => (LEVEL_RANK[b.level] - LEVEL_RANK[a.level]) || a.name.localeCompare(b.name, "zh"));

    if (!rules.length) {
      ui.clauseList.innerHTML = '<p class="clause-empty">这一类暂时没有内置条款。</p>';
      return;
    }

    ui.clauseList.innerHTML = rules.map((r) => {
      const cls = LEVEL_CLS[r.level];
      const mark = LEVEL_MARK[r.level];
      const off = r.enabled === false;
      return `<article class="clause-card ${cls}${off ? " is-off" : ""}">
        <div class="clause-card-head">
          <span class="risk-mark ${mark}"></span>
          <span class="clause-card-name">${esc(r.name)}</span>
          <span class="clause-card-level level-${cls}">${r.level}风险</span>
          ${off ? '<span class="clause-card-level level-off">已停用</span>' : ""}
          ${r.builtin ? "" : '<span class="clause-card-level level-custom">自定义</span>'}
          <span class="clause-card-type">${esc(r.basis)}</span>
        </div>
        <p class="clause-card-condition">${esc(r.condition)}</p>
        <div class="clause-card-basis">关键词：${esc((r.keywords || []).join(" / "))}</div>
        <div class="clause-card-advice"><b>替代写法</b>${esc(r.advice)}</div>
      </article>`;
    }).join("");
  }

  // ═════════════ 审查规则（V1.5） ═════════════

  function renderRuleFilters() {
    if (!ui.ruleFilters) return;
    const types = ["全部"].concat(WB.CONTRACT_TYPES, ["通用"]);
    ui.ruleFilters.innerHTML = types.map((t) => {
      const active = t === state.ruleFilter ? " active" : "";
      const label = t === "全部" ? "全部" : t === "通用" ? "通用" : t.replace("合同", "");
      return `<button class="filter-chip${active}" type="button" data-rule-type="${esc(t)}">${esc(label)}</button>`;
    }).join("");
  }

  function renderRuleMeta() {
    if (!ui.ruleMeta) return;
    const meta = WB.RULES_META;
    if (!meta || !meta.verifiedAt) {
      ui.ruleMeta.innerHTML = "";
      return;
    }
    const sources = (meta.sources || []).map((s) => {
      const version = s.version ? `<em>${esc(s.version)}</em>` : "";
      return `<li><span>${esc(s.name)}</span>${version}</li>`;
    }).join("");
    ui.ruleMeta.innerHTML = `<details>
      <summary>内置规则法条依据核对于 ${esc(meta.verifiedAt)} · ${(meta.sources || []).length} 部现行法规</summary>
      <p>${esc(meta.note || "")}</p>
      <ul>${sources}</ul>
    </details>`;
  }

  function renderRules() {
    if (!ui.ruleList) return;
    const all = WB.RULES || [];
    const q = state.ruleQuery.trim().toLowerCase();
    const rules = all.filter((r) => {
      if (state.ruleFilter !== "全部" && r.contractType !== state.ruleFilter) return false;
      if (state.ruleStatus === "已启用" && !r.enabled) return false;
      if (state.ruleStatus === "已停用" && r.enabled) return false;
      if (!q) return true;
      const hay = [r.name, r.contractType, r.condition, r.basis, r.advice]
        .concat(r.keywords || [])
        .join(" ")
        .toLowerCase();
      return hay.indexOf(q) >= 0;
    });

    const typeOrder = {};
    WB.CONTRACT_TYPES.concat(["通用"]).forEach((t, i) => { typeOrder[t] = i; });
    rules.sort((a, b) => {
      const ta = typeOrder[a.contractType] == null ? 9 : typeOrder[a.contractType];
      const tb = typeOrder[b.contractType] == null ? 9 : typeOrder[b.contractType];
      return ta - tb || (LEVEL_RANK[b.level] - LEVEL_RANK[a.level]) || a.name.localeCompare(b.name, "zh");
    });

    const enabled = all.filter((r) => r.enabled).length;
    const custom = all.filter((r) => !r.builtin).length;
    if (ui.ruleSummary) {
      ui.ruleSummary.textContent =
        `共 ${all.length} 条 · 已启用 ${enabled} · 已停用 ${all.length - enabled} · 内置 ${all.length - custom} · 自定义 ${custom}`;
    }
    if (!rules.length) {
      ui.ruleList.innerHTML = '<p class="clause-empty">没有匹配的规则。</p>';
      return;
    }
    ui.ruleList.innerHTML = rules.map((r) => {
      const cls = LEVEL_CLS[r.level];
      const mark = LEVEL_MARK[r.level];
      const off = r.enabled === false;
      const edited = r.builtin && WB.RuleStore && WB.RuleStore.hasOverride(r.id);
      return `<article class="rule-row level-${cls}${off ? " is-off" : ""}" data-rule-row="${esc(r.id)}">
        <div class="rule-row-main">
          <div class="rule-row-top">
            <span class="risk-mark ${mark}"></span>
            <h3>${esc(r.name)}</h3>
            <span class="clause-card-level level-${cls}">${r.level}风险</span>
            ${r.builtin ? "" : '<span class="rule-tag custom">自定义</span>'}
            ${off ? '<span class="rule-tag off">已停用</span>' : ""}
            ${edited ? '<span class="rule-tag edited">已修改</span>' : ""}
            <span class="rule-type">${esc(r.contractType)}</span>
          </div>
          <p class="rule-condition">${esc(r.condition)}</p>
          <p class="rule-keywords">关键词：<b>${esc((r.keywords || []).join(" / "))}</b></p>
          <p class="rule-basis">${esc(r.basis)}</p>
          <p class="rule-advice"><b>建议</b>${esc(r.advice)}</p>
        </div>
        <div class="rule-actions">
          <label class="rule-switch" title="${off ? "启用规则" : "停用规则"}">
            <input type="checkbox" data-toggle-rule="${esc(r.id)}" ${off ? "" : "checked"} aria-label="${esc((off ? "启用" : "停用") + "规则：" + r.name)}">
            <span class="rule-switch-track" aria-hidden="true"></span>
          </label>
          <button type="button" data-edit-rule="${esc(r.id)}">编辑</button>
          ${r.builtin ? "" : `<button type="button" data-delete-rule="${esc(r.id)}">删除</button>`}
        </div>
      </article>`;
    }).join("");
  }

  function openRuleForm(id) {
    if (!ui.ruleDrawer) return;
    const rule = id ? WB.RuleStore.find(id) : null;
    const defaultType = state.ruleFilter !== "全部"
      ? state.ruleFilter
      : (state.settings && state.settings.contractType) || WB.CONTRACT_TYPES[0];
    ui.ruleFormTitle.textContent = rule ? "编辑规则" : "新增规则";
    ui.ruleId.value = rule ? rule.id : "";
    ui.ruleName.value = rule ? rule.name : "";
    ui.ruleType.value = rule ? rule.contractType : defaultType;
    ui.ruleLevel.value = rule ? rule.level : "中";
    ui.ruleKeywords.value = rule ? (rule.keywords || []).join("、") : "";
    ui.ruleCondition.value = rule ? rule.condition : "";
    ui.ruleBasis.value = rule ? rule.basis : "";
    ui.ruleAdvice.value = rule ? rule.advice : "";
    ui.ruleFormNote.textContent = rule && rule.builtin
      ? "内置规则可以修改和停用，但保留在本机规则库中，不能删除。"
      : "自定义规则只保存在本机浏览器，可随时删除。";
    ui.ruleBackdrop.classList.remove("hidden");
    ui.ruleDrawer.classList.remove("hidden");
    ui.ruleName.focus();
  }

  function closeRuleForm() {
    if (!ui.ruleDrawer) return;
    ui.ruleBackdrop.classList.add("hidden");
    ui.ruleDrawer.classList.add("hidden");
  }

  function ruleErrorToast(res) {
    if (!res) return;
    if (res.reason === "conflict") {
      toast("规则已在其他标签页更新，已载入最新版本", "error");
      if (ui.ruleDrawer && !ui.ruleDrawer.classList.contains("hidden")) closeRuleForm();
      renderRuleFilters();
      renderRules();
      renderClauses();
      return;
    }
    if (res.reason === "limit") {
      toast(`自定义规则已达 ${res.limit || WB.RuleStore.maxCustom} 条上限`, "error");
      return;
    }
    if (res.reason === "invalid") {
      toast(res.message || "规则内容不完整", "error");
      return;
    }
    if (res.reason === "builtin") {
      toast("内置规则不能删除，可以停用");
      return;
    }
    if (res.reason === "missing") {
      toast("规则已不存在，正在刷新列表", "error");
      renderRules();
      refreshRulesFromStorage();
      return;
    }
    toast("规则未保存：浏览器存储不可用", "error");
    renderRules();
  }

  function refreshRulesFromStorage() {
    if (!WB.RuleStore || !WB.RuleStore.refresh) return;
    WB.RuleStore.refresh()
      .then((changed) => {
        if (!changed) return;
        if ($("#view-rules") && !$("#view-rules").classList.contains("hidden")) {
          renderRuleFilters();
          renderRules();
        }
        renderClauses();
        if (ui.ruleDrawer && !ui.ruleDrawer.classList.contains("hidden")) {
          closeRuleForm();
          toast("规则已在其他标签页更新，请重新编辑");
        }
      })
      .catch(() => {});
  }

  async function toggleRule(id, enabled) {
    const res = await WB.RuleStore.setEnabled(id, enabled);
    if (!res.ok) {
      ruleErrorToast(res);
      return;
    }
    renderRules();
    renderClauses();
  }

  async function saveRuleFromForm(e) {
    e.preventDefault();
    const raw = {
      contractType: ui.ruleType.value,
      name: ui.ruleName.value,
      keywords: ui.ruleKeywords.value,
      condition: ui.ruleCondition.value,
      level: ui.ruleLevel.value,
      basis: ui.ruleBasis.value,
      advice: ui.ruleAdvice.value,
    };
    const check = WB.RuleStore.validate(raw);
    if (!check.ok) {
      toast(check.message, "error");
      return;
    }
    const id = ui.ruleId.value;
    const res = id ? await WB.RuleStore.update(id, raw) : await WB.RuleStore.addCustom(raw);
    if (!res.ok) {
      ruleErrorToast(res);
      return;
    }
    closeRuleForm();
    renderRuleFilters();
    renderRules();
    renderClauses();
    toast(id ? "规则已更新" : "规则已新增");
  }

  async function deleteRule(id) {
    const rule = WB.RuleStore.find(id);
    if (!rule) return;
    if (rule.builtin) {
      toast("内置规则不能删除，可以停用");
      return;
    }
    if (!window.confirm(`删除自定义规则「${rule.name}」？`)) return;
    const res = await WB.RuleStore.removeCustom(id);
    if (!res.ok) {
      ruleErrorToast(res);
      return;
    }
    renderRuleFilters();
    renderRules();
    renderClauses();
    toast("规则已删除");
  }

  async function resetBuiltinRules() {
    const count = Object.keys(WB.RuleStore.state().overrides).length;
    if (!count) {
      toast("内置规则没有被修改过");
      return;
    }
    if (!window.confirm(`恢复 ${count} 条内置规则的默认内容？停用状态也会一并恢复。`)) return;
    const res = await WB.RuleStore.resetBuiltin();
    if (!res.ok) {
      ruleErrorToast(res);
      return;
    }
    renderRuleFilters();
    renderRules();
    renderClauses();
    toast("内置规则已恢复默认");
  }

  // ═════════════ 事件 ═════════════

  function bindEvents() {
    $$(".nav-item").forEach((btn) => {
      btn.addEventListener("click", () => {
        if (!btn.dataset.view) return;
        switchView(btn.dataset.view);
      });
    });

    ui.typeSelect.addEventListener("change", () => setType(ui.typeSelect.value));
    ui.stanceSelect.addEventListener("change", () => {
      state.settings.stance = ui.stanceSelect.value;
      updateStanceHint();
      WB.saveSettings(state.settings).catch(() => {});
    });

    ui.input.addEventListener("input", () => {
      updateCharCount();
      scheduleTypeRecommend();
    });

    ui.input.addEventListener("keydown", (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
        e.preventDefault();
        startReview();
      }
    });

    ui.sampleRow.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-sample]");
      if (!btn) return;
      loadSample(btn.dataset.sample);
    });

    ui.fileBtn.addEventListener("click", () => ui.fileInput.click());
    ui.fileInput.addEventListener("change", () => {
      const file = ui.fileInput.files && ui.fileInput.files[0];
      if (file) handleFile(file);
    });
    ui.empty.addEventListener("dragover", (e) => {
      if (!e.dataTransfer) return;
      e.preventDefault();
      e.dataTransfer.dropEffect = "copy";
      ui.input.classList.add("dragover");
    });
    ui.empty.addEventListener("dragleave", (e) => {
      if (!ui.empty.contains(e.relatedTarget)) ui.input.classList.remove("dragover");
    });
    ui.empty.addEventListener("drop", (e) => {
      e.preventDefault();
      ui.input.classList.remove("dragover");
      const file = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
      if (file) handleFile(file);
    });

    $("#btn-start").addEventListener("click", startReview);
    $("#btn-clear").addEventListener("click", () => {
      ui.input.value = "";
      updateCharCount();
      ui.typeHint.textContent = "";
      resetFileStatus();
      ui.input.focus();
    });

    $("#btn-cancel").addEventListener("click", cancelReview);
    $("#btn-retry").addEventListener("click", startReview);
    $("#btn-back").addEventListener("click", showEmpty);

    $("#btn-export").addEventListener("click", exportDoc);
    $("#btn-print").addEventListener("click", () => {
      if (!state.lastResult) return;
      activateTab("report");
      window.print();
    });
    $("#btn-new").addEventListener("click", nextReview);

    $$(".panel-tab").forEach((btn) => {
      btn.addEventListener("click", () => activateTab(btn.dataset.tab));
    });

    ui.riskList.addEventListener("click", (e) => {
      const btn = e.target.closest(".risk-item");
      if (!btn) return;
      jumpToRisk(btn.dataset.idx, btn);
    });

    ui.clauseFilters.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-type]");
      if (!btn) return;
      state.clauseFilter = btn.dataset.type;
      renderClauseFilters();
      renderClauses();
    });

    if (ui.ruleFilters) {
      ui.ruleFilters.addEventListener("click", (e) => {
        const btn = e.target.closest("[data-rule-type]");
        if (!btn) return;
        state.ruleFilter = btn.dataset.ruleType;
        renderRuleFilters();
        renderRules();
      });
    }
    if (ui.ruleStatusFilter) {
      ui.ruleStatusFilter.addEventListener("change", () => {
        state.ruleStatus = ui.ruleStatusFilter.value;
        renderRules();
      });
    }
    if (ui.ruleSearch) {
      ui.ruleSearch.addEventListener("input", () => {
        state.ruleQuery = ui.ruleSearch.value;
        renderRules();
      });
    }
    if (ui.ruleList) {
      ui.ruleList.addEventListener("change", (e) => {
        const toggle = e.target.closest("[data-toggle-rule]");
        if (toggle) toggleRule(toggle.dataset.toggleRule, toggle.checked);
      });
      ui.ruleList.addEventListener("click", (e) => {
        const del = e.target.closest("[data-delete-rule]");
        if (del) {
          deleteRule(del.dataset.deleteRule);
          return;
        }
        const edit = e.target.closest("[data-edit-rule]");
        if (edit) {
          openRuleForm(edit.dataset.editRule);
          return;
        }
        const row = e.target.closest("[data-rule-row]");
        if (row && !e.target.closest(".rule-switch")) openRuleForm(row.dataset.ruleRow);
      });
    }
    if (ui.ruleAdd) ui.ruleAdd.addEventListener("click", () => openRuleForm(null));
    if (ui.ruleReset) ui.ruleReset.addEventListener("click", resetBuiltinRules);
    if (ui.ruleBackdrop) ui.ruleBackdrop.addEventListener("click", closeRuleForm);
    if (ui.ruleForm) ui.ruleForm.addEventListener("submit", saveRuleFromForm);
    $("#btn-close-rule").addEventListener("click", closeRuleForm);
    $("#btn-cancel-rule").addEventListener("click", closeRuleForm);

    ui.homeReview.addEventListener("click", nextReview);
    ui.homeTabs.forEach((btn) => {
      btn.addEventListener("click", () => setHomeTab(btn.dataset.homeTab));
    });
    ui.historySearch.addEventListener("input", () => {
      applyHomeQuery(ui.historySearch.value);
    });
    if (ui.sidebarSearch) {
      ui.sidebarSearch.addEventListener("input", () => {
        setHomeTab("reviews");
        applyHomeQuery(ui.sidebarSearch.value);
        if ($("#view-home").classList.contains("hidden")) switchView("home");
      });
    }
    if (ui.contractsSearch) {
      ui.contractsSearch.addEventListener("input", () => {
        applyHomeQuery(ui.contractsSearch.value);
      });
    }
    if (ui.sidebarSearchClear) {
      ui.sidebarSearchClear.addEventListener("click", () => {
        applyHomeQuery("");
        if (ui.sidebarSearch) ui.sidebarSearch.focus();
      });
    }
    ui.historyList.addEventListener("click", (e) => {
      if (e.target.closest("[data-new-review]")) {
        nextReview();
        return;
      }
      const del = e.target.closest("[data-delete-review]");
      if (del) {
        deleteHistory(del.dataset.deleteReview);
        return;
      }
      const ledgerHit = e.target.closest("[data-search-ledger]");
      if (ledgerHit) {
        openLedgerForm(ledgerHit.dataset.searchLedger);
        return;
      }
      const item = e.target.closest("[data-open-review]");
      if (item) openHistory(item.dataset.openReview);
    });
    ui.historyClear.addEventListener("click", clearHistory);
    if (ui.homeContractsList) {
      ui.homeContractsList.addEventListener("click", (e) => {
        if (e.target.closest("[data-home-ledger-add]")) {
          switchView("ledger");
          openLedgerForm(null);
          return;
        }
        const row = e.target.closest("[data-home-ledger]");
        if (row) openLedgerForm(row.dataset.homeLedger);
      });
    }
    if (ui.homeLedgerAll) {
      ui.homeLedgerAll.addEventListener("click", () => switchView("ledger"));
    }

    ui.homeLedger.addEventListener("click", () => switchView("ledger"));
    if (ui.homeIcs) ui.homeIcs.addEventListener("click", () => exportLedgerIcs());
    ui.homeReminders.addEventListener("click", (e) => {
      const item = e.target.closest("[data-reminder-entry]");
      if (item) openLedgerForm(item.dataset.reminderEntry);
    });

    ui.ledgerAdd.addEventListener("click", () => openLedgerForm(null));
    ui.ledgerIcs.addEventListener("click", () => exportLedgerIcs());
    ui.ledgerCsv.addEventListener("click", exportLedgerCsv);
    ui.ledgerSearch.addEventListener("input", () => {
      applyHomeQuery(ui.ledgerSearch.value);
    });
    if (ui.ledgerTypeFilter) {
      ui.ledgerTypeFilter.addEventListener("change", () => {
        state.ledgerType = ui.ledgerTypeFilter.value;
        renderLedger();
      });
    }
    if (ui.ledgerDatesList) {
      ui.ledgerDatesList.addEventListener("click", (e) => {
        const item = e.target.closest("[data-edit-ledger]");
        if (item) openLedgerForm(item.dataset.editLedger);
      });
    }
    ui.ledgerFilters.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-status]");
      if (!btn) return;
      state.ledgerStatus = btn.dataset.status;
      renderLedger();
    });
    ui.ledgerList.addEventListener("click", (e) => {
      if (e.target.closest("[data-ledger-add]")) {
        openLedgerForm(null);
        return;
      }
      const del = e.target.closest("[data-delete-ledger]");
      if (del) {
        deleteLedger(del.dataset.deleteLedger);
        return;
      }
      const ics = e.target.closest("[data-ics-ledger]");
      if (ics) {
        exportLedgerIcs(ics.dataset.icsLedger);
        return;
      }
      const edit = e.target.closest("[data-edit-ledger]");
      if (edit) {
        openLedgerForm(edit.dataset.editLedger);
        return;
      }
      const review = e.target.closest("[data-open-ledger-review]");
      if (review) {
        openHistory(review.dataset.openLedgerReview);
        return;
      }
      const row = e.target.closest("[data-ledger-row]");
      if (row) openLedgerForm(row.dataset.ledgerRow);
    });
    ui.ledgerBackdrop.addEventListener("click", closeLedgerForm);
    $("#btn-close-ledger").addEventListener("click", closeLedgerForm);
    $("#btn-cancel-ledger").addEventListener("click", closeLedgerForm);
    ui.ledgerForm.addEventListener("submit", saveLedgerFromForm);
    $("#btn-add-ledger").addEventListener("click", addCurrentToLedger);

    $("#btn-settings").addEventListener("click", openSettings);
    $("#btn-close-settings").addEventListener("click", closeSettings);
    ui.backdrop.addEventListener("click", closeSettings);
    $("#set-provider").addEventListener("change", onProviderChange);
    $("#btn-toggle-key").addEventListener("click", toggleKeyVisibility);
    $("#btn-save-settings").addEventListener("click", saveSettings);

    document.addEventListener("keydown", (e) => {
      if (e.key !== "Escape") return;
      if (ui.ruleDrawer && !ui.ruleDrawer.classList.contains("hidden")) {
        closeRuleForm();
        return;
      }
      if (!ui.ledgerDrawer.classList.contains("hidden")) {
        closeLedgerForm();
        return;
      }
      if (!ui.drawer.classList.contains("hidden")) closeSettings();
    });
    window.addEventListener("resize", scheduleBeamRedraw);
    window.addEventListener("focus", refreshRulesFromStorage);

    // 复制修改条款（报告内的按钮）
    document.addEventListener("click", (e) => {
      const btn = e.target.closest(".copy-btn");
      if (!btn) return;
      copyText(btn.dataset.copy || "");
    });

    window.addEventListener("beforeunload", (e) => {
      if (!state.running) return;
      e.preventDefault();
      e.returnValue = "";
    });
  }

  // ═════════════ 视图切换 ═════════════

  function switchView(view) {
    $$(".nav-item").forEach((b) => b.classList.toggle("active", b.dataset.view === view));
    $$(".view").forEach((v) => v.classList.toggle("hidden", v.id !== "view-" + view));
    if (ui.topbar) ui.topbar.classList.toggle("home-mode", view === "home");
    if (ui.homeGreetingBlock) ui.homeGreetingBlock.classList.toggle("hidden", view !== "home");
    if (ui.homeReview) ui.homeReview.classList.toggle("hidden", view !== "home");
    if (view === "clauses") renderClauses();
    if (view === "rules") {
      renderRuleFilters();
      renderRules();
      refreshRulesFromStorage();
    }
    if (view === "home") renderHome();
    if (view === "ledger") renderLedger();
  }

  // ═════════════ 案头 / 审查历史 ═════════════

  function reviewTitle(text, contractType) {
    const lines = String(text || "")
      .split(/\n/)
      .map((s) => s.trim())
      .filter(Boolean);
    const hit = lines.find(
      (line) =>
        line.length >= 4 &&
        line.length <= 40 &&
        !/^(甲方|乙方|身份证|电话|地址|联系人|统一社会信用代码)/.test(line)
    );
    return (hit || contractType || "未命名合同").slice(0, 40);
  }

  function historyPreview(text) {
    // 先留足缓冲区再脱敏，避免证件/手机号刚好被 96 字截断而漏出半截。
    const raw = String(text || "").slice(0, 4096);
    try {
      return WB.maskText(raw, (state.settings && state.settings.hiddenNames) || []).text.slice(0, 96);
    } catch (e) {
      return "（预览已隐藏）";
    }
  }

  function maskedText(value) {
    try {
      return WB.maskText(String(value == null ? "" : value), (state.settings && state.settings.hiddenNames) || []).text;
    } catch (e) {
      return "（内容已隐藏）";
    }
  }

  function maskedHistoryTitle(item) {
    return maskedText((item && item.title) || "未命名合同") || "未命名合同";
  }

  function formatHistoryDate(ts, short) {
    const d = new Date(Number(ts) || Date.now());
    if (Number.isNaN(d.getTime())) return "—";
    return d.toLocaleString(
      "zh-CN",
      short
        ? { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false }
        : { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false }
    );
  }

  function greetingFor(date) {
    const hour = date.getHours();
    if (hour < 6) return "夜深了";
    if (hour < 12) return "早上好";
    if (hour < 14) return "中午好";
    if (hour < 18) return "下午好";
    return "晚上好";
  }

  function homeDateLine(date) {
    const week = "日一二三四五六"[date.getDay()];
    return `${date.getMonth() + 1} 月 ${date.getDate()} 日 周${week}`;
  }

  function renderHome() {
    const items = state.history || [];
    const total = items.length;
    const high = items.reduce(
      (sum, item) => sum + Number((item.result && item.result.counts && item.result.counts.high) || 0),
      0
    );
    const highContracts = items.filter(
      (item) => Number((item.result && item.result.counts && item.result.counts.high) || 0) > 0
    ).length;
    const last = items[0] ? formatHistoryDate(items[0].createdAt, true) : "尚无记录";
    const due = WB.Ledger.reminders(state.ledger || [], new Date());
    const overdue = due.filter((r) => r.days < 0).length;

    if (ui.homeGreeting) ui.homeGreeting.textContent = greetingFor(new Date());
    if (ui.homeSub) {
      ui.homeSub.textContent = `${homeDateLine(new Date())} · ${due.length} 项待办 · 高风险 ${highContracts} 份`;
    }

    ui.homeStats.innerHTML = `
      <div class="home-stat">
        <span>已审合同</span>
        <div class="home-stat-value"><b>${total}</b><em>份</em></div>
        <p>最近 ${esc(last)}</p>
      </div>
      <div class="home-stat high">
        <span>高风险合计</span>
        <div class="home-stat-value"><b>${high}</b><em>条</em></div>
        <p>涉及 ${highContracts} 份合同</p>
      </div>
      <div class="home-stat">
        <span>30 天内待办</span>
        <div class="home-stat-value"><b>${due.length}</b><em>项</em></div>
        <p>${overdue ? `${overdue} 项已逾期` : "到期与付款节点"}</p>
      </div>`;
    syncHomeSearch();
    renderReminders();
    renderHistory();
    renderHomeContracts();
    applyHomeTab();
  }

  function applyHomeTab() {
    if (!ui.homeReviewsPane || !ui.homeContractsPane) return;
    const tab = state.homeTab === "contracts" ? "contracts" : "reviews";
    ui.homeTabs.forEach((btn) => {
      const on = btn.dataset.homeTab === tab;
      btn.classList.toggle("active", on);
      btn.setAttribute("aria-selected", on ? "true" : "false");
    });
    ui.homeReviewsPane.classList.toggle("hidden", tab !== "reviews");
    ui.homeContractsPane.classList.toggle("hidden", tab !== "contracts");
    ui.homeReviewTools.classList.toggle("hidden", tab !== "reviews");
    ui.homeContractTools.classList.toggle("hidden", tab !== "contracts");
  }

  function setHomeTab(tab) {
    state.homeTab = tab === "contracts" ? "contracts" : "reviews";
    applyHomeTab();
    if (state.homeTab === "contracts") renderHomeContracts();
  }

  function syncHomeSearch() {
    [ui.sidebarSearch, ui.historySearch, ui.contractsSearch, ui.ledgerSearch].forEach((el) => {
      if (el && el.value !== state.historyQuery) el.value = state.historyQuery;
    });
    if (ui.sidebarSearchClear) {
      ui.sidebarSearchClear.classList.toggle("hidden", !state.historyQuery);
    }
  }

  function applyHomeQuery(value) {
    state.historyQuery = String(value == null ? "" : value);
    syncHomeSearch();
    renderHistory();
    renderHomeContracts();
    renderLedger();
  }

  function formatLedgerAmount(value) {
    const raw = String(value == null ? "" : value).trim();
    if (!raw) return "";
    const n = Number(raw.replace(/,/g, ""));
    if (isFinite(n) && /^[0-9.,]+$/.test(raw)) return "¥" + n.toLocaleString("zh-CN");
    return raw;
  }

  function ledgerDisplayDate(value) {
    const s = WB.Ledger.formatDate(value);
    return s ? s.replace(/\//g, ".") : "";
  }

  function ledgerEntryTitle(entry) {
    const type = String((entry && entry.contractType) || "").replace(/合同$/, "");
    const title = maskedHistoryTitle(entry);
    return type && title.indexOf(type) !== 0 ? `${type} · ${title}` : title;
  }

  function ledgerRisk(entry) {
    const review = entry && entry.reviewId
      ? (state.history || []).find((r) => r.id === entry.reviewId)
      : null;
    const c = review && review.result && review.result.counts;
    const [h, m, l] = [Number(c && c.high) || 0, Number(c && c.mid) || 0, Number(c && c.low) || 0];
    if (!c) return { level: "none", text: "未审查" };
    if (!h && !m && !l) return { level: "none", text: "无风险" };
    return {
      level: h > 0 ? "high" : m > 0 ? "mid" : "low",
      text: [h ? `高 ${h}` : "", m ? `中 ${m}` : "", l ? `低 ${l}` : ""].filter(Boolean).join(" · "),
    };
  }

  function renderHomeContracts() {
    if (!ui.homeContractsList) return;
    const all = (state.ledger || []).slice().sort(ledgerSort);
    const q = state.historyQuery.trim().toLowerCase();
    const entries = q
      ? all.filter((entry) =>
          [
            entry.title,
            entry.contractType,
            entry.counterparty,
            entry.amount,
            entry.paymentAmount,
            entry.note,
            entry.status,
            entry.startDate,
            entry.endDate,
            entry.paymentDate,
          ]
            .join("\n")
            .toLowerCase()
            .indexOf(q) >= 0
        )
      : all;
    if (ui.homeLedgerAll) ui.homeLedgerAll.textContent = `查看全部 ${all.length} 份`;
    if (!entries.length) {
      const empty = q
        ? `<p>没有匹配「${esc(state.historyQuery)}」的合同</p>`
        : '<p>台账还是空的</p><button class="btn btn-primary" type="button" data-home-ledger-add>新增第一份合同</button>';
      ui.homeContractsList.innerHTML = `<div class="history-empty">${empty}</div>`;
      return;
    }
    ui.homeContractsList.innerHTML = entries
      .map((entry) => {
        const status = entry.status || "履行中";
        const risk = ledgerRisk(entry);
        const range =
          entry.startDate || entry.endDate
            ? `${entry.startDate ? ledgerDisplayDate(entry.startDate) : "—"} – ${entry.endDate ? ledgerDisplayDate(entry.endDate) : "—"}`
            : "";
        const meta = [
          entry.counterparty ? maskedText(entry.counterparty) : "",
          formatLedgerAmount(entry.amount),
          range,
        ]
          .filter(Boolean)
          .join(" · ");
        return `<button class="home-contract-row ${risk.level}" type="button" data-home-ledger="${esc(entry.id)}">
          <span class="home-contract-main">
            <b class="home-contract-title">${esc(ledgerEntryTitle(entry))}</b>
            <span class="home-contract-meta">${esc(meta || "还没有补充金额或日期")}</span>
          </span>
          <span class="home-contract-side">
            <span class="history-risk ${risk.level}">${esc(risk.text)}</span>
            <span class="ledger-status ${WB.Ledger.statusClass(status)}">${esc(status)}</span>
          </span>
        </button>`;
      })
      .join("");
  }

  function renderReminders() {
    if (!(state.ledger || []).length) {
      ui.homeReminders.innerHTML = '<p class="reminder-empty">台账还是空的，新增合同后这里会出现到期与付款提醒。</p>';
      return;
    }
    const items = WB.Ledger.reminders(state.ledger || [], new Date());
    if (!items.length) {
      ui.homeReminders.innerHTML = '<p class="reminder-empty">未来 30 天没有到期或付款节点。</p>';
      return;
    }
    const visible = items.slice(0, 6);
    ui.homeReminders.innerHTML = visible
      .map((r) => {
        const cls = r.days < 0 ? "overdue" : r.days <= 7 ? "urgent" : "";
        const amount = r.kind === "付款" && r.amount ? ` · ${esc(r.amount)}` : "";
        const kind = r.kind === "付款" ? "pay" : "due";
        return `<button class="reminder-item ${cls}" type="button" data-reminder-entry="${esc(r.entry.id)}">
          <span class="reminder-icon ${kind}">${iconSvg(r.kind === "付款" ? "wallet" : "clock")}</span>
          <span class="reminder-main"><b>${esc(maskedHistoryTitle(r.entry))}</b><em>${esc(WB.Ledger.formatDate(r.date))}${amount}</em></span>
          <span class="reminder-count">${esc(WB.Ledger.countdownShort(r.days))}</span>
        </button>`;
      })
      .join("") +
      (items.length > visible.length
        ? `<p class="reminder-more">还有 ${items.length - visible.length} 条，去台账查看</p>`
        : "");
  }

  function renderHistory() {
    const q = state.historyQuery.trim().toLowerCase();
    const items = (state.history || []).filter((item) => {
      if (!q) return true;
      return [item.title, item.contractType, item.contractText]
        .join("\n")
        .toLowerCase()
        .indexOf(q) >= 0;
    });
    const ledgerHits = q
      ? (state.ledger || [])
          .filter((entry) =>
            [
              entry.title,
              entry.contractType,
              entry.counterparty,
              entry.amount,
              entry.paymentAmount,
              entry.note,
              entry.status,
              entry.startDate,
              entry.endDate,
              entry.paymentDate,
            ]
              .join("\n")
              .toLowerCase()
              .indexOf(q) >= 0
          )
          .sort(ledgerSort)
      : [];


    if (!items.length && !ledgerHits.length) {
      const empty = q
        ? `<p>没有匹配「${esc(state.historyQuery)}」的审查记录或台账条目</p>`
        : "<p>还没有审查记录</p><button class=\"btn btn-primary\" type=\"button\" data-new-review>去审查第一份合同</button>";
      ui.historyList.innerHTML = `<div class="history-empty">${empty}</div>`;
      return;
    }

    let html = items
      .map((item) => {
        const c = (item.result && item.result.counts) || {};
        const [h, m, l] = [Number(c.high) || 0, Number(c.mid) || 0, Number(c.low) || 0];
        const level = h > 0 ? "high" : m > 0 ? "mid" : "low";
        const score = item.result && item.result.score;
        const meta = [formatHistoryDate(item.createdAt), score == null ? "" : `综合评分 ${score}`]
          .filter(Boolean)
          .join(" · ");
        const risk = h || m || l
          ? [h ? `高 ${h}` : "", m ? `中 ${m}` : "", l ? `低 ${l}` : ""].filter(Boolean).join(" · ")
          : "无风险";
        return `<article class="history-item ${level}" data-open-review="${esc(item.id)}" title="${esc(historyPreview(item.contractText))}">
          <div class="history-item-main">
            <div class="history-item-top">
              <h4>${esc(maskedHistoryTitle(item))}</h4>
              <span class="history-type">${esc(item.contractType || "")}</span>
            </div>
            <p class="history-meta">${esc(meta)}</p>
          </div>
          <div class="history-side">
            <span class="history-risk ${level}">${esc(risk)}</span>
            <div class="history-actions">
              <button class="history-open" type="button" data-open-review="${esc(item.id)}">查看</button>
              <button class="history-delete" type="button" data-delete-review="${esc(item.id)}">删除</button>
            </div>
          </div>
        </article>`;
      })
      .join("");

    if (ledgerHits.length) {
      html += `<div class="search-ledger-group">
        <p class="search-ledger-title">台账匹配 · ${ledgerHits.length}</p>
        ${ledgerHits
          .map((entry) => {
            const meta = maskedText(
              [
                entry.counterparty,
                entry.contractType,
                entry.endDate ? `到期 ${WB.Ledger.formatDate(entry.endDate, true)}` : "",
              ]
                .filter(Boolean)
                .join(" · ")
            );
            return `<button class="search-ledger-row" type="button" data-search-ledger="${esc(entry.id)}">
              <span class="search-ledger-main">
                <b>${esc(maskedHistoryTitle(entry))}</b>
                <em>${esc(meta || "台账条目")}</em>
              </span>
              <span class="search-ledger-status">${esc(entry.status || "履行中")}</span>
            </button>`;
          })
          .join("")}
      </div>`;
    }

    ui.historyList.innerHTML = html;
  }

  function openHistory(id) {
    const item = (state.history || []).find((r) => r.id === id);
    if (!item || !item.result) {
      toast("这条审查记录已不存在", "error");
      state.history = (state.history || []).filter((r) => r.id !== id);
      WB.deleteReview(id).catch(() => {});
      renderHome();
      return;
    }
    state.lastReviewId = item.id;
    ui.input.value = item.contractText || "";
    updateCharCount();
    if (item.contractType) setType(item.contractType, false);
    showResult(item.result, item.contractText || "");
    WB.saveCurrent({
      contractText: item.contractText || "",
      contractType: item.contractType || ui.typeSelect.value,
      result: item.result,
      savedAt: item.createdAt,
      reviewId: item.id,
    }).catch(() => {});
    toast("已打开历史审查");
  }

  async function deleteHistory(id) {
    const item = (state.history || []).find((r) => r.id === id);
    if (!item) return;
    if (!window.confirm(`删除「${maskedHistoryTitle(item)}」？`)) return;
    const ok = await WB.deleteReview(id);
    if (!ok) {
      toast("删除失败，请重试", "error");
      return;
    }
    state.history = (state.history || []).filter((r) => r.id !== id);
    renderHome();
    toast("已删除这条审查记录");
  }

  async function clearHistory() {
    if (!(state.history || []).length) {
      toast("还没有审查记录");
      return;
    }
    if (!window.confirm("清空全部审查历史？此操作无法撤销。")) return;
    const ok = await WB.clearReviews();
    if (!ok) {
      toast("清空失败，请重试", "error");
      return;
    }
    state.history = [];
    state.historyQuery = "";
    if (ui.historySearch) ui.historySearch.value = "";
    if (ui.sidebarSearch) ui.sidebarSearch.value = "";
    if (ui.contractsSearch) ui.contractsSearch.value = "";
    if (ui.ledgerSearch) ui.ledgerSearch.value = "";
    renderHome();
    toast("审查历史已清空");
  }

  // ═════════════ 合同台账 ═════════════

  function ledgerSort(a, b) {
    const ae = a.endDate || "9999-12-31";
    const be = b.endDate || "9999-12-31";
    return ae.localeCompare(be) || (Number(b.updatedAt) || 0) - (Number(a.updatedAt) || 0);
  }

  function ledgerFiltered() {
    const q = state.historyQuery.trim().toLowerCase();
    return (state.ledger || [])
      .filter((entry) => {
        if (state.ledgerStatus !== "全部" && (entry.status || "履行中") !== state.ledgerStatus) return false;
        if (state.ledgerType !== "全部类型" && (entry.contractType || "其他") !== state.ledgerType) return false;
        if (!q) return true;
        return [
          entry.title,
          entry.contractType,
          entry.counterparty,
          entry.amount,
          entry.paymentAmount,
          entry.note,
          entry.status,
          entry.startDate,
          entry.endDate,
          entry.paymentDate,
        ]
          .join("\n")
          .toLowerCase()
          .indexOf(q) >= 0;
      })
      .sort(ledgerSort);
  }

  function renderLedgerFilters() {
    const options = ["全部"].concat(WB.Ledger.STATUSES);
    if (options.indexOf(state.ledgerStatus) < 0) state.ledgerStatus = "全部";
    ui.ledgerFilters.innerHTML = options
      .map((status) => {
        const count = status === "全部"
          ? (state.ledger || []).length
          : (state.ledger || []).filter((e) => (e.status || "履行中") === status).length;
        return `<button class="filter-chip${state.ledgerStatus === status ? " active" : ""}" type="button" data-status="${esc(status)}">${esc(status)} ${count}</button>`;
      })
      .join("");
  }

  function ledgerRowHTML(entry) {
    const status = entry.status || "履行中";
    const cls = WB.Ledger.statusClass(status);
    const linked = entry.reviewId && (state.history || []).some((r) => r.id === entry.reviewId);
    const range =
      entry.startDate || entry.endDate
        ? `${entry.startDate ? ledgerDisplayDate(entry.startDate) : "—"} – ${entry.endDate ? ledgerDisplayDate(entry.endDate) : "—"}`
        : "";
    const meta = [range, entry.note].filter(Boolean).join(" · ");
    return `<article class="ledger-row status-${cls}" data-ledger-row="${esc(entry.id)}">
      <div class="ledger-cell ledger-cell-name">
        <div class="ledger-name-main">
          <h3>${esc(ledgerEntryTitle(entry))}</h3>
          <p>${esc(meta || entry.contractType || "还没有补充日期")}</p>
        </div>
      </div>
      <div class="ledger-cell ledger-cell-party">${esc(entry.counterparty || "—")}</div>
      <div class="ledger-cell ledger-cell-amount">${esc(formatLedgerAmount(entry.amount) || "—")}</div>
      <div class="ledger-cell ledger-cell-end">${esc(entry.endDate ? ledgerDisplayDate(entry.endDate) : "—")}</div>
      <div class="ledger-cell ledger-cell-status"><span class="ledger-status ${cls}">${esc(status)}</span></div>
      <div class="ledger-cell ledger-cell-actions">
        <div class="ledger-actions">
          ${linked ? `<button type="button" data-open-ledger-review="${esc(entry.reviewId)}" title="查看审查" aria-label="查看审查">${iconSvg("review")}</button>` : ""}
          <button type="button" data-ics-ledger="${esc(entry.id)}" title="导出提醒" aria-label="导出提醒">${iconSvg("calendar")}</button>
          <button type="button" data-edit-ledger="${esc(entry.id)}" title="编辑合同" aria-label="编辑合同">${iconSvg("edit")}</button>
          <button type="button" data-delete-ledger="${esc(entry.id)}" title="删除合同" aria-label="删除合同">${iconSvg("trash")}</button>
        </div>
      </div>
    </article>`;
  }

  function renderLedgerDates(entries) {
    if (!ui.ledgerDatesList) return;
    const now = new Date();
    const events = [];
    (entries || []).forEach((entry) => {
      const status = entry.status || "履行中";
      const inactive = status === "已归档" || status === "已终止";
      [
        ["到期", entry.endDate],
        ["付款", entry.paymentDate],
      ].forEach(([kind, date]) => {
        const days = WB.Ledger.daysUntil(date, now);
        if (days == null || days < -30 || days > 365) return;
        events.push({ entry, kind, date, days, inactive, status });
      });
    });
    events.sort((a, b) => a.days - b.days || String(a.date).localeCompare(String(b.date)));
    const visible = events.slice(0, 8);
    if (!visible.length) {
      ui.ledgerDatesList.innerHTML = '<p class="reminder-empty">未来一年还没有到期或付款节点。</p>';
      return;
    }
    ui.ledgerDatesList.innerHTML = visible
      .map((e) => {
        const tone = e.inactive
          ? "is-muted"
          : e.days < 0
            ? "is-overdue"
            : e.kind === "付款"
              ? "is-payment"
              : e.days <= 7
                ? "is-soon"
                : "is-normal";
        const note = e.inactive
          ? `${e.status} · 无需提醒`
          : `${e.kind === "付款" ? "付款节点" : "合同到期"} · ${WB.Ledger.countdown(e.kind, e.days)}`;
        return `<button class="ledger-date-item ${tone}" type="button" data-edit-ledger="${esc(e.entry.id)}">
          <b>${esc(ledgerDisplayDate(e.date))} · ${esc(maskedHistoryTitle(e.entry))}</b>
          <em>${esc(note)}</em>
        </button>`;
      })
      .join("");
  }

  function renderLedger() {
    if (!ui.ledgerList) return;
    syncHomeSearch();
    const all = state.ledger || [];
    renderLedgerFilters();
    const items = ledgerFiltered();
    const dueReminders = WB.Ledger.reminders(all, new Date());
    const highContracts = all.filter((entry) => ledgerRisk(entry).level === "high").length;
    const typeCount = new Set(all.map((entry) => entry.contractType || "其他")).size;
    if (ui.ledgerSummary) {
      ui.ledgerSummary.textContent = `${all.length} 份合同 · ${typeCount} 类 · 高风险 ${highContracts} 份 · 合同原文全部存在本机`;
    }
    if (ui.ledgerTableCount) ui.ledgerTableCount.textContent = `共 ${items.length} 份 · 按到期日排序`;
    if (ui.ledgerDatesSub) ui.ledgerDatesSub.textContent = `最近 30 天 ${dueReminders.length} 项`;
    renderLedgerDates(all);

    if (!items.length) {
      const filtered = state.historyQuery.trim() || state.ledgerStatus !== "全部" || state.ledgerType !== "全部类型";
      const empty = filtered
        ? "<p>没有匹配的合同</p>"
        : '<p>台账还是空的</p><p class="ledger-empty-sub">新增一份合同，或审查完成后在结果页点「加入台账」。</p><button class="btn btn-primary" type="button" data-ledger-add>新增第一份合同</button>';
      ui.ledgerList.innerHTML = `<div class="ledger-empty">${empty}</div>`;
      return;
    }
    ui.ledgerList.innerHTML = items.map(ledgerRowHTML).join("");
  }

  function openLedgerForm(id, prefill) {
    const item = id ? (state.ledger || []).find((e) => e.id === id) : null;
    if (id && !item) {
      toast("这条台账记录已不存在", "error");
      return;
    }
    const data = item || prefill || {};
    state.editingLedgerId = item ? item.id : null;
    closeSettings();
    ui.ledgerForm.reset();
    ui.ledgerFormTitle.textContent = item ? "编辑合同" : "新增合同";
    ui.ledgerTitle.value = data.title || "";
    ui.ledgerType.value = WB.CONTRACT_TYPES.includes(data.contractType)
      ? data.contractType
      : data.contractType
        ? "其他"
        : WB.CONTRACT_TYPES.includes(ui.typeSelect.value)
          ? ui.typeSelect.value
          : WB.CONTRACT_TYPES[0];
    ui.ledgerStatus.value = WB.Ledger.STATUSES.includes(data.status) ? data.status : "履行中";
    ui.ledgerCounterparty.value = data.counterparty || "";
    ui.ledgerAmount.value = data.amount || "";
    ui.ledgerStart.value = data.startDate || "";
    ui.ledgerEnd.value = data.endDate || "";
    ui.ledgerPaymentDate.value = data.paymentDate || "";
    ui.ledgerPaymentAmount.value = data.paymentAmount || "";
    ui.ledgerNote.value = data.note || "";
    ui.ledgerReviewId.value = data.reviewId || "";
    ui.ledgerBackdrop.classList.remove("hidden");
    ui.ledgerDrawer.classList.remove("hidden");
    setTimeout(() => ui.ledgerTitle.focus(), 30);
  }

  function closeLedgerForm() {
    ui.ledgerDrawer.classList.add("hidden");
    ui.ledgerBackdrop.classList.add("hidden");
    state.editingLedgerId = null;
  }

  async function saveLedgerFromForm(event) {
    event.preventDefault();
    const title = ui.ledgerTitle.value.trim();
    if (!title) {
      toast("先填合同名称", "error");
      ui.ledgerTitle.focus();
      return;
    }
    const startDate = ui.ledgerStart.value;
    const endDate = ui.ledgerEnd.value;
    if (startDate && endDate && endDate < startDate) {
      toast("到期日不能早于起始日", "error");
      return;
    }

    const existing = state.editingLedgerId
      ? (state.ledger || []).find((e) => e.id === state.editingLedgerId)
      : null;
    const now = Date.now();
    const entry = {
      id: existing ? existing.id : WB.Ledger.createId(),
      createdAt: existing ? existing.createdAt : now,
      updatedAt: now,
      title,
      contractType: ui.ledgerType.value,
      counterparty: ui.ledgerCounterparty.value.trim(),
      amount: ui.ledgerAmount.value.trim(),
      startDate,
      endDate,
      paymentDate: ui.ledgerPaymentDate.value,
      paymentAmount: ui.ledgerPaymentAmount.value.trim(),
      status: ui.ledgerStatus.value,
      note: ui.ledgerNote.value.trim(),
      reviewId: ui.ledgerReviewId.value || (existing && existing.reviewId) || "",
    };

    const saved = await WB.saveLedgerEntry(entry);
    if (!saved) {
      toast("台账保存失败，请重试", "error");
      return;
    }
    const index = (state.ledger || []).findIndex((e) => e.id === entry.id);
    if (index >= 0) state.ledger[index] = entry;
    else state.ledger.unshift(entry);
    closeLedgerForm();
    renderLedger();
    renderHome();
    toast(existing ? "台账已更新" : "已加入台账");
  }

  async function deleteLedger(id) {
    const item = (state.ledger || []).find((e) => e.id === id);
    if (!item) return;
    if (!window.confirm(`从台账删除「${maskedHistoryTitle(item)}」？`)) return;
    const ok = await WB.deleteLedgerEntry(id);
    if (!ok) {
      toast("删除失败，请重试", "error");
      return;
    }
    state.ledger = (state.ledger || []).filter((e) => e.id !== id);
    renderLedger();
    renderHome();
    toast("已从台账删除");
  }

  function exportLedgerCsv() {
    const entries = state.ledger || [];
    if (!entries.length) {
      toast("台账还是空的");
      return;
    }
    const csv = WB.Ledger.buildCSV(entries.slice().sort(ledgerSort));
    downloadText("﻿" + csv, `合同台账-${dateStamp()}.csv`, "text/csv;charset=utf-8");
    toast("台账已导出 CSV");
  }

  function exportLedgerIcs(id) {
    const entries = id
      ? (state.ledger || []).filter((e) => e.id === id)
      : (state.ledger || []).filter((e) => e.status !== "已归档" && e.status !== "已终止");
    if (!entries.length) {
      toast(id ? "台账还是空的" : "没有需要提醒的合同");
      return;
    }
    const ics = WB.Ledger.buildICS(entries);
    if (!ics) {
      toast("还没有可导出的到期或付款日期", "error");
      return;
    }
    const name = id
      ? `${safeFilename(entries[0].title)}-提醒.ics`
      : `合同提醒-${dateStamp()}.ics`;
    downloadText(ics, name, "text/calendar;charset=utf-8");
    toast("提醒已导出，可导入手机日历");
  }

  function addCurrentToLedger() {
    if (!state.lastResult) {
      toast("先完成一次审查", "error");
      return;
    }
    const existing = state.lastReviewId
      ? (state.ledger || []).find((e) => e.reviewId === state.lastReviewId)
      : null;
    if (existing) {
      openLedgerForm(existing.id);
      toast("这份合同已在台账里");
      return;
    }
    openLedgerForm(null, {
      title: reviewTitle(state.lastContractText, ui.typeSelect.value),
      contractType: ui.typeSelect.value,
      status: "待签",
      reviewId: state.lastReviewId || "",
    });
  }

  function hideStates() {
    clearBeam();
    [ui.empty, ui.running, ui.result, ui.error].forEach((el) => el.classList.add("hidden"));
  }

  function showEmpty() {
    hideStates();
    ui.empty.classList.remove("hidden");
    switchView("review");
    updateCharCount();
  }

  function showRunning() {
    hideStates();
    ui.running.classList.remove("hidden");
    switchView("review");
  }

  function showError(err) {
    hideStates();
    ui.error.classList.remove("hidden");
    switchView("review");
    ui.errorTitle.textContent = err && err.code === "auth" ? "API Key 有问题" : "审查中断";
    ui.errorDetail.textContent = (err && err.message) || "未知错误，请重试。";
  }

  // ═════════════ 审查流程 ═════════════

  async function startReview() {
    if (state.running) return;
    if (state.parsingFile) { toast("正在解析文件，稍等一下"); return; }

    const text = ui.input.value.trim();
    if (text.length < 50) { toast("合同内容太短（至少 50 字）", "error"); return; }
    if (text.length > 50000) { toast("合同超过 5 万字上限，请分拆后再审", "error"); return; }

    const providerKey = state.settings.provider;
    const apiKey = (state.settings.apiKeys || {})[providerKey] || "";
    if (!apiKey) {
      openSettings();
      toast("先配置 API Key", "error");
      return;
    }

    state.running = true;
    state.abort = new AbortController();
    const statuses = {};
    showRunning();
    renderPipeline(ui.pipeline, statuses);
    ui.runningTitle.textContent = "正在准备审查……";
    ui.runningDetail.textContent = "整个过程通常需要 30–90 秒";

    const settings = {
      provider: providerKey,
      baseUrl: state.settings.baseUrl || WB.PROVIDERS[providerKey].baseUrl,
      model: state.settings.model || WB.PROVIDERS[providerKey].model,
      apiKey,
    };

    const onProgress = (e) => {
      statuses[e.step] = e.status;
      renderPipeline(ui.pipeline, statuses);
      if (e.status === "running") {
        ui.runningTitle.textContent = RUNNING_TITLES[e.step] || "正在审查……";
      }
      if (e.status === "done" && e.detail) {
        ui.runningDetail.textContent = `第 ${e.step} 步完成 · ${e.detail}`;
      }
      if (e.status === "error") {
        ui.runningDetail.textContent = e.detail || "该步骤失败";
      }
    };

    try {
      const contractType = ui.typeSelect.value;
      const stance = state.settings.stance || "neutral";
      const stanceLabel = WB.stanceLabel(contractType, stance);
      const result = await WB.runPipeline({
        contractText: text,
        contractType,
        stance,
        stanceLabel,
        settings,
        hiddenNames: state.settings.hiddenNames || [],
        masking: state.settings.masking !== false,
        signal: state.abort.signal,
        onProgress,
      });

      state.running = false;
      state.lastContractText = text;
      state.lastResult = result;
      showResult(result, text);

      const savedAt = Date.now();
      const record = {
        id: "rv_" + savedAt,
        createdAt: savedAt,
        contractType,
        stance,
        title: reviewTitle(text, contractType),
        contractText: text,
        result,
      };
      state.lastReviewId = record.id;
      await WB.saveCurrent({
        contractText: text,
        contractType,
        stance,
        result,
        savedAt,
        reviewId: record.id,
      });
      const savedReview = await WB.saveReview(record);
      if (savedReview) {
        state.history = [savedReview].concat(
          (state.history || []).filter((r) => r.id !== savedReview.id)
        );
        renderHome();
        renderLedger();
        toast("审查完成");
      } else {
        toast("审查完成，但历史记录保存失败", "error");
      }
    } catch (err) {
      state.running = false;
      if (err && err.code === "aborted") {
        showEmpty();
        toast("已取消审查");
        return;
      }
      showError(err);
    }
  }

  function cancelReview() {
    if (state.abort) state.abort.abort();
  }

  function nextReview() {
    state.lastResult = null;
    state.lastContractText = "";
    state.lastReviewId = null;
    ui.input.value = "";
    ui.typeHint.textContent = "";
    updateCharCount();
    resetFileStatus();
    WB.clearCurrent().catch(() => {});
    showEmpty();
    ui.input.focus();
  }

  function renderPipeline(container, statuses) {
    if (!container) return;
    container.innerHTML = STEPS.map((s) => {
      const st = statuses[s.n] || "pending";
      const dot = st === "done" ? "✓" : st === "error" ? "!" : String(s.n);
      return `<div class="pipeline-step step-${st}">
        <span class="step-dot">${dot}</span>
        <span class="step-label">${s.label}</span>
      </div>`;
    }).join("");
  }

  // ═════════════ 结果渲染 ═════════════

  function showResult(result, contractText) {
    state.lastResult = result;
    state.lastContractText = contractText;
    hideStates();
    ui.result.classList.remove("hidden");
    switchView("review");

    const resultType = result.contractType && WB.CONTRACT_TYPES.includes(result.contractType)
      ? result.contractType
      : state.settings.contractType;
    ui.typeSelect.value = resultType;
    state.settings.contractType = resultType;
    state.settings.stance = result.stance || "neutral";
    populateStances(resultType);

    const c = result.counts || { high: 0, mid: 0, low: 0 };
    ui.resultStats.innerHTML = `
      <span class="result-stat high">高风险 <b>${c.high}</b></span>
      <span class="result-stat mid">中风险 <b>${c.mid}</b></span>
      <span class="result-stat low">低风险 <b>${c.low}</b></span>
      <span class="result-stat score">综合评分 <b>${result.score == null ? "—" : result.score}</b><span>/100</span></span>
      <span class="result-stat">审查视角 <b>${esc(result.stanceLabel || WB.stanceLabel(resultType, result.stance))}</b></span>`;

    ui.contractView.innerHTML = WB.highlightContract(contractText, result.findings || []);
    ui.reportView.innerHTML = result.reportHtml || "";
    ui.riskCount.textContent = `${(result.findings || []).length} 条风险`;
    renderRiskList(result);
    renderPipeline(ui.pipelineResult, { 1: "done", 2: "done", 3: "done", 4: "done", 5: "done" });
    activateTab("list");
  }

  function renderRiskList(result) {
    const findings = (result.findings || []).map((f, i) =>
      Object.assign({}, f, { level: f.level || WB.deriveLevel(f), _idx: i })
    );
    if (!findings.length) {
      ui.riskList.innerHTML = '<p class="empty-line">未发现明显风险。仍建议逐条核对合同原文与附件。</p>';
      return;
    }

    let html = "";
    ["高", "中", "低"].forEach((level) => {
      const list = findings
        .filter((f) => f.level === level)
        .sort((a, b) => Math.max(b.fairness, b.clarity, b.exposure) - Math.max(a.fairness, a.clarity, a.exposure));
      if (!list.length) return;
      html += `<div class="risk-group-title"><span class="risk-mark ${LEVEL_MARK[level]}"></span>${level}风险 · ${list.length}</div>`;
      list.forEach((f) => {
        html += `<button class="risk-item ${LEVEL_CLS[level]}" type="button" data-idx="${f._idx}">
          <div class="risk-item-head">
            <span class="risk-mark ${LEVEL_MARK[level]}"></span>
            <span class="risk-item-name">${esc(f.rule_name || f.rule_id)}</span>
          </div>
          <p class="risk-item-text">${esc((f.clause_text || "").slice(0, 90))}</p>
          <div class="risk-item-basis">${esc(f.basis || "")}</div>
        </button>`;
      });
    });

    ui.riskList.innerHTML = html || '<p class="empty-line">未发现明显风险。</p>';
  }

  function clearBeam() {
    beamMark = null;
    clearTimeout(beamResizeTimer);
    if (!ui.contractView) return;
    ui.contractView.querySelectorAll(".hl-beam-rect").forEach((el) => el.remove());
    ui.contractView.querySelectorAll("mark.hl-beam-source").forEach((el) => {
      el.classList.remove("hl-beam-source");
    });
    ui.contractView.querySelectorAll("mark.hl-flash").forEach((el) => {
      el.classList.remove("hl-flash");
    });
  }

  function redrawBeam() {
    if (!beamMark || !ui.contractView || !ui.contractView.contains(beamMark)) return;
    const mark = beamMark;
    clearBeam();
    mark.classList.add("hl-beam-source");
    showBeam(mark);
  }

  function scheduleBeamRedraw() {
    if (!beamMark) return;
    clearTimeout(beamResizeTimer);
    beamResizeTimer = setTimeout(redrawBeam, 120);
  }

  // 高风险条款：在原文每一行外画一圈旋转光束，参考问数精灵登录按钮的 BorderBeam。
  function showBeam(mark) {
    beamMark = mark;
    const view = ui.contractView;
    const viewRect = view.getBoundingClientRect();
    const rects = Array.from(mark.getClientRects()).filter((r) => r.width > 2 && r.height > 2);
    if (!rects.length) return;

    rects.forEach((r) => {
      const beam = document.createElement("div");
      beam.className = "hl-beam-rect";
      beam.setAttribute("aria-hidden", "true");
      beam.style.left = `${r.left - viewRect.left + view.scrollLeft - 4}px`;
      beam.style.top = `${r.top - viewRect.top + view.scrollTop - 4}px`;
      beam.style.width = `${r.width + 8}px`;
      beam.style.height = `${r.height + 8}px`;
      view.appendChild(beam);
    });
  }

  function jumpToRisk(idx, sourceBtn) {
    $$(".risk-item.is-active").forEach((el) => el.classList.remove("is-active"));
    clearBeam();

    let mark = ui.contractView.querySelector(`mark[data-risk-index="${idx}"]`);
    // 同一条款可能对应多个风险点，高亮只保留一个；回退到相同原文的标记
    if (!mark && state.lastResult && state.lastResult.findings) {
      const target = state.lastResult.findings[Number(idx)];
      if (target) {
        const alt = state.lastResult.findings.findIndex((f) => f.clause_text === target.clause_text);
        if (alt >= 0) mark = ui.contractView.querySelector(`mark[data-risk-index="${alt}"]`);
      }
    }
    if (!mark) {
      toast("正文中未定位到该条款，可对照右侧原文核对", "error");
      return;
    }

    if (sourceBtn) sourceBtn.classList.add("is-active");
    mark.scrollIntoView({ behavior: "smooth", block: "center" });

    const finding = state.lastResult && state.lastResult.findings
      ? state.lastResult.findings[Number(idx)]
      : null;
    const level = finding ? (finding.level || WB.deriveLevel(finding)) : "";
    if (level === "高") {
      mark.classList.add("hl-beam-source");
      showBeam(mark);
      return;
    }

    mark.classList.add("hl-flash");
    setTimeout(() => mark.classList.remove("hl-flash"), 1200);
  }

  function activateTab(tab) {
    state.reportTab = tab;
    $$(".panel-tab").forEach((b) => {
      const on = b.dataset.tab === tab;
      b.classList.toggle("active", on);
      b.setAttribute("aria-selected", on ? "true" : "false");
    });
    ui.riskList.classList.toggle("hidden", tab !== "list");
    ui.reportView.classList.toggle("hidden", tab !== "report");
  }

  // ═════════════ 文件解析 ═════════════

  function setFileStatus(text, kind) {
    ui.fileStatus.textContent = text;
    ui.fileStatus.className = "file-status" + (kind ? " " + kind : "");
  }

  function resetFileStatus() {
    setFileStatus("支持文字层 PDF / DOCX / TXT，文件只在本机解析", "");
    if (ui.fileInput) ui.fileInput.value = "";
  }

  function parseWithTimeout(file) {
    return new Promise((resolve, reject) => {
      const timer = setTimeout(
        () => reject(new Error("文件解析超时（60 秒），请检查文件是否损坏或拆分后再试")),
        60000
      );
      WB.parseFile(file).then(
        (result) => { clearTimeout(timer); resolve(result); },
        (err) => { clearTimeout(timer); reject(err); }
      );
    });
  }

  async function handleFile(file) {
    if (state.parsingFile || !file) return;
    state.parsingFile = true;
    showEmpty();
    setFileStatus(`正在解析 ${file.name}……`, "");
    try {
      const parsed = await parseWithTimeout(file);
      ui.input.value = parsed.text;
      ui.input.dispatchEvent(new Event("input", { bubbles: true }));
      updateCharCount();
      showEmpty();

      const pages = parsed.meta && parsed.meta.pages ? ` · ${parsed.meta.pages} 页` : "";
      const warning = parsed.warnings && parsed.warnings.length ? ` · ${parsed.warnings[0]}` : "";
      const tooLong = parsed.text.length > WB.PARSE_LIMITS.maxTextChars;
      const kind = tooLong ? "error" : parsed.warnings && parsed.warnings.length ? "warn" : "ok";
      setFileStatus(
        `已从 ${parsed.fileName} 提取 ${parsed.text.length.toLocaleString("zh-CN")} 字${pages}${warning}`,
        kind
      );
      if (parsed.warnings && parsed.warnings.length) toast(parsed.warnings[0]);
      ui.input.focus();
    } catch (err) {
      const message = (err && err.message) || "文件解析失败";
      setFileStatus(message, "error");
      toast(message, "error");
    } finally {
      state.parsingFile = false;
      ui.fileInput.value = "";
    }
  }

  // ═════════════ 输入辅助 ═════════════

  function updateCharCount() {
    const n = ui.input.value.length;
    ui.charCount.textContent = n.toLocaleString("zh-CN") + " 字";
    ui.charCount.style.color = n > 50000 ? "var(--high)" : n > 30000 ? "var(--mid)" : "";
  }

  function scheduleTypeRecommend() {
    clearTimeout(state.recommendTimer);
    state.recommendTimer = setTimeout(recommendType, 350);
  }

  function recommendType() {
    const text = ui.input.value;
    if (text.length < 60) return;
    let best = null;
    let bestScore = 0;

    Object.keys(TYPE_KEYWORDS).forEach((type) => {
      let score = 0;
      TYPE_KEYWORDS[type].forEach((word) => {
        let from = 0;
        while (true) {
          const at = text.indexOf(word, from);
          if (at < 0 || score >= 30) break;
          score += 1;
          from = at + word.length;
        }
      });
      if (score > bestScore) { bestScore = score; best = type; }
    });

    const current = ui.typeSelect.value;
    if (best && bestScore >= 3 && best !== current) {
      ui.typeSelect.value = best;
      state.settings.contractType = best;
      populateStances(best);
      showTypeHint(`检测到像「${best}」，已切换`);
    } else if (best && best !== current && bestScore >= 2) {
      showTypeHint(`看起来更像「${best}」？可在上方切换`);
    }
  }

  function showTypeHint(text) {
    ui.typeHint.textContent = text;
    clearTimeout(state.hintTimer);
    state.hintTimer = setTimeout(() => { ui.typeHint.textContent = ""; }, 5000);
  }

  function loadSample(key) {
    const sample = (WB.SAMPLES || []).find((s) => s.key === key);
    if (!sample) return;
    ui.input.value = sample.text;
    updateCharCount();
    setType(sample.name);
    showTypeHint(`已载入示例：${sample.name}`);
    resetFileStatus();
    ui.input.focus();
  }

  // ═════════════ 设置 ═════════════

  function openSettings() {
    closeLedgerForm();
    populateProviderOptions();
    fillSettingsForm();
    ui.drawer.classList.remove("hidden");
    ui.backdrop.classList.remove("hidden");
    setTimeout(() => $("#set-provider").focus(), 30);
  }

  function closeSettings() {
    ui.drawer.classList.add("hidden");
    ui.backdrop.classList.add("hidden");
  }

  function populateProviderOptions() {
    // 已由 init 填过；这里只确保存在
    if (!$("#set-provider").options.length) populateProviders();
  }

  function fillSettingsForm() {
    const s = state.settings;
    $("#set-provider").value = s.provider;
    $("#set-apikey").value = (s.apiKeys || {})[s.provider] || "";
    $("#set-model").value = s.model;
    $("#set-masking").checked = s.masking !== false;
    $("#set-names").value = (s.hiddenNames || []).join("\n");
    updateProviderNote();
  }

  function updateProviderNote() {
    const key = $("#set-provider").value;
    const p = WB.PROVIDERS[key];
    $("#set-provider-note").textContent = p ? p.note : "";
  }

  function onProviderChange() {
    const key = $("#set-provider").value;
    const p = WB.PROVIDERS[key];
    if (!p) return;
    $("#set-provider-note").textContent = p.note;
    $("#set-model").value = p.model;
    $("#set-apikey").value = (state.settings.apiKeys || {})[key] || "";
    updateProviderNote();
  }

  function toggleKeyVisibility() {
    const input = $("#set-apikey");
    const isPassword = input.type === "password";
    input.type = isPassword ? "text" : "password";
    $("#btn-toggle-key").textContent = isPassword ? "隐藏" : "显示";
  }

  async function saveSettings() {
    const provider = $("#set-provider").value;
    const p = WB.PROVIDERS[provider];
    const apiKey = $("#set-apikey").value.trim();
    const model = $("#set-model").value.trim() || p.model;
    const masking = $("#set-masking").checked;
    const names = $("#set-names").value
      .split(/[\n,，、;；]+/)
      .map((s) => s.trim())
      .filter(Boolean);

    const apiKeys = Object.assign({}, state.settings.apiKeys);
    apiKeys[provider] = apiKey;

    state.settings = {
      provider,
      baseUrl: p.baseUrl,
      model,
      apiKeys,
      masking,
      hiddenNames: names,
      contractType: state.settings.contractType || WB.CONTRACT_TYPES[0],
      stance: state.settings.stance || "neutral",
    };

    await WB.saveSettings(state.settings);
    updateModelStatus();
    closeSettings();
    toast("设置已保存");
  }

  function updateModelStatus() {
    const s = state.settings;
    const p = WB.PROVIDERS[s.provider] || WB.PROVIDERS.dashscope;
    const hasKey = Boolean((s.apiKeys || {})[s.provider]);
    ui.modelStatus.classList.remove("ok", "warn");
    if (!hasKey) {
      ui.modelStatusText.textContent = "未配置模型";
      ui.modelStatus.title = "未配置模型";
      return;
    }
    ui.modelStatusText.textContent = s.model;
    ui.modelStatus.title = `${p.label} · ${s.model}`;
    ui.modelStatus.classList.add("ok");
  }

  // ═════════════ 导出 / 复制 ═════════════

  function downloadText(text, filename, type) {
    const blob = new Blob([text], { type });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1500);
  }

  function safeFilename(name) {
    return String(name || "合同").replace(/[\\/:*?"<>|]+/g, "_").slice(0, 60) || "合同";
  }

  function exportDoc() {
    if (!state.lastResult) return;
    const html = WB.buildDocHtml(state.lastResult.reportHtml || "", state.lastResult.contractType || "");
    downloadText("﻿" + html, `合同审查报告-${dateStamp()}.doc`, "application/msword");
    toast("报告已导出");
  }

  function dateStamp() {
    const d = new Date();
    const p = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}`;
  }

  async function copyText(text) {
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      toast("已复制修改条款");
    } catch (e) {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand("copy"); toast("已复制修改条款"); }
      catch (e2) { toast("复制失败，请手动选择", "error"); }
      ta.remove();
    }
  }

  // ═════════════ Toast ═════════════

  let toastTimer = null;
  function toast(message, kind) {
    ui.toast.textContent = message;
    ui.toast.className = "toast" + (kind === "error" ? " error" : "");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => ui.toast.classList.add("hidden"), 2800);
  }
})(globalThis);
