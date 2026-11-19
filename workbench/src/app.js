/* 合同工作台 · UI 逻辑 */
(function (root) {
  const WB = (root.WB = root.WB || {});
  const $ = (sel, el) => (el || document).querySelector(sel);
  const $$ = (sel, el) => Array.from((el || document).querySelectorAll(sel));
  const esc = WB.escapeHtml;

  const ICONS = {
    review: '<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4"/><circle cx="11" cy="13" r="3"/><path d="M13.2 15.2 16 18"/>',
    clause: '<path d="M6 3h12v18l-6-4-6 4z"/>',
    settings: '<path d="M4 7h16M4 12h16M4 17h16"/><circle cx="9" cy="7" r="2"/><circle cx="15" cy="12" r="2"/><circle cx="8" cy="17" r="2"/>',
    export: '<path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M4 20h16"/>',
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
    abort: null,
    clauseFilter: "房屋租赁合同",
    reportTab: "list",
    hintTimer: null,
    recommendTimer: null,
  };

  const ui = {};

  document.addEventListener("DOMContentLoaded", init);

  async function init() {
    cacheUI();
    injectIcons();
    state.settings = await WB.loadSettings();
    populateTypes();
    populateProviders();
    renderSamples();
    renderClauseFilters();
    renderClauses();
    bindEvents();
    updateModelStatus();

    const saved = await WB.loadCurrent();
    if (saved && saved.result && saved.contractText) {
      ui.input.value = saved.contractText;
      updateCharCount();
      if (saved.contractType) setType(saved.contractType);
      showResult(saved.result, saved.contractText);
      toast("已恢复上次审查结果");
    } else {
      showEmpty();
    }
  }

  function cacheUI() {
    ui.typeSelect = $("#contract-type");
    ui.modelStatus = $("#model-status");
    ui.modelStatusText = $("#model-status-text");
    ui.input = $("#contract-input");
    ui.charCount = $("#char-count");
    ui.typeHint = $("#type-hint");
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
    ui.drawer = $("#settings-drawer");
    ui.backdrop = $("#settings-backdrop");
    ui.toast = $("#toast");
    ui.errorTitle = $("#error-title");
    ui.errorDetail = $("#error-detail");
  }

  function injectIcons() {
    $$("[data-icon]").forEach((el) => {
      const svg = ICONS[el.dataset.icon];
      if (!svg) return;
      el.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${svg}</svg>`;
      el.classList.add("icon");
    });
  }

  // ═════════════ 初始化数据 ═════════════

  function populateTypes() {
    ui.typeSelect.innerHTML = WB.CONTRACT_TYPES.map(
      (t) => `<option value="${esc(t)}">${esc(t)}</option>`
    ).join("");
    setType(state.settings.contractType || WB.CONTRACT_TYPES[0]);
  }

  function setType(type) {
    if (!WB.CONTRACT_TYPES.includes(type)) return;
    ui.typeSelect.value = type;
    state.settings.contractType = type;
    WB.saveSettings(state.settings).catch(() => {});
  }

  function populateProviders() {
    const sel = $("#set-provider");
    sel.innerHTML = Object.keys(WB.PROVIDERS).map((k) => {
      const p = WB.PROVIDERS[k];
      return `<option value="${esc(k)}">${esc(p.label)}</option>`;
    }).join("");
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
      return `<article class="clause-card ${cls}">
        <div class="clause-card-head">
          <span class="risk-mark ${mark}"></span>
          <span class="clause-card-name">${esc(r.name)}</span>
          <span class="clause-card-level level-${cls}">${r.level}风险</span>
          <span class="clause-card-type">${esc(r.basis)}</span>
        </div>
        <p class="clause-card-condition">${esc(r.condition)}</p>
        <div class="clause-card-basis">关键词：${esc((r.keywords || []).join(" / "))}</div>
        <div class="clause-card-advice"><b>替代写法</b>${esc(r.advice)}</div>
      </article>`;
    }).join("");
  }

  // ═════════════ 事件 ═════════════

  function bindEvents() {
    $$(".nav-item").forEach((btn) => {
      btn.addEventListener("click", () => switchView(btn.dataset.view));
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

    $("#btn-start").addEventListener("click", startReview);
    $("#btn-clear").addEventListener("click", () => {
      ui.input.value = "";
      updateCharCount();
      ui.typeHint.textContent = "";
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
      jumpToRisk(btn.dataset.idx);
    });

    ui.clauseFilters.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-type]");
      if (!btn) return;
      state.clauseFilter = btn.dataset.type;
      renderClauseFilters();
      renderClauses();
    });

    $("#btn-settings").addEventListener("click", openSettings);
    $("#btn-close-settings").addEventListener("click", closeSettings);
    ui.backdrop.addEventListener("click", closeSettings);
    $("#set-provider").addEventListener("change", onProviderChange);
    $("#btn-toggle-key").addEventListener("click", toggleKeyVisibility);
    $("#btn-save-settings").addEventListener("click", saveSettings);

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !ui.drawer.classList.contains("hidden")) closeSettings();
    });

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
    if (view === "clauses") renderClauses();
  }

  function hideStates() {
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
      const result = await WB.runPipeline({
        contractText: text,
        contractType: ui.typeSelect.value,
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
      await WB.saveCurrent({
        contractText: text,
        contractType: ui.typeSelect.value,
        result,
        savedAt: Date.now(),
      });
      toast("审查完成");
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
    ui.input.value = "";
    ui.typeHint.textContent = "";
    updateCharCount();
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
    hideStates();
    ui.result.classList.remove("hidden");
    switchView("review");

    if (result.contractType && WB.CONTRACT_TYPES.includes(result.contractType)) {
      ui.typeSelect.value = result.contractType;
    }

    const c = result.counts || { high: 0, mid: 0, low: 0 };
    ui.resultStats.innerHTML = `
      <span class="result-stat high">高风险 <b>${c.high}</b></span>
      <span class="result-stat mid">中风险 <b>${c.mid}</b></span>
      <span class="result-stat low">低风险 <b>${c.low}</b></span>
      <span class="result-stat score">综合评分 <b>${result.score == null ? "—" : result.score}</b><span>/100</span></span>`;

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

  function jumpToRisk(idx) {
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
    mark.scrollIntoView({ behavior: "smooth", block: "center" });
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
    ui.input.focus();
  }

  // ═════════════ 设置 ═════════════

  function openSettings() {
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
    };

    await WB.saveSettings(state.settings);
    updateModelStatus();
    closeSettings();
    toast("设置已保存");
  }

  function updateModelStatus() {
    const s = state.settings;
    const p = WB.PROVIDERS[s.provider] || WB.PROVIDERS.deepseek;
    const hasKey = Boolean((s.apiKeys || {})[s.provider]);
    ui.modelStatus.classList.remove("ok", "warn");
    if (!hasKey) {
      ui.modelStatusText.textContent = "未配置模型";
      return;
    }
    ui.modelStatusText.textContent = `${p.label} · ${s.model}`;
    ui.modelStatus.classList.add(s.provider === "zhipu" ? "warn" : "ok");
  }

  // ═════════════ 导出 / 复制 ═════════════

  function exportDoc() {
    if (!state.lastResult) return;
    const html = WB.buildDocHtml(state.lastResult.reportHtml || "", state.lastResult.contractType || "");
    const blob = new Blob(["﻿", html], { type: "application/msword" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `合同审查报告-${dateStamp()}.doc`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1500);
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
