#!/usr/bin/env node
/* 文件解析验收：在真实 dist/index.html + Chrome 里上传 PDF / DOCX / .doc。
 *
 * 用法：node workbench/scripts/parser_check.mjs
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { launchBrowser, waitFor, sleep } from "./lib.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const WB_DIR = path.resolve(__dirname, "..");
const INDEX = path.join(WB_DIR, "dist", "index.html");
const FIX = path.join(WB_DIR, "tests", "fixtures");
const PDF = path.join(FIX, "parse_sample.pdf");
const LEASE_PDF = path.join(FIX, "lease_sample.pdf");
const DOCX = path.join(FIX, "parse_sample.docx");
const DOC = path.join(FIX, "parse_sample.doc");

const results = [];
function ok(name, passed, detail) {
  results.push({ name, passed });
  console.log(`${passed ? "✓" : "✗"} ${name}${detail ? " · " + detail : ""}`);
}

async function setFile(cdp, filePath) {
  await sleep(200);
  await cdp.send("DOM.enable");
  const doc = await cdp.send("DOM.getDocument");
  const node = await cdp.send("DOM.querySelector", { nodeId: doc.result.root.nodeId, selector: "#file-input" });
  if (!node.result || !node.result.nodeId) throw new Error("找不到 #file-input");
  await cdp.send("DOM.setFileInputFiles", { nodeId: node.result.nodeId, files: [filePath] });
  await cdp.eval(`document.getElementById("file-input").dispatchEvent(new Event("change", { bubbles: true })); true`);
}

async function main() {
  for (const p of [PDF, LEASE_PDF, DOCX, DOC]) {
    if (!fs.existsSync(p)) throw new Error("缺少测试文件：" + p);
  }
  if (!fs.existsSync(INDEX)) throw new Error("dist/index.html 不存在，请先运行 python workbench/build.py");

  const browser = await launchBrowser({ url: pathToFileURL(INDEX).href, prefix: "wb-parser" });
  try {
    const cdp = browser.cdp;
    await waitFor(cdp, `document.readyState === "complete" && window.__WB_READY__ === true && document.querySelectorAll(".sample-chip").length === 6`);

    await setFile(cdp, PDF);
    const pdfOk = await waitFor(
      cdp,
      `document.querySelector("#contract-input").value.indexOf("PDF_PARSE_OK") >= 0`,
      30000
    ).catch(() => false);
    const pdfText = await cdp.eval(`document.querySelector("#contract-input").value`);
    const pdfStatus = await cdp.eval(`document.querySelector("#file-status").textContent`);
    ok("PDF 提取", !!pdfOk, `${pdfText.length} 字 · ${pdfStatus.slice(0, 60)}`);
    ok("PDF 保留条款", pdfText.indexOf("Article 3 Liability") >= 0);

    await setFile(cdp, LEASE_PDF);
    const leaseOk = await waitFor(
      cdp,
      `document.querySelector("#contract-input").value.indexOf("房屋租赁合同") >= 0`,
      30000
    ).catch(() => false);
    const leaseText = await cdp.eval(`document.querySelector("#contract-input").value`);
    const leaseStatus = await cdp.eval(`document.querySelector("#file-status").textContent`);
    ok("中文 PDF 提取", !!leaseOk, `${leaseText.length} 字 · ${leaseStatus.slice(0, 60)}`);
    ok("中文 PDF 关键词", leaseText.indexOf("违约金") >= 0 && leaseText.indexOf("押金") >= 0);

    await setFile(cdp, DOCX);
    const docxOk = await waitFor(
      cdp,
      `document.querySelector("#contract-input").value.indexOf("DOCX_PARSE_OK") >= 0`,
      30000
    ).catch(() => false);
    const docxText = await cdp.eval(`document.querySelector("#contract-input").value`);
    const docxStatus = await cdp.eval(`document.querySelector("#file-status").textContent`);
    ok("DOCX 提取", !!docxOk, `${docxText.length} 字 · ${docxStatus.slice(0, 60)}`);
    ok("DOCX 保留条款", docxText.indexOf("第二条 租金及支付方式") >= 0);

    await setFile(cdp, DOC);
    const docRejected = await waitFor(
      cdp,
      `document.querySelector("#file-status").textContent.indexOf("暂不支持 .doc") >= 0`,
      10000
    ).catch(() => false);
    ok("旧版 .doc 明确拒绝", !!docRejected);

    ok("无控制台异常", cdp.exceptions.length === 0, cdp.exceptions.slice(0, 3).join(" | "));
  } finally {
    await browser.close();
  }

  const failed = results.filter((r) => !r.passed);
  console.log("");
  console.log(failed.length ? `✗ ${failed.length} 项未通过` : `✓ 全部 ${results.length} 项通过`);
  if (failed.length) process.exitCode = 1;
}

main().catch((e) => { console.error("✗ " + e.message); process.exitCode = 1; });
