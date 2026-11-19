/* 合同工作台 · 本地存储
 * 优先 IndexedDB（file:// 下实测可用），失败时回退 localStorage。
 */
(function (root) {
  const WB = (root.WB = root.WB || {});

  const DB_NAME = "contract-workbench";
  const DB_VERSION = 1;
  const LS_KEY = "contract-workbench:";

  let dbPromise = null;

  WB.defaultSettings = function () {
    const p = WB.PROVIDERS.deepseek;
    return {
      provider: "deepseek",
      baseUrl: p.baseUrl,
      model: p.model,
      apiKeys: { deepseek: "", dashscope: "", zhipu: "" },
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
})(globalThis);
