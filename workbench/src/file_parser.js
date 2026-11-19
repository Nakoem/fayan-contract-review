/* 合同工作台 · 本地文件解析
 * PDF（文字层）/ DOCX / TXT / MD → 纯文本。
 * 文件只在本机解析，不上传；解析器本身来自内联 vendor。
 */
(function (root) {
  const WB = (root.WB = root.WB || {});

  const MAX_FILE_BYTES = 25 * 1024 * 1024;
  const MAX_TEXT_CHARS = 50000;
  const MAX_TEXT_HARD = 200000;
  const MAX_PDF_PAGES = 300;

  WB.PARSE_LIMITS = {
    maxFileBytes: MAX_FILE_BYTES,
    maxTextChars: MAX_TEXT_CHARS,
    maxPdfPages: MAX_PDF_PAGES,
  };

  // Chrome / Word 导出的部分 PDF 会把汉字映射成康熙部首，统一还原成常用字。
  const RADICAL_FIX = {
    "⺠": "民", "⻅": "见", "⻔": "门", "⻢": "马", "⻋": "车",
    "⻛": "风", "⻥": "鱼", "⻦": "鸟", "⻰": "龙", "⻮": "齿",
    "⾦": "金", "⾼": "高", "⾏": "行", "⾯": "面", "⾝": "身",
    "⼀": "一", "⼄": "乙", "⼆": "二", "⼈": "人", "⼤": "大",
    "⼩": "小", "⼯": "工", "⽅": "方", "⽆": "无", "⽇": "日",
    "⽉": "月", "⽔": "水", "⽹": "网", "⽣": "生", "⽤": "用",
    "⽬": "目", "⽯": "石", "⽴": "立", "⽶": "米", "⽺": "羊",
    "⽼": "老", "⽿": "耳", "⾁": "肉", "⾃": "自", "⾄": "至",
    "⾊": "色", "⾍": "虫", "⾎": "血", "⾐": "衣", "⾓": "角",
    "⾔": "言", "⾕": "谷", "⾖": "豆", "⾙": "贝", "⾜": "足",
    "⾞": "车", "⾟": "辛", "⾥": "里", "⾨": "门", "⾬": "雨",
    "⾮": "非", "⾳": "音", "⾴": "页", "⾵": "风", "⾷": "食",
    "⾸": "首", "⾺": "马", "⾻": "骨", "⿁": "鬼", "⿂": "鱼",
    "⿃": "鸟", "⿅": "鹿", "⿆": "麦", "⿈": "黄", "⿊": "黑",
  };

  function parseError(code, message) {
    const e = new Error(message);
    e.code = code;
    return e;
  }

  function fixText(input) {
    let t = String(input || "").replace(/\u0000/g, "");
    if (t.normalize) t = t.normalize("NFKC");
    const radicalRe = new RegExp(
      "[" + String.fromCharCode(0x2e80) + "-" + String.fromCharCode(0x2fdf) + "]",
      "g"
    );
    t = t.replace(radicalRe, (ch) => RADICAL_FIX[ch] || ch);
    return t.replace(/[ \t]+\n/g, "\n").replace(/\n{3,}/g, "\n\n").trim();
  }

  // ───────────────────────── PDF ─────────────────────────

  let pdfLibPromise = null;

  function base64ToBlob(id) {
    const el = document.getElementById(id);
    if (!el) throw parseError("parser_missing", "PDF 解析器未加载，请重新构建页面");
    const bin = atob(el.textContent.trim());
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return new Blob([bytes], { type: "text/javascript" });
  }

  function loadPdfLib() {
    if (!pdfLibPromise) {
      pdfLibPromise = (async () => {
        const mainUrl = URL.createObjectURL(base64ToBlob("pdfjs-main"));
        const workerUrl = URL.createObjectURL(base64ToBlob("pdfjs-worker"));
        const mod = await import(mainUrl);
        mod.GlobalWorkerOptions.workerSrc = workerUrl;
        return mod;
      })();
    }
    return pdfLibPromise;
  }

  function appendPdfItem(text, str) {
    if (!str) return text;
    const prev = text ? text[text.length - 1] : "";
    const next = str[0];
    // 中文之间不插空格；英文/数字之间保留一个空格。
    if (/[A-Za-z0-9]/.test(prev) && /[A-Za-z0-9]/.test(next)) text += " ";
    return text + str;
  }

  async function parsePdf(file) {
    const mod = await loadPdfLib();
    let pdf;
    try {
      const buf = await file.arrayBuffer();
      pdf = await mod.getDocument({
        data: new Uint8Array(buf),
        isEvalSupported: false,
      }).promise;
    } catch (e) {
      const msg = String((e && e.message) || e);
      if ((e && e.name === "PasswordException") || /password/i.test(msg)) {
        throw parseError("pdf_password", "这份 PDF 有密码，请先解除密码后再上传");
      }
      throw parseError("pdf_parse", "PDF 解析失败：" + msg);
    }

    try {
      if (pdf.numPages > MAX_PDF_PAGES) {
        throw parseError("pdf_pages", "PDF 页数过多（" + pdf.numPages + " 页），请拆分后再上传");
      }

      const parts = [];
      const emptyPages = [];
      for (let p = 1; p <= pdf.numPages; p++) {
        let text = "";
        try {
          const page = await pdf.getPage(p);
          const content = await page.getTextContent();
          let lastY = null;
          for (const item of content.items || []) {
            if (!item || typeof item.str !== "string") continue;
            const y = item.transform ? item.transform[5] : null;
            const h = item.height || 10;
            if (lastY !== null && y !== null && Math.abs(y - lastY) > Math.max(3, h * 0.5)) {
              text += "\n";
            }
            text = appendPdfItem(text, item.str);
            if (y !== null) lastY = y;
          }
        } catch (e) {
          // 单页失败不拖垮整份文件，按空白页处理。
        }
        const clean = fixText(text);
        if (clean) parts.push(clean);
        else emptyPages.push(p);
      }

      const text = fixText(parts.join("\n\n"));
      const warnings = [];
      if (emptyPages.length && emptyPages.length < pdf.numPages) {
        const shown = emptyPages.slice(0, 6).join("、");
        warnings.push(
          "第 " + shown + (emptyPages.length > 6 ? " 等" : "") + " 页没有文字层，可能是扫描页，已跳过"
        );
      }
      if (!text || text.length < 50) {
        throw parseError(
          "pdf_scanned",
          "这份 PDF 没有可提取的文字层，可能是扫描件。V1 暂不支持 OCR，请粘贴文字或上传 DOCX。"
        );
      }
      return { text, warnings, meta: { pages: pdf.numPages, emptyPages } };
    } finally {
      try { await pdf.destroy(); } catch (e) { /* ignore */ }
    }
  }

  // ───────────────────────── DOCX / TXT ─────────────────────────

  async function parseDocx(file) {
    if (!root.mammoth || typeof root.mammoth.extractRawText !== "function") {
      throw parseError("parser_missing", "DOCX 解析器未加载，请重新构建页面");
    }
    let result;
    try {
      result = await root.mammoth.extractRawText({ arrayBuffer: await file.arrayBuffer() });
    } catch (e) {
      throw parseError("docx_parse", "DOCX 解析失败：" + ((e && e.message) || e));
    }
    const text = fixText(result.value);
    if (!text) throw parseError("docx_empty", "这份 DOCX 没有可提取的文字");
    const warnings = (result.messages || [])
      .filter((m) => m && m.type === "warning")
      .map((m) => m.message)
      .slice(0, 3);
    return { text, warnings, meta: {} };
  }

  async function parsePlain(file) {
    const text = fixText(await file.text());
    if (!text) throw parseError("text_empty", "文件是空的");
    return { text, warnings: [], meta: {} };
  }

  WB.parseFile = async function (file) {
    if (!file) throw parseError("no_file", "没有选择文件");
    if (file.size > MAX_FILE_BYTES) {
      throw parseError("too_large", "文件超过 25MB，请拆分后再上传");
    }

    const name = String(file.name || "");
    const match = name.match(/\.([^.]+)$/);
    const ext = match ? match[1].toLowerCase() : "";
    let result;
    if (ext === "pdf") result = await parsePdf(file);
    else if (ext === "docx") result = await parseDocx(file);
    else if (ext === "txt" || ext === "md") result = await parsePlain(file);
    else if (ext === "doc") {
      throw parseError("doc_legacy", "暂不支持 .doc，请另存为 .docx 或直接粘贴文字");
    } else {
      throw parseError("unsupported", "暂不支持这种文件，请上传 PDF / DOCX / TXT");
    }

    result.fileName = name;
    result.fileType = ext;
    if (result.text.length > MAX_TEXT_HARD) {
      throw parseError("text_huge", "提取文字超过 20 万字，请拆分后再上传");
    }
    if (result.text.length > MAX_TEXT_CHARS) {
      result.warnings = (result.warnings || []).concat(
        "提取了 " + result.text.length + " 字，超过 5 万字上限，请拆分后再审"
      );
    }
    return result;
  };
})(globalThis);
