/* 测试脚本公共库：Chrome 启动 / CDP 客户端 / 等待 / .env 读取 */
import { spawn } from "node:child_process";
import fs from "node:fs";
import net from "node:net";
import os from "node:os";
import path from "node:path";

export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const CHROME_CANDIDATES = [
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
  "/usr/bin/google-chrome",
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
];

export function findChrome() {
  const hit = CHROME_CANDIDATES.find((p) => fs.existsSync(p));
  if (!hit) throw new Error("找不到 Chrome / Edge");
  return hit;
}

export function loadEnv(repoDir) {
  const p = path.join(repoDir, ".env");
  const out = {};
  if (!fs.existsSync(p)) return out;
  fs.readFileSync(p, "utf-8").split(/\r?\n/).forEach((line) => {
    const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/);
    if (!m) return;
    let v = m[2].trim();
    if ((v.startsWith('"') && v.endsWith('"')) || (v.startsWith("'") && v.endsWith("'"))) v = v.slice(1, -1);
    out[m[1]] = v;
  });
  return out;
}

async function getTargets(port) {
  const hosts = ["127.0.0.1", "localhost", "[::1]"];
  for (let i = 0; i < 80; i++) {
    for (const h of hosts) {
      try {
        const res = await fetch(`http://${h}:${port}/json/list`);
        return await res.json();
      } catch (e) { /* next */ }
    }
    await sleep(200);
  }
  throw new Error("CDP 端点不可达");
}

export class CDP {
  constructor(ws) {
    this.ws = ws;
    this.id = 0;
    this.pending = new Map();
    this.exceptions = [];
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.id && this.pending.has(msg.id)) {
        this.pending.get(msg.id)(msg);
        this.pending.delete(msg.id);
      } else if (msg.method === "Runtime.exceptionThrown") {
        const d = msg.params.exceptionDetails || {};
        this.exceptions.push(d.exception && d.exception.description ? d.exception.description : d.text);
      } else if (msg.method === "Runtime.consoleAPICalled" && msg.params.type === "error") {
        this.exceptions.push(msg.params.args.map((a) => a.value || a.description || "").join(" "));
      }
    };
  }

  send(method, params = {}) {
    return new Promise((resolve) => {
      const id = ++this.id;
      this.pending.set(id, resolve);
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }

  async eval(expression) {
    const msg = await this.send("Runtime.evaluate", {
      expression,
      awaitPromise: true,
      returnByValue: true,
    });
    if (msg.result && msg.result.exceptionDetails) {
      throw new Error(
        (msg.result.exceptionDetails.exception && msg.result.exceptionDetails.exception.description) ||
        msg.result.exceptionDetails.text
      );
    }
    return msg.result && msg.result.result ? msg.result.result.value : undefined;
  }
}

export async function waitFor(cdp, expression, timeout = 15000, interval = 200) {
  const start = Date.now();
  let lastErr = null;
  while (Date.now() - start < timeout) {
    try {
      const v = await cdp.eval(expression);
      if (v) return v;
    } catch (e) { lastErr = e; }
    await sleep(interval);
  }
  if (lastErr) throw new Error(`等待超时：${expression}（${lastErr.message}）`);
  return null;
}

/** 刷新页面并等待新文档真正就绪（避免 CDP 在旧文档上提前判定 ready） */
export async function reloadPage(cdp, readyExpression = `document.readyState === "complete" && window.__WB_READY__ === true && document.querySelectorAll(".sample-chip").length === 6`, timeout = 15000) {
  await cdp.eval(`window.__wbReloadMarker = true; true`);
  await cdp.send("Page.reload", { ignoreCache: true });
  await waitFor(
    cdp,
    `typeof window.__wbReloadMarker === "undefined" && typeof WB === "object" && ${readyExpression}`,
    timeout
  );
}

export async function screenshot(cdp, outPath) {
  const s = await cdp.send("Page.captureScreenshot", { format: "png" });
  fs.writeFileSync(outPath, Buffer.from(s.result.data, "base64"));
  return outPath;
}

function findFreePort() {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.unref();
    srv.on("error", reject);
    srv.listen(0, "127.0.0.1", () => {
      const { port } = srv.address();
      srv.close(() => resolve(port));
    });
  });
}

/** 启动 headless Chrome，连接 CDP，返回可关闭的句柄 */
export async function launchBrowser({ url, width = 1280, height = 900, prefix = "wb", profileDir = null }) {
  const chrome = findChrome();
  // 随机端口可能撞上别的 Chrome（如 Playwright 的 9333），用系统空闲端口更稳。
  const port = await findFreePort();
  const profile = profileDir || fs.mkdtempSync(path.join(os.tmpdir(), prefix + "-"));
  const ownsProfile = !profileDir;

  const child = spawn(chrome, [
    "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
    `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, url,
  ], { stdio: "ignore" });

  const cleanup = () => {
    try { child.kill(); } catch (e) { /* ignore */ }
    if (ownsProfile) {
      try { fs.rmSync(profile, { recursive: true, force: true }); } catch (e) { /* ignore */ }
    }
  };

  try {
    const targets = await getTargets(port);
    const page = targets.find((t) => t.type === "page");
    if (!page) throw new Error("找不到页面目标");

    const ws = new WebSocket(page.webSocketDebuggerUrl);
    await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject; });
    const cdp = new CDP(ws);
    await cdp.send("Page.enable");
    await cdp.send("Runtime.enable");
    await cdp.send("Emulation.setDeviceMetricsOverride", {
      width, height, deviceScaleFactor: 1, mobile: false,
    });

    return {
      cdp,
      child,
      profile,
      async close() {
        try { ws.close(); } catch (e) { /* ignore */ }
        cleanup();
      },
      async closeGracefully() {
        try { await cdp.send("Browser.close"); } catch (e) { /* ignore */ }
        await new Promise((resolve) => {
          if (child.exitCode !== null) return resolve();
          const timer = setTimeout(resolve, 3000);
          child.once("exit", () => { clearTimeout(timer); resolve(); });
        });
        try { ws.close(); } catch (e) { /* ignore */ }
        cleanup();
      },
    };
  } catch (err) {
    cleanup();
    throw err;
  }
}
