# 第三方解析器

这里存放合同工作台在浏览器里解析 PDF / DOCX 用的第三方库。构建时由 `build.py` 内联进 `dist/index.html`，运行时从 Blob URL 加载，不访问网络。

| 目录 | 版本 | 用途 | 许可证 |
|---|---|---|---|
| `pdfjs/` | pdfjs-dist 6.5.438 | 提取 PDF 文字层 | Apache-2.0（见 `pdfjs/LICENSE`） |
| `mammoth/` | mammoth 1.13.0 | 提取 DOCX 纯文本 | BSD-2-Clause（见 `mammoth/LICENSE`） |

## 文件说明

- `pdfjs/pdf.min.mjs`：PDF.js 主模块，构建时 base64 编码后放进 `<script type="text/plain" id="pdfjs-main">`
- `pdfjs/pdf.worker.min.mjs`：PDF.js worker，构建时同样 base64 编码，运行时通过 Blob URL 指定给 `GlobalWorkerOptions.workerSrc`
- `mammoth/mammoth.browser.min.js`：Mammoth 浏览器 UMD 包，构建时直接内联

## 升级步骤

1. 从 npm 官方包替换上述文件（保持文件名）
2. 保留各自的 `LICENSE`
3. 运行 `python workbench/build.py`，确认体积仍在 4MB 内
4. 运行 `node workbench/scripts/parser_check.mjs`，确认 PDF / DOCX 解析和 `.doc` 拒绝都通过

只用文字层解析，不执行 PDF / DOCX 里的脚本或宏；扫描版 PDF 不做 OCR。
