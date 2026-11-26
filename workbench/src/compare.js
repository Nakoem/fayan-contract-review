/* 合同工作台 · V3 合同版本对比
 * 本地做条款对齐和文本差异；两边都带审查结果时，再比较风险变化。
 * 不调用模型，不上传。
 */
(function (root) {
  const WB = (root.WB = root.WB || {});
  const DISCLAIMER = "本对比由合同工作台本地生成，仅供参考，不构成法律意见；正式签署前请由执业律师复核。";
  const LEVEL_RANK = { 高: 3, 中: 2, 低: 1 };

  function escape(s) {
    return WB.escapeHtml(s == null ? "" : s);
  }

  function norm(s) {
    return String(s == null ? "" : s)
      .replace(/[\s　]+/g, "")
      .replace(/[，。；：、！？,.;:!?"'“”‘’（）()【】\[\]《》<>]/g, "");
  }

  function textHtml(s) {
    return escape(s).replace(/\n/g, "<br>");
  }

  function firstTitle(text) {
    const line = String(text || "")
      .split(/\r?\n/)
      .map((s) => s.trim())
      .find(Boolean);
    return (line || "未命名合同").slice(0, 60);
  }

  function articleTitle(title) {
    return String(title || "").replace(/^第[一二三四五六七八九十百千零〇\d]+条\s*/, "");
  }

  function itemKey(item, useText) {
    // 条款模式按标题对齐，可容忍「第 X 条」整体重编号；
    // 无条款结构的段落模式必须按正文对齐，否则中间插一段会让后面全部错位成“修改”。
    const title = useText ? "" : norm(articleTitle(item && item.title)).slice(0, 24);
    return title || norm(item && item.text).slice(0, 60);
  }

  function splitItems(text) {
    const clauses = WB.splitClauses(text);
    if (clauses.length >= 2) {
      return {
        kind: "clause",
        items: clauses.map((c) => ({ index: c.index, title: c.title, text: c.text })),
      };
    }
    const raw = String(text || "").trim();
    if (!raw) return { kind: "block", items: [] };
    let parts = raw.split(/\n\s*\n+/).map((s) => s.trim()).filter(Boolean);
    if (parts.length < 2) parts = raw.split(/\n+/).map((s) => s.trim()).filter(Boolean);
    return {
      kind: "block",
      items: parts.map((textPart, i) => ({
        index: i + 1,
        title: "第 " + (i + 1) + " 段",
        text: textPart,
      })),
    };
  }

  // 超大文本（例如 PDF 逐字换行）不适合 O(n×m) 的动态规划：
  // 2000×2000 的 Uint16 表已占 8MB，再大就可能让页面卡死。
  function keyedPairs(a, b) {
    const index = new Map();
    b.forEach((key, j) => {
      if (!index.has(key)) index.set(key, []);
      index.get(key).push(j);
    });
    const pairs = [];
    a.forEach((key, i) => {
      const list = index.get(key);
      if (list && list.length) pairs.push([i, list.shift()]);
    });
    pairs.sort((x, y) => x[0] - y[0]);
    const out = [];
    let lastNew = -1;
    pairs.forEach((pair) => {
      if (pair[1] > lastNew) {
        out.push(pair);
        lastNew = pair[1];
      }
    });
    return out;
  }

  function lcsPairs(a, b) {
    const n = a.length;
    const m = b.length;
    if (!n || !m) return [];
    if (n * m > 4000000) return keyedPairs(a, b);
    const dp = Array.from({ length: n + 1 }, () => new Uint16Array(m + 1));
    for (let i = 1; i <= n; i++) {
      for (let j = 1; j <= m; j++) {
        dp[i][j] = a[i - 1] === b[j - 1]
          ? dp[i - 1][j - 1] + 1
          : Math.max(dp[i - 1][j], dp[i][j - 1]);
      }
    }
    let i = n;
    let j = m;
    const pairs = [];
    while (i > 0 && j > 0) {
      if (a[i - 1] === b[j - 1]) {
        pairs.push([i - 1, j - 1]);
        i--;
        j--;
      } else if (dp[i - 1][j] >= dp[i][j - 1]) {
        i--;
      } else {
        j--;
      }
    }
    return pairs.reverse();
  }

  function bigrams(s) {
    const text = norm(s);
    const set = new Set();
    if (text.length < 2) {
      if (text) set.add(text);
      return set;
    }
    for (let i = 0; i < text.length - 1; i++) set.add(text.slice(i, i + 2));
    return set;
  }

  function similarity(a, b) {
    if (norm(a) === norm(b)) return 1;
    const left = bigrams(a);
    const right = bigrams(b);
    if (!left.size || !right.size) return 0;
    let common = 0;
    left.forEach((token) => { if (right.has(token)) common++; });
    return common / Math.max(left.size, right.size);
  }

  function pairGap(oldItems, newItems) {
    const pairs = [];
    if (!oldItems.length || !newItems.length) return pairs;
    if (oldItems.length * newItems.length > 250000) return pairs;
    const used = new Set();
    oldItems.forEach((oldItem, oldIndex) => {
      let best = -1;
      let bestScore = 0.35;
      newItems.forEach((newItem, newIndex) => {
        if (used.has(newIndex)) return;
        const score = similarity(oldItem.text, newItem.text);
        if (score > bestScore) {
          bestScore = score;
          best = newIndex;
        }
      });
      if (best >= 0) {
        used.add(best);
        pairs.push([oldIndex, best]);
      }
    });
    return pairs;
  }

  function splitSegments(s) {
    const text = String(s || "");
    if (!text) return [];
    const parts = text.split(/([，。；：！？\n])/);
    const out = [];
    let buffer = "";
    parts.forEach((part) => {
      if (!part) return;
      buffer += part;
      if (/^[，。；：！？\n]$/.test(part)) {
        out.push(buffer);
        buffer = "";
      }
    });
    if (buffer) out.push(buffer);
    return out.length ? out : [text];
  }

  function diffSegments(oldText, newText) {
    const a = splitSegments(oldText);
    const b = splitSegments(newText);
    if (a.length > 240 || b.length > 240) {
      return { oldHtml: textHtml(oldText), newHtml: textHtml(newText) };
    }
    const n = a.length;
    const m = b.length;
    const dp = Array.from({ length: n + 1 }, () => new Uint16Array(m + 1));
    for (let i = 1; i <= n; i++) {
      for (let j = 1; j <= m; j++) {
        dp[i][j] = norm(a[i - 1]) === norm(b[j - 1])
          ? dp[i - 1][j - 1] + 1
          : Math.max(dp[i - 1][j], dp[i][j - 1]);
      }
    }
    let i = n;
    let j = m;
    const ops = [];
    while (i > 0 && j > 0) {
      if (norm(a[i - 1]) === norm(b[j - 1])) {
        ops.push({ type: "same", a: a[i - 1], b: b[j - 1] });
        i--;
        j--;
      } else if (dp[i - 1][j] >= dp[i][j - 1]) {
        ops.push({ type: "del", a: a[i - 1] });
        i--;
      } else {
        ops.push({ type: "ins", b: b[j - 1] });
        j--;
      }
    }
    while (i > 0) ops.push({ type: "del", a: a[--i] });
    while (j > 0) ops.push({ type: "ins", b: b[--j] });
    ops.reverse();

    let oldHtml = "";
    let newHtml = "";
    ops.forEach((op) => {
      if (op.type === "same") {
        oldHtml += textHtml(op.a);
        newHtml += textHtml(op.b);
      } else if (op.type === "del") {
        oldHtml += "<del>" + textHtml(op.a) + "</del>";
      } else {
        newHtml += "<ins>" + textHtml(op.b) + "</ins>";
      }
    });
    return {
      oldHtml: oldHtml || textHtml(oldText),
      newHtml: newHtml || textHtml(newText),
    };
  }

  function bodyText(item) {
    if (!item) return "";
    const text = String(item.text || "");
    const title = String(item.title || "");
    return title && text.indexOf(title) === 0 ? text.slice(title.length).trim() : text;
  }

  function makeRow(oldItem, newItem) {
    const oldText = oldItem ? oldItem.text : "";
    const newText = newItem ? newItem.text : "";
    let type;
    if (oldItem && newItem) {
      type = norm(bodyText(oldItem)) === norm(bodyText(newItem)) ? "same" : "modified";
    } else {
      type = oldItem ? "removed" : "added";
    }
    const diff = type === "modified"
      ? diffSegments(oldText, newText)
      : { oldHtml: textHtml(oldText), newHtml: textHtml(newText) };
    return {
      type: type,
      oldIndex: oldItem ? oldItem.index : null,
      newIndex: newItem ? newItem.index : null,
      oldTitle: oldItem ? oldItem.title : "",
      newTitle: newItem ? newItem.title : "",
      oldText: oldText,
      newText: newText,
      oldHtml: diff.oldHtml,
      newHtml: diff.newHtml,
    };
  }

  function riskLevel(finding) {
    const level = finding && finding.level;
    if (level === "高" || level === "中" || level === "低") return level;
    return WB.deriveLevel(finding || {});
  }

  function riskKey(finding) {
    const identity = finding.rule_id || finding.rule_name || "";
    return norm(identity + "::" + String(finding.clause_text || "").slice(0, 180));
  }

  function riskItem(finding) {
    return {
      key: riskKey(finding),
      rule_id: finding.rule_id || "",
      rule_name: finding.rule_name || finding.rule_id || "未命名风险",
      level: riskLevel(finding),
      clause_index: Number(finding.clause_index) || 0,
      clause_text: String(finding.clause_text || ""),
      risk_reason: String(finding.risk_reason || ""),
      suggestion: String(finding.suggestion || ""),
    };
  }

  function countsOf(items) {
    const counts = { high: 0, mid: 0, low: 0 };
    items.forEach((item) => {
      if (item.level === "高") counts.high++;
      else if (item.level === "中") counts.mid++;
      else counts.low++;
    });
    return counts;
  }

  function countsFor(result, items) {
    // 报告里的低风险还包含未单独成条的 lowRiskClauses，直接数 findings 会少算。
    const counts = result && result.counts;
    if (counts && typeof counts.high === "number" && typeof counts.mid === "number" && typeof counts.low === "number") {
      return { high: counts.high, mid: counts.mid, low: counts.low };
    }
    return countsOf(items);
  }

  function sortRisks(items) {
    return items.slice().sort((a, b) => (LEVEL_RANK[b.level] || 0) - (LEVEL_RANK[a.level] || 0));
  }

  function sameRule(a, b) {
    if (a.rule_id && b.rule_id) return a.rule_id === b.rule_id;
    return !!a.rule_name && a.rule_name === b.rule_name;
  }

  function compareRisk(oldResult, newResult) {
    const oldSafe = oldResult || {};
    const newSafe = newResult || {};
    const oldItems = (Array.isArray(oldSafe.findings) ? oldSafe.findings : []).map(riskItem);
    const newItems = (Array.isArray(newSafe.findings) ? newSafe.findings : []).map(riskItem);
    const oldMap = new Map(oldItems.map((item) => [item.key, item]));
    const newMap = new Map(newItems.map((item) => [item.key, item]));
    const exactAdded = newItems.filter((item) => !oldMap.has(item.key));
    const exactResolved = oldItems.filter((item) => !newMap.has(item.key));
    const levelChanged = [];
    newItems.forEach((item) => {
      const before = oldMap.get(item.key);
      if (before && before.level !== item.level) {
        levelChanged.push({ old: before, new: item });
      }
    });

    // 条款文字改了但规则和位置没变，仍视为同一条风险，避免“修改一处”被算成新增 + 消除。
    const usedResolved = new Set();
    const added = [];
    exactAdded.forEach((item) => {
      let best = -1;
      let bestScore = 0;
      exactResolved.forEach((before, index) => {
        if (usedResolved.has(index) || !sameRule(before, item)) return;
        const score = before.clause_index && item.clause_index && before.clause_index === item.clause_index
          ? 1
          : similarity(before.clause_text, item.clause_text);
        if (score > bestScore) {
          bestScore = score;
          best = index;
        }
      });
      if (best >= 0 && bestScore >= 0.5) {
        usedResolved.add(best);
        const before = exactResolved[best];
        if (before.level !== item.level) levelChanged.push({ old: before, new: item });
      } else {
        added.push(item);
      }
    });
    const resolved = exactResolved.filter((_item, index) => !usedResolved.has(index));
    levelChanged.sort((a, b) => (LEVEL_RANK[b.new.level] || 0) - (LEVEL_RANK[a.new.level] || 0));
    const oldCounts = countsFor(oldResult, oldItems);
    const newCounts = countsFor(newResult, newItems);
    const oldScore = typeof oldSafe.score === "number" ? oldSafe.score : null;
    const newScore = typeof newSafe.score === "number" ? newSafe.score : null;
    return {
      old: {
        counts: oldCounts,
        score: oldScore,
        contractType: oldSafe.contractType || "",
        stanceLabel: oldSafe.stanceLabel || "",
      },
      new: {
        counts: newCounts,
        score: newScore,
        contractType: newSafe.contractType || "",
        stanceLabel: newSafe.stanceLabel || "",
      },
      delta: {
        high: newCounts.high - oldCounts.high,
        mid: newCounts.mid - oldCounts.mid,
        low: newCounts.low - oldCounts.low,
        score: oldScore != null && newScore != null ? newScore - oldScore : null,
      },
      added: sortRisks(added),
      resolved: sortRisks(resolved),
      levelChanged: levelChanged,
    };
  }

  function compareContracts(oldText, newText, opts) {
    const oldSource = String(oldText || "").trim();
    const newSource = String(newText || "").trim();
    if (!oldSource || !newSource) return null;
    const options = opts || {};
    const oldSplit = splitItems(oldSource);
    const newSplit = splitItems(newSource);
    const oldItems = oldSplit.items;
    const newItems = newSplit.items;
    const oldKeys = oldItems.map((item) => itemKey(item, oldSplit.kind !== "clause"));
    const newKeys = newItems.map((item) => itemKey(item, newSplit.kind !== "clause"));
    const matches = lcsPairs(oldKeys, newKeys);
    const rows = [];

    function addGap(oldStart, oldEnd, newStart, newEnd) {
      const oldGap = oldItems.slice(oldStart, oldEnd);
      const newGap = newItems.slice(newStart, newEnd);
      const pairs = pairGap(oldGap, newGap);
      const paired = new Set(pairs.map((pair) => pair[0]));
      const usedNew = new Set(pairs.map((pair) => pair[1]));
      pairs
        .slice()
        .sort((a, b) => a[0] - b[0])
        .forEach((pair) => {
          rows.push(makeRow(oldGap[pair[0]], newGap[pair[1]]));
        });
      oldGap.forEach((item, index) => {
        if (!paired.has(index)) rows.push(makeRow(item, null));
      });
      newGap.forEach((item, index) => {
        if (!usedNew.has(index)) rows.push(makeRow(null, item));
      });
    }

    let oldCursor = 0;
    let newCursor = 0;
    matches.forEach((pair) => {
      addGap(oldCursor, pair[0], newCursor, pair[1]);
      rows.push(makeRow(oldItems[pair[0]], newItems[pair[1]]));
      oldCursor = pair[0] + 1;
      newCursor = pair[1] + 1;
    });
    addGap(oldCursor, oldItems.length, newCursor, newItems.length);

    const summary = { same: 0, modified: 0, added: 0, removed: 0 };
    rows.forEach((row) => { summary[row.type]++; });
    const oldResult = options.oldResult || null;
    const newResult = options.newResult || null;
    return {
      oldTitle: firstTitle(oldSource),
      newTitle: firstTitle(newSource),
      oldLabel: options.oldLabel || "旧版",
      newLabel: options.newLabel || "新版",
      oldCount: oldItems.length,
      newCount: newItems.length,
      kind: oldSplit.kind === newSplit.kind ? oldSplit.kind : "mixed",
      rows: rows,
      summary: summary,
      risk: oldResult && newResult ? compareRisk(oldResult, newResult) : null,
    };
  }

  function levelClass(level) {
    return level === "高" ? "high" : level === "中" ? "mid" : "low";
  }

  function clauseLabel(index) {
    const n = Number(index) || 0;
    return n > 0 ? "第 " + n + " 条" : "缺失条款";
  }

  function signed(n) {
    if (n == null) return "—";
    return n > 0 ? "+" + n : String(n);
  }

  function riskListHtml(items, emptyText, changed) {
    if (!items.length) return '<p class="compare-risk-empty">' + escape(emptyText) + "</p>";
    return '<ul class="compare-risk-list">' + items.map((item) => {
      if (changed) {
        return `<li><span class="compare-risk-level ${levelClass(item.new.level)}">${escape(item.old.level)} → ${escape(item.new.level)}</span>` +
          `<b>${escape(item.new.rule_name)}</b> ${escape(clauseLabel(item.new.clause_index))}</li>`;
      }
      return `<li><span class="compare-risk-level ${levelClass(item.level)}">${escape(item.level)}</span>` +
        `<b>${escape(item.rule_name)}</b> ${escape(clauseLabel(item.clause_index))}` +
        (item.risk_reason ? `<p>${escape(item.risk_reason)}</p>` : "") + "</li>";
    }).join("") + "</ul>";
  }

  function renderRisk(risk) {
    if (!risk) {
      return '<p class="compare-hint">两边都从历史审查记录或当前审查带入，才能比较风险变化；目前只显示文本差异。</p>';
    }
    const oldCounts = risk.old.counts;
    const newCounts = risk.new.counts;
    const delta = risk.delta;
    const mismatch = (risk.old.contractType && risk.new.contractType && risk.old.contractType !== risk.new.contractType) ||
      (risk.old.stanceLabel && risk.new.stanceLabel && risk.old.stanceLabel !== risk.new.stanceLabel);
    return `<div class="compare-risk">
      <div class="compare-risk-head">
        <h3>风险变化</h3>
        <span>旧版 ${escape(risk.old.contractType || "未标注类型")} · 新版 ${escape(risk.new.contractType || "未标注类型")}</span>
      </div>
      <div class="compare-risk-grid">
        <div class="compare-risk-box">
          <span>旧版</span>
          <b>高 ${oldCounts.high} · 中 ${oldCounts.mid} · 低 ${oldCounts.low}</b>
          <em>评分 ${risk.old.score == null ? "—" : risk.old.score}</em>
        </div>
        <div class="compare-risk-box">
          <span>新版</span>
          <b>高 ${newCounts.high} · 中 ${newCounts.mid} · 低 ${newCounts.low}</b>
          <em>评分 ${risk.new.score == null ? "—" : risk.new.score}</em>
        </div>
      </div>
      <p class="compare-risk-delta">高风险 ${signed(delta.high)} · 中风险 ${signed(delta.mid)} · 低风险 ${signed(delta.low)} · 评分 ${signed(delta.score)}</p>
      ${mismatch ? '<p class="compare-hint">两份审查的合同类型或审查视角不同，风险变化仅供参考。</p>' : ""}
      <div class="compare-risk-lists">
        <div><h4>新增风险</h4>${riskListHtml(risk.added, "没有新增风险。", false)}</div>
        <div><h4>已消除风险</h4>${riskListHtml(risk.resolved, "没有已消除风险。", false)}</div>
        <div><h4>等级变化</h4>${riskListHtml(risk.levelChanged, "没有等级变化。", true)}</div>
      </div>
    </div>`;
  }

  function renderCompareBody(result, opts) {
    if (!result) return "";
    const onlyChanged = !!(opts && opts.onlyChanged);
    const rows = result.rows.filter((row) => !onlyChanged || row.type !== "same");
    const summary = result.summary;
    let html = `<div class="compare-summary">
      <span class="compare-stat same"><b>${summary.same}</b> 未变化</span>
      <span class="compare-stat modified"><b>${summary.modified}</b> 修改</span>
      <span class="compare-stat added"><b>${summary.added}</b> 新增</span>
      <span class="compare-stat removed"><b>${summary.removed}</b> 删除</span>
      <span class="compare-count">旧版 ${result.oldCount} 条 · 新版 ${result.newCount} 条</span>
    </div>`;
    html += renderRisk(result.risk);
    html += `<div class="compare-diff-card">
      <div class="compare-diff-head"><h3>条款差异</h3><span>${onlyChanged ? "只看变化" : "全部条款"}</span></div>`;
    if (!rows.length) {
      html += '<p class="compare-empty-row">两版条款没有差异。</p>';
    } else {
      rows.forEach((row) => {
        const badge = row.type === "same" ? "未变" : row.type === "modified" ? "修改" : row.type === "added" ? "新增" : "删除";
        const oldTitle = row.oldTitle || "（无）";
        const newTitle = row.newTitle || "（无）";
        const title = row.oldTitle && row.newTitle && row.oldTitle !== row.newTitle
          ? escape(oldTitle) + " → " + escape(newTitle)
          : escape(row.oldTitle || row.newTitle || "未命名条款");
        html += `<div class="compare-row ${row.type}">
          <div class="compare-row-head">
            <span class="compare-badge ${row.type}">${badge}</span>
            <span>${title}</span>
          </div>
          <table class="compare-row-body"><tr>
            <td class="compare-side old"><span class="compare-side-label">旧版</span><div class="compare-diff-text">${row.oldHtml || "（无）"}</div></td>
            <td class="compare-side new"><span class="compare-side-label">新版</span><div class="compare-diff-text">${row.newHtml || "（无）"}</div></td>
          </tr></table>
        </div>`;
      });
    }
    html += "</div>";
    html += '<p class="compare-hint">对比结果仅作辅助，不构成法律意见；正式签署前请由执业律师复核。</p>';
    return html;
  }

  // Word 导入 HTML 时会把 <del> 当修订删除处理，旧版差异整段消失；
  // 导出前换成普通 span 删除线，屏幕端仍保留语义化的 <del>/<ins>。
  function wordDiff(html) {
    return String(html || "")
      .replace(/<del>/g, '<span class="diff-del">')
      .replace(/<\/del>/g, "</span>")
      .replace(/<ins>/g, '<span class="diff-ins">')
      .replace(/<\/ins>/g, "</span>");
  }

  function buildCompareHtml(result, meta) {
    const css = `
      @page WordSection1 { size:21.0cm 29.7cm; margin:2.0cm 2.2cm; }
      div.WordSection1 { page:WordSection1; }
      body { font-family:"宋体",SimSun,serif; font-size:10.5pt; line-height:1.7; color:#111; margin:0; }
      h1 { font-family:"黑体",SimHei,sans-serif; font-size:18pt; text-align:center; margin:0 0 6pt; }
      h3 { font-size:12pt; margin:12pt 0 6pt; }
      h4 { font-size:10.5pt; margin:8pt 0 4pt; }
      .compare-meta, .compare-hint { color:#666; font-size:9pt; line-height:1.5; }
      .compare-summary { margin:10pt 0; }
      .compare-stat { display:inline-block; margin:0 8pt 4pt 0; padding:2pt 6pt; border:1pt solid #ccc; }
      .compare-stat.modified { border-color:#b9842f; }
      .compare-stat.added { border-color:#2f7d5c; }
      .compare-stat.removed { border-color:#b24a4a; }
      .compare-count { color:#666; font-size:9pt; margin-left:6pt; }
      .compare-risk { margin:10pt 0; padding:8pt; border:1pt solid #ddd; }
      .compare-risk-head { margin-bottom:6pt; }
      .compare-risk-head h3 { margin:0 0 2pt; }
      .compare-risk-head span { color:#666; font-size:9pt; }
      .compare-risk-grid { width:100%; margin:6pt 0; }
      .compare-risk-box { display:inline-block; width:45%; margin-right:3%; padding:5pt; border:1pt solid #ddd; vertical-align:top; }
      .compare-risk-box span { display:block; color:#666; font-size:9pt; }
      .compare-risk-box b { display:block; margin:3pt 0; }
      .compare-risk-box em { color:#666; font-size:9pt; font-style:normal; }
      .compare-risk-delta { margin:5pt 0; color:#333; }
      .compare-risk-lists div { margin:4pt 0; }
      .compare-risk-list { margin:0; padding-left:16pt; }
      .compare-risk-list li { margin:3pt 0; }
      .compare-risk-list p { margin:2pt 0 0; color:#555; font-size:9pt; }
      .compare-risk-level { display:inline-block; min-width:14pt; margin-right:4pt; padding:0 3pt; border:1pt solid #bbb; text-align:center; font-size:8.5pt; }
      .compare-risk-level.high { color:#a33; border-color:#d9a0a0; }
      .compare-risk-level.mid { color:#8a6a1f; border-color:#dcc58e; }
      .compare-risk-level.low { color:#2f6b50; border-color:#a9ccb9; }
      .compare-risk-empty { color:#666; font-size:9pt; margin:2pt 0; }
      .compare-diff-card { margin-top:12pt; }
      .compare-diff-head { margin-bottom:6pt; }
      .compare-diff-head h3 { display:inline; margin:0; }
      .compare-diff-head span { color:#666; font-size:9pt; margin-left:6pt; }
      .compare-row { margin:0 0 8pt; page-break-inside:avoid; }
      .compare-row-head { margin-bottom:2pt; page-break-after:avoid; }
      .compare-badge { display:inline-block; margin-right:5pt; padding:0 4pt; border:1pt solid #bbb; font-size:8.5pt; }
      .compare-badge.modified { color:#8a6a1f; border-color:#dcc58e; }
      .compare-badge.added { color:#2f6b50; border-color:#a9ccb9; }
      .compare-badge.removed { color:#a33; border-color:#d9a0a0; }
      .compare-row-body { width:100%; border-collapse:collapse; table-layout:fixed; page-break-inside:avoid; }
      .compare-row-body tr { page-break-inside:avoid; }
      .compare-side { width:50%; vertical-align:top; padding:5pt; border:1pt solid #ddd; }
      .compare-side-label { display:block; color:#666; font-size:8.5pt; margin-bottom:3pt; }
      .compare-diff-text { white-space:normal; }
      span.diff-del { color:#a33; text-decoration:line-through; }
      span.diff-ins { color:#1f6b4f; text-decoration:none; background:#eaf7ef; }
      .compare-empty-row { color:#666; }
      .compare-disclaimer { margin-top:16pt; padding-top:6pt; border-top:1pt solid #ddd; color:#777; font-size:8.5pt; }
    `;
    const body = wordDiff(renderCompareBody(result, { onlyChanged: false }));
    return `<!DOCTYPE html><html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:w="urn:schemas-microsoft-com:office:word" xmlns="http://www.w3.org/TR/REC-html40"><head><meta charset="utf-8"><title>合同版本对比</title>
      <!--[if gte mso 9]><xml><w:WordDocument><w:View>Print</w:View><w:Zoom>100</w:Zoom><w:DoNotOptimizeForBrowser/></w:WordDocument></xml><![endif]-->
      <style>${css}</style></head><body><div class="WordSection1">
      <h1>合同版本对比</h1>
      <p class="compare-meta">${escape(meta || "")}</p>
      ${body}
      <p class="compare-disclaimer">${escape(DISCLAIMER)}</p>
      </div></body></html>`;
  }

  function buildCompareDocx(result, meta) {
    return WB.buildDocxFromHtml(buildCompareHtml(result, meta));
  }

  WB.compareContracts = compareContracts;
  WB.compareRisk = compareRisk;
  WB.renderCompareBody = renderCompareBody;
  WB.buildCompareHtml = buildCompareHtml;
  WB.buildCompareDocx = buildCompareDocx;
})(globalThis);
