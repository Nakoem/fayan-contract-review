/* 合同工作台 · 规则包（L3）
 * 只打包「内置规则覆盖 + 自定义规则」，接收方仍使用自己的内置规则版本。
 */
(function (root) {
  const WB = (root.WB = root.WB || {});

  const APP = "contract-workbench-rules";
  const VERSION = 1;

  function cleanName(value) {
    return String(value == null ? "" : value).trim().slice(0, 60) || "未命名规则包";
  }

  function buildRulePack(ruleState, meta) {
    const state = ruleState || {};
    const info = meta || {};
    return {
      app: APP,
      version: VERSION,
      name: cleanName(info.name),
      note: String(info.note || "").trim().slice(0, 300),
      exportedAt: new Date().toISOString(),
      overrides: state.overrides && typeof state.overrides === "object" ? state.overrides : {},
      custom: Array.isArray(state.custom) ? state.custom : [],
    };
  }

  function parseRulePack(text) {
    let raw;
    try { raw = JSON.parse(String(text || "")); }
    catch (e) { throw new Error("规则包不是合法 JSON"); }
    if (!raw || typeof raw !== "object") throw new Error("规则包内容不是对象");
    if (raw.app !== APP) throw new Error("这不是合同工作台的规则包");
    if (Number(raw.version) !== VERSION) throw new Error("规则包版本不支持：" + raw.version);
    return {
      name: cleanName(raw.name),
      note: String(raw.note || "").trim().slice(0, 300),
      overrides: raw.overrides && typeof raw.overrides === "object" ? raw.overrides : {},
      custom: Array.isArray(raw.custom) ? raw.custom : [],
    };
  }

  WB.RulePack = {
    APP,
    VERSION,
    build: buildRulePack,
    parse: parseRulePack,
  };
})(globalThis);
