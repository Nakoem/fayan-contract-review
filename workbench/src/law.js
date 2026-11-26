/* 合同工作台 · 法条速查
 * 只用构建时内联的法规库做本地检索，不联网、不调用模型。
 * 中文按「单字 + 双字」切词，套一个轻量 BM25。
 */
(function (root) {
  const WB = (root.WB = root.WB || {});

  const CATEGORIES = ["全部", "法规", "判例", "地方", "税务", "新规"];

  const SOURCES = [
    { key: "regulation", category: "法规", label: "法规 / 法条" },
    { key: "caseLaw", category: "判例", label: "参考判例" },
    { key: "localPolicy", category: "地方", label: "地方政策" },
    { key: "taxRule", category: "税务", label: "税务口径" },
    { key: "webKb", category: "新规", label: "新规动态" },
  ];

  const K1 = 1.2;
  const B = 0.75;

  function tokenize(text) {
    const s = String(text || "").toLowerCase();
    const out = [];
    const ascii = s.match(/[a-z0-9]{2,}/g) || [];
    ascii.forEach((word) => out.push(word));
    const runs = s.match(/[一-鿿]+/g) || [];
    runs.forEach((run) => {
      for (let i = 0; i < run.length; i++) {
        out.push(run.charAt(i));
        if (i + 1 < run.length) out.push(run.slice(i, i + 2));
      }
    });
    return out;
  }

  /** 查询词只取双字（单字查询才取单字），避免常用单字把无关文档全捞出来。 */
  function queryTokens(text) {
    const s = String(text || "").toLowerCase();
    const out = [];
    const ascii = s.match(/[a-z0-9]{2,}/g) || [];
    ascii.forEach((word) => out.push(word));
    const runs = s.match(/[一-鿿]+/g) || [];
    runs.forEach((run) => {
      if (run.length === 1) {
        out.push(run);
        return;
      }
      for (let i = 0; i + 1 < run.length; i++) out.push(run.slice(i, i + 2));
    });
    return out;
  }

  function lawDocs() {
    const K = WB.KNOWLEDGE || {};
    const docs = [];
    SOURCES.forEach((source) => {
      const group = K[source.key];
      if (!group || typeof group !== "object") return;
      Object.keys(group).forEach((title) => {
        const text = String(group[title] || "").trim();
        if (!text) return;
        docs.push({
          id: source.key + ":" + title,
          source: source.key,
          category: source.category,
          label: source.label,
          title,
          text,
        });
      });
    });
    return docs;
  }

  function uniqueTokens(tokens) {
    const seen = {};
    const out = [];
    tokens.forEach((token) => {
      if (seen[token]) return;
      seen[token] = 1;
      out.push(token);
    });
    return out;
  }

  function prepare(doc) {
    const tokens = tokenize(doc.title + "\n" + doc.text);
    const counts = {};
    tokens.forEach((token) => { counts[token] = (counts[token] || 0) + 1; });
    return {
      doc,
      tokens,
      counts,
      length: tokens.length || 1,
      compact: (doc.title + "\n" + doc.text).replace(/\s+/g, "").toLowerCase(),
    };
  }

  function scoreDocs(qTokens, docs, qText) {
    const prepared = docs.map(prepare);
    const total = prepared.length;
    if (!total) return [];
    const avgLength = prepared.reduce((sum, item) => sum + item.length, 0) / total;
    const compactQuery = String(qText || "").replace(/\s+/g, "").toLowerCase();
    const need = Math.min(2, qTokens.length);
    const df = {};
    prepared.forEach((item) => {
      qTokens.forEach((token) => {
        if (item.counts[token]) df[token] = (df[token] || 0) + 1;
      });
    });
    return prepared.map((item) => {
      // 长查询至少命中两个双字词，或整串原样出现，避免单个常用词把整库捞出来。
      const hits = qTokens.filter((token) => item.counts[token]).length;
      const exact = compactQuery && item.compact.indexOf(compactQuery) >= 0;
      if (!exact && hits < need) return null;
      let score = 0;
      qTokens.forEach((token) => {
        const tf = item.counts[token] || 0;
        if (!tf) return;
        const n = df[token] || 0;
        const idf = Math.log(1 + (total - n + 0.5) / (n + 0.5));
        score += idf * (tf * (K1 + 1)) / (tf + K1 * (1 - B + B * (item.length / avgLength)));
      });
      // 标题命中额外加权，避免正文里偶然出现一次就排到最前。
      const title = item.doc.title.replace(/\s+/g, "").toLowerCase();
      if (compactQuery && title.indexOf(compactQuery) >= 0) score += 4;
      if (exact) score += 2;
      return { doc: item.doc, score };
    }).filter(Boolean).sort(
      (a, b) => b.score - a.score || a.doc.title.localeCompare(b.doc.title, "zh")
    );
  }

  function snippet(text, query, max) {
    const clean = String(text || "").replace(/\s+/g, " ").trim();
    if (!clean) return "";
    const limit = max || 120;
    const q = String(query || "").trim();
    const pos = q ? clean.indexOf(q) : -1;
    if (pos > 30) {
      const start = Math.max(0, pos - 24);
      return "…" + clean.slice(start, start + limit) + (clean.length > start + limit ? "…" : "");
    }
    return clean.slice(0, limit) + (clean.length > limit ? "…" : "");
  }

  /** query 为空时返回全部；category 为「全部」时不过滤。 */
  function searchLaw(query, category) {
    const q = String(query || "").trim();
    const cat = CATEGORIES.indexOf(category) >= 0 ? category : "全部";
    let docs = lawDocs();
    if (cat !== "全部") docs = docs.filter((doc) => doc.category === cat);
    if (!q) {
      return docs.map((doc) => ({ doc, score: 0, snippet: snippet(doc.text, "", 110) }));
    }
    const tokens = uniqueTokens(queryTokens(q));
    if (!tokens.length) return [];
    return scoreDocs(tokens, docs, q).map((item) => ({
      doc: item.doc,
      score: item.score,
      snippet: snippet(item.doc.text, q, 120),
    }));
  }

  function categoryCounts() {
    const docs = lawDocs();
    const counts = { 全部: docs.length };
    CATEGORIES.slice(1).forEach((cat) => {
      counts[cat] = docs.filter((doc) => doc.category === cat).length;
    });
    return counts;
  }

  WB.LAW_CATEGORIES = CATEGORIES;
  WB.lawDocs = lawDocs;
  WB.searchLaw = searchLaw;
  WB.lawCategoryCounts = categoryCounts;
  WB.lawTokenize = tokenize;
})(globalThis);
