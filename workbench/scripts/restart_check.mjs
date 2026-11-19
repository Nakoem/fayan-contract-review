#!/usr/bin/env node
/* 关掉浏览器再打开：验证 IndexedDB 里的设置与 Key 仍在。
 *
 * 用法：node workbench/scripts/restart_check.mjs
 */
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { launchBrowser, waitFor } from "./lib.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const INDEX = path.join(path.resolve(__dirname, ".."), "dist", "index.html");
const PROFILE = fs.mkdtempSync(path.join(os.tmpdir(), "wb-restart-"));
const URL = pathToFileURL(INDEX).href;
const KEY = "restart-check-key";

async function open() {
  const browser = await launchBrowser({ url: URL, prefix: "wb-restart", profileDir: PROFILE });
  await waitFor(browser.cdp, `document.readyState === "complete" && window.__WB_READY__ === true`);
  return browser;
}

async function main() {
  if (!fs.existsSync(INDEX)) throw new Error("dist/index.html 不存在，请先运行 python workbench/build.py");

  let browser = null;
  try {
    browser = await open();
    const written = await browser.cdp.eval(`(async () => {
      await WB.saveSettings({
        provider: "dashscope",
        baseUrl: "https://dashscope.aliyuncs.com/compatible-mode/v1",
        model: "qwen3.8-max-0902",
        apiKeys: { deepseek: "", dashscope: ${JSON.stringify(KEY)} },
        masking: true, hiddenNames: ["张三"], contractType: "房屋租赁合同"
      });
      const s = await WB.loadSettings();
      return s.apiKeys.dashscope;
    })()`);
    if (written !== KEY) throw new Error("写入后立即读回失败，IndexedDB 未提交");
    await browser.closeGracefully();
    browser = null;
    await new Promise((r) => setTimeout(r, 800));

    browser = await open();
    const saved = await browser.cdp.eval(`(async () => {
      const s = await WB.loadSettings();
      return { key: s.apiKeys.dashscope, provider: s.provider, hidden: s.hiddenNames };
    })()`);
    const ok = saved.key === KEY && saved.provider === "dashscope" && (saved.hidden || []).indexOf("张三") >= 0;
    console.log(`${ok ? "✓" : "✗"} 关浏览器重开设置仍在 · ${JSON.stringify(saved)}`);
    if (!ok) process.exitCode = 1;
  } finally {
    if (browser) await browser.close();
    try { fs.rmSync(PROFILE, { recursive: true, force: true }); } catch (e) { /* ignore */ }
  }
}

main().catch((e) => { console.error("✗ " + e.message); process.exitCode = 1; });
