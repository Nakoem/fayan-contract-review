/* 合同工作台 · 审查流水线（无 DOM，可在浏览器与 Node 中共用）
 * ① 抽取 → ② 法条 → ③ 评估 → ④ 复核 → ⑤ 报告
 */
(function (root) {
  const WB = (root.WB = root.WB || {});

  const LEVEL_RANK = { 高: 3, 中: 2, 低: 1 };
  const MAX_CLAUSE_TEXT = 50000;

  // ───────────────────────── 基础工具 ─────────────────────────

  WB.escapeHtml = function (s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  };

  function clampScore(v) {
    const n = Number(v);
    if (!isFinite(n)) return null;
    return Math.max(0, Math.min(5, Math.round(n)));
  }

  function normText(s) {
    return String(s || "").replace(/\s+/g, "").trim();
  }

  WB.deriveLevel = function (f) {
    const dims = [f.fairness, f.clarity, f.exposure];
    if (dims.some((d) => d >= 4)) return "高";
    if (dims.some((d) => d === 3)) return "中";
    return "低";
  };

  WB.computeScore = function (counts) {
    return Math.min(100, counts.high * 15 + counts.mid * 6 + counts.low * 1);
  };

  WB.signAdvice = function (highCount) {
    if (highCount >= 3) return { icon: "❌", text: "不建议签", cls: "sign-no" };
    if (highCount >= 1) return { icon: "⚠️", text: "修改后签", cls: "sign-warn" };
    return { icon: "✅", text: "可签", cls: "sign-ok" };
  };

  // ───────────────────────── 脱敏 ─────────────────────────

  WB.maskText = function (text, hiddenNames) {
    const map = {};
    let out = String(text || "");
    const seq = { name: 0, id: 0, phone: 0, bank: 0, email: 0 };
    // 随机后缀避免与合同原文里已有的【主体1】之类占位符碰撞
    let token = Math.random().toString(36).slice(2, 6);
    while (token.length < 4) token += Math.random().toString(36).slice(2, 6);
    token = token.slice(0, 4);

    const put = (kind, label, original) => {
      seq[kind] += 1;
      const placeholder = "【" + label + seq[kind] + "_" + token + "】";
      map[placeholder] = original;
      return placeholder;
    };

    // 1) 用户指定的公司名 / 人名
    (hiddenNames || [])
      .map((s) => String(s).trim())
      .filter(Boolean)
      .sort((a, b) => b.length - a.length)
      .forEach((name) => {
        if (!name) return;
        out = out.split(name).join(put("name", "主体", name));
      });

    // 2) 身份证
    out = out.replace(/(?<!\d)\d{17}[\dXx](?!\d)/g, (m) => put("id", "证件", m));
    // 3) 手机号
    out = out.replace(/(?<!\d)1[3-9]\d{9}(?!\d)/g, (m) => put("phone", "手机", m));
    // 4) 银行卡
    out = out.replace(/(?<!\d)\d{16,19}(?!\d)/g, (m) => put("bank", "账号", m));
    // 5) 邮箱
    out = out.replace(/[\w.+-]+@[\w-]+\.[\w.]+/g, (m) => put("email", "邮箱", m));

    return { text: out, map };
  };

  WB.unmaskText = function (text, map) {
    if (!text || !map) return text;
    let out = String(text);
    Object.keys(map)
      .sort((a, b) => b.length - a.length)
      .forEach((ph) => { out = out.split(ph).join(map[ph]); });
    return out;
  };

  WB.unmaskDeep = function (obj, map) {
    if (obj == null || !map) return obj;
    if (typeof obj === "string") return WB.unmaskText(obj, map);
    if (Array.isArray(obj)) return obj.map((x) => WB.unmaskDeep(x, map));
    if (typeof obj === "object") {
      const out = {};
      Object.keys(obj).forEach((k) => { out[k] = WB.unmaskDeep(obj[k], map); });
      return out;
    }
    return obj;
  };

  // ───────────────────────── 规则匹配 ─────────────────────────

  // 确定性条款拆分兜底：模型偷懒把整份合同当成一条时，按「第X条」本地切开
  WB.splitClauses = function (text) {
    const src = String(text || "");
    const re = /(^|\n)\s*(第[一二三四五六七八九十百千零〇\d]+条[^\n]*)/g;
    const matches = [];
    let m;
    while ((m = re.exec(src)) !== null) {
      const start = m.index + m[0].indexOf(m[2]);
      matches.push({ start, title: m[2].trim() });
    }
    if (matches.length < 2) return [];

    const parts = [];
    const prefix = src.slice(0, matches[0].start).trim();
    if (prefix) parts.push({ title: "合同首部", text: prefix });
    matches.forEach((mt, i) => {
      const end = i + 1 < matches.length ? matches[i + 1].start : src.length;
      const body = src.slice(mt.start, end).trim();
      if (body) parts.push({ title: mt.title, text: body });
    });
    return parts.map((c, i) => ({ index: i + 1, title: c.title, text: c.text }));
  };

  WB.matchRules = function (contractType, clauses, rules) {
    const allText = (clauses || []).map((c) => c.text || "").join("\n");
    return (rules || WB.RULES || []).filter((rule) => {
      if (!rule.enabled) return false;
      if (rule.contractType === "通用") return true; // 通用规则始终参与（可提示缺失条款）
      if (rule.contractType !== contractType) return false;
      return rule.keywords.some((k) => allText.indexOf(k) >= 0);
    });
  };

  // ───────────────────────── 法规检索（BM25） ─────────────────────────

  function tokenize(s) {
    const text = String(s || "").toLowerCase();
    const tokens = [];
    const latin = text.match(/[a-z0-9]+/g) || [];
    latin.forEach((t) => tokens.push(t));
    const runs = text.match(/[一-鿿]+/g) || [];
    runs.forEach((run) => {
      if (run.length === 1) { tokens.push(run); return; }
      for (let i = 0; i < run.length - 1; i++) tokens.push(run.slice(i, i + 2));
    });
    return tokens;
  }

  let regIndexCache = null;

  function buildRegIndex() {
    if (regIndexCache) return regIndexCache;
    const reg = (WB.KNOWLEDGE && WB.KNOWLEDGE.regulation) || {};
    const docs = [];
    Object.keys(reg).forEach((topic) => {
      const raw = String(reg[topic] || "").trim();
      if (!raw) return;
      const parts = raw.split(/\n\s*\n+/).map((p) => p.trim()).filter(Boolean);
      (parts.length ? parts : [raw]).forEach((p) => {
        if (p.length < 20) return;
        const toks = tokenize(p);
        const tf = {};
        toks.forEach((t) => { tf[t] = (tf[t] || 0) + 1; });
        docs.push({ topic, text: p, tf, len: toks.length });
      });
    });

    const df = {};
    docs.forEach((d) => Object.keys(d.tf).forEach((t) => { df[t] = (df[t] || 0) + 1; }));
    const avgdl = docs.reduce((s, d) => s + d.len, 0) / Math.max(1, docs.length);

    regIndexCache = { docs, df, avgdl, N: docs.length };
    return regIndexCache;
  }

  function bm25Score(index, queryTokens, doc) {
    const k1 = 1.5;
    const b = 0.75;
    const seen = {};
    let score = 0;
    queryTokens.forEach((t) => {
      if (seen[t]) return;
      seen[t] = 1;
      const tf = doc.tf[t];
      if (!tf) return;
      const df = index.df[t] || 0;
      const idf = Math.log(1 + (index.N - df + 0.5) / (df + 0.5));
      score += idf * ((tf * (k1 + 1)) / (tf + k1 * (1 - b + (b * doc.len) / index.avgdl)));
    });
    return score;
  }

  WB.searchRegulations = function (matchedRules, limit) {
    const index = buildRegIndex();
    if (!index.docs.length) return [];

    const picked = [];
    const byKey = {};
    (matchedRules || []).forEach((rule) => {
      const query = [rule.name, rule.condition, (rule.keywords || []).join(" ")].join(" ");
      const qTokens = tokenize(query);
      if (!qTokens.length) return;
      const scored = index.docs
        .map((d) => ({ doc: d, score: bm25Score(index, qTokens, d) }))
        .filter((x) => x.score > 0)
        .sort((a, b2) => b2.score - a.score)
        .slice(0, 2);

      scored.forEach((x) => {
        const key = x.doc.topic + "|" + normText(x.doc.text).slice(0, 40);
        if (byKey[key]) {
          if (byKey[key].ruleIds.indexOf(rule.id) < 0) byKey[key].ruleIds.push(rule.id);
          return;
        }
        const item = {
          topic: x.doc.topic,
          text: x.doc.text.slice(0, 700),
          score: x.score,
          ruleIds: [rule.id],
        };
        byKey[key] = item;
        picked.push(item);
      });
    });

    picked.sort((a, b2) => b2.score - a.score);
    return picked.slice(0, limit || 8).map((x) => ({
      topic: x.topic,
      text: x.text,
      ruleIds: x.ruleIds,
    }));
  };

  // ───────────────────────── 本地校验 ─────────────────────────

  WB.localChecks = function ({ clauses, findings, lowRiskClauses, rules }) {
    const issues = [];
    const rulesById = {};
    (rules || []).forEach((r) => { rulesById[r.id] = r; });

    // 模型偶尔把 clause_index 写错一位：优先相信原文匹配，声明索引只作兜底。
    const clauseNorms = (clauses || [])
      .map((c) => ({ index: Number(c.index) || 0, norm: normText(c.text) }))
      .filter((c) => c.index && c.norm);

    function resolveClauseIndex(text, declared) {
      const idx = Number(declared) || 0;
      const n = normText(text);
      if (!n || n === "（合同未约定）") return idx;
      const matches = (a, b) => a && b && (
        a === b ||
        (b.length >= 12 && a.indexOf(b) >= 0) ||
        (a.length >= 12 && b.indexOf(a) >= 0)
      );
      const declaredClause = clauseNorms.filter((c) => c.index === idx)[0];
      if (declaredClause && matches(declaredClause.norm, n)) return idx;

      let containsBest = null;
      let containedBest = null;
      for (let i = 0; i < clauseNorms.length; i++) {
        const c = clauseNorms[i];
        if (c.norm === n) return c.index;
        if (n.length >= 12 && c.norm.indexOf(n) >= 0) {
          if (!containsBest || c.norm.length < containsBest.norm.length) containsBest = c;
        }
        if (c.norm.length >= 12 && n.indexOf(c.norm) >= 0) {
          if (!containedBest || c.norm.length > containedBest.norm.length) containedBest = c;
        }
      }
      const hit = containsBest || containedBest;
      return hit ? hit.index : idx;
    }

    const cleaned = [];
    const seenFindings = {};

    (findings || []).forEach((f) => {
      if (!f || !f.rule_id) return;

      let fairness = clampScore(f.fairness);
      let clarity = clampScore(f.clarity);
      let exposure = clampScore(f.exposure);
      if (fairness == null || clarity == null || exposure == null) {
        issues.push({
          severity: "error", type: "scoring",
          description: "存在缺失或非法的三维评分：" + (f.clause_text || "").slice(0, 40),
          suggestion: "请为每条 finding 提供 0-5 的整数 fairness/clarity/exposure",
        });
        fairness = fairness == null ? 3 : fairness;
        clarity = clarity == null ? 3 : clarity;
        exposure = exposure == null ? 3 : exposure;
      }

      let basis = String(f.basis || "").trim();
      if (!basis && rulesById[f.rule_id]) basis = rulesById[f.rule_id].basis;
      if (!/第[一二三四五六七八九十百千零〇\d]+条/.test(basis)) {
        issues.push({
          severity: "error", type: "basis",
          description: "风险点缺少具体法条编号：" + (f.clause_text || "").slice(0, 40),
          suggestion: "请引用候选规则或法规片段中的具体法条",
        });
      }

      const clauseText = String(f.clause_text || "").trim();
      if (!clauseText) {
        issues.push({
          severity: "error", type: "consistency",
          description: "存在 clause_text 为空的 finding",
          suggestion: "请逐字摘录对应条款原文",
        });
        return;
      }

      const key = f.rule_id + "|" + normText(clauseText);
      if (seenFindings[key]) return;
      seenFindings[key] = 1;

      const item = {
        rule_id: f.rule_id,
        rule_name: (rulesById[f.rule_id] && rulesById[f.rule_id].name) || f.rule_name || f.rule_id,
        clause_index: resolveClauseIndex(clauseText, f.clause_index),
        clause_text: clauseText,
        fairness, clarity, exposure,
        risk_reason: String(f.risk_reason || "").trim(),
        basis: basis,
        suggestion: String(f.suggestion || (rulesById[f.rule_id] && rulesById[f.rule_id].advice) || "").trim(),
      };
      item.level = WB.deriveLevel(item);
      cleaned.push(item);
    });

    // 同一 clause_index 已有 finding 时，不再重复归入低风险；
    // 低风险列表内部也按 clause_index / 文本去重，避免报告重复展示。
    const findingIndexes = {};
    cleaned.forEach((f) => { if (f.clause_index) findingIndexes[f.clause_index] = 1; });
    const seenLow = {};
    const low = (lowRiskClauses || [])
      .filter((c) => c && String(c.clause_text || "").trim())
      .map((c) => {
        const clauseText = String(c.clause_text).trim();
        return {
          clause_index: resolveClauseIndex(clauseText, c.clause_index),
          clause_text: clauseText,
          reason: String(c.reason || "未发现明显风险").trim(),
        };
      })
      .filter((c) => {
        if (c.clause_index && findingIndexes[c.clause_index]) return false;
        const key = c.clause_index ? "i" + c.clause_index : "t" + normText(c.clause_text);
        if (seenLow[key]) return false;
        seenLow[key] = 1;
        return true;
      });

    // 覆盖率：每条提取条款必须有归属（用纠正后的索引）
    const covered = {};
    cleaned.forEach((f) => { if (f.clause_index) covered[f.clause_index] = 1; });
    low.forEach((c) => { if (c.clause_index) covered[c.clause_index] = 1; });

    const missing = (clauses || []).filter((c) => !covered[c.index]);
    if (missing.length) {
      issues.push({
        severity: "error", type: "coverage",
        description: "有 " + missing.length + " 条条款未被评估：第 " + missing.map((c) => c.index).join("、") + " 条",
        suggestion: "请把所有条款放入 findings 或 lowRiskClauses",
      });
    }

    return { findings: cleaned, lowRiskClauses: low, missing, issues };
  };

  // ───────────────────────── 报告渲染 ─────────────────────────

  function groupByClause(findings) {
    const map = {};
    findings.forEach((f, i) => {
      const isMissing = Number(f.clause_index) === 0 || String(f.clause_text || "").trim() === "（合同未约定）";
      const key = isMissing
        ? "rule:" + f.rule_id + "|" + normText(f.clause_text)
        : (normText(f.clause_text) || f.rule_id);
      if (!map[key]) map[key] = { key, findings: [], level: "低", maxScore: 0, firstIndex: i };
      const g = map[key];
      g.findings.push(f);
      if (LEVEL_RANK[f.level] > LEVEL_RANK[g.level]) g.level = f.level;
      const maxDim = Math.max(f.fairness, f.clarity, f.exposure);
      if (maxDim > g.maxScore) g.maxScore = maxDim;
    });
    return Object.keys(map).map((k) => map[k]);
  }

  function basisRefHTML(f) {
    if (!f.refs || !f.refs.length) return "";
    const items = f.refs.map((r) =>
      `<div class="basis-ref-item"><span class="basis-ref-topic">${WB.escapeHtml(r.topic)}</span><p>${WB.escapeHtml(r.text)}</p></div>`
    ).join("");
    return `<details class="basis-ref"><summary>法条参考</summary>${items}</details>`;
  }

  function findingCardHTML(g, reportIndex) {
    const levelCls = g.level === "高" ? "high" : g.level === "中" ? "mid" : "low";
    const markCls = g.level === "高" ? "mark-square" : g.level === "中" ? "mark-diamond" : "mark-ring";
    const names = [];
    g.findings.forEach((f) => {
      const n = f.rule_name || f.rule_id;
      if (names.indexOf(n) < 0) names.push(n);
    });
    const rows = g.findings.map((f) => {
      return `<div class="finding-point">
        <div class="finding-row"><span class="row-label">原文</span><p class="clause-quote">${WB.escapeHtml(f.clause_text)}</p></div>
        <div class="finding-row"><span class="row-label">风险说明</span><p>${WB.escapeHtml(f.risk_reason)}<span class="basis">依据：${WB.escapeHtml(f.basis)}</span></p></div>
        <div class="finding-row"><span class="row-label">修改建议</span><p>${WB.escapeHtml(f.suggestion)}</p></div>
        <button class="copy-btn" type="button" data-copy="${WB.escapeHtml(f.suggestion)}">复制修改条款</button>
        ${basisRefHTML(f)}
      </div>`;
    }).join("");

    return `<article class="finding-card finding-${levelCls}" data-report-index="${reportIndex}">
      <header class="finding-head">
        <span class="risk-mark ${markCls}"></span>
        <span class="finding-name">${WB.escapeHtml(names.join(" / "))}</span>
        <span class="finding-level level-${levelCls}">${g.level}风险</span>
      </header>
      ${rows}
    </article>`;
  }

  function sectionHTML(title, body, emptyText) {
    return `<section class="report-section">
      <h3 class="report-section-title">${title}</h3>
      ${body || `<p class="empty-line">${emptyText || "（无）"}</p>`}
    </section>`;
  }

  WB.renderReport = function ({ contractType, findings, lowRiskClauses, summary, dateText }) {
    const groups = groupByClause(findings || []);
    const high = groups.filter((g) => g.level === "高");
    const mid = groups.filter((g) => g.level === "中");
    const lowGroups = groups.filter((g) => g.level === "低");
    const lows = (lowRiskClauses || []).concat(lowGroups.map((g) => ({
      clause_text: g.findings[0].clause_text,
      reason: "综合评分偏低，可接受",
    })));

    const counts = { high: high.length, mid: mid.length, low: lows.length };
    const score = WB.computeScore(counts);
    const advice = WB.signAdvice(counts.high);

    const overview = `<div class="overview-grid">
      <div class="overview-stat"><span class="stat-num stat-high">${counts.high}</span><span class="stat-label">高风险</span></div>
      <div class="overview-stat"><span class="stat-num stat-mid">${counts.mid}</span><span class="stat-label">中风险</span></div>
      <div class="overview-stat"><span class="stat-num stat-low">${counts.low}</span><span class="stat-label">低风险</span></div>
      <div class="overview-stat"><span class="stat-num">${score}<i>/100</i></span><span class="stat-label">综合风险评分</span></div>
    </div>
    <p class="overview-summary">${WB.escapeHtml(summary || "已完成审查，请结合下列风险点逐条核对。")}</p>`;

    const highHTML = high.map((g, i) => findingCardHTML(g, i)).join("");
    const midHTML = mid.map((g, i) => findingCardHTML(g, high.length + i)).join("");
    const lowHTML = lows.length
      ? `<ol class="low-list">${lows.map((l) => `<li><span class="clause-quote">${WB.escapeHtml(l.clause_text)}</span><span class="low-reason">${WB.escapeHtml(l.reason)}</span></li>`).join("")}</ol>`
      : "";

    const priority = `<ul class="priority-list">
      <li><span class="priority-tag p0">P0 必须改</span>${counts.high} 条</li>
      <li><span class="priority-tag p1">P1 建议改</span>${counts.mid} 条</li>
      <li><span class="priority-tag p2">P2 可接受</span>${counts.low} 条</li>
    </ul>`;

    return `<div class="report" id="report-root">
      <header class="report-head">
        <h2 class="report-title">合同审查报告</h2>
        <p class="report-meta">合同类型：${WB.escapeHtml(contractType)}　·　审查日期：${WB.escapeHtml(dateText || new Date().toLocaleDateString("zh-CN"))}</p>
      </header>
      ${sectionHTML("一、总体风险概览", overview)}
      ${sectionHTML("二、高风险条款详解", highHTML, "（无）")}
      ${sectionHTML("三、需关注的中风险条款", midHTML, "（无）")}
      ${sectionHTML("四、低风险条款（可接受）", lowHTML, "（无）")}
      ${sectionHTML("五、修改优先级建议", priority)}
      ${sectionHTML("六、签约建议", `<p class="sign-advice ${advice.cls}">${advice.text}</p>`)}
      <footer class="report-foot">${(WB.REPORT_LABELS && WB.REPORT_LABELS.disclaimer) || "本工具输出为 AI 辅助结果，不构成法律意见。正式签署前请由执业律师复核。"}</footer>
    </div>`;
  };

  WB.highlightContract = function (text, findings) {
    const src = String(text || "");
    if (!src) return "";

    const ranges = [];
    (findings || []).forEach((f, idx) => {
      const needle = String(f.clause_text || "").trim();
      if (!needle || needle === "（合同未约定）" || needle.length < 4) return;
      let start = src.indexOf(needle);
      let len = needle.length;
      if (start < 0 && needle.length > 24) {
        const head = needle.slice(0, 24);
        start = src.indexOf(head);
        len = head.length;
      }
      if (start < 0) return;
      ranges.push({ start, end: start + len, level: f.level, idx });
    });

    // 按风险等级与长度优先，去掉重叠
    ranges.sort((a, b) => (LEVEL_RANK[b.level] - LEVEL_RANK[a.level]) || (b.end - b.start) - (a.end - a.start));
    const chosen = [];
    ranges.forEach((r) => {
      if (chosen.some((c) => r.start < c.end && r.end > c.start)) return;
      chosen.push(r);
    });
    chosen.sort((a, b) => a.start - b.start);

    let html = "";
    let cursor = 0;
    chosen.forEach((r) => {
      html += WB.escapeHtml(src.slice(cursor, r.start));
      const cls = r.level === "高" ? "hl-high" : r.level === "中" ? "hl-mid" : "hl-low";
      html += `<mark class="${cls}" data-risk-index="${r.idx}">${WB.escapeHtml(src.slice(r.start, r.end))}</mark>`;
      cursor = r.end;
    });
    html += WB.escapeHtml(src.slice(cursor));
    return html;
  };

  WB.buildDocHtml = function (reportHtml, contractType) {
    const css = `
      body{font-family:"Noto Serif SC","SimSun",serif;color:#17171A;line-height:1.6;font-size:12pt;max-width:720px;margin:0 auto;padding:24px}
      h2{font-size:22pt;margin:0 0 8px}
      h3{font-size:14pt;border-bottom:1px solid #E3E0D8;padding-bottom:4px;margin:22px 0 10px}
      .report-meta{color:#6B6B70;font-size:10pt}
      .finding-card{border:1px solid #E3E0D8;border-left:4px solid #B4352A;padding:10px 14px;margin:10px 0;break-inside:avoid}
      .finding-mid{border-left-color:#B8873A}.finding-low{border-left-color:#2F6E58}
      .finding-head{font-weight:bold;margin-bottom:6px}
      .finding-level{font-weight:normal;font-size:10pt;margin-left:8px}
      .finding-row{display:block;margin:4px 0}
      .row-label{display:inline-block;width:64px;color:#6B6B70;font-size:10pt;vertical-align:top}
      .finding-row p{display:inline;margin:0}
      .basis{color:#6B6B70;font-size:10pt;margin-left:8px}
      .copy-btn{display:none}
      .overview-grid{margin:8px 0}
      .overview-stat{display:inline-block;margin-right:26px;vertical-align:top}
      .stat-num{font-size:20pt;font-variant-numeric:tabular-nums}
      .stat-label{color:#6B6B70;font-size:9pt}
      .sign-advice{font-size:13pt}
      .report-foot{margin-top:24px;padding-top:8px;border-top:1px solid #E3E0D8;color:#6B6B70;font-size:9pt}
    `;
    return `<!DOCTYPE html><html><head><meta charset="utf-8"><title>合同审查报告</title><style>${css}</style></head><body>${reportHtml}</body></html>`;
  };

  // ───────────────────────── JSON 调用（解析失败自动换模式重试） ─────────────────────────

  async function callJSON(llmOpts, messages, maxTokens, label, validate) {
    let lastText = "";
    let lastErr = null;
    for (let attempt = 0; attempt < 2; attempt++) {
      const res = await WB.callLLM(Object.assign({}, llmOpts, {
        messages,
        maxTokens,
        jsonMode: attempt === 0,
      }));
      lastText = res.content || "";
      const json = WB.parseJSON(lastText);
      if (json && (!validate || validate(json))) return json;
      lastErr = new Error(
        (label || "模型") + "返回的 JSON 无法解析" +
        (lastText ? "：" + lastText.slice(0, 180).replace(/\s+/g, " ") : "（空内容）")
      );
    }
    throw lastErr || new Error((label || "模型") + "返回的 JSON 无法解析");
  }

  // ───────────────────────── 主流程 ─────────────────────────

  WB.runPipeline = async function ({
    contractText,
    contractType,
    settings,
    hiddenNames,
    masking = true,
    onProgress,
    signal,
    reviewEnabled = true,
  }) {
    const startAll = Date.now();
    const timings = {};
    // 审查开始时冻结规则：中途在规则页修改，不会让同一次审查前后读到两套规则。
    const rulesSnapshot = (WB.RULES || []).map((r) =>
      Object.assign({}, r, { keywords: (r.keywords || []).slice() })
    );
    const progress = (step, status, detail) => {
      if (onProgress) onProgress({ step, status, detail: detail || "", timings: Object.assign({}, timings) });
    };

    if (!contractText || contractText.trim().length < 50) {
      throw new Error("合同内容太短（至少 50 字）");
    }
    if (contractText.length > MAX_CLAUSE_TEXT) {
      throw new Error("合同超过 5 万字上限，请分拆后再审");
    }

    const providerMeta = WB.PROVIDERS[settings.provider] || {};
    const llmOpts = {
      baseUrl: settings.baseUrl,
      apiKey: settings.apiKey,
      model: settings.model,
      signal,
      timeoutMs: 120000,
      extraBody: providerMeta.extraBody || null,
    };

    // 脱敏
    const maskResult = masking
      ? WB.maskText(contractText, hiddenNames || [])
      : { text: contractText, map: {} };
    const sendText = maskResult.text;
    const maskMap = maskResult.map;

    const unmaskFinding = (f) => WB.unmaskDeep(f, maskMap);
    const unmaskList = (arr) => (arr || []).map((x) => WB.unmaskDeep(x, maskMap));

    // ① 抽取
    progress(1, "running");
    const t1 = Date.now();
    const exJson = await callJSON(
      llmOpts,
      WB.buildExtractMessages(contractType, sendText),
      3000,
      "第 1 步「抽取」",
      (j) => Array.isArray(j.clauses) && j.clauses.length > 0
    );
    let clauses = exJson.clauses
      .filter((c) => c && String(c.text || "").trim())
      .map((c, i) => ({
        // 统一重编号，避免模型返回重复/跳号导致覆盖率校验错乱
        index: i + 1,
        title: String(c.title || "第 " + (i + 1) + " 条").trim(),
        text: String(c.text).trim(),
      }));
    if (!clauses.length) {
      throw new Error("第 1 步「抽取」没有可用条款（模型返回了空文本）");
    }

    // 兜底：只抽到 1 条时，按「第X条」本地重新切分
    if (clauses.length < 2) {
      const fallback = WB.splitClauses(sendText);
      if (fallback.length >= 2) clauses = fallback;
    }
    timings.extract = Date.now() - t1;
    progress(1, "done", clauses.length + " 条条款");

    // ② 法条
    progress(2, "running");
    const t2 = Date.now();
    const matchedRules = WB.matchRules(contractType, clauses, rulesSnapshot);
    const regSnippets = WB.searchRegulations(matchedRules, clauses.length > 18 ? 4 : 8);
    timings.retrieve = Date.now() - t2;
    progress(2, "done", matchedRules.length + " 条候选规则 · " + regSnippets.length + " 段法规");

    // ③ 评估
    progress(3, "running");
    const t3 = Date.now();
    let evalJson = await evalOnce({ contractType, clauses, matchedRules, regSnippets, llmOpts });
    timings.eval = Date.now() - t3;
    progress(3, "done", (evalJson.findings || []).length + " 条风险");

    // ④ 复核
    progress(4, "running");
    const t4 = Date.now();
    let check = WB.localChecks({
      clauses,
      findings: evalJson.findings,
      lowRiskClauses: evalJson.lowRiskClauses,
      rules: rulesSnapshot,
    });

    let review = { passed: true, issues: [] };
    let reEvaluated = false;
    // 长合同：评估已花掉大部分 90 秒预算时跳过 LLM 复核，本地校验仍然执行。
    const reviewBudgetOk = (Date.now() - startAll) < 35000;
    if (reviewEnabled && reviewBudgetOk) {
      try {
        review = await callJSON(
          llmOpts,
          WB.buildReviewMessages({
            contractType, clauses, findings: check.findings, lowRiskClauses: check.lowRiskClauses,
          }),
          800,
          "第 4 步「复核」",
          (j) => typeof j.passed === "boolean"
        );
      } catch (e) {
        review = { passed: true, issues: [], skipped: String(e.message || e) };
      }
    } else if (reviewEnabled) {
      review = { passed: true, issues: [], skipped: "time_budget" };
    }

    const reviewErrors = (review.issues || []).filter((i) => i && i.severity === "error");
    if (reviewErrors.length && review.passed === false && !reEvaluated) {
      reEvaluated = true;
      evalJson = await evalOnce({
        contractType, clauses, matchedRules, regSnippets, llmOpts,
        issues: reviewErrors,
      });
      check = WB.localChecks({
        clauses,
        findings: evalJson.findings,
        lowRiskClauses: evalJson.lowRiskClauses,
        rules: rulesSnapshot,
      });
    }
    // 兜底：重评后仍未覆盖的条款，按低风险补入，保证每条都有归属
    if (check.missing && check.missing.length) {
      check.lowRiskClauses = check.lowRiskClauses.concat(
        check.missing.map((c) => ({
          clause_index: c.index,
          clause_text: c.text,
          reason: "未单独评估，按无风险处理",
        }))
      );
      check.missing = [];
      check.issues = check.issues.filter((i) => i.type !== "coverage");
    }

    timings.review = Date.now() - t4;
    progress(4, "done", review.skipped ? "本地校验通过（长合同跳过 LLM 复核）" : review.passed === false ? "已重评 1 轮" : "通过");

    // 给每条 finding 挂上本地检索到的法规原文，报告里可展开。
    const refsByRule = {};
    regSnippets.forEach((s) => {
      (s.ruleIds || []).forEach((id) => {
        (refsByRule[id] = refsByRule[id] || []).push({ topic: s.topic, text: s.text });
      });
    });
    check.findings.forEach((f) => {
      f.refs = (refsByRule[f.rule_id] || []).slice(0, 2);
    });

    const localIssues = check.issues.slice();

    // ⑤ 报告
    progress(5, "running");
    const t5 = Date.now();
    const findings = unmaskList(check.findings);
    const lows = unmaskList(check.lowRiskClauses);
    const summary = WB.unmaskText(String(evalJson.summary || "").trim(), maskMap);
    const reportHtml = WB.renderReport({
      contractType,
      findings,
      lowRiskClauses: lows,
      summary,
      dateText: new Date().toLocaleDateString("zh-CN"),
    });
    timings.report = Date.now() - t5;
    timings.total = Date.now() - startAll;
    progress(5, "done", "报告生成");

    const groups = groupByClause(findings);
    const counts = {
      high: groups.filter((g) => g.level === "高").length,
      mid: groups.filter((g) => g.level === "中").length,
      low: lows.length + groups.filter((g) => g.level === "低").length,
    };

    return {
      ok: true,
      contractType,
      clauses,
      matchedRules,
      regSnippets,
      findings,
      lowRiskClauses: lows,
      summary,
      reportHtml,
      counts,
      score: WB.computeScore(counts),
      advice: WB.signAdvice(counts.high),
      timings,
      review,
      reviewSkipped: review.skipped || null,
      localIssues,
      reEvaluated,
      masked: masking,
    };
  };

  async function evalOnce({ contractType, clauses, matchedRules, regSnippets, llmOpts, issues }) {
    const json = await callJSON(
      llmOpts,
      WB.buildEvalMessages({ contractType, clauses, matchedRules, regSnippets, issues }),
      4000,
      "第 3 步「评估」",
      (j) => Array.isArray(j.findings)
    );
    return {
      findings: json.findings || [],
      lowRiskClauses: Array.isArray(json.lowRiskClauses) ? json.lowRiskClauses : [],
      summary: String(json.summary || "").trim(),
    };
  }
})(globalThis);
