/* 合同工作台 · 附件管理
 * 独立 IndexedDB 库存二进制，避免给主库升版本导致旧标签页阻塞。
 * 只保存在本机；不做任何上传。
 */
(function (root) {
  const WB = (root.WB = root.WB || {});

  const DB_NAME = "contract-workbench-files";
  const DB_VERSION = 1;
  const MAX_FILE = 25 * 1024 * 1024;
  const MAX_TOTAL = 100 * 1024 * 1024;
  const ALLOWED = [
    "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx",
    "jpg", "jpeg", "png", "webp", "gif", "txt", "md", "zip", "rar", "7z",
  ];

  let dbPromise = null;

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
        if (!db.objectStoreNames.contains("meta")) {
          const store = db.createObjectStore("meta", { keyPath: "id" });
          store.createIndex("entryId", "entryId");
        }
        if (!db.objectStoreNames.contains("files")) db.createObjectStore("files");
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error || new Error("IndexedDB open failed"));
      req.onblocked = () => reject(new Error("IndexedDB blocked"));
    });
    // 失败不缓存，下次操作可重试（例如另一个标签页关闭后解除 blocked）。
    dbPromise = dbPromise.catch((err) => {
      dbPromise = null;
      throw err;
    });
    return dbPromise;
  }

  function newId() {
    return "att_" + Date.now().toString(36) + "_" + Math.random().toString(36).slice(2, 7);
  }

  function extension(name) {
    const m = /\.([A-Za-z0-9]{1,8})$/.exec(String(name || "").trim());
    return m ? m[1].toLowerCase() : "";
  }

  function formatSize(size) {
    const n = Number(size) || 0;
    if (n < 1024) return n + " B";
    if (n < 1024 * 1024) return (n / 1024).toFixed(n < 10240 ? 1 : 0) + " KB";
    return (n / 1024 / 1024).toFixed(1) + " MB";
  }

  /** 返回空字符串表示可以添加，否则返回给用户看的原因。 */
  function checkFile(file, usedBytes) {
    if (!file || !file.name) return "没有选择文件";
    if (!file.size) return "文件是空的";
    if (!extension(file.name)) return "文件缺少扩展名";
    if (ALLOWED.indexOf(extension(file.name)) < 0) {
      return "不支持这种文件类型（支持 PDF / Word / Excel / PPT / 图片 / 文本 / 压缩包）";
    }
    if (file.size > MAX_FILE) return `单个附件不能超过 ${formatSize(MAX_FILE)}`;
    if ((Number(usedBytes) || 0) + file.size > MAX_TOTAL) {
      return `这份合同的附件合计不能超过 ${formatSize(MAX_TOTAL)}`;
    }
    return "";
  }

  async function add(entryId, file) {
    if (!entryId) throw new Error("缺少合同 id");
    const db = await openDB();
    const meta = {
      id: newId(),
      entryId: String(entryId),
      name: String(file.name || "未命名附件").slice(0, 160),
      type: String(file.type || ""),
      size: Number(file.size) || 0,
      createdAt: Date.now(),
    };
    return new Promise((resolve, reject) => {
      const tx = db.transaction(["meta", "files"], "readwrite");
      tx.objectStore("meta").put(meta);
      tx.objectStore("files").put(file, meta.id);
      tx.oncomplete = () => resolve(meta);
      tx.onerror = () => reject(tx.error || new Error("附件保存失败"));
      tx.onabort = () => reject(tx.error || new Error("附件保存已中止"));
    });
  }

  function list(entryId) {
    return openDB().then((db) => new Promise((resolve, reject) => {
      const tx = db.transaction("meta", "readonly");
      const index = tx.objectStore("meta").index("entryId");
      const req = index.getAll(String(entryId));
      req.onsuccess = () => resolve((req.result || []).sort((a, b) => Number(b.createdAt) - Number(a.createdAt)));
      req.onerror = () => reject(req.error);
    }));
  }

  function listAll() {
    return openDB().then((db) => new Promise((resolve, reject) => {
      const tx = db.transaction("meta", "readonly");
      const req = tx.objectStore("meta").getAll();
      req.onsuccess = () => resolve(req.result || []);
      req.onerror = () => reject(req.error);
    }));
  }

  function getBlob(id) {
    return openDB().then((db) => new Promise((resolve, reject) => {
      const tx = db.transaction("files", "readonly");
      const req = tx.objectStore("files").get(String(id));
      req.onsuccess = () => resolve(req.result || null);
      req.onerror = () => reject(req.error);
    }));
  }

  function remove(id) {
    return openDB().then((db) => new Promise((resolve, reject) => {
      const tx = db.transaction(["meta", "files"], "readwrite");
      tx.objectStore("meta").delete(String(id));
      tx.objectStore("files").delete(String(id));
      tx.oncomplete = () => resolve(true);
      tx.onerror = () => reject(tx.error);
      tx.onabort = () => reject(tx.error || new Error("附件删除已中止"));
    }));
  }

  function removeEntry(entryId) {
    return list(entryId).then(async (items) => {
      for (const item of items) {
        try { await remove(item.id); } catch (e) { /* 继续删剩下的 */ }
      }
      return true;
    }).catch(() => false);
  }

  /** 清理不属于任何现存台账记录的附件（导入备份后调用）。 */
  function prune(validEntryIds) {
    const valid = new Set((validEntryIds || []).map((id) => String(id)));
    return listAll().then(async (items) => {
      let removed = 0;
      for (const item of items) {
        if (valid.has(String(item.entryId))) continue;
        try { await remove(item.id); removed++; } catch (e) { /* 继续 */ }
      }
      return removed;
    }).catch(() => 0);
  }

  WB.Attachments = {
    MAX_FILE,
    MAX_TOTAL,
    ALLOWED,
    extension,
    formatSize,
    checkFile,
    add,
    list,
    listAll,
    getBlob,
    remove,
    removeEntry,
    prune,
  };
})(globalThis);
