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
fs.mkdirSync(SHOT_DIR, { recursive: true });
const ATTACH_FILE = path.join(SHOT_DIR, "ui-attachment.txt");
fs.writeFileSync(ATTACH_FILE, "合同附件测试\n第二行\n", "utf8");

const isoDate = (d) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const today = new Date();
const startDay = new Date(today); startDay.setDate(startDay.getDate() - 30);
const payDay = new Date(today); payDay.setDate(payDay.getDate() + 5);
const dueDay = new Date(today); dueDay.setDate(dueDay.getDate() + 10);
const START_ISO = isoDate(startDay);
const PAY_ISO = isoDate(payDay);
const PAY2_ISO = isoDate(new Date(today.getFullYear(), today.getMonth(), today.getDate() + 8));
const RENEW_ISO = isoDate(new Date(today.getFullYear(), today.getMonth(), today.getDate() + 6));
const DUE_ISO = isoDate(dueDay);
const XSS_RULE_NAME = "<b>测试自定义规则</b>";

const MOCK = String.raw`(() => {
  WB.callLLM = async function (opts) {
    const first = opts.messages && opts.messages[0] && opts.messages[0].content;
    if (Array.isArray(first) && first.some(function (part) { return part && part.type === "image_url"; })) {
      window.__mockOcrCalls = (window.__mockOcrCalls || 0) + 1;
      return {
        content: "第一条 租金\n乙方应于每月5日前支付租金5000元。\n\n第二条 押金\n押金为10000元。",
        usage: null
      };
    }
    const sys = first || "";
    if (sys.indexOf("条款抽取器") >= 0) {
      const text = document.querySelector("#contract-input").value;
      const parts = text.split(/\n\s*\n/).filter(function (s) { return s.trim(); });
      const clauses = parts.map(function (p, i) { return { index: i + 1, title: "第 " + (i + 1) + " 条", text: p.trim() }; });
      window.__mockClauses = clauses;
      return { content: JSON.stringify({ clauses: clauses }), usage: null };
    }
    if (sys.indexOf("风险分析师") >= 0) {
      window.__mockEvalUser = (opts.messages && opts.messages[1] && opts.messages[1].content) || "";
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
    if (sys.indexOf("文书起草助手") >= 0) {
      window.__mockDocUser = (opts.messages && opts.messages[1] && opts.messages[1].content) || "";
      return {
        content: "催款函\n\n致：张三\n\n根据双方签订的《房屋租赁合同》，贵方应于每月 5 日前支付租金。截至本函发出之日，贵方仍未支付到期租金人民币 15,000 元。\n\n请贵方于收到本函后 15 日内付清上述款项。逾期未付的，我方将按合同约定继续主张违约责任。\n\n此致\n\n上海某公司\n2026年11月26日\n\n本函为 AI 辅助草稿，正式发出前请由律师复核。",
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

    const stanceOptions = await cdp.eval(`Array.from(document.querySelectorAll("#review-stance option")).map((o) => o.textContent)`);
    const stanceHint = await cdp.eval(`document.querySelector("#stance-hint").textContent`);
    ok(
      "审查视角默认中立",
      stanceOptions.length === 3 && stanceOptions[0] === "中立（双方）" &&
        stanceOptions.indexOf("承租人") >= 0 && stanceHint.indexOf("公平") >= 0,
      stanceOptions.join(" / ")
    );
    await cdp.eval(`(() => { const s = document.querySelector("#review-stance"); s.value = "tenant"; s.dispatchEvent(new Event("change", { bubbles: true })); return true; })()`);
    await cdp.eval(`(() => { const s = document.querySelector("#contract-type"); s.value = "劳动合同"; s.dispatchEvent(new Event("change", { bubbles: true })); return true; })()`);
    const laborStances = await cdp.eval(`Array.from(document.querySelectorAll("#review-stance option")).map((o) => o.textContent)`);
    const laborStanceValue = await cdp.eval(`document.querySelector("#review-stance").value`);
    await cdp.eval(`(() => { const s = document.querySelector("#contract-type"); s.value = "房屋租赁合同"; s.dispatchEvent(new Event("change", { bubbles: true })); return true; })()`);
    ok(
      "视角随合同类型切换",
      laborStances.length === 3 && laborStances.indexOf("劳动者") >= 0 &&
        laborStances.indexOf("用人单位") >= 0 && laborStanceValue === "neutral",
      `${laborStances.join(" / ")} · 切换后 ${laborStanceValue}`
    );
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
    await cdp.eval(`(() => { const s = document.querySelector("#review-stance"); s.value = "tenant"; s.dispatchEvent(new Event("change", { bubbles: true })); return true; })()`);

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
    const stampText = await cdp.eval(`(document.querySelector("#report-view .report-stamp") || {}).textContent || ""`);

    ok("结果渲染", riskItems === 3, `风险条目 ${riskItems} 条 · 正文标色 ${marks} 处`);
    ok("报告六段", sections === 6, `${sections} 段`);
    ok("报告已审查印章", stampText.indexOf("已审查") >= 0, stampText.trim());
    ok("签约建议", signText.indexOf("修改后签") >= 0, signText.trim());
    ok("评分概览", stats.indexOf("综合评分") >= 0, stats);
    const reportMeta = await cdp.eval(`(document.querySelector("#report-view .report-meta") || {}).textContent || ""`);
    const evalRequest = await cdp.eval(`window.__mockEvalUser || ""`);
    ok(
      "审查视角进入结果",
      stats.indexOf("承租人") >= 0 && reportMeta.indexOf("审查视角：承租人") >= 0,
      reportMeta.replace(/\s+/g, " ").trim()
    );
    ok("视角进入评估请求", evalRequest.indexOf("审查视角：承租人") >= 0, evalRequest.slice(0, 40).replace(/\s+/g, " "));
    const exportLabel = await cdp.eval(`document.querySelector("#btn-export").textContent`);
    const docxCheck = await cdp.eval(`(async () => {
      const b = WB.buildDocx({
        contractType: "房屋租赁合同", stanceLabel: "承租人",
        findings: [], lowRiskClauses: [], summary: "测试", dateText: "2026-11-24"
      });
      return { type: b.type, size: b.size };
    })()`);
    ok(
      "Word 导出 .docx",
      exportLabel.indexOf(".docx") >= 0 &&
        docxCheck.type.indexOf("openxmlformats") >= 0 && docxCheck.size > 1000,
      `${exportLabel.trim()} · ${docxCheck.size}B`
    );
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
        toolbar: getComputedStyle(document.querySelector(".result-toolbar")).display,
        otherViews: ["view-home", "view-ledger", "view-documents", "view-templates", "view-compare", "view-clauses", "view-law", "view-rules"]
          .map(function (id) { return getComputedStyle(document.getElementById(id)).display; })
      };
    })()`);
    await cdp.send("Emulation.setEmulatedMedia", { media: "" });
    const printOthersHidden = printStyles.otherViews.every((d) => d === "none");
    ok(
      "打印样式只保留报告",
      printStyles.report === "block" && printStyles.contract === "none" && printStyles.toolbar === "none" && printOthersHidden,
      JSON.stringify(printStyles)
    );

    // ── 合同台账：从审查结果加入 ──
    await cdp.eval(`document.querySelector("#btn-add-ledger").click(); true`);
    await waitFor(cdp, `!document.querySelector("#ledger-drawer").classList.contains("hidden")`, 3000);
    const draft = await cdp.eval(`({
      title: document.querySelector("#ledger-title").value,
      type: document.querySelector("#ledger-type").value,
      status: document.querySelector("#ledger-status").value,
      review: document.querySelector("#ledger-review-id").value,
      counterparty: document.querySelector("#ledger-counterparty").value,
      amount: document.querySelector("#ledger-amount").value,
      start: document.querySelector("#ledger-start").value,
      end: document.querySelector("#ledger-end").value,
      renewal: document.querySelector("#ledger-renewal").value,
      payments: Array.from(document.querySelectorAll("#ledger-payments .payment-row")).map(function (row) {
        return {
          date: row.querySelector(".payment-date").value,
          amount: row.querySelector(".payment-amount").value,
          note: row.querySelector(".payment-note").value
        };
      }),
      note: document.querySelector("#ledger-note").value
    })`);
    ok(
      "加入台账预填",
      draft.title.length > 0 &&
        draft.type === "房屋租赁合同" &&
        draft.status === "待签" &&
        draft.review.length > 0 &&
        draft.counterparty === "张三" &&
        draft.amount.indexOf("15,000") >= 0 &&
        draft.start === "2026-06-01" &&
        draft.end === "2029-05-31" &&
        draft.renewal === "" &&
        draft.payments.length === 1 &&
        /-05$/.test(draft.payments[0].date) &&
        draft.payments[0].amount === "15000" &&
        draft.note.indexOf("押金") >= 0,
      JSON.stringify(draft)
    );
    await shot("ui-ledger-form.png");

    await cdp.eval(`(() => {
      const set = (sel, value) => { const el = document.querySelector(sel); el.value = value; el.dispatchEvent(new Event("input", { bubbles: true })); };
      set("#ledger-start", ${JSON.stringify(START_ISO)});
      set("#ledger-end", ${JSON.stringify(DUE_ISO)});
      set("#ledger-renewal", ${JSON.stringify(RENEW_ISO)});
      set("#ledger-counterparty", "测试对方");
      set("#ledger-amount", "120000");
      set("#ledger-note", "押金两个月");
      const first = document.querySelector("#ledger-payments .payment-row");
      first.querySelector(".payment-date").value = ${JSON.stringify(PAY_ISO)};
      first.querySelector(".payment-amount").value = "8000";
      document.querySelector("#btn-add-payment").click();
      const rows = document.querySelectorAll("#ledger-payments .payment-row");
      const second = rows[rows.length - 1];
      second.querySelector(".payment-date").value = ${JSON.stringify(PAY2_ISO)};
      second.querySelector(".payment-amount").value = "7000";
      second.querySelector(".payment-note").value = "第二期";
      document.querySelector("#ledger-form").requestSubmit();
      return true;
    })()`);
    const ledgerSaved = await waitFor(cdp, `(async () => (await WB.listLedger()).length)()`, 5000).catch(() => 0);
    const savedEntry = await cdp.eval(`(async () => (await WB.listLedger())[0])()`);
    ok(
      "台账保存",
      ledgerSaved === 1 &&
        savedEntry.renewalDate === RENEW_ISO &&
        Array.isArray(savedEntry.payments) &&
        savedEntry.payments.length === 2 &&
        savedEntry.payments[1].amount === "7000" &&
        savedEntry.payments[1].note === "第二期",
      `${ledgerSaved} 条 · ${JSON.stringify(savedEntry && savedEntry.payments)}`
    );

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

    // ── 对方主体档案 ──
    await cdp.eval(`document.querySelector("#btn-ledger-parties").click(); true`);
    await waitFor(cdp, `!document.querySelector("#party-drawer").classList.contains("hidden")`, 3000);
    const partyState = await cdp.eval(`({
      cards: document.querySelectorAll("#party-list .party-card").length,
      summary: document.querySelector("#party-summary").textContent,
      badge: (document.querySelector("#party-list .party-risk-badge") || {}).textContent || ""
    })`);
    await cdp.eval(`document.querySelector("#party-list .party-head").click(); true`);
    const partyOpen = await cdp.eval(`({
      open: !!document.querySelector("#party-list .party-card.open"),
      contracts: document.querySelectorAll("#party-list .party-contract").length,
      risks: document.querySelectorAll("#party-list .party-risk-item").length,
      body: (document.querySelector("#party-list .party-body") || { innerText: "" }).innerText.replace(/\\s+/g, " ")
    })`);
    ok(
      "对方档案汇总",
      partyState.cards === 1 && partyState.summary.indexOf("1 个对方主体") >= 0 && partyState.badge.indexOf("未审查") < 0,
      `${partyState.cards} 个 · ${partyState.summary} · ${partyState.badge}`
    );
    ok(
      "对方档案展开",
      partyOpen.open && partyOpen.contracts === 1 && partyOpen.risks >= 1 && partyOpen.body.indexOf("历史条款口径") >= 0,
      `${partyOpen.contracts} 份合同 · ${partyOpen.risks} 条历史风险`
    );
    await shot("ui-party-drawer.png");

    await cdp.eval(`(() => { const s = document.querySelector("#party-search"); s.value = "测试"; s.dispatchEvent(new Event("input", { bubbles: true })); return true; })()`);
    const partyHits = await cdp.eval(`document.querySelectorAll("#party-list .party-card").length`);
    await cdp.eval(`(() => { const s = document.querySelector("#party-search"); s.value = "不存在"; s.dispatchEvent(new Event("input", { bubbles: true })); return true; })()`);
    const partyMiss = await cdp.eval(`document.querySelector("#party-list").innerText`);
    await cdp.eval(`(() => { const s = document.querySelector("#party-search"); s.value = ""; s.dispatchEvent(new Event("input", { bubbles: true })); return true; })()`);
    ok("对方档案搜索", partyHits === 1 && partyMiss.indexOf("没有匹配") >= 0, `${partyHits} 条`);

    await cdp.eval(`document.querySelector("#party-list .party-contract").click(); true`);
    await waitFor(cdp, `!document.querySelector("#ledger-drawer").classList.contains("hidden")`, 3000);
    const partyContractTitle = await cdp.eval(`document.querySelector("#ledger-title").value`);
    await cdp.eval(`document.querySelector("#btn-cancel-ledger").click(); true`);
    ok("对方档案合同入口", partyContractTitle.length > 0, partyContractTitle);

    await cdp.eval(`document.querySelector("#ledger-list [data-open-party]").click(); true`);
    await waitFor(cdp, `!document.querySelector("#party-drawer").classList.contains("hidden")`, 3000);
    const partyLinkOpen = await cdp.eval(`!!document.querySelector("#party-list .party-card.open")`);
    await cdp.eval(`document.querySelector("#btn-close-party").click(); true`);
    ok("台账对方链接", partyLinkOpen === true);

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

    // ── 附件管理：挂到台账合同、刷新后仍在、删合同时清理 ──
    await cdp.eval(`document.querySelector("#ledger-list [data-edit-ledger]").click(); true`);
    await waitFor(cdp, `!document.querySelector("#ledger-drawer").classList.contains("hidden")`, 3000);
    const attachmentEntryId = await cdp.eval(`(async () => (await WB.listLedger())[0].id)()`);
    const attachmentDoc = await cdp.send("DOM.getDocument", { depth: -1 });
    const attachmentNode = await cdp.send("DOM.querySelector", { nodeId: attachmentDoc.result.root.nodeId, selector: "#attachment-input" });
    await cdp.send("DOM.setFileInputFiles", { nodeId: attachmentNode.result.nodeId, files: [ATTACH_FILE] });
    await cdp.eval(`document.querySelector("#attachment-input").dispatchEvent(new Event("change", { bubbles: true })); true`);
    await waitFor(cdp, `document.querySelectorAll("#ledger-attachments .attachment-row").length === 1`, 5000);
    const attachmentState = await cdp.eval(`(async () => {
      const metas = await WB.Attachments.list(${JSON.stringify(attachmentEntryId)});
      const blob = metas[0] ? await WB.Attachments.getBlob(metas[0].id) : null;
      return {
        rows: document.querySelectorAll("#ledger-attachments .attachment-row").length,
        text: document.querySelector("#ledger-attachments").innerText.replace(/\\s+/g, " "),
        name: metas[0] && metas[0].name,
        size: metas[0] && metas[0].size,
        blobSize: blob && blob.size,
        enabled: !document.querySelector("#btn-add-attachment").disabled
      };
    })()`);
    ok(
      "附件上传",
      attachmentState.rows === 1 &&
        attachmentState.name === "ui-attachment.txt" &&
        attachmentState.size > 0 &&
        attachmentState.blobSize === attachmentState.size &&
        attachmentState.text.indexOf("ui-attachment.txt") >= 0 &&
        attachmentState.enabled,
      JSON.stringify(attachmentState)
    );
    await shot("ui-attachment.png");
    await cdp.eval(`document.querySelector("#btn-cancel-ledger").click(); true`);

    // ── 文书起草：当前审查 → 催款函 ──
    await cdp.eval(`document.querySelector('.nav-item[data-view="documents"]').click(); true`);
    await waitFor(cdp, `!document.querySelector("#view-documents").classList.contains("hidden")`, 3000);
    const docSetup = await cdp.eval(`({
      types: Array.from(document.querySelectorAll("#doc-type option")).map(function (o) { return o.textContent; }),
      source: document.querySelector("#doc-source").value,
      sender: document.querySelector("#doc-sender").value,
      counterparty: document.querySelector("#doc-counterparty").value,
      amount: document.querySelector("#doc-amount").value,
      due: document.querySelector("#doc-due-date").value,
      demand: document.querySelector("#doc-demand-date").value,
      clauses: document.querySelectorAll("#doc-clause-list input:checked").length
    })`);
    ok(
      "文书入口与预填",
      docSetup.types.length === 6 &&
        docSetup.types.indexOf("催款函") >= 0 &&
        docSetup.types.indexOf("整改函") >= 0 &&
        docSetup.types.indexOf("律师函（草稿）") >= 0 &&
        docSetup.types.indexOf("续签提醒函") >= 0 &&
        docSetup.types.indexOf("变更通知函") >= 0 &&
        docSetup.source === "current" &&
        docSetup.sender === "李四" &&
        docSetup.counterparty === "张三" &&
        docSetup.amount.indexOf("15,000") >= 0 &&
        /-05$/.test(docSetup.due) &&
        docSetup.demand.length === 10 &&
        docSetup.clauses >= 1,
      JSON.stringify(docSetup)
    );

    const lawyerMeta = await cdp.eval(`(() => {
      const s = document.querySelector("#doc-type");
      s.value = "lawyer";
      s.dispatchEvent(new Event("change", { bubbles: true }));
      return {
        due: document.querySelector("#doc-due-label").textContent,
        demand: document.querySelector("#doc-demand-label").textContent,
        facts: document.querySelector("#doc-facts-label").textContent,
        status: document.querySelector("#doc-status").textContent
      };
    })()`);
    ok(
      "律师函草稿入口",
      lawyerMeta.due === "合同到期日（可选）" &&
        lawyerMeta.demand === "要求回应期限" &&
        lawyerMeta.facts.indexOf("委托事项") >= 0,
      JSON.stringify(lawyerMeta)
    );
    await cdp.eval(`(() => {
      const s = document.querySelector("#doc-type");
      s.value = "demand";
      s.dispatchEvent(new Event("change", { bubbles: true }));
      return true;
    })()`);

    await cdp.eval(`document.querySelector("#btn-doc-generate").click(); true`);
    await waitFor(cdp, `document.querySelector("#doc-draft").value.length > 0 && !document.querySelector("#doc-draft").classList.contains("hidden")`, 5000);
    const docDraft = await cdp.eval(`document.querySelector("#doc-draft").value`);
    const docRequest = await cdp.eval(`window.__mockDocUser || ""`);
    const docStatus = await cdp.eval(`document.querySelector("#doc-status").textContent`);
    const docxDocCheck = await cdp.eval(`(async () => {
      const b = WB.buildDocDocx({ text: document.querySelector("#doc-draft").value, meta: "测试合同 · 催款函" });
      return { type: b.type, size: b.size };
    })()`);
    ok(
      "文书草稿生成",
      docDraft.indexOf("催款函") >= 0 &&
        docDraft.indexOf("律师复核") >= 0 &&
        docRequest.indexOf("发函方") >= 0 &&
        docRequest.indexOf("对方主体") >= 0 &&
        docStatus.indexOf("草稿已生成") >= 0,
      `草稿 ${docDraft.length} 字 · ${docStatus}`
    );
    ok(
      "文书导出 .docx",
      docxDocCheck.type.indexOf("openxmlformats") >= 0 && docxDocCheck.size > 1000,
      `${docxDocCheck.size}B`
    );
    await shot("ui-documents.png");

    // ── 合同范本：本地生成 / 表单联动 / 导出 ──
    await cdp.eval(`document.querySelector('.nav-item[data-view="templates"]').click(); true`);
    await waitFor(cdp, `!document.querySelector("#view-templates").classList.contains("hidden")`, 3000);
    const templateSetup = await cdp.eval(`({
      cards: document.querySelectorAll("#template-list .template-card").length,
      available: document.querySelectorAll("#template-list .template-card:not(:disabled)").length,
      active: (document.querySelector("#template-list .template-card.active .template-card-name") || {}).textContent || "",
      fields: document.querySelectorAll("#template-fields [data-template-field]").length,
      text: document.querySelector("#template-text").value,
      meta: document.querySelector("#template-meta").textContent,
      topbarType: getComputedStyle(document.querySelector("#contract-type").closest(".type-select-wrap")).display
    })`);
    ok(
      "范本入口与租赁默认",
      templateSetup.cards === 6 &&
        templateSetup.available === 6 &&
        templateSetup.active === "房屋租赁合同" &&
        templateSetup.fields >= 10 &&
        templateSetup.text.indexOf("房屋租赁合同") >= 0 &&
        templateSetup.text.indexOf("律师复核") >= 0 &&
        templateSetup.topbarType === "none",
      JSON.stringify({ cards: templateSetup.cards, available: templateSetup.available, fields: templateSetup.fields })
    );

    await cdp.eval(`document.querySelector('[data-template="employment"]').click(); true`);
    await sleep(100);
    const laborTemplate = await cdp.eval(`({
      active: (document.querySelector("#template-list .template-card.active .template-card-name") || {}).textContent || "",
      title: document.querySelector("#template-form-title").textContent,
      labels: Array.from(document.querySelectorAll("#template-fields .field-label")).map(function (el) { return el.textContent.trim(); }),
      text: document.querySelector("#template-text").value
    })`);
    ok(
      "范本切换劳动合同",
      laborTemplate.active === "劳动合同" &&
        laborTemplate.title === "劳动合同" &&
        laborTemplate.labels.some(function (x) { return x.indexOf("甲方（用人单位）") >= 0; }) &&
        laborTemplate.labels.some(function (x) { return x.indexOf("乙方（劳动者）") >= 0; }) &&
        laborTemplate.text.indexOf("劳动合同") >= 0 &&
        laborTemplate.text.indexOf("社会保险") >= 0,
      `${laborTemplate.active} · ${laborTemplate.labels.length} 个字段`
    );

    await cdp.eval(`(() => {
      const set = (key, value) => {
        const el = document.querySelector('[data-template-field="' + key + '"]');
        el.value = value;
        el.dispatchEvent(new Event("input", { bubbles: true }));
      };
      set("employer", "上海测试公司");
      set("employee", "李四");
      set("position", "产品运营");
      set("salary", "8000 元");
      return true;
    })()`);
    const laborText = await cdp.eval(`document.querySelector("#template-text").value`);
    const templateStatus = await cdp.eval(`document.querySelector("#template-status").textContent`);
    ok(
      "范本表单联动",
      laborText.indexOf("上海测试公司") >= 0 &&
        laborText.indexOf("李四") >= 0 &&
        laborText.indexOf("产品运营") >= 0 &&
        laborText.indexOf("8000 元") >= 0 &&
        templateStatus.indexOf("随表单更新") >= 0,
      `${laborText.length} 字 · ${templateStatus}`
    );

    const templateDocx = await cdp.eval(`(async () => {
      const b = WB.buildTemplateDocx({
        text: document.querySelector("#template-text").value,
        meta: "合同范本：劳动合同"
      });
      return { type: b.type, size: b.size };
    })()`);
    ok(
      "范本导出 .docx",
      templateDocx.type.indexOf("openxmlformats") >= 0 && templateDocx.size > 1000,
      `${templateDocx.size}B`
    );
    await cdp.eval(`document.querySelector("#toast").classList.add("hidden"); true`);
    await shot("ui-templates.png");

    // ── 合同版本对比：本地条款差异 ──
    await cdp.eval(`document.querySelector('.nav-item[data-view="compare"]').click(); true`);
    await waitFor(cdp, `!document.querySelector("#view-compare").classList.contains("hidden")`, 3000);
    const compareEntry = await cdp.eval(`({
      sources: document.querySelectorAll("#compare-old-source option").length,
      view: !document.querySelector("#view-compare").classList.contains("hidden"),
      topbarType: getComputedStyle(document.querySelector("#contract-type").closest(".type-select-wrap")).display
    })`);
    ok(
      "版本对比入口",
      compareEntry.view && compareEntry.sources >= 3 && compareEntry.topbarType === "none",
      `${compareEntry.sources} 个来源`
    );

    const compareOldText = [
      "房屋租赁合同",
      "",
      "第一条 租金",
      "乙方应于每月5日前支付租金5000元。",
      "",
      "第二条 押金",
      "押金为10000元。",
      "",
      "第三条 转租",
      "未经甲方书面同意不得转租。",
    ].join("\n");
    const compareNewText = [
      "房屋租赁合同",
      "",
      "第一条 租金",
      "乙方应于每月10日前支付租金6000元。",
      "",
      "第二条 押金",
      "押金为10000元。",
      "",
      "第四条 维修",
      "房屋维修由甲方负责。",
    ].join("\n");
    await cdp.eval(`(() => {
      const set = (sel, value) => {
        const el = document.querySelector(sel);
        el.value = value;
        el.dispatchEvent(new Event("input", { bubbles: true }));
      };
      set("#compare-old-text", ${JSON.stringify(compareOldText)});
      set("#compare-new-text", ${JSON.stringify(compareNewText)});
      document.querySelector("#btn-compare-run").click();
      return true;
    })()`);
    await waitFor(cdp, `!document.querySelector("#compare-output").classList.contains("hidden") && document.querySelectorAll("#compare-output .compare-row").length > 0`, 3000);
    const compareCounts = await cdp.eval(`({
      same: document.querySelector("#compare-output .compare-stat.same").innerText,
      modified: document.querySelector("#compare-output .compare-stat.modified").innerText,
      added: document.querySelector("#compare-output .compare-stat.added").innerText,
      removed: document.querySelector("#compare-output .compare-stat.removed").innerText
    })`);
    const compareRows = await cdp.eval(`document.querySelectorAll("#compare-output .compare-row").length`);
    const compareStatus = await cdp.eval(`document.querySelector("#compare-status").textContent`);
    const compareDiff = await cdp.eval(`document.querySelector("#compare-output").innerText`);
    ok(
      "版本对比条款差异",
      compareCounts.modified.indexOf("1") >= 0 &&
        compareCounts.added.indexOf("1") >= 0 &&
        compareCounts.removed.indexOf("1") >= 0 &&
        compareRows === 3 &&
        compareDiff.indexOf("每月5日") >= 0 &&
        compareDiff.indexOf("每月10日") >= 0 &&
        compareStatus.indexOf("已比较") >= 0,
      `${compareRows} 行 · ${JSON.stringify(compareCounts)}`
    );

    await cdp.eval(`(() => { const el = document.querySelector("#compare-only-changed"); el.checked = false; el.dispatchEvent(new Event("change", { bubbles: true })); return true; })()`);
    const allCompareRows = await cdp.eval(`document.querySelectorAll("#compare-output .compare-row").length`);
    const compareDocx = await cdp.eval(`(async () => {
      const r = WB.compareContracts(document.querySelector("#compare-old-text").value, document.querySelector("#compare-new-text").value);
      const b = WB.buildCompareDocx(r, "旧版：租赁合同 · 新版：租赁合同");
      return { type: b.type, size: b.size };
    })()`);
    ok(
      "版本对比展开与导出",
      allCompareRows === 5 &&
        compareDocx.type.indexOf("openxmlformats") >= 0 &&
        compareDocx.size > 1000,
      `${allCompareRows} 行 · ${compareDocx.size}B`
    );
    await cdp.eval(`document.querySelector("#toast").classList.add("hidden"); true`);
    await shot("ui-compare.png");

    // ── OCR：图片走现有上传入口，识别后回填文本框 ──
    const ocrImage = path.join(SHOT_DIR, "ocr-test.png");
    fs.writeFileSync(
      ocrImage,
      Buffer.from(
        "iVBORw0KGgoAAAANSUhEUgAAAEAAAAAgCAIAAAAt/+nTAAAATElEQVR4nNXOQREAIADDsFL/nocIHlyjIGcbZRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncRIncf4OvLoyKwM90wQTbwAAAABJRU5ErkJggg==",
        "base64"
      )
    );
    await cdp.eval(`document.querySelector('.nav-item[data-view="review"]').click(); true`);
    await cdp.eval(`(() => {
      const result = document.querySelector("#review-result");
      if (result && !result.classList.contains("hidden")) document.querySelector("#btn-new").click();
      return true;
    })()`);
    await waitFor(cdp, `!document.querySelector("#review-empty").classList.contains("hidden")`, 3000);
    const domDoc = await cdp.send("DOM.getDocument", { depth: -1 });
    const fileNode = await cdp.send("DOM.querySelector", { nodeId: domDoc.result.root.nodeId, selector: "#file-input" });
    await cdp.send("DOM.setFileInputFiles", { nodeId: fileNode.result.nodeId, files: [ocrImage] });
    await cdp.eval(`document.querySelector("#file-input").dispatchEvent(new Event("change", { bubbles: true })); true`);
    await waitFor(
      cdp,
      `!document.querySelector("#btn-ocr").classList.contains("hidden") && document.querySelector("#file-status").textContent.indexOf("OCR") >= 0`,
      5000
    );
    await cdp.eval(`document.querySelector("#btn-ocr").click(); true`);
    await waitFor(
      cdp,
      `document.querySelector("#contract-input").value.indexOf("第一条 租金") >= 0 && document.querySelector("#btn-ocr").classList.contains("hidden")`,
      5000
    );
    const ocrState = await cdp.eval(`({
      calls: window.__mockOcrCalls || 0,
      chars: document.querySelector("#contract-input").value.length,
      status: document.querySelector("#file-status").textContent
    })`);
    ok(
      "OCR 图片识别",
      ocrState.calls >= 1 && ocrState.chars > 20 && ocrState.status.indexOf("已识别") >= 0,
      `${ocrState.calls} 次调用 · ${ocrState.chars} 字`
    );
    await shot("ui-ocr.png");
    await cdp.eval(`document.querySelector("#btn-clear").click(); true`);

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
    ok(
      "台账 ICS 内容",
      ics.indexOf("BEGIN:VEVENT") >= 0 &&
        ics.indexOf("合同到期") >= 0 &&
        ics.indexOf("续签提醒") >= 0 &&
        ics.indexOf("付款节点") >= 0 &&
        ics.indexOf("VALARM") >= 0,
      `${ics.length} 字符 · ${(ics.match(/BEGIN:VEVENT/g) || []).length} 个事件`
    );
    const csv = await cdp.eval(`(async () => WB.Ledger.buildCSV(await WB.listLedger()))()`);
    ok(
      "台账 CSV 内容",
      csv.indexOf("合同名称") >= 0 &&
        csv.indexOf("续签日期") >= 0 &&
        csv.indexOf("付款节点") >= 0 &&
        csv.indexOf("修改后对方") >= 0 &&
        csv.indexOf("第二期") >= 0,
      `${csv.length} 字符`
    );
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
    const savedStance = await cdp.eval(`(async () => (await WB.loadSettings()).stance)()`);
    ok("刷新恢复审查结果", !!restored);
    ok("API Key 持久化", savedKey === "test-key", savedKey ? "已读取" : "未找到");
    ok("审查视角持久化", savedStance === "tenant", savedStance);

    await cdp.eval(`document.querySelector("#risk-list .risk-item.high").click(); true`);
    const restoredBeam = (await waitFor(cdp, `document.querySelectorAll(".hl-beam-rect").length`, 3000).catch(() => 0)) || 0;
    ok("刷新恢复后光束仍可用", restoredBeam >= 1, `${restoredBeam} 段`);

    await cdp.eval(`document.querySelector('.nav-item[data-view="ledger"]').click(); true`);
    await sleep(200);
    const ledgerAfterReload = (await waitFor(cdp, `document.querySelectorAll("#ledger-list .ledger-row").length`, 3000).catch(() => 0)) || 0;
    const ledgerTextAfterReload = await cdp.eval(`document.querySelector("#ledger-list").innerText`);
    ok("台账刷新后仍在", ledgerAfterReload === 1 && ledgerTextAfterReload.indexOf("修改后对方") >= 0, `${ledgerAfterReload} 条`);
    const attachmentsAfterReload = await cdp.eval(`(async () => (await WB.Attachments.list(${JSON.stringify(attachmentEntryId)})).length)()`);
    ok("附件刷新后仍在", attachmentsAfterReload === 1, `${attachmentsAfterReload} 个`);

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
    const attachmentsAfterDelete = await waitFor(
      cdp,
      `(async () => (await WB.Attachments.list(${JSON.stringify(attachmentEntryId)})).length === 0)()`,
      3000
    ).catch(() => false);
    ok("删合同清理附件", attachmentsAfterDelete === true, `清理 ${attachmentsAfterDelete}`);

    await cdp.eval(`document.querySelector("#ledger-list [data-ledger-add]").click(); true`);
    await waitFor(cdp, `!document.querySelector("#ledger-drawer").classList.contains("hidden")`, 3000);
    const manualDraft = await cdp.eval(`({
      title: document.querySelector("#ledger-title").value,
      type: document.querySelector("#ledger-type").value,
      status: document.querySelector("#ledger-status").value
    })`);
    await cdp.eval(`document.querySelector("#btn-cancel-ledger").click(); true`);
    ok("台账手动新增入口", manualDraft.title === "" && manualDraft.type === "房屋租赁合同" && manualDraft.status === "履行中", JSON.stringify(manualDraft));

    // ── 审查规则：渲染 / 停用 / 编辑 / 持久化 / 恢复 / 自定义 ──
    await cdp.eval(`document.querySelector('.nav-item[data-view="rules"]').click(); true`);
    await sleep(250);
    const ruleRows = await cdp.eval(`document.querySelectorAll("#rule-list .rule-row").length`);
    const ruleSummary = await cdp.eval(`document.querySelector("#rule-summary").textContent`);
    ok("审查规则渲染", ruleRows === 111 && ruleSummary.indexOf("内置 111") >= 0, `${ruleRows} 条 · ${ruleSummary}`);
    const ruleMeta = await cdp.eval(
      `(document.querySelector("#rules-law-meta summary") || {}).textContent || ""`
    );
    ok(
      "规则法条核对信息",
      ruleMeta.indexOf("2026-11-24") >= 0 && ruleMeta.indexOf("20 部") >= 0,
      ruleMeta
    );
    await shot("ui-rules.png");

    await cdp.eval(`document.querySelector('#rule-filters [data-rule-type="买卖合同"]').click(); true`);
    const typeRuleRows = await cdp.eval(`document.querySelectorAll("#rule-list .rule-row").length`);
    await cdp.eval(`document.querySelector('#rule-filters [data-rule-type="全部"]').click(); true`);
    ok("规则类型筛选", typeRuleRows === 15, `买卖合同 ${typeRuleRows} 条`);

    await cdp.eval(`document.querySelector('[data-rule-row="r_lease_penalty"] [data-toggle-rule]').click(); true`);
    const ruleOff = await waitFor(
      cdp,
      `WB.RuleStore.find("r_lease_penalty").enabled === false && WB.RuleStore.revision() > 0`,
      3000
    ).catch(() => false);
    const offRow = await cdp.eval(`document.querySelector('[data-rule-row="r_lease_penalty"]').classList.contains("is-off")`);
    ok("规则停用", !!ruleOff && offRow);

    await cdp.eval(`(() => { const s = document.querySelector("#rule-status-filter"); s.value = "已停用"; s.dispatchEvent(new Event("change", { bubbles: true })); return true; })()`);
    const offFiltered = await cdp.eval(`document.querySelectorAll("#rule-list .rule-row").length`);
    await cdp.eval(`(() => { const s = document.querySelector("#rule-status-filter"); s.value = "全部状态"; s.dispatchEvent(new Event("change", { bubbles: true })); return true; })()`);
    ok("规则状态筛选", offFiltered === 1, `已停用 ${offFiltered} 条`);

    await cdp.eval(`document.querySelector('[data-rule-row="r_lease_penalty"] [data-edit-rule]').click(); true`);
    await waitFor(cdp, `!document.querySelector("#rule-drawer").classList.contains("hidden")`, 3000);
    const ruleDraft = await cdp.eval(`({
      title: document.querySelector("#rule-form-title").textContent,
      name: document.querySelector("#rule-name").value,
      keywords: document.querySelector("#rule-keywords").value
    })`);
    await cdp.eval(`(() => {
      document.querySelector("#rule-advice").value = "测试修改后的建议话术";
      document.querySelector("#rule-form").requestSubmit();
      return true;
    })()`);
    const editedRule = await waitFor(
      cdp,
      `WB.RuleStore.find("r_lease_penalty").advice === "测试修改后的建议话术" &&
        document.querySelector("#toast").textContent.indexOf("规则已更新") >= 0`,
      3000
    ).catch(() => false);
    ok(
      "规则编辑",
      ruleDraft.title === "编辑规则" && ruleDraft.name === "违约金过高" &&
        ruleDraft.keywords.indexOf("违约金") >= 0 && !!editedRule,
      JSON.stringify(ruleDraft)
    );

    await cdp.eval(`document.querySelector('.nav-item[data-view="clauses"]').click(); true`);
    const clauseOff = await cdp.eval(`document.querySelectorAll("#clause-list .clause-card.is-off").length`);
    const clauseText = await cdp.eval(`document.querySelector("#clause-list").innerText`);
    ok(
      "条款库同步规则",
      clauseOff === 1 && clauseText.indexOf("测试修改后的建议话术") >= 0 && clauseText.indexOf("已停用") >= 0,
      `停用卡 ${clauseOff} 张`
    );

    await reloadPage(cdp);
    await cdp.eval(`document.querySelector('.nav-item[data-view="rules"]').click(); true`);
    await sleep(200);
    const persistedRule = await cdp.eval(`({
      enabled: WB.RuleStore.find("r_lease_penalty").enabled,
      advice: WB.RuleStore.find("r_lease_penalty").advice
    })`);
    ok("规则刷新后仍在", persistedRule.enabled === false && persistedRule.advice === "测试修改后的建议话术", JSON.stringify(persistedRule));

    const resetClick = cdp.eval(`document.querySelector("#btn-rule-reset").click(); true`);
    await sleep(300);
    await cdp.send("Page.handleJavaScriptDialog", { accept: true });
    await resetClick;
    const resetDone = await waitFor(
      cdp,
      `WB.RuleStore.find("r_lease_penalty").enabled === true &&
        WB.RuleStore.find("r_lease_penalty").advice.indexOf("违约金上限") >= 0 &&
        document.querySelector("#toast").textContent.indexOf("已恢复默认") >= 0`,
      3000
    ).catch(() => false);
    ok("恢复内置默认", !!resetDone);

    const rollback = await cdp.eval(`(async () => {
      const original = WB.saveRuleState;
      WB.saveRuleState = async () => ({ ok: false });
      const beforeEnabled = WB.RuleStore.find("r_lease_penalty").enabled;
      try {
        document.querySelector('[data-rule-row="r_lease_penalty"] [data-toggle-rule]').click();
        await new Promise(function (r) { setTimeout(r, 250); });
      } finally {
        WB.saveRuleState = original;
      }
      return {
        beforeEnabled: beforeEnabled,
        afterEnabled: WB.RuleStore.find("r_lease_penalty").enabled,
        checked: document.querySelector('[data-rule-row="r_lease_penalty"] [data-toggle-rule]').checked,
        toast: document.querySelector("#toast").textContent
      };
    })()`);
    ok(
      "规则写入失败回滚",
      rollback.beforeEnabled === true && rollback.afterEnabled === true && rollback.checked &&
        rollback.toast.indexOf("存储不可用") >= 0,
      JSON.stringify(rollback)
    );

    await cdp.eval(`document.querySelector("#btn-rule-add").click(); true`);
    await waitFor(cdp, `!document.querySelector("#rule-drawer").classList.contains("hidden")`, 3000);
    await cdp.eval(`(() => {
      const set = (sel, value) => { document.querySelector(sel).value = value; };
      set("#rule-name", ${JSON.stringify(XSS_RULE_NAME)});
      set("#rule-type", "买卖合同");
      set("#rule-level", "中");
      set("#rule-keywords", "测试关键词、验收");
      set("#rule-condition", "出现测试关键词时提示");
      set("#rule-basis", "民法典第509条");
      set("#rule-advice", "建议补充明确约定");
      document.querySelector("#rule-form").requestSubmit();
      return true;
    })()`);
    const customReady = await waitFor(
      cdp,
      `WB.RULES.filter(function (r) { return !r.builtin; }).length > 0 &&
        document.querySelector("#toast").textContent.indexOf("规则已新增") >= 0`,
      3000
    ).catch(() => false);
    const customRule = await cdp.eval(`WB.RULES.filter(function (r) { return !r.builtin; })[0] || null`);
    ok(
      "新增自定义规则",
      !!customReady && !!customRule && customRule.name === XSS_RULE_NAME && customRule.keywords.length === 2,
      JSON.stringify(customRule)
    );
    const xssRender = await cdp.eval(`(() => {
      const row = document.querySelector('[data-rule-row="' + WB.RULES.filter(function (r) { return !r.builtin; })[0].id + '"]');
      return {
        html: row.querySelector("h3").innerHTML,
        bold: row.querySelectorAll("h3 b").length,
        flagged: window.__ruleXss === true
      };
    })()`);
    ok(
      "规则字段转义",
      xssRender.html.indexOf("&lt;b&gt;") >= 0 && xssRender.bold === 0 && !xssRender.flagged,
      xssRender.html
    );
    await shot("ui-rules-custom.png");

    const customRuleId = customRule.id;
    await cdp.eval(`document.querySelector('[data-rule-row="${customRuleId}"] [data-edit-rule]').click(); true`);
    await waitFor(cdp, `!document.querySelector("#rule-drawer").classList.contains("hidden")`, 3000);
    await cdp.eval(`(() => {
      document.querySelector("#rule-advice").value = "自定义规则修改后的建议";
      document.querySelector("#rule-form").requestSubmit();
      return true;
    })()`);
    const customEdited = await waitFor(
      cdp,
      `WB.RuleStore.find(${JSON.stringify(customRuleId)}).advice === "自定义规则修改后的建议" &&
        document.querySelector("#toast").textContent.indexOf("规则已更新") >= 0`,
      3000
    ).catch(() => false);
    ok("编辑自定义规则", !!customEdited);

    await cdp.eval(`(() => { const s = document.querySelector("#rule-search"); s.value = "测试自定义"; s.dispatchEvent(new Event("input", { bubbles: true })); return true; })()`);
    const searchRows = await cdp.eval(`document.querySelectorAll("#rule-list .rule-row").length`);
    await cdp.eval(`(() => { const s = document.querySelector("#rule-search"); s.value = ""; s.dispatchEvent(new Event("input", { bubbles: true })); return true; })()`);
    ok("规则搜索", searchRows === 1, `${searchRows} 行`);

    const builtinDelete = await cdp.eval(`document.querySelectorAll('[data-rule-row="r_lease_penalty"] [data-delete-rule]').length`);
    ok("内置规则不可删", builtinDelete === 0);

    await reloadPage(cdp);
    await cdp.eval(`document.querySelector('.nav-item[data-view="rules"]').click(); true`);
    await sleep(200);
    const customPersisted = await cdp.eval(`WB.RULES.filter(function (r) { return !r.builtin; }).length`);
    ok("自定义规则刷新后仍在", customPersisted === 1, `${customPersisted} 条`);

    const customId = await cdp.eval(`WB.RULES.filter(function (r) { return !r.builtin; })[0].id`);
    const deleteRuleClick = cdp.eval(`document.querySelector('[data-rule-row="' + ${JSON.stringify(customId)} + '"] [data-delete-rule]').click(); true`);
    await sleep(300);
    await cdp.send("Page.handleJavaScriptDialog", { accept: true });
    await deleteRuleClick;
    const customDeleted = await waitFor(
      cdp,
      `WB.RULES.filter(function (r) { return !r.builtin; }).length === 0 &&
        document.querySelector("#toast").textContent.indexOf("规则已删除") >= 0`,
      3000
    ).catch(() => false);
    ok("删除自定义规则", !!customDeleted);

    // 模拟另一标签页写入：广播 -> 本页 refresh -> 规则与列表同步
    const remoteSync = await cdp.eval(`(async () => {
      const before = WB.RuleStore.find("r_loan_rate").enabled;
      const rev = WB.RuleStore.revision();
      const remote = {
        overrides: {
          r_loan_rate: {
            contractType: "借款合同", name: "年利率超过 LPR 四倍",
            keywords: ["年利率", "利率", "利息"],
            condition: "年利率超过合同成立时一年期 LPR 的四倍",
            level: "高", basis: "民间借贷司法解释第25条",
            advice: "测试远端建议", enabled: false
          }
        },
        custom: [],
        updatedAt: (rev || Date.now()) + 1000
      };
      const saved = await WB.saveRuleState(remote, rev);
      const stale = await WB.saveRuleState(
        { overrides: {}, custom: [], updatedAt: remote.updatedAt + 1000 },
        rev
      );
      const ch = new BroadcastChannel("contract-workbench-rules");
      ch.postMessage({ type: "rules-updated", tabId: "other-tab" });
      ch.close();
      await new Promise(function (r) { setTimeout(r, 400); });
      return {
        saved: saved,
        stale: stale,
        before: before,
        after: WB.RuleStore.find("r_loan_rate").enabled,
        advice: WB.RuleStore.find("r_loan_rate").advice
      };
    })()`);
    ok(
      "跨标签页规则同步",
      remoteSync.saved && remoteSync.saved.ok && remoteSync.stale &&
        remoteSync.stale.ok === false && remoteSync.stale.conflict === true &&
        remoteSync.before === true && remoteSync.after === false &&
        remoteSync.advice === "测试远端建议",
      JSON.stringify(remoteSync)
    );
    await cdp.eval(`(async () => { await WB.RuleStore.resetBuiltin(); return true; })()`);

    // ── 法条速查 ──
    await cdp.eval(`document.querySelector('.nav-item[data-view="law"]').click(); true`);
    await sleep(150);
    const lawInitial = await cdp.eval(`({
      chips: document.querySelectorAll("#law-filters .filter-chip").length,
      cards: document.querySelectorAll("#law-list .law-card").length,
      title: document.querySelector("#view-law .view-title").textContent
    })`);
    ok(
      "法条速查渲染",
      lawInitial.chips === 6 && lawInitial.cards >= 40 && lawInitial.title === "法条速查",
      `${lawInitial.chips} 个分类 · ${lawInitial.cards} 条`
    );
    await cdp.eval(`(() => { const s = document.querySelector("#law-search"); s.value = "押金"; s.dispatchEvent(new Event("input", { bubbles: true })); return true; })()`);
    const lawSearch = await cdp.eval(`({
      cards: document.querySelectorAll("#law-list .law-card").length,
      open: document.querySelectorAll("#law-list .law-card[open]").length,
      marks: document.querySelectorAll("#law-list .law-card[open] mark").length,
      text: (document.querySelector("#law-list .law-card[open] .law-body") || { innerText: "" }).innerText
    })`);
    ok("法条速查搜索", lawSearch.cards > 0 && lawSearch.open === 1 && lawSearch.marks > 0 && lawSearch.text.indexOf("押金") >= 0, `${lawSearch.cards} 条 · ${lawSearch.marks} 处高亮`);
    await cdp.eval(`document.querySelector('#law-filters [data-law-cat="判例"]').click(); true`);
    const lawCases = await cdp.eval(`({
      cards: document.querySelectorAll("#law-list .law-card").length,
      cats: Array.from(document.querySelectorAll("#law-list .law-cat")).map(function (el) { return el.textContent; })
    })`);
    ok("法条分类过滤", lawCases.cards > 0 && lawCases.cats.every(function (c) { return c === "判例"; }), `${lawCases.cards} 条`);
    await cdp.eval(`(() => { const s = document.querySelector("#law-search"); s.value = "火星基地不存在"; s.dispatchEvent(new Event("input", { bubbles: true })); return true; })()`);
    const lawMiss = await cdp.eval(`({ cards: document.querySelectorAll("#law-list .law-card").length, text: document.querySelector("#law-list").innerText })`);
    ok("法条空态", lawMiss.cards === 0 && lawMiss.text.indexOf("没有匹配") >= 0);
    await cdp.eval(`(() => { const s = document.querySelector("#law-search"); s.value = ""; s.dispatchEvent(new Event("input", { bubbles: true })); })()`);
    await cdp.eval(`document.querySelector('#law-filters [data-law-cat="全部"]').click(); true`);

    // ── 范本送去审查 ──
    await cdp.eval(`document.querySelector('.nav-item[data-view="templates"]').click(); true`);
    await sleep(150);
    await cdp.eval(`document.querySelector("#btn-template-review").click(); true`);
    const templateSend = await cdp.eval(`({
      view: !document.querySelector("#view-review").classList.contains("hidden"),
      text: document.querySelector("#contract-input").value,
      type: document.querySelector("#contract-type").value,
      chars: document.querySelector("#char-count").textContent
    })`);
    ok(
      "范本送去审查",
      templateSend.view &&
        templateSend.text.indexOf("房屋租赁合同") >= 0 &&
        templateSend.type === "房屋租赁合同" &&
        templateSend.chars.indexOf("字") >= 0,
      `${templateSend.type} · ${templateSend.chars}`
    );

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
