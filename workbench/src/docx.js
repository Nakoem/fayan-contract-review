/* 合同工作台 · Word 导出（真 .docx）
 *
 * 用 Office Open XML 的 altChunk 把已经排好版的报告 HTML 交给 Word 导入：
 * - 外层是真正的 .docx（ZIP），Word 不再提示“扩展名与格式不一致”
 * - 内容仍复用 buildDocHtml 的表格排版，不需要维护两套 Word 生成逻辑
 * - 不依赖任何第三方库，单文件构建可直接内联
 */
(function (root) {
  const WB = (root.WB = root.WB || {});

  const MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
  const enc = new TextEncoder();

  const CRC_TABLE = (() => {
    const table = new Uint32Array(256);
    for (let n = 0; n < 256; n++) {
      let c = n;
      for (let k = 0; k < 8; k++) {
        c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1);
      }
      table[n] = c >>> 0;
    }
    return table;
  })();

  function crc32(data) {
    let c = 0xFFFFFFFF;
    for (let i = 0; i < data.length; i++) {
      c = CRC_TABLE[(c ^ data[i]) & 0xFF] ^ (c >>> 8);
    }
    return (c ^ 0xFFFFFFFF) >>> 0;
  }

  function bytes(parts) {
    let total = 0;
    parts.forEach((p) => { total += p.length; });
    const out = new Uint8Array(total);
    let at = 0;
    parts.forEach((p) => {
      out.set(p, at);
      at += p.length;
    });
    return out;
  }

  const u16 = (n) => new Uint8Array([n & 255, (n >>> 8) & 255]);
  const u32 = (n) => new Uint8Array([
    n & 255, (n >>> 8) & 255, (n >>> 16) & 255, (n >>> 24) & 255,
  ]);

  // Store（不压缩）ZIP。DOCX 很小，省掉压缩后仍只有几十 KB。
  function zipStore(files) {
    const localChunks = [];
    const central = [];
    let offset = 0;

    files.forEach((file) => {
      const name = enc.encode(file.name);
      const data = typeof file.data === "string" ? enc.encode(file.data) : file.data;
      const crc = crc32(data);
      const localHeader = bytes([
        u32(0x04034B50), u16(20), u16(0x0800), u16(0), u16(0), u16(0),
        u32(crc), u32(data.length), u32(data.length), u16(name.length), u16(0), name,
      ]);
      localChunks.push(localHeader, data);
      central.push({ name, crc, size: data.length, offset });
      offset += localHeader.length + data.length;
    });

    const centralStart = offset;
    const centralChunks = [];
    central.forEach((entry) => {
      centralChunks.push(bytes([
        u32(0x02014B50), u16(20), u16(20), u16(0x0800), u16(0), u16(0), u16(0),
        u32(entry.crc), u32(entry.size), u32(entry.size), u16(entry.name.length),
        u16(0), u16(0), u16(0), u16(0), u32(0), u32(entry.offset), entry.name,
      ]));
    });
    const centralSize = centralChunks.reduce((sum, c) => sum + c.length, 0);
    const end = bytes([
      u32(0x06054B50), u16(0), u16(0), u16(central.length), u16(central.length),
      u32(centralSize), u32(centralStart), u16(0),
    ]);

    return new Blob(localChunks.concat(centralChunks, [end]), { type: MIME });
  }

  const CONTENT_TYPES = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Default Extension="html" ContentType="text/html"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>`;

  const ROOT_RELS = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>`;

  const DOC_RELS = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="htmlChunk" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/aFChunk" Target="afchunk.html"/>
</Relationships>`;

  const DOCUMENT = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<w:body><w:altChunk r:id="htmlChunk"/><w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134" w:header="720" w:footer="720" w:gutter="0"/></w:sectPr></w:body>
</w:document>`;

  // 任意 Word 友好 HTML → 真 .docx。报告和文书共用同一套 OOXML 包装。
  WB.buildDocxFromHtml = function (html) {
    return zipStore([
      { name: "[Content_Types].xml", data: CONTENT_TYPES },
      { name: "_rels/.rels", data: ROOT_RELS },
      { name: "word/document.xml", data: DOCUMENT },
      { name: "word/_rels/document.xml.rels", data: DOC_RELS },
      { name: "word/afchunk.html", data: String(html || "") },
    ]);
  };

  WB.buildDocx = function (result) {
    return WB.buildDocxFromHtml(WB.buildDocHtml(result || {}));
  };
})(globalThis);
