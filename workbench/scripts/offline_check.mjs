#!/usr/bin/env node
/* 断网验收：离线状态下仍能打开单文件页面、查看本地条款库。
 *
 * 用法：node workbench/scripts/offline_check.mjs
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { launchBrowser, waitFor, reloadPage } from "./lib.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const INDEX = path.join(path.resolve(__dirname, ".."), "dist", "index.html");

async function main() {
  if (!fs.existsSync(INDEX)) throw new Error("dist/index.html 不存在，请先运行 python workbench/build.py");
  const browser = await launchBrowser({ url: pathToFileURL(INDEX).href, prefix: "wb-offline" });
  try {
    await waitFor(browser.cdp, `document.readyState === "complete" && window.__WB_READY__ === true && document.querySelectorAll(".sample-chip").length === 6`);
    await browser.cdp.send("Network.enable");
    await browser.cdp.send("Network.emulateNetworkConditions", {
      offline: true, latency: 0, downloadThroughput: 0, uploadThroughput: 0,
    });
    await reloadPage(browser.cdp);
    await browser.cdp.eval(`document.querySelector('.nav-item[data-view="clauses"]').click(); true`);
    const cards = await browser.cdp.eval(`document.querySelectorAll(".clause-card").length`);
    console.log(`${cards > 0 ? "✓" : "✗"} 断网可打开并查看条款库 · ${cards} 张卡片`);
    if (cards <= 0) process.exitCode = 1;
  } finally {
    await browser.close();
  }
}

main().catch((e) => { console.error("✗ " + e.message); process.exitCode = 1; });
