/* 合同工作台 · 本机备份
 * 只导出数据与设置，不导出 API Key；JSON 文件由用户自己保管。
 */
(function (root) {
  const WB = (root.WB = root.WB || {});

  const APP = "contract-workbench";
  const VERSION = 1;
  const MAX_RECORDS = 500;

  function backupError(message) {
    const e = new Error(message);
    e.code = "backup_invalid";
    return e;
  }

  function safeSettings(settings) {
    const s = settings || {};
    return {
      provider: s.provider || "dashscope",
      model: s.model || "",
      masking: s.masking !== false,
      hiddenNames: Array.isArray(s.hiddenNames) ? s.hiddenNames.slice(0, 200) : [],
      contractType: s.contractType || "房屋租赁合同",
      stance: s.stance || "neutral",
    };
  }

  function cleanRecords(list, kind) {
    const out = [];
    (Array.isArray(list) ? list : []).forEach((item) => {
      if (!item || typeof item !== "object" || typeof item.id !== "string" || !item.id) return;
      out.push(item);
    });
    if (out.length > MAX_RECORDS) {
      throw backupError(kind + "超过 " + MAX_RECORDS + " 条，备份文件可能被篡改或过大");
    }
    return out;
  }

  WB.buildBackup = function (payload) {
    const p = payload || {};
    // 导出与导入共用同一个上限，避免导出的备份自己无法导入。
    const reviews = Array.isArray(p.reviews) ? p.reviews.slice(0, MAX_RECORDS) : [];
    const ledger = Array.isArray(p.ledger) ? p.ledger.slice(0, MAX_RECORDS) : [];
    return {
      app: APP,
      version: VERSION,
      exportedAt: new Date().toISOString(),
      data: {
        settings: safeSettings(p.settings),
        reviews: reviews,
        ledger: ledger,
        rules: p.rules && typeof p.rules === "object" ? p.rules : null,
        current: p.current && typeof p.current === "object" ? p.current : null,
      },
    };
  };

  WB.validateBackup = function (raw) {
    if (!raw || typeof raw !== "object") throw backupError("备份文件不是对象");
    if (raw.app !== APP) throw backupError("这不是合同工作台的备份文件");
    if (Number(raw.version) !== VERSION) throw backupError("备份版本不支持：" + raw.version);
    const data = raw.data;
    if (!data || typeof data !== "object") throw backupError("备份文件缺少 data");
    const rules = data.rules && typeof data.rules === "object" ? data.rules : null;
    const current = data.current && typeof data.current === "object" ? data.current : null;
    return {
      exportedAt: String(raw.exportedAt || ""),
      settings: safeSettings(data.settings),
      reviews: cleanRecords(data.reviews, "审查历史"),
      ledger: cleanRecords(data.ledger, "合同台账"),
      rules: rules,
      current: current,
    };
  };

  WB.parseBackup = function (text) {
    let raw;
    try {
      raw = JSON.parse(String(text || ""));
    } catch (e) {
      throw backupError("备份文件不是合法 JSON");
    }
    return WB.validateBackup(raw);
  };

  WB.BACKUP_VERSION = VERSION;
})(globalThis);
