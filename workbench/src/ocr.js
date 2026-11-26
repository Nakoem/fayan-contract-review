/* 合同工作台 · 扫描件 OCR
 * 只在用户主动点「识别文字」时调用视觉模型；图片不会自动上传。
 * 复用当前服务商 / 模型 / Key，不新增一套 OCR 配置。
 */
(function (root) {
  const WB = (root.WB = root.WB || {});

  const OCR_PROMPT =
    "你是合同 OCR。请逐字提取图片中的全部文字，保留条款编号、段落和表格顺序；" +
    "不要总结、不要解释、不要补全缺失内容。只输出识别到的文字。";

  const MAX_OCR_TEXT = 200000;

  function ocrError(code, message) {
    const e = new Error(message);
    e.code = code;
    return e;
  }

  function cleanOcrText(text) {
    return String(text || "")
      .replace(/^\s*```[a-z0-9_-]*\s*/i, "")
      .replace(/```\s*$/i, "")
      .replace(/\r\n/g, "\n")
      .trim();
  }

  WB.ocrImage = async function (dataUrl, settings, opts) {
    const options = opts || {};
    const s = settings || {};
    const providerKey = s.provider || "dashscope";
    const preset = WB.PROVIDERS[providerKey];
    if (!preset) throw ocrError("ocr_provider", "当前服务商不支持 OCR，请切换到 DashScope / DeepSeek");
    const apiKey = (s.apiKeys || {})[providerKey] || "";
    if (!apiKey) throw ocrError("ocr_key", "还没有配置 " + preset.label + " 的 API Key");
    if (!dataUrl || String(dataUrl).indexOf("data:image/") !== 0) {
      throw ocrError("ocr_image", "图片格式无法识别");
    }

    let res;
    try {
      res = await WB.callLLM({
        baseUrl: s.baseUrl || preset.baseUrl,
        apiKey,
        model: s.model || preset.model,
        messages: [
          {
            role: "user",
            content: [
              { type: "text", text: OCR_PROMPT },
              { type: "image_url", image_url: { url: dataUrl, detail: "high" } },
            ],
          },
        ],
        maxTokens: 2000,
        jsonMode: false,
        timeoutMs: 120000,
        retries: 0,
        signal: options.signal,
        extraBody: preset.extraBody || null,
      });
    } catch (e) {
      if (e && e.code === "auth") {
        throw ocrError(
          "ocr_auth",
          "OCR 的 API Key 被拒绝。如果 Key 来自阿里云百炼，请把服务商切到 DashScope；" +
            "如果用的是 DeepSeek 官方 Key，请切到 DeepSeek。"
        );
      }
      if (e && e.code === "http") {
        throw ocrError(
          "ocr_model",
          "OCR 请求失败，当前模型可能不支持图片输入。请切换到支持视觉的模型（如 deepseek-v4.1-flash / deepseek-flash / qwen3.6-flash）。" +
            "（" + e.message + "）"
        );
      }
      if (e && e.code === "rate") {
        throw ocrError("ocr_rate", "OCR 请求太频繁或额度不足，请稍后再试");
      }
      if (e && e.code === "timeout") {
        throw ocrError("ocr_timeout", "OCR 单页识别超时，请稍后重试或减少页数");
      }
      throw e;
    }

    const text = cleanOcrText(res.content);
    if (!text) throw ocrError("ocr_empty", "这一页没有识别到文字，请换一张更清晰的照片或检查扫描件");
    return text;
  };

  WB.ocrFile = async function (file, settings, opts) {
    const options = opts || {};
    if (!file) throw ocrError("ocr_file", "没有待识别的文件");
    const name = String(file.name || "");
    const match = name.match(/\.([^.]+)$/);
    const ext = match ? match[1].toLowerCase() : "";
    const isImage = ext === "jpg" || ext === "jpeg" || ext === "png" || ext === "webp";
    const isPdf = ext === "pdf";
    if (!isImage && !isPdf) {
      throw ocrError("ocr_type", "OCR 只支持扫描 PDF 和 JPG / PNG / WEBP 图片");
    }

    let pages;
    if (isImage) {
      if (options.onProgress) options.onProgress({ phase: "render", page: 1, total: 1 });
      const image = await WB.imageFileToDataUrl(file, { maxWidth: 1600, quality: 0.82 });
      pages = [image.dataUrl];
    } else {
      pages = await WB.renderPdfPageImages(file, {
        maxPages: (WB.PARSE_LIMITS && WB.PARSE_LIMITS.maxOcrPages) || 30,
        signal: options.signal,
        onProgress: (page, total) => {
          if (options.onProgress) options.onProgress({ phase: "render", page, total });
        },
      });
    }

    if (!pages.length) throw ocrError("ocr_empty", "没有可识别的页面");
    const texts = [];
    for (let i = 0; i < pages.length; i++) {
      if (options.signal && options.signal.aborted) {
        const err = new Error("已取消 OCR");
        err.code = "aborted";
        throw err;
      }
      if (options.onProgress) options.onProgress({ phase: "ocr", page: i + 1, total: pages.length });
      texts.push(await WB.ocrImage(pages[i], settings, { signal: options.signal }));
    }

    const text = texts.join("\n\n").trim();
    if (!text) throw ocrError("ocr_empty", "没有识别到合同文字，请检查图片是否清晰");
    if (text.length > MAX_OCR_TEXT) {
      throw ocrError("ocr_huge", "OCR 结果超过 20 万字，请拆分后再识别");
    }
    return { text: text, pages: pages.length, meta: { pages: pages.length } };
  };

  WB.OCR_PROMPT = OCR_PROMPT;
})(globalThis);
