/* 合同工作台 · 本地存储
 * 优先 IndexedDB（file:// 下实测可用），失败时回退 localStorage。
 */
(function (root) {
  const WB = (root.WB = root.WB || {});

  const DB_NAME = "contract-workbench";
  const DB_VERSION = 3;
  const LS_KEY = "contract-workbench:";

  let dbPromise = null;

  WB.defaultSettings = function () {
    const p = WB.PROVIDERS.dashscope;
    return {
      provider: "dashscope",
      baseUrl: p.baseUrl,
      model: p.model,
      apiKeys: { deepseek: "", dashscope: "" },
      masking: true,
      hiddenNames: [],
      contractType: "房屋租赁合同",
    };
  };

  function mergeSettings(saved) {
    const base = WB.defaultSettings();
    if (!saved || typeof saved !== "object") return base;
    const provider = WB.PROVIDERS[saved.provider] ? saved.provider : base.provider;
    const p = WB.PROVIDERS[provider];
    return {
      provider,
      baseUrl: p.baseUrl,
      model: saved.model || p.model,
      apiKeys: Object.assign({}, base.apiKeys, saved.apiKeys || {}),
      masking: saved.masking !== false,
      hiddenNames: Array.isArray(saved.hiddenNames) ? saved.hiddenNames : [],
      contractType: saved.contractType || base.contractType,
    };
  }

  function openDB() {
    if (dbPromise) return dbPromise;
    dbPromise = new Promise((resolve, reject) => {
      if (!root.indexedDB) {
        reject(new Error("IndexedDB unavailable"));
        return;
      }
      let req;
      try { req = root.indexedDB.open(DB_NAME, DB_VERSION); }
      catch (e) { reject(e); return; }

      req.onupgradeneeded = () => {
        const db = req.result;
        if (!db.objectStoreNames.contains("settings")) db.createObjectStore("settings");
        if (!db.objectStoreNames.contains("current")) db.createObjectStore("current");
        if (!db.objectStoreNames.contains("reviews")) {
          const store = db.createObjectStore("reviews", { keyPath: "id" });
          store.createIndex("createdAt", "createdAt");
        }
        if (!db.objectStoreNames.contains("ledger")) {
          const store = db.createObjectStore("ledger", { keyPath: "id" });
          store.createIndex("endDate", "endDate");
        }
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error || new Error("IndexedDB open failed"));
      req.onblocked = () => reject(new Error("IndexedDB blocked"));
    });
    return dbPromise;
  }

  function idbGet(store, key) {
    return openDB().then(
      (db) => new Promise((resolve, reject) => {
        const tx = db.transaction(store, "readonly");
        const req = tx.objectStore(store).get(key);
        req.onsuccess = () => resolve(req.result);
        req.onerror = () => reject(req.error);
      })
    );
  }

  function idbPut(store, key, value) {
    return openDB().then(
      (db) => new Promise((resolve, reject) => {
        const tx = db.transaction(store, "readwrite");
        tx.objectStore(store).put(value, key);
        tx.oncomplete = () => resolve(true);
        tx.onerror = () => reject(tx.error);
        tx.onabort = () => reject(tx.error || new Error("IndexedDB tx aborted"));
      })
    );
  }

  function idbPutInline(store, value) {
    return openDB().then(
      (db) => new Promise((resolve, reject) => {
        const tx = db.transaction(store, "readwrite");
        tx.objectStore(store).put(value);
        tx.oncomplete = () => resolve(true);
        tx.onerror = () => reject(tx.error);
        tx.onabort = () => reject(tx.error || new Error("IndexedDB tx aborted"));
      })
    );
  }

  function idbGetAll(store) {
    return openDB().then(
      (db) => new Promise((resolve, reject) => {
        const tx = db.transaction(store, "readonly");
        const req = tx.objectStore(store).getAll();
        req.onsuccess = () => resolve(req.result || []);
        req.onerror = () => reject(req.error);
      })
    );
  }

  function idbDelete(store, key) {
    return openDB().then(
      (db) => new Promise((resolve, reject) => {
        const tx = db.transaction(store, "readwrite");
        tx.objectStore(store).delete(key);
        tx.oncomplete = () => resolve(true);
        tx.onerror = () => reject(tx.error);
        tx.onabort = () => reject(tx.error || new Error("IndexedDB tx aborted"));
      })
    );
  }

  function idbClear(store) {
    return openDB().then(
      (db) => new Promise((resolve, reject) => {
        const tx = db.transaction(store, "readwrite");
        tx.objectStore(store).clear();
        tx.oncomplete = () => resolve(true);
        tx.onerror = () => reject(tx.error);
        tx.onabort = () => reject(tx.error || new Error("IndexedDB tx aborted"));
      })
    );
  }

  // 只有浏览器完全没有 IndexedDB 时，删除 / 清空才走 LS 兜底；
  // 被旧标签页阻塞或事务失败时旧库还在，报成功会“刷新后复活”。
  async function canFallbackToLs() {
    try {
      await openDB();
      return false;
    } catch (e) {
      return /unavailable/i.test(String((e && e.message) || e));
    }
  }

  function lsGet(key) {
    try {
      const raw = root.localStorage.getItem(LS_KEY + key);
      return raw ? JSON.parse(raw) : null;
    } catch (e) { return null; }
  }

  function lsPut(key, value) {
    try { root.localStorage.setItem(LS_KEY + key, JSON.stringify(value)); return true; }
    catch (e) { return false; }
  }

  function lsDelete(key) {
    try { root.localStorage.removeItem(LS_KEY + key); return true; }
    catch (e) { return false; }
  }

  WB.loadSettings = async function () {
    try {
      const saved = await idbGet("settings", "app");
      return mergeSettings(saved);
    } catch (e) {
      return mergeSettings(lsGet("settings"));
    }
  };

  WB.saveSettings = async function (settings) {
    const clean = mergeSettings(settings);
    try { await idbPut("settings", "app", clean); }
    catch (e) { lsPut("settings", clean); }
    return clean;
  };

  WB.loadCurrent = async function () {
    try { return (await idbGet("current", "latest")) || null; }
    catch (e) { return lsGet("current"); }
  };

  WB.saveCurrent = async function (payload) {
    try { await idbPut("current", "latest", payload); }
    catch (e) { lsPut("current", payload); }
    return true;
  };

  WB.clearCurrent = async function () {
    try { await idbPut("current", "latest", null); }
    catch (e) { lsPut("current", null); }
  };

  // 审查规则：与设置共用 settings store，键名区分，避免升级数据库版本。
  WB.loadRuleState = async function () {
    try {
      return await idbGet("settings", "rules");
    } catch (e) {
      return lsGet("rules");
    }
  };

  // 比较并写入：IndexedDB 事务内读旧 revision，避免两个标签页同时保存时静默覆盖。
  WB.saveRuleState = async function (ruleState, expectedRevision) {
    const fallback = () => {
      const current = lsGet("rules");
      const currentRev = current && Number(current.updatedAt) || 0;
      if (expectedRevision != null && current && currentRev !== expectedRevision) {
        return { ok: false, conflict: true };
      }
      return lsPut("rules", ruleState) ? { ok: true } : { ok: false };
    };
    let db;
    try { db = await openDB(); }
    catch (e) { return fallback(); }
    try {
      return await new Promise((resolve, reject) => {
        const tx = db.transaction("settings", "readwrite");
        const store = tx.objectStore("settings");
        const get = store.get("rules");
        let conflict = false;
        get.onsuccess = () => {
          const current = get.result;
          const currentRev = current && Number(current.updatedAt) || 0;
          if (expectedRevision != null && current && currentRev !== expectedRevision) {
            conflict = true;
            return;
          }
          store.put(ruleState, "rules");
        };
        tx.oncomplete = () => resolve(conflict ? { ok: false, conflict: true } : { ok: true });
        tx.onerror = () => reject(tx.error);
        tx.onabort = () => reject(tx.error || new Error("IndexedDB tx aborted"));
      });
    } catch (e) {
      return { ok: false };
    }
  };

  // ───────────────────────── 通用记录（审查历史 / 台账） ─────────────────────────

  async function saveRecord(store, lsKey, record) {
    if (!record || !record.id) return null;
    try {
      await idbPutInline(store, record);
      return record;
    } catch (e) {
      const list = (lsGet(lsKey) || []).filter((r) => r && r.id !== record.id);
      list.unshift(record);
      return lsPut(lsKey, list) ? record : null;
    }
  }

  async function listRecords(store, lsKey) {
    let idbList = [];
    try { idbList = await idbGetAll(store); }
    catch (e) { idbList = []; }
    // localStorage 里可能是旧版本或降级期间写入的记录；同 id 取更新时间较新的。
    const merged = new Map();
    const put = (r) => {
      if (!r || !r.id) return;
      const prev = merged.get(r.id);
      const rTime = Number(r.updatedAt || r.createdAt) || 0;
      const pTime = prev ? Number(prev.updatedAt || prev.createdAt) || 0 : -1;
      if (!prev || rTime >= pTime) merged.set(r.id, r);
    };
    (lsGet(lsKey) || []).forEach(put);
    (idbList || []).forEach(put);
    return Array.from(merged.values())
      .sort((a, b) => (Number(b.createdAt) || 0) - (Number(a.createdAt) || 0));
  }

  async function deleteRecord(store, lsKey, id) {
    if (!id) return false;
    const rest = (lsGet(lsKey) || []).filter((r) => r && r.id !== id);
    try {
      await idbDelete(store, id);
      lsPut(lsKey, rest);
      return true;
    } catch (e) {
      if (!(await canFallbackToLs())) return false;
      return lsPut(lsKey, rest);
    }
  }

  async function clearRecords(store, lsKey) {
    try {
      await idbClear(store);
      lsDelete(lsKey);
      return true;
    } catch (e) {
      if (!(await canFallbackToLs())) return false;
      return lsDelete(lsKey);
    }
  }

  // ───────────────────────── 审查历史 ─────────────────────────

  WB.saveReview = (review) => saveRecord("reviews", "reviews", review);
  WB.listReviews = () => listRecords("reviews", "reviews");
  WB.deleteReview = (id) => deleteRecord("reviews", "reviews", id);
  WB.clearReviews = () => clearRecords("reviews", "reviews");

  // ───────────────────────── 合同台账 ─────────────────────────

  WB.saveLedgerEntry = (entry) => saveRecord("ledger", "ledger", entry);
  WB.listLedger = () => listRecords("ledger", "ledger");
  WB.deleteLedgerEntry = (id) => deleteRecord("ledger", "ledger", id);
})(globalThis);
