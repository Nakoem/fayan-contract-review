#!/usr/bin/env node
/* UI 冒烟测试：在真 Chrome 里打开 dist/index.html（file://），
 * 用 mock LLM 走完整流程，验证界面、渲染、跳转、打印与持久化。
 *
 * 用法：node workbench/scripts/ui_smoke.mjs
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { launchBrowser, waitFor, screenshot, reloadPage, sleep } from "./lib.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const WB_DIR = path.resolve(__dirname, "..");
const INDEX = path.join(WB_DIR, "dist", "index.html");
const SHOT_DIR = path.join(WB_DIR, "screenshots");

const isoDate = (d) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const today = new Date();
const startDay = new Date(today); startDay.setDate(startDay.getDate() - 30);
const payDay = new Date(today); payDay.setDate(payDay.getDate() + 5);
const dueDay = new Date(today); dueDay.setDate(dueDay.getDate() + 10);
const START_ISO = isoDate(startDay);
const PAY_ISO = isoDate(payDay);
const DUE_ISO = isoDate(dueDay);

const MOCK = String.raw`(() => {
  WB.callLLM = async function (opts) {
    const sys = (opts.messages && opts.messages[0] && opts.messages[0].content) || "";
    if (sys.indexOf("条款抽取器") >= 0) {
      const text = document.querySelector("#contract-input").value;
      const parts = text.split(/\n\s*\n/).filter(function (s) { return s.trim(); });
      const clauses = parts.map(function (p, i) { return { index: i + 1, title: "第 " + (i + 1) + " 条", text: p.trim() }; });
      window.__mockClauses = clauses;
      return { content: JSON.stringify({ clauses: clauses }), usage: null };
    }
    if (sys.indexOf("风险分析师") >= 0) {
      const cs = window.__mockClauses || [];
      const findIndex = function (needle) {
        for (let i = 0; i < cs.length; i++) { if (cs[i].text.indexOf(needle) >= 0) return cs[i].index; }
        return 1;
      };
      const findings = [
        {
          rule_id: "r_lease_penalty", clause_index: findIndex("乙方逾期支付租金超过15日"),
          clause_text: "乙方逾期支付租金超过15日的，每逾期一日按应付租金的5%支付违约金。",
          fairness: 4, clarity: 4, exposure: 5,
          risk_reason: "按日 5% 的违约金明显高于实际损失，属于畸高。",
          basis: "民法典第585条", suggestion: "建议以实际损失的 30% 为上限，或改为按日万分之五。"
        },
        {
          rule_id: "r_lease_unilateral_termination", clause_index: findIndex("有下列情形之一的，甲方有权单方解除合同"),
          clause_text: "有下列情形之一的，甲方有权单方解除合同：",
          fairness: 3, clarity: 3, exposure: 4,
          risk_reason: "单方解除条件较宽，未约定催告与腾退程序。",
          basis: "住房租赁条例第12条", suggestion: "补充书面催告、合理腾退期与交接程序。"
        },
        {
          rule_id: "r_lease_expenses", clause_index: findIndex("租赁期间，水费、电费、网络费"),
          clause_text: "租赁期间，水费、电费、网络费由乙方承担，物业费、取暖费由甲方承担。",
          fairness: 3, clarity: 2, exposure: 3,
          risk_reason: "费用分摊基本清晰，但缺少结算方式与票据义务。",
          basis: "民法典第510条", suggestion: "补充费用结算周期与凭证提供义务。"
        }
      ];
      const used = findings.map(function (f) { return f.clause_index; });
      const low = cs.filter(function (c) { return used.indexOf(c.index) < 0; }).map(function (c) {
        return { clause_index: c.index, clause_text: c.text, reason: "常规条款，无明显风险" };
      });
      return {
        content: JSON.stringify({
          findings: findings,
          lowRiskClauses: low,
          summary: "合同整体风险中等，重点关注违约金与单方解除条款。"
        }),
        usage: null
      };
    }
    if (sys.indexOf("质量审核员") >= 0) {
      return { content: JSON.stringify({ passed: true, issues: [] }), usage: null };
    }
    return { content: "{}", usage: null };
  };
  return true;
})()`;

async function main() {
  if (!fs.existsSync(INDEX)) throw new Error("dist/index.html 不存在，请先运行 build.py");
  fs.mkdirSync(SHOT_DIR, { recursive: true });

  const results = [];
  const ok = (name, passed, detail) => {
    results.push({ name, passed, detail });
    console.log(`${passed ? "✓" : "✗"} ${name}${detail ? " · " + detail : ""}`);
  };

  let browser = null;
  try {
    browser = await launchBrowser({
      url: pathToFileURL(INDEX).href,
      prefix: "wb-smoke",
    });
    const cdp = browser.cdp;
    const shot = async (name) => {
      const p = await screenshot(cdp, path.join(SHOT_DIR, name));
      console.log(`  截图：${p}`);
    };

    await waitFor(cdp, `document.readyState === "complete" && window.__WB_READY__ === true && document.querySelectorAll(".sample-chip").length === 6`);

    ok("页面加载", true, await cdp.eval(`document.title`));
    ok("示例合同 6 份", (await cdp.eval(`document.querySelectorAll(".sample-chip").length`)) === 6);
    ok("合同类型 6 类", (await cdp.eval(`document.querySelectorAll("#contract-type option").length`)) === 6);
    await shot("ui-empty.png");

    await cdp.eval(`document.querySelector('.nav-item[data-view="clauses"]').click(); true`);
    const cardCount = await cdp.eval(`document.querySelectorAll(".clause-card").length`);
    ok("条款库渲染", cardCount > 0, cardCount + " 张卡片");
    await shot("ui-clauses.png");

    await cdp.eval(`document.querySelector("#btn-settings").click(); true`);
    await waitFor(cdp, `!document.querySelector("#settings-drawer").classList.contains("hidden")`);
    await shot("ui-settings.png");
    await cdp.eval(`document.querySelector("#btn-close-settings").click(); true`);

    await cdp.eval(`(async () => {
      await WB.saveSettings({
        provider: "dashscope",
        baseUrl: "https://dashscope.aliyuncs.com/compatible-mode/v1",
        model: "qwen3.8-max-0902",
        apiKeys: { deepseek: "", dashscope: "test-key" },
        masking: true, hiddenNames: [], contractType: "房屋租赁合同"
      });
      return true;
    })()`);
    await reloadPage(cdp);

    await cdp.eval(MOCK);

    await cdp.eval(`(() => {
      const s = WB.SAMPLES.find(function (x) { return x.key === "lease"; });
      const ta = document.querySelector("#contract-input");
      ta.value = s.text;
      ta.dispatchEvent(new Event("input", { bubbles: true }));
      document.querySelector('.nav-item[data-view="review"]').click();
      document.querySelector("#btn-start").click();
      return true;
    })()`);

    await waitFor(
      cdp,
      `!document.querySelector("#review-result").classList.contains("hidden") && document.querySelectorAll("#risk-list .risk-item").length > 0`,
      20000
    );

    const stats = await cdp.eval(`document.querySelector("#result-stats").innerText.replace(/\\s+/g, " ")`);
    const riskItems = await cdp.eval(`document.querySelectorAll("#risk-list .risk-item").length`);
    const marks = await cdp.eval(`document.querySelectorAll("#contract-view mark").length`);
    const sections = await cdp.eval(`document.querySelectorAll("#report-view .report-section").length`);
    const signText = await cdp.eval(`document.querySelector("#report-view .sign-advice") ? document.querySelector("#report-view .sign-advice").textContent : ""`);

    ok("结果渲染", riskItems === 3, `风险条目 ${riskItems} 条 · 正文标色 ${marks} 处`);
    ok("报告六段", sections === 6, `${sections} 段`);
    ok("签约建议", signText.indexOf("修改后签") >= 0, signText.trim());
    ok("评分概览", stats.indexOf("综合评分") >= 0, stats);
    await shot("ui-result-list.png");

    await cdp.eval(`document.querySelector("#risk-list .risk-item.high").click(); true`);
    const beam = (await waitFor(cdp, `document.querySelectorAll(".hl-beam-rect").length`, 3000).catch(() => 0)) || 0;
    const active = await cdp.eval(`document.querySelectorAll("#risk-list .risk-item.is-active").length`);
    ok("高风险原文光束", beam >= 1, `${beam} 段 · 选中态 ${active}`);
    await sleep(700);
    await shot("ui-result-beam.png");

    await cdp.send("Emulation.setDeviceMetricsOverride", { width: 1180, height: 900, deviceScaleFactor: 1, mobile: false });
    await sleep(350);
    const beamResized = await cdp.eval(`document.querySelectorAll(".hl-beam-rect").length`);
    ok("窗口变化光束跟随", beamResized >= 1, `${beamResized} 段`);
    await cdp.send("Emulation.setDeviceMetricsOverride", { width: 1280, height: 900, deviceScaleFactor: 1, mobile: false });
    await sleep(200);

    await cdp.eval(`document.querySelector("#risk-list .risk-item.mid").click(); true`);
    const midFlash = await cdp.eval(`document.querySelectorAll("mark.hl-flash").length`);
    const beamAfterMid = await cdp.eval(`document.querySelectorAll(".hl-beam-rect").length`);
    ok("中风险仍闪烁", midFlash >= 1 && beamAfterMid === 0, `闪烁 ${midFlash} · 光束 ${beamAfterMid}`);

    await cdp.eval(`document.querySelector('.panel-tab[data-tab="report"]').click(); true`);
    const reportVisible = await cdp.eval(`!document.querySelector("#report-view").classList.contains("hidden")`);
    ok("完整报告标签页", reportVisible);
    await shot("ui-result-report.png");
    await cdp.eval(`(() => { const v = document.querySelector("#report-view"); if (v) v.scrollTop = v.scrollHeight; return true; })()`);
    await shot("ui-result-report-bottom.png");

    const pdf = await cdp.send("Page.printToPDF", { printBackground: true, preferCSSPageSize: true });
    const pdfPath = path.join(SHOT_DIR, "ui-report.pdf");
    fs.writeFileSync(pdfPath, Buffer.from(pdf.result.data, "base64"));
    ok("打印 PDF 生成", fs.statSync(pdfPath).size > 1000, `${(fs.statSync(pdfPath).size / 1024).toFixed(1)} KB`);

    await cdp.send("Emulation.setEmulatedMedia", { media: "print" });
    const printStyles = await cdp.eval(`(() => {
      return {
        report: getComputedStyle(document.querySelector("#report-view")).display,
        contract: getComputedStyle(document.querySelector(".contract-panel")).display,
        toolbar: getComputedStyle(document.querySelector(".result-toolbar")).display
      };
    })()`);
    await cdp.send("Emulation.setEmulatedMedia", { media: "" });
    ok("打印样式只保留报告", printStyles.report === "block" && printStyles.contract === "none" && printStyles.toolbar === "none", JSON.stringify(printStyles));

    // ── 合同台账：从审查结果加入 ──
    await cdp.eval(`document.querySelector("#btn-add-ledger").click(); true`);
    await waitFor(cdp, `!document.querySelector("#ledger-drawer").classList.contains("hidden")`, 3000);
    const draft = await cdp.eval(`({
      title: document.querySelector("#ledger-title").value,
      type: document.querySelector("#ledger-type").value,
      status: document.querySelector("#ledger-status").value,
      review: document.querySelector("#ledger-review-id").value
    })`);
    ok("加入台账预填", draft.title.length > 0 && draft.type === "房屋租赁合同" && draft.status === "待签" && draft.review.length > 0, JSON.stringify(draft));
    await shot("ui-ledger-form.png");

    await cdp.eval(`(() => {
      const set = (sel, value) => { const el = document.querySelector(sel); el.value = value; el.dispatchEvent(new Event("input", { bubbles: true })); };
      set("#ledger-start", ${JSON.stringify(START_ISO)});
      set("#ledger-end", ${JSON.stringify(DUE_ISO)});
      set("#ledger-payment-date", ${JSON.stringify(PAY_ISO)});
      set("#ledger-counterparty", "测试对方");
      set("#ledger-amount", "120000");
      set("#ledger-payment-amount", "8000");
      set("#ledger-note", "押金两个月");
      document.querySelector("#ledger-form").requestSubmit();
      return true;
    })()`);
    const ledgerSaved = await waitFor(cdp, `(async () => (await WB.listLedger()).length)()`, 5000).catch(() => 0);
    ok("台账保存", ledgerSaved === 1, `${ledgerSaved} 条`);

    await cdp.eval(`document.querySelector('.nav-item[data-view="home"]').click(); true`);
    await sleep(250);
    const reminderCount = (await waitFor(cdp, `document.querySelectorAll("#home-reminder-list .reminder-item").length`, 3000).catch(() => 0)) || 0;
    const reminderText = await cdp.eval(`document.querySelector("#home-reminder-list").innerText.replace(/\\s+/g, " ")`);
    ok("案头到期提醒", reminderCount >= 2, `${reminderCount} 条 · ${reminderText}`);

    await cdp.eval(`document.querySelector("#home-reminder-list .reminder-item").click(); true`);
    await waitFor(cdp, `!document.querySelector("#ledger-drawer").classList.contains("hidden")`, 3000);
    const reminderEditTitle = await cdp.eval(`document.querySelector("#ledger-form-title").textContent`);
    await cdp.eval(`document.querySelector("#btn-cancel-ledger").click(); true`);
    ok("案头待办打开编辑", reminderEditTitle === "编辑合同", reminderEditTitle);

    await cdp.eval(`document.querySelector('.nav-item[data-view="ledger"]').click(); true`);
    await sleep(250);
    const ledgerRows = (await waitFor(cdp, `document.querySelectorAll("#ledger-list .ledger-row").length`, 3000).catch(() => 0)) || 0;
    const ledgerText = await cdp.eval(`document.querySelector("#ledger-list").innerText.replace(/\\s+/g, " ")`);
    const linkedReview = await cdp.eval(`document.querySelectorAll("#ledger-list [data-open-ledger-review]").length`);
    ok("合同台账渲染", ledgerRows === 1 && ledgerText.indexOf("测试对方") >= 0 && ledgerText.indexOf("120,000") >= 0, `${ledgerRows} 条 · ${ledgerText.slice(0, 90)}`);
    ok("台账关联审查", linkedReview === 1, `${linkedReview} 个入口`);
    await cdp.eval(`document.querySelector("#toast").classList.add("hidden"); true`);
    await shot("ui-ledger.png");

    await cdp.eval(`(() => { const s = document.querySelector("#ledger-search"); s.value = "测试对方"; s.dispatchEvent(new Event("input", { bubbles: true })); return true; })()`);
    const ledgerSearch = await cdp.eval(`document.querySelectorAll("#ledger-list .ledger-row").length`);
    await cdp.eval(`(() => { const s = document.querySelector("#ledger-search"); s.value = "不存在"; s.dispatchEvent(new Event("input", { bubbles: true })); return true; })()`);
    const ledgerEmpty = await cdp.eval(`document.querySelector("#ledger-list").innerText`);
    await cdp.eval(`(() => { const s = document.querySelector("#ledger-search"); s.value = ""; s.dispatchEvent(new Event("input", { bubbles: true })); return true; })()`);
    ok("台账搜索", ledgerSearch === 1 && ledgerEmpty.indexOf("没有匹配") >= 0, `${ledgerSearch} 条`);

    await cdp.eval(`document.querySelector('#ledger-filters [data-status="已归档"]').click(); true`);
    const archivedRows = await cdp.eval(`document.querySelectorAll("#ledger-list .ledger-row").length`);
    await cdp.eval(`document.querySelector('#ledger-filters [data-status="全部"]').click(); true`);
    ok("台账状态筛选", archivedRows === 0, `已归档 ${archivedRows} 条`);

    await cdp.eval(`(() => { const s = document.querySelector("#ledger-type-filter"); s.value = "劳动合同"; s.dispatchEvent(new Event("change", { bubbles: true })); return true; })()`);
    const typeFilteredRows = await cdp.eval(`document.querySelectorAll("#ledger-list .ledger-row").length`);
    const typeEmptyText = await cdp.eval(`document.querySelector("#ledger-list").innerText`);
    await cdp.eval(`(() => { const s = document.querySelector("#ledger-type-filter"); s.value = "全部类型"; s.dispatchEvent(new Event("change", { bubbles: true })); return true; })()`);
    const typeResetRows = await cdp.eval(`document.querySelectorAll("#ledger-list .ledger-row").length`);
    ok("台账类型筛选", typeFilteredRows === 0 && typeEmptyText.indexOf("没有匹配") >= 0 && typeResetRows === 1, `劳动 ${typeFilteredRows} 条 · 重置 ${typeResetRows} 条`);

    await cdp.eval(`document.querySelector("#ledger-list [data-edit-ledger]").click(); true`);
    await waitFor(cdp, `!document.querySelector("#ledger-drawer").classList.contains("hidden")`, 3000);
    await cdp.eval(`(() => {
      const el = document.querySelector("#ledger-counterparty");
      el.value = "修改后对方";
      el.dispatchEvent(new Event("input", { bubbles: true }));
      document.querySelector("#ledger-form").requestSubmit();
      return true;
    })()`);
    const edited = await waitFor(cdp, `(async () => { const rows = await WB.listLedger(); return rows.length === 1 && rows[0].counterparty === "修改后对方"; })()`, 5000).catch(() => false);
    ok("台账编辑", !!edited);

    await cdp.eval(`document.querySelector('.nav-item[data-view="home"]').click(); true`);
    await cdp.eval(`document.querySelector("#home-tab-contracts").click(); true`);
    const homeContractRows = await cdp.eval(`document.querySelectorAll("#home-contracts-list .home-contract-row").length`);
    const homeContractText = await cdp.eval(`document.querySelector("#home-contracts-list").innerText.replace(/\\s+/g, " ")`);
    const homeContractTools = await cdp.eval(`!document.querySelector("#home-contract-tools").classList.contains("hidden")`);
    const activeNav = await cdp.eval(`(document.querySelector(".nav-item.active") || {}).innerText || ""`);
    await shot("ui-home-contracts.png");

    await cdp.eval(`(() => { const s = document.querySelector("#contracts-search"); s.value = "修改后对方"; s.dispatchEvent(new Event("input", { bubbles: true })); return true; })()`);
    const contractsHits = await cdp.eval(`document.querySelectorAll("#home-contracts-list .home-contract-row").length`);
    const contractsSyncSidebar = await cdp.eval(`document.querySelector("#sidebar-search").value`);
    const contractsSyncHistory = await cdp.eval(`document.querySelector("#history-search").value`);
    const contractsTabKept = await cdp.eval(`!document.querySelector("#home-contracts-pane").classList.contains("hidden")`);
    await cdp.eval(`(() => { const s = document.querySelector("#contracts-search"); s.value = "不存在的合同"; s.dispatchEvent(new Event("input", { bubbles: true })); return true; })()`);
    const contractsMiss = await cdp.eval(`document.querySelectorAll("#home-contracts-list .home-contract-row").length`);
    const contractsMissText = await cdp.eval(`document.querySelector("#home-contracts-list").innerText`);
    await cdp.eval(`(() => { const s = document.querySelector("#contracts-search"); s.value = ""; s.dispatchEvent(new Event("input", { bubbles: true })); return true; })()`);
    const contractsReset = await cdp.eval(`document.querySelectorAll("#home-contracts-list .home-contract-row").length`);
    ok(
      "我的合同搜索",
      contractsHits === 1 && contractsSyncSidebar === "修改后对方" && contractsSyncHistory === "修改后对方" &&
        contractsTabKept && contractsMiss === 0 && contractsMissText.indexOf("没有匹配") >= 0 && contractsReset === 1,
      `${contractsHits} 条 · 空态 ${contractsMiss} · 重置 ${contractsReset}`
    );

    await cdp.eval(`document.querySelector("#home-tab-reviews").click(); true`);
    ok(
      "案头我的合同",
      homeContractRows === 1 && homeContractText.indexOf("修改后对方") >= 0 && homeContractTools && activeNav.indexOf("案头") >= 0,
      `${homeContractRows} 条 · ${homeContractText.slice(0, 70)} · 当前 ${activeNav.trim()}`
    );

    const dateLogic = await cdp.eval(`WB.Ledger.daysUntil("2026-11-25", new Date(2026, 10, 19))`);
    ok("台账日期计算", dateLogic === 6, `${dateLogic} 天`);
    const ics = await cdp.eval(`(async () => WB.Ledger.buildICS(await WB.listLedger()))()`);
    ok("台账 ICS 内容", ics.indexOf("BEGIN:VEVENT") >= 0 && ics.indexOf("合同到期") >= 0 && ics.indexOf("VALARM") >= 0, `${ics.length} 字符`);
    const csv = await cdp.eval(`(async () => WB.Ledger.buildCSV(await WB.listLedger()))()`);
    ok("台账 CSV 内容", csv.indexOf("合同名称") >= 0 && csv.indexOf("修改后对方") >= 0, `${csv.length} 字符`);
    const csvSafe = await cdp.eval(`WB.Ledger.buildCSV([{ title: "=1+1" }])`);
    ok("CSV 公式防护", csvSafe.indexOf("'=1+1") >= 0, csvSafe.split("\n")[1]);

    await cdp.eval(`document.querySelector('.nav-item[data-view="home"]').click(); true`);
    await sleep(250); // 等导航胶囊过渡结束再截图
    const historyCount = (await waitFor(cdp, `document.querySelectorAll("#history-list .history-item").length`, 5000).catch(() => 0)) || 0;
    const homeStats = await cdp.eval(`document.querySelector("#home-stats").innerText.replace(/\\s+/g, " ")`);
    ok("案头历史记录", historyCount >= 1, `${historyCount} 条 · ${homeStats}`);
    await cdp.eval(`document.querySelector("#toast").classList.add("hidden"); true`);
    await shot("ui-home.png");

    await cdp.eval(`(() => { const s = document.querySelector("#history-search"); s.value = "租赁"; s.dispatchEvent(new Event("input", { bubbles: true })); return true; })()`);
    const searchCount = await cdp.eval(`document.querySelectorAll("#history-list .history-item").length`);
    ok("历史搜索命中", searchCount >= 1, `${searchCount} 条`);

    await cdp.eval(`(() => { const s = document.querySelector("#history-search"); s.value = "不存在的关键词"; s.dispatchEvent(new Event("input", { bubbles: true })); return true; })()`);
    const noMatch = await cdp.eval(`document.querySelectorAll("#history-list .history-item").length`);
    ok("历史搜索空态", noMatch === 0, `${noMatch} 条`);

    await cdp.eval(`(() => { const s = document.querySelector("#history-search"); s.value = ""; s.dispatchEvent(new Event("input", { bubbles: true })); return true; })()`);
    await cdp.eval(`document.querySelector('.nav-item[data-view="review"]').click(); true`);
    await cdp.eval(`(() => { const s = document.querySelector("#sidebar-search"); s.value = "租赁"; s.dispatchEvent(new Event("input", { bubbles: true })); return true; })()`);
    const sidebarHits = await cdp.eval(`document.querySelectorAll("#history-list .history-item").length`);
    const sidebarSynced = await cdp.eval(`document.querySelector("#history-search").value`);
    const sidebarContractSynced = await cdp.eval(`document.querySelector("#contracts-search").value`);
    const sidebarView = await cdp.eval(`!document.querySelector("#view-home").classList.contains("hidden")`);
    await cdp.eval(`(() => { const s = document.querySelector("#sidebar-search"); s.value = "不存在的关键词"; s.dispatchEvent(new Event("input", { bubbles: true })); return true; })()`);
    const sidebarMiss = await cdp.eval(`document.querySelectorAll("#history-list .history-item").length`);
    await cdp.eval(`(() => { const s = document.querySelector("#sidebar-search"); s.value = "修改后对方"; s.dispatchEvent(new Event("input", { bubbles: true })); return true; })()`);
    const ledgerSearchHits = await cdp.eval(`document.querySelectorAll("#history-list .search-ledger-row").length`);
    const ledgerSearchHistory = await cdp.eval(`document.querySelectorAll("#history-list .history-item").length`);
    await shot("ui-search-ledger.png");
    await cdp.eval(`document.querySelector("#history-list .search-ledger-row").click(); true`);
    await waitFor(cdp, `!document.querySelector("#ledger-drawer").classList.contains("hidden")`, 3000);
    const ledgerSearchTitle = await cdp.eval(`document.querySelector("#ledger-form-title").textContent`);
    await cdp.eval(`document.querySelector("#btn-cancel-ledger").click(); true`);
    ok(
      "侧栏全局搜索",
      sidebarHits >= 1 && sidebarSynced === "租赁" && sidebarContractSynced === "租赁" && sidebarMiss === 0 && sidebarView &&
        ledgerSearchHits === 1 && ledgerSearchHistory === 0 && ledgerSearchTitle === "编辑合同",
      `${sidebarHits} 条 · 空态 ${sidebarMiss} · 台账 ${ledgerSearchHits} 条 · 跨页 ${sidebarView}`
    );
    await cdp.eval(`document.querySelector("#sidebar-search-clear").click(); true`);
    const clearState = await cdp.eval(`({
      sidebar: document.querySelector("#sidebar-search").value,
      history: document.querySelector("#history-search").value,
      contracts: document.querySelector("#contracts-search").value,
      ledger: document.querySelector("#ledger-search").value,
      hidden: document.querySelector("#sidebar-search-clear").classList.contains("hidden"),
      focused: document.activeElement.id
    })`);
    ok(
      "侧栏清空按钮",
      clearState.sidebar === "" && clearState.history === "" && clearState.contracts === "" &&
        clearState.ledger === "" && clearState.hidden && clearState.focused === "sidebar-search",
      JSON.stringify(clearState)
    );
    await cdp.eval(`document.querySelector("#history-list .history-open").click(); true`);
    const openedHistory = await waitFor(cdp, `!document.querySelector("#review-result").classList.contains("hidden")`, 3000).catch(() => false);
    ok("历史记录打开报告", !!openedHistory);

    await reloadPage(cdp);
    const restored = await waitFor(cdp, `!document.querySelector("#review-result").classList.contains("hidden")`, 8000).catch(() => false);
    const savedKey = await cdp.eval(`(async () => { const s = await WB.loadSettings(); return s.apiKeys.dashscope; })()`);
    ok("刷新恢复审查结果", !!restored);
    ok("API Key 持久化", savedKey === "test-key", savedKey ? "已读取" : "未找到");

    await cdp.eval(`document.querySelector("#risk-list .risk-item.high").click(); true`);
    const restoredBeam = (await waitFor(cdp, `document.querySelectorAll(".hl-beam-rect").length`, 3000).catch(() => 0)) || 0;
    ok("刷新恢复后光束仍可用", restoredBeam >= 1, `${restoredBeam} 段`);

    await cdp.eval(`document.querySelector('.nav-item[data-view="ledger"]').click(); true`);
    await sleep(200);
    const ledgerAfterReload = (await waitFor(cdp, `document.querySelectorAll("#ledger-list .ledger-row").length`, 3000).catch(() => 0)) || 0;
    const ledgerTextAfterReload = await cdp.eval(`document.querySelector("#ledger-list").innerText`);
    ok("台账刷新后仍在", ledgerAfterReload === 1 && ledgerTextAfterReload.indexOf("修改后对方") >= 0, `${ledgerAfterReload} 条`);

    await cdp.eval(`document.querySelector('.nav-item[data-view="home"]').click(); true`);
    const historyAfterReload = await cdp.eval(`document.querySelectorAll("#history-list .history-item").length`);
    ok("历史刷新后仍在", historyAfterReload >= 1, `${historyAfterReload} 条`);

    // 删除：window.confirm 会阻塞渲染进程，需要在 CDP 侧确认
    const deleteClick = cdp.eval(`document.querySelector("#history-list .history-delete").click(); true`);
    await sleep(300);
    await cdp.send("Page.handleJavaScriptDialog", { accept: true });
    await deleteClick;
    const deleted = await waitFor(cdp, `document.querySelectorAll("#history-list .history-item").length === 0`, 3000).catch(() => false);
    const remainAfterDelete = await cdp.eval(`WB.listReviews().then((r) => r.length)`);
    ok("删除历史记录", !!deleted && remainAfterDelete === 0, `剩余 ${remainAfterDelete} 条`);

    const clearStore = await cdp.eval(`(async () => {
      await WB.saveReview({ id: "rv_clear_test", createdAt: Date.now(), title: "清空测试", contractType: "房屋租赁合同", contractText: "清空测试", result: { counts: { high: 0, mid: 0, low: 0 }, findings: [], reportHtml: "" } });
      const before = (await WB.listReviews()).length;
      const ok = await WB.clearReviews();
      const after = (await WB.listReviews()).length;
      return { before: before, ok: ok, after: after };
    })()`);
    ok("清空历史存储", clearStore && clearStore.ok === true && clearStore.before >= 1 && clearStore.after === 0, JSON.stringify(clearStore));

    await cdp.eval(`document.querySelector('.nav-item[data-view="ledger"]').click(); true`);
    await sleep(200);
    const deleteLedgerClick = cdp.eval(`document.querySelector("#ledger-list [data-delete-ledger]").click(); true`);
    await sleep(300);
    await cdp.send("Page.handleJavaScriptDialog", { accept: true });
    await deleteLedgerClick;
    const ledgerDeleted = await waitFor(cdp, `(async () => (await WB.listLedger()).length === 0)()`, 3000).catch(() => false);
    const ledgerRowsAfterDelete = await cdp.eval(`document.querySelectorAll("#ledger-list .ledger-row").length`);
    ok("删除台账记录", !!ledgerDeleted && ledgerRowsAfterDelete === 0, `剩余 ${ledgerRowsAfterDelete} 行`);

    await cdp.eval(`document.querySelector("#ledger-list [data-ledger-add]").click(); true`);
    await waitFor(cdp, `!document.querySelector("#ledger-drawer").classList.contains("hidden")`, 3000);
    const manualDraft = await cdp.eval(`({
      title: document.querySelector("#ledger-title").value,
      type: document.querySelector("#ledger-type").value,
      status: document.querySelector("#ledger-status").value
    })`);
    await cdp.eval(`document.querySelector("#btn-cancel-ledger").click(); true`);
    ok("台账手动新增入口", manualDraft.title === "" && manualDraft.type === "房屋租赁合同" && manualDraft.status === "履行中", JSON.stringify(manualDraft));

    ok("无控制台异常", cdp.exceptions.length === 0, cdp.exceptions.slice(0, 3).join(" | "));
  } catch (err) {
    console.error("✗ 测试异常：" + err.message);
    process.exitCode = 1;
  } finally {
    if (browser) await browser.close();
  }

  const failed = results.filter((r) => !r.passed);
  console.log("");
  console.log(failed.length ? `✗ ${failed.length} 项未通过` : `✓ 全部 ${results.length} 项通过`);
  if (failed.length) process.exitCode = 1;
}

main().catch((e) => { console.error(e); process.exitCode = 1; });
