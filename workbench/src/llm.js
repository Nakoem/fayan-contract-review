/* 合同工作台 · LLM 客户端
 * 浏览器与 Node 共用：只依赖 fetch / AbortController，不碰 DOM。
 */
(function (root) {
  const WB = (root.WB = root.WB || {});

  WB.PROVIDERS = {
    deepseek: {
      key: "deepseek",
      label: "DeepSeek",
      baseUrl: "https://api.deepseek.com",
      model: "deepseek-flash",
      note: "默认 · 浏览器直连可用",
    },
    dashscope: {
      key: "dashscope",
      label: "DashScope（通义）",
      baseUrl: "https://dashscope.aliyuncs.com/compatible-mode/v1",
      model: "qwen3.8-max-0902",
      note: "默认 · 浏览器直连可用",
      extraBody: { enable_thinking: false },
    },
  };

  function makeError(code, message, status) {
    const e = new Error(message);
    e.code = code;
    e.status = status;
    return e;
  }

  /* 从文本中提取第一个「平衡」的 JSON 对象/数组。
   * 处理模型把多个 JSON 拼接在一起、或前后带说明文字的情况。 */
  function extractFirstJSON(text) {
    for (let start = 0; start < text.length; start++) {
      const ch = text[start];
      if (ch !== "{" && ch !== "[") continue;

      let depth = 0;
      let inString = false;
      let escaped = false;
      for (let i = start; i < text.length; i++) {
        const c = text[i];
        if (inString) {
          if (escaped) escaped = false;
          else if (c === "\\") escaped = true;
          else if (c === '"') inString = false;
          continue;
        }
        if (c === '"') { inString = true; continue; }
        if (c === "{" || c === "[") depth += 1;
        else if (c === "}" || c === "]") {
          depth -= 1;
          if (depth === 0) return text.slice(start, i + 1);
          if (depth < 0) break;
        }
      }
    }
    return null;
  }

  /* 移植 utils.repair_json 的策略，另加代码围栏清理 + 平衡 JSON 提取 */
  WB.repairJSON = function (text) {
    if (!text || !text.trim()) return null;
    let t = text.trim().replace(/^﻿/, "");
    t = t.replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/, "").trim();

    const tryParse = (s) => {
      try { JSON.parse(s); return s; } catch (e) { return null; }
    };

    let ok = tryParse(t);
    if (ok) return ok;

    // 1) 首个平衡 JSON（可处理多 JSON 拼接 / 前后说明文字）
    const balanced = extractFirstJSON(t);
    if (balanced) {
      ok = tryParse(balanced);
      if (ok) return ok;
      const fixedBalanced = balanced.replace(/,\s*([}\]])/g, "$1");
      ok = tryParse(fixedBalanced);
      if (ok) return ok;
    }

    // 2) 尾逗号
    const repaired = t.replace(/,\s*([}\]])/g, "$1");
    ok = tryParse(repaired);
    if (ok) return ok;

    // 3) 最外层 {...} / [...]
    const objMatch = repaired.match(/\{[\s\S]*\}/);
    if (objMatch) {
      ok = tryParse(objMatch[0]);
      if (ok) return ok;
    }
    const arrMatch = repaired.match(/\[[\s\S]*\]/);
    if (arrMatch) {
      ok = tryParse(arrMatch[0]);
      if (ok) return ok;
    }

    // 4) 单引号 → 双引号
    const squoted = repaired.replace(/'/g, '"');
    ok = tryParse(squoted);
    if (ok) return ok;

    return null;
  };

  WB.parseJSON = function (text) {
    const fixed = WB.repairJSON(text);
    if (!fixed) return null;
    try { return JSON.parse(fixed); } catch (e) { return null; }
  };

  function buildUrl(baseUrl) {
    const base = String(baseUrl || "").replace(/\/+$/, "");
    return /\/chat\/completions$/.test(base) ? base : base + "/chat/completions";
  }

  async function doFetch(url, apiKey, payload, timeoutMs, outerSignal) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort("timeout"), timeoutMs);
    const onAbort = () => controller.abort("user");
    if (outerSignal) outerSignal.addEventListener("abort", onAbort, { once: true });

    try {
      return await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer " + apiKey,
        },
        body: JSON.stringify(payload),
        signal: controller.signal,
      });
    } catch (err) {
      if (err && err.name === "AbortError") {
        if (controller.signal.reason === "timeout") {
          throw makeError("timeout", "请求超时（" + Math.round(timeoutMs / 1000) + " 秒）");
        }
        throw makeError("aborted", "已取消");
      }
      throw makeError("network", "网络请求失败：" + (err && err.message ? err.message : err));
    } finally {
      clearTimeout(timer);
      if (outerSignal) outerSignal.removeEventListener("abort", onAbort);
    }
  }

  /**
   * 调用 OpenAI 兼容接口
   * @returns {Promise<{content:string, usage:object|null}>}
   */
  WB.callLLM = async function ({
    baseUrl,
    apiKey,
    model,
    messages,
    maxTokens = 3000,
    jsonMode = true,
    timeoutMs = 120000,
    retries = 1,
    signal,
    extraBody = null,
  }) {
    if (!apiKey) throw makeError("no_key", "未配置 API Key");
    if (!model) throw makeError("no_model", "未配置模型名");

    const url = buildUrl(baseUrl);
    const basePayload = Object.assign({}, extraBody || {}, {
      model,
      messages,
      temperature: 0,
      max_tokens: maxTokens,
      stream: false,
    });

    let lastErr = null;
    for (let attempt = 0; attempt <= retries; attempt++) {
      if (signal && signal.aborted) throw makeError("aborted", "已取消");

      let res;
      try {
        res = await doFetch(
          url,
          apiKey,
          jsonMode ? Object.assign({}, basePayload, { response_format: { type: "json_object" } }) : basePayload,
          timeoutMs,
          signal
        );

        // 有些服务商/模型不支持 JSON mode：去掉该字段再试一次
        if (res.status === 400 && jsonMode) {
          res = await doFetch(url, apiKey, basePayload, timeoutMs, signal);
        }
      } catch (err) {
        lastErr = err;
        if (err.code === "aborted" || err.code === "auth") throw err;
        if (attempt < retries) { await sleep(1000 * (attempt + 1)); continue; }
        throw err;
      }

      if (!res.ok) {
        const bodyText = await res.text().catch(() => "");
        let detail = bodyText;
        try {
          const j = JSON.parse(bodyText);
          detail = (j.error && (j.error.message || j.error.code)) || j.message || bodyText;
        } catch (e) { /* keep raw */ }
        detail = String(detail || "").slice(0, 300);

        if (res.status === 401 || res.status === 403) {
          throw makeError("auth", "API Key 无效或无权限（HTTP " + res.status + "）", res.status);
        }
        if (res.status === 429) {
          lastErr = makeError("rate", "请求太频繁（HTTP 429）", 429);
          if (attempt < retries) { await sleep(1500 * (attempt + 1)); continue; }
          throw lastErr;
        }
        if (res.status >= 500) {
          lastErr = makeError("server", "服务商异常（HTTP " + res.status + "）", res.status);
          if (attempt < retries) { await sleep(1500 * (attempt + 1)); continue; }
          throw lastErr;
        }
        throw makeError("http", "请求失败（HTTP " + res.status + "）：" + detail, res.status);
      }

      let data;
      try { data = await res.json(); }
      catch (e) { throw makeError("format", "响应不是合法 JSON"); }

      const content =
        data && data.choices && data.choices[0] && data.choices[0].message
          ? data.choices[0].message.content
          : "";
      if (!content) throw makeError("format", "服务商返回空内容");

      return { content, usage: (data && data.usage) || null };
    }

    throw lastErr || makeError("unknown", "请求失败");
  };

  function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
})(globalThis);
