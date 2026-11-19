#!/usr/bin/env node
/* M0 技术验证：真调 LLM 跑 5 步流水线，量耗时与质量。
 *
 * 用法：
 *   node workbench/scripts/spike.mjs --sample=lease
 *   node workbench/scripts/spike.mjs --all --gate
 *
 * Key 从仓库根目录 .env 读取（DASHSCOPE_API_KEY / DEEPSEEK_API_KEY / ZHIPU_API_KEY）
 */
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { loadEnv } from "./lib.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const WB_DIR = path.resolve(__dirname, "..");
const REPO = path.resolve(WB_DIR, "..");

const load = (rel) => import(pathToFileURL(path.join(WB_DIR, rel)).href);
await load("src/data/rules.js");
await load("src/data/samples.js");
await load("src/data/knowledge.js");
await load("src/prompts.js");
await load("src/llm.js");
await load("src/pipeline.js");

const WB = globalThis.WB;

const args = process.argv.slice(2);
function arg(name, fallback) {
  const hit = args.find((a) => a.startsWith(`--${name}=`));
  return hit ? hit.split("=").slice(1).join("=") : fallback;
}
const hasFlag = (name) => args.includes(`--${name}`);

const env = loadEnv(REPO);
const providerKey = arg("provider", "dashscope");
const provider = WB.PROVIDERS[providerKey];
if (!provider) {
  console.error(`未知服务商：${providerKey}`);
  process.exit(1);
}

const keyMap = { dashscope: "DASHSCOPE_API_KEY", deepseek: "DEEPSEEK_API_KEY", zhipu: "ZHIPU_API_KEY" };
const apiKey = process.env[keyMap[providerKey]] || env[keyMap[providerKey]] || "";
if (!apiKey) {
  console.error(`缺少 ${keyMap[providerKey]}（可写在仓库根目录 .env）`);
  process.exit(1);
}

const settings = {
  provider: providerKey,
  baseUrl: provider.baseUrl,
  model: arg("model", provider.model),
  apiKey,
};

const sampleArg = arg("sample", "lease");
const samples = hasFlag("all")
  ? WB.SAMPLES
  : WB.SAMPLES.filter((s) => s.key === sampleArg);

if (!samples.length) {
  console.error(`找不到示例：${sampleArg}`);
  process.exit(1);
}

console.log(`服务商：${provider.label} · 模型：${settings.model}`);

let failed = false;

for (const sample of samples) {
  console.log("\n" + "═".repeat(62));
  console.log(`示例：${sample.name}（${sample.file}，${sample.text.length} 字）`);
  console.log("═".repeat(62));

  const t0 = Date.now();
  try {
    const result = await WB.runPipeline({
      contractText: sample.text,
      contractType: sample.name,
      settings,
      masking: true,
      hiddenNames: [],
      onProgress: (e) => {
        const mark = e.status === "done" ? "✓" : "…";
        console.log(`  ${mark} 步骤 ${e.step} ${e.status}${e.detail ? " · " + e.detail : ""}`);
      },
    });

    const secs = ((Date.now() - t0) / 1000).toFixed(1);
    console.log(`\n耗时：${secs}s（抽取 ${(result.timings.extract / 1000).toFixed(1)}s / 评估 ${(result.timings.eval / 1000).toFixed(1)}s / 复核 ${(result.timings.review / 1000).toFixed(1)}s）`);
    console.log(`风险：高 ${result.counts.high} · 中 ${result.counts.mid} · 低 ${result.counts.low} · 综合评分 ${result.score}/100`);
    console.log(`结论：${result.advice.icon} ${result.advice.text}${result.reEvaluated ? "（复核重评过）" : ""}`);
    console.log(`摘要：${result.summary || "（无）"}`);
    if (result.localIssues && result.localIssues.length) {
      console.log(`本地校验：${result.localIssues.length} 个问题`);
      result.localIssues.slice(0, 6).forEach((i) => console.log(`  · [${i.severity}] ${i.type}: ${i.description}`));
    }
    if (result.review && result.review.issues && result.review.issues.length) {
      console.log(`复核意见：${result.review.issues.length} 条`);
      result.review.issues.slice(0, 6).forEach((i) => console.log(`  · [${i.severity}] ${i.type}: ${i.description}`));
    }

    const withBasis = result.findings.filter((f) => /第[一二三四五六七八九十百千零〇\d]+条/.test(f.basis || ""));
    console.log(`风险条数：${result.findings.length}，其中带法条：${withBasis.length}`);

    for (const f of result.findings) {
      console.log(`  [${f.level}] ${f.rule_name} · ${f.basis} · ${(f.clause_text || "").slice(0, 36)}…`);
    }

    const gateOk = Number(secs) <= 90 && result.findings.length >= 5 && withBasis.length >= 5;
    if (hasFlag("gate") && !gateOk) {
      failed = true;
      console.log("✗ 门禁未过：需 ≤90s、风险 ≥5 条且全部带法条");
    } else if (hasFlag("gate")) {
      console.log("✓ 门禁通过");
    }
  } catch (err) {
    failed = true;
    console.error(`✗ 失败：${err.message}`);
    if (err.stack) console.error(err.stack.split("\n").slice(1, 4).join("\n"));
  }
}

process.exitCode = failed ? 1 : 0;
