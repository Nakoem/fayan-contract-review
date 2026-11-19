#!/usr/bin/env node
/* UI 冒烟测试：在真 Chrome 里打开 dist/index.html（file://），
 * 用 mock LLM 走完整流程，验证界面、渲染、跳转、打印与持久化。
 *
 * 用法：node workbench/scripts/ui_smoke.mjs
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { launchBrowser, waitFor, screenshot } from "./lib.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const WB_DIR = path.resolve(__dirname, "..");
const INDEX = path.join(WB_DIR, "dist", "index.html");
const SHOT_DIR = path.join(WB_DIR, "screenshots");

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

    await waitFor(cdp, `document.readyState === "complete" && document.querySelectorAll(".sample-chip").length === 6`);

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
        model: "qwen-plus",
        apiKeys: { deepseek: "", dashscope: "test-key", zhipu: "" },
        masking: true, hiddenNames: [], contractType: "房屋租赁合同"
      });
      return true;
    })()`);
    await cdp.send("Page.reload", { ignoreCache: true });
    await waitFor(cdp, `document.readyState === "complete" && document.querySelectorAll(".sample-chip").length === 6`);

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

    await waitFor(cdp, `!document.querySelector("#review-result").classList.contains("hidden")`, 20000);

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

    await cdp.eval(`document.querySelector("#risk-list .risk-item").click(); true`);
    const flash = await cdp.eval(`document.querySelectorAll("mark.hl-flash").length`);
    ok("风险条目跳转", flash >= 1, flash ? "已定位并闪烁" : "未定位");

    await cdp.eval(`document.querySelector('.panel-tab[data-tab="report"]').click(); true`);
    const reportVisible = await cdp.eval(`!document.querySelector("#report-view").classList.contains("hidden")`);
    ok("完整报告标签页", reportVisible);
    await shot("ui-result-report.png");

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

    await cdp.send("Page.reload", { ignoreCache: true });
    await waitFor(cdp, `document.readyState === "complete" && document.querySelectorAll(".sample-chip").length === 6`);
    const restored = await waitFor(cdp, `!document.querySelector("#review-result").classList.contains("hidden")`, 8000).catch(() => false);
    const savedKey = await cdp.eval(`(async () => { const s = await WB.loadSettings(); return s.apiKeys.dashscope; })()`);
    ok("刷新恢复审查结果", !!restored);
    ok("API Key 持久化", savedKey === "test-key", savedKey ? "已读取" : "未找到");

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
