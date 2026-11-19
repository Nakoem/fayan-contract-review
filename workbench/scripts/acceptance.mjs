#!/usr/bin/env node
/* PRD 验收脚本（真调 LLM）
 *
 * 用法：
 *   node workbench/scripts/acceptance.mjs
 *   node workbench/scripts/acceptance.mjs --provider=deepseek --sample=lease
 *   node workbench/scripts/acceptance.mjs --file=workbench/tests/fixtures/lease_sample.pdf
 *
 * Key 从仓库根目录 .env 读取：
 *   DASHSCOPE_API_KEY / DEEPSEEK_API_KEY
 *
 * 验收项（对应 PRD §7）：
 *   1. 3000 字内租赁合同 ≤90 秒出报告（用 sample_lease，实测）
 *   2. 风险 ≥5 条且每条带法条
 *   4. 关浏览器重开 API Key 还在
 *   5. 产物 <4MB（由 test_build.py 覆盖）
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { launchBrowser, waitFor, screenshot, loadEnv, sleep, reloadPage } from "./lib.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const WB_DIR = path.resolve(__dirname, "..");
const REPO = path.resolve(WB_DIR, "..");
const INDEX = path.join(WB_DIR, "dist", "index.html");
const SHOT_DIR = path.join(WB_DIR, "screenshots");

const PROVIDERS = {
  deepseek: {
    baseUrl: "https://api.deepseek.com", model: "deepseek-flash", env: "DEEPSEEK_API_KEY",
  },
  dashscope: {
    baseUrl: "https://dashscope.aliyuncs.com/compatible-mode/v1", model: "qwen3.8-max-0902", env: "DASHSCOPE_API_KEY",
  },
};

const args = process.argv.slice(2);
function arg(name, fallback) {
  const hit = args.find((a) => a.startsWith(`--${name}=`));
  return hit ? hit.split("=").slice(1).join("=") : fallback;
}

async function main() {
  if (!fs.existsSync(INDEX)) throw new Error("dist/index.html 不存在，请先 python workbench/build.py");
  fs.mkdirSync(SHOT_DIR, { recursive: true });

  const providerKey = arg("provider", "dashscope");
  const provider = PROVIDERS[providerKey];
  if (!provider) throw new Error("未知服务商：" + providerKey);

  const env = loadEnv(REPO);
  const apiKey = process.env[provider.env] || env[provider.env] || "";
  if (!apiKey) {
    console.error(`缺少 ${provider.env}（可写在仓库根目录 .env）`);
    process.exitCode = 2;
    return;
  }

  const sampleKey = arg("sample", "lease");
  const fileArg = arg("file", "");
  let browser = null;
  try {
    browser = await launchBrowser({
      url: pathToFileURL(INDEX).href,
      prefix: "wb-accept",
    });
    const cdp = browser.cdp;

    await waitFor(cdp, `document.readyState === "complete" && window.__WB_READY__ === true && document.querySelectorAll(".sample-chip").length === 6`);

    console.log(`服务商：${providerKey} · 模型：${provider.model}`);
    console.log("写入测试配置……");
    await cdp.eval(`(async () => {
      await WB.saveSettings({
        provider: ${JSON.stringify(providerKey)},
        baseUrl: ${JSON.stringify(provider.baseUrl)},
        model: ${JSON.stringify(provider.model)},
        apiKeys: { deepseek: "", dashscope: "", ${JSON.stringify(providerKey)}: ${JSON.stringify(apiKey)} },
        masking: true, hiddenNames: [], contractType: "房屋租赁合同"
      });
      return true;
    })()`);
    await reloadPage(cdp);

    let parseSeconds = 0;
    if (fileArg) {
      const filePath = path.resolve(REPO, fileArg);
      if (!fs.existsSync(filePath)) throw new Error("找不到合同文件：" + fileArg);
      console.log("上传文件：" + fileArg);
      const parseStarted = Date.now();
      await sleep(500);
      await cdp.send("DOM.enable");
      const doc = await cdp.send("DOM.getDocument");
      const node = await cdp.send("DOM.querySelector", { nodeId: doc.result.root.nodeId, selector: "#file-input" });
      if (!node.result || !node.result.nodeId) throw new Error("找不到文件输入框");
      await cdp.send("DOM.setFileInputFiles", { nodeId: node.result.nodeId, files: [filePath] });
      await cdp.eval(`document.getElementById("file-input").dispatchEvent(new Event("change", { bubbles: true })); true`);
      const ready = await waitFor(
        cdp,
        `document.querySelector("#file-status").textContent.indexOf("已从") >= 0 && document.querySelector("#contract-input").value.length > 50`,
        120000
      ).catch(() => false);
      if (!ready) {
        const detail = await cdp.eval(`document.querySelector("#file-status").textContent`);
        throw new Error("文件解析失败：" + detail);
      }
      parseSeconds = (Date.now() - parseStarted) / 1000;
      console.log(`文件解析：${parseSeconds.toFixed(1)}s · ${await cdp.eval(`document.querySelector("#file-status").textContent`)}`);
    }

    const started = Date.now();
    if (fileArg) {
      await cdp.eval(`document.querySelector("#btn-start").click(); true`);
    } else {
      await cdp.eval(`(() => {
        const s = WB.SAMPLES.find(function (x) { return x.key === ${JSON.stringify(sampleKey)}; });
        if (!s) return false;
        const ta = document.querySelector("#contract-input");
        ta.value = s.text;
        ta.dispatchEvent(new Event("input", { bubbles: true }));
        document.querySelector("#btn-start").click();
        return true;
      })()`);
    }

    const state = await waitFor(cdp, `(() => {
      const r = !document.querySelector("#review-result").classList.contains("hidden");
      const e = !document.querySelector("#review-error").classList.contains("hidden");
      return r ? "done" : e ? "error" : "";
    })()`, 240000, 400);
    const elapsed = (Date.now() - started) / 1000;

    if (state === "error") {
      const detail = await cdp.eval(`document.querySelector("#error-detail").textContent`);
      throw new Error(`审查失败（${elapsed.toFixed(1)}s）：${detail}`);
    }
    if (state !== "done") throw new Error("等待审查结果超时");

    const saved = await cdp.eval(`WB.loadCurrent()`);
    const result = saved && saved.result ? saved.result : null;
    if (!result) throw new Error("没有拿到审查结果");

    const findings = result.findings || [];
    const withBasis = findings.filter((f) => /第[一二三四五六七八九十百千零〇\d]+条/.test(f.basis || ""));
    const withRefs = findings.filter((f) => f.refs && f.refs.length);
    const sections = await cdp.eval(`document.querySelectorAll("#report-view .report-section").length`);
    const stats = await cdp.eval(`document.querySelector("#result-stats").innerText.replace(/\\s+/g, " ")`);

    console.log("");
    console.log(`耗时：${elapsed.toFixed(1)}s`);
    console.log(`结果：${stats}`);
    console.log(`风险：${findings.length} 条，其中带法条 ${withBasis.length} 条 · 法条参考 ${withRefs.length} 条 · 报告 ${sections} 段`);

    const shotPath = await screenshot(cdp, path.join(SHOT_DIR, "acceptance-result.png"));
    console.log(`截图：${shotPath}`);
    await cdp.eval(`document.querySelector('.panel-tab[data-tab="report"]').click(); true`);
    const reportShot = await screenshot(cdp, path.join(SHOT_DIR, "acceptance-report.png"));
    console.log(`报告截图：${reportShot}`);

    // 持久化
    await reloadPage(cdp);
    const restored = await waitFor(cdp, `!document.querySelector("#review-result").classList.contains("hidden")`, 10000).catch(() => false);
    const savedKey = await cdp.eval(`(async () => { const st = await WB.loadSettings(); return st.apiKeys[${JSON.stringify(providerKey)}]; })()`);

    const checks = [
      ["90 秒内出报告", elapsed <= 90, `${elapsed.toFixed(1)}s`],
      ["风险 ≥5 条", findings.length >= 5, `${findings.length} 条`],
      ["每条风险带法条", withBasis.length === findings.length, `${withBasis.length}/${findings.length}`],
      ["法条参考已挂载", withRefs.length > 0, `${withRefs.length}/${findings.length}`],
      ["报告六段", sections === 6, `${sections} 段`],
      ["刷新恢复结果", !!restored, ""],
      ["API Key 持久化", savedKey === apiKey, ""],
      ["无控制台异常", cdp.exceptions.length === 0, cdp.exceptions.slice(0, 2).join(" | ")],
    ];

    let failed = 0;
    checks.forEach(([name, pass, detail]) => {
      if (!pass) failed += 1;
      console.log(`${pass ? "✓" : "✗"} ${name}${detail ? " · " + detail : ""}`);
    });
    console.log("");
    console.log(failed ? `✗ ${failed} 项未通过` : "✓ 验收全部通过");
    if (failed) process.exitCode = 1;
  } catch (err) {
    console.error("✗ " + err.message);
    process.exitCode = 1;
  } finally {
    if (browser) await browser.close();
  }
}

main().catch((e) => { console.error(e); process.exitCode = 1; });
