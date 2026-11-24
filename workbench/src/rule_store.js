/* 合同工作台 · 审查规则存取（V1.5）
 * 只占用 settings store 的 "rules" 键：保存「内置规则覆盖 + 自定义规则」，
 * 不冻结内置内容，以后新增内置规则会自然出现。
 * 审查链路继续只读 WB.RULES，这里负责在启动时把状态合并进去。
 *
 * 写入策略：
 * - 每次保存携带上一次读到的 revision（updatedAt），存储层在事务里比对后再写，
 *   两个标签页同时保存时后写者会收到 conflict，不会静默覆盖先写者。
 * - 保存失败会回滚内存状态，界面不会出现“看起来改了、其实没存上”。
 */
(function (root) {
  const WB = (root.WB = root.WB || {});
  const clone = (v) => JSON.parse(JSON.stringify(v));

  const LEVELS = ["高", "中", "低"];
  const MAX_CUSTOM = 200;
  const BASIS_RE = /第[一二三四五六七八九十百千零〇\d]+条/;
  const BUILTIN = clone(WB.RULES || []);
  const BUILTIN_IDS = new Set(BUILTIN.map((r) => r.id));
  const TAB_ID = Date.now().toString(36) + Math.random().toString(36).slice(2, 6);

  let state = { overrides: {}, custom: [] };
  let revision = 0;
  let writeQueue = Promise.resolve();

  // 同一标签页内的修改串行执行：避免快速连续操作共用旧 revision 互相冲突。
  function serialize(task) {
    const run = writeQueue.then(task, task);
    writeQueue = run.then(() => {}, () => {});
    return run;
  }

  let channel = null;
  try {
    // Node 测试里也有 BroadcastChannel，会挂住事件循环；只在浏览器页面创建。
    if (root.BroadcastChannel && typeof root.document !== "undefined") {
      channel = new root.BroadcastChannel("contract-workbench-rules");
    }
  } catch (e) { channel = null; }
  if (channel) {
    channel.onmessage = (ev) => {
      const data = ev && ev.data;
      if (!data || data.type !== "rules-updated" || data.tabId === TAB_ID) return;
      WB.RuleStore.refresh()
        .then((changed) => {
          if (changed && typeof WB.RuleStore.onRemoteChange === "function") {
            WB.RuleStore.onRemoteChange();
          }
        })
        .catch(() => {});
    };
  }

  const text = (v, max) => String(v == null ? "" : v).trim().slice(0, max);

  function cleanKeywords(value) {
    const list = Array.isArray(value)
      ? value
      : String(value == null ? "" : value).split(/[,，、;；\n]/);
    const out = [];
    list.forEach((k) => {
      const s = text(k, 24);
      if (s && out.indexOf(s) < 0) out.push(s);
    });
    return out.slice(0, 20);
  }

  function cleanType(value) {
    const t = text(value, 20);
    return WB.CONTRACT_TYPES.indexOf(t) >= 0 || t === "通用" ? t : "通用";
  }

  function cleanLevel(value) {
    return LEVELS.indexOf(value) >= 0 ? value : "中";
  }

  function cleanFields(raw) {
    const src = raw && typeof raw === "object" ? raw : {};
    return {
      contractType: cleanType(src.contractType),
      name: text(src.name, 30),
      keywords: cleanKeywords(src.keywords),
      condition: text(src.condition, 240),
      level: cleanLevel(src.level),
      basis: text(src.basis, 80),
      advice: text(src.advice, 300),
      enabled: src.enabled !== false,
    };
  }

  function validate(raw) {
    const fields = cleanFields(raw);
    if (!fields.name) return { ok: false, message: "规则名称不能为空" };
    if (!fields.keywords.length) return { ok: false, message: "至少填写一个适用关键词" };
    if (!fields.condition) return { ok: false, message: "判定条件不能为空" };
    if (!fields.basis) return { ok: false, message: "法条依据不能为空" };
    if (!BASIS_RE.test(fields.basis)) {
      return { ok: false, message: "法条依据需包含具体条号，例如：民法典第585条" };
    }
    if (!fields.advice) return { ok: false, message: "建议话术不能为空" };
    return { ok: true, fields };
  }

  function normalizeCustom(raw, i) {
    const check = validate(raw);
    if (!check.ok) return null;
    const rawId = text(raw && raw.id, 60);
    const id = /^r_custom_[a-z0-9_-]+$/i.test(rawId)
      ? rawId
      : `r_custom_${Date.now().toString(36)}_${i}`;
    return Object.assign({ id, builtin: false, stance: null }, check.fields);
  }

  function normalizeState(raw) {
    const out = { overrides: {}, custom: [] };
    if (!raw || typeof raw !== "object") return out;
    const ov = raw.overrides && typeof raw.overrides === "object" ? raw.overrides : {};
    Object.keys(ov).forEach((id) => {
      if (!BUILTIN_IDS.has(id)) return;
      const check = validate(ov[id]);
      if (!check.ok) return;
      out.overrides[id] = check.fields;
    });
    const list = Array.isArray(raw.custom) ? raw.custom : [];
    list.slice(0, MAX_CUSTOM).forEach((item, i) => {
      const rule = normalizeCustom(item, i);
      if (rule) out.custom.push(rule);
    });
    return out;
  }

  function apply() {
    const rules = BUILTIN.map((base) => {
      const ov = state.overrides[base.id];
      const merged = Object.assign(clone(base), ov ? clone(ov) : {});
      merged.builtin = true;
      return merged;
    });
    state.custom.forEach((r) => rules.push(clone(r)));
    WB.RULES = rules;
    return WB.RULES;
  }

  function readPersisted() {
    return Promise.resolve()
      .then(() => WB.loadRuleState())
      .catch(() => null);
  }

  function applyPersisted(raw) {
    state = normalizeState(raw);
    revision = raw && typeof raw === "object" ? Number(raw.updatedAt) || 0 : 0;
    apply();
  }

  async function persist() {
    apply();
    const next = Math.max(Date.now(), revision + 1);
    const payload = { overrides: state.overrides, custom: state.custom, updatedAt: next };
    let result;
    try { result = await WB.saveRuleState(payload, revision); }
    catch (e) { result = { ok: false }; }
    if (result && result.ok) {
      revision = next;
      if (channel) {
        try { channel.postMessage({ type: "rules-updated", tabId: TAB_ID }); }
        catch (e) { /* 广播失败不影响本机保存 */ }
      }
      return { ok: true };
    }
    if (result && result.conflict) {
      const raw = await readPersisted();
      if (raw) {
        applyPersisted(raw);
        return { ok: false, reason: "conflict" };
      }
      return { ok: false, reason: "storage" };
    }
    return { ok: false, reason: "storage" };
  }

  async function saveWithRollback(before) {
    const saved = await persist();
    if (!saved.ok && saved.reason !== "conflict") {
      state = before;
      apply();
    }
    return saved;
  }

  WB.RuleStore = {
    builtinCount: BUILTIN.length,
    maxCustom: MAX_CUSTOM,
    onRemoteChange: null,

    builtinRules() {
      return clone(BUILTIN);
    },

    state() {
      return clone(state);
    },

    revision() {
      return revision;
    },

    find(id) {
      return (WB.RULES || []).filter((r) => r.id === id)[0] || null;
    },

    hasOverride(id) {
      return !!state.overrides[id];
    },

    validate,

    applyState(raw) {
      applyPersisted(raw);
      return WB.RULES;
    },

    async load() {
      const raw = await readPersisted();
      applyPersisted(raw);
      return WB.RULES;
    },

    refresh() {
      return serialize(() => this._refresh());
    },

    async _refresh() {
      const raw = await readPersisted();
      if (!raw || typeof raw !== "object") return false;
      const rev = Number(raw.updatedAt) || 0;
      if (rev === revision) return false;
      applyPersisted(raw);
      return true;
    },

    setEnabled(id, enabled) {
      return serialize(() => this._setEnabled(id, enabled));
    },

    async _setEnabled(id, enabled) {
      const rule = this.find(id);
      if (!rule) return { ok: false, reason: "missing" };
      const before = clone(state);
      if (rule.builtin) {
        const ov = state.overrides[id] || cleanFields(rule);
        ov.enabled = !!enabled;
        state.overrides[id] = cleanFields(ov);
      } else {
        const custom = state.custom.filter((r) => r.id === id)[0];
        if (!custom) return { ok: false, reason: "missing" };
        custom.enabled = !!enabled;
      }
      const saved = await saveWithRollback(before);
      return saved.ok ? { ok: true, rule: this.find(id) } : saved;
    },

    update(id, raw) {
      return serialize(() => this._update(id, raw));
    },

    async _update(id, raw) {
      const rule = this.find(id);
      if (!rule) return { ok: false, reason: "missing" };
      const check = validate(raw);
      if (!check.ok) return { ok: false, reason: "invalid", message: check.message };
      const fields = check.fields;
      fields.enabled = rule.enabled;
      const before = clone(state);
      if (rule.builtin) {
        state.overrides[id] = fields;
      } else {
        const custom = state.custom.filter((r) => r.id === id)[0];
        if (!custom) return { ok: false, reason: "missing" };
        Object.keys(fields).forEach((k) => { custom[k] = fields[k]; });
      }
      const saved = await saveWithRollback(before);
      return saved.ok ? { ok: true, rule: this.find(id) } : saved;
    },

    addCustom(raw) {
      return serialize(() => this._addCustom(raw));
    },

    async _addCustom(raw) {
      if (state.custom.length >= MAX_CUSTOM) {
        return { ok: false, reason: "limit", limit: MAX_CUSTOM };
      }
      const check = validate(raw);
      if (!check.ok) return { ok: false, reason: "invalid", message: check.message };
      const id = `r_custom_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 5)}`;
      const before = clone(state);
      state.custom.push(Object.assign({ id, builtin: false, stance: null }, check.fields));
      const saved = await saveWithRollback(before);
      return saved.ok ? { ok: true, rule: this.find(id) } : saved;
    },

    removeCustom(id) {
      return serialize(() => this._removeCustom(id));
    },

    async _removeCustom(id) {
      const rule = this.find(id);
      if (!rule) return { ok: false, reason: "missing" };
      if (rule.builtin) return { ok: false, reason: "builtin" };
      const before = clone(state);
      state.custom = state.custom.filter((r) => r.id !== id);
      return saveWithRollback(before);
    },

    resetBuiltin() {
      return serialize(() => this._resetBuiltin());
    },

    async _resetBuiltin() {
      if (!Object.keys(state.overrides).length) return { ok: true, noop: true };
      const before = clone(state);
      state.overrides = {};
      return saveWithRollback(before);
    },
  };
})(globalThis);
