# 合同工作台（个人版）· MVP

> 法眼企业版的 C 端产品线：同一套审查内核，另一种包装。
> 给没有法务部的人，一个「一个人的法务部」。

---

## 快速开始

1. 双击 `dist/index.html`（Chrome / Edge，1280px 以上）
2. 右上角「设置」→ 选服务商 → 填 API Key → 保存
3. 粘贴合同，或上传 PDF / Word，或点一份示例合同 → 「开始审查」

首次使用必须配置自己的模型 Key。合同原文只会发送给你选择的模型服务商；其余数据留在本机浏览器。

### 服务商

| 服务商 | 默认模型 | 浏览器直连 |
|---|---|---|
| DashScope（通义） | `qwen3.8-max-0902` | ✅ |
| DeepSeek | `deepseek-flash` | ✅ |

模型名可编辑；Key 分服务商保存在 IndexedDB。

### 文件解析

- 支持文字层 PDF、DOCX、TXT / MD；旧版 `.doc` 会提示另存为 `.docx`
- 文件只在本机浏览器解析，不上传；点「开始审查」时才把提取出的文字发给所选模型
- 扫描版 PDF（没有文字层）V1 不做 OCR，会提示粘贴文字或换 DOCX
- 上限：单文件 25MB、PDF 300 页、提取文字 20 万字；送审仍受 5 万字限制
- 解析器版本与许可证见 `vendor/README.md`

---

## 开发

### 构建

```bash
python workbench/build.py
```

- 读取仓库根目录 `sample_*.txt` 和 `knowledge/*.json`
- 生成 `src/data/samples.js` / `src/data/knowledge.js`（自动生成，勿手改）
- 把 CSS / JS 全部内联成 `dist/index.html`
- 构建后自动检查体积、外链和必备内容

### 测试

```bash
# 规则 schema + 构建产物
.venv/Scripts/python.exe -m pytest workbench/tests -v

# UI 冒烟（真 Chrome + mock LLM，不花钱）
node workbench/scripts/ui_smoke.mjs

# 文件解析验收（中文 PDF / 英文 PDF / DOCX / .doc 拒绝）
node workbench/scripts/parser_check.mjs

# 单份示例真调模型（量耗时与 JSON 稳定性）
node workbench/scripts/spike.mjs --sample=lease --provider=dashscope

# 3000 字长合同压测（长合同会自动跳过 LLM 复核保 90 秒）
node workbench/scripts/spike.mjs --file=workbench/tests/fixtures/lease_3000.txt --type=房屋租赁合同 --gate

# 断网 / 关浏览器重开
node workbench/scripts/offline_check.mjs
node workbench/scripts/restart_check.mjs

# PRD 验收（真调模型，检查 90 秒 / ≥5 条风险 / 持久化）
node workbench/scripts/acceptance.mjs --provider=dashscope

# 端到端：上传中文 PDF → 解析 → 真调模型 → 报告
node workbench/scripts/acceptance.mjs --file=workbench/tests/fixtures/lease_sample.pdf
```

真调脚本从仓库根目录 `.env` 读取 `DASHSCOPE_API_KEY` / `DEEPSEEK_API_KEY`。

---

## 目录

```
workbench/
├─ src/
│  ├─ index.html      页面骨架
│  ├─ styles.css      屏幕玻璃风（含报告）+ 打印纸感
│  ├─ data/
│  │  ├─ rules.js     66 条审查规则（手写源）
│  │  ├─ samples.js   6 份示例合同（自动生成）
│  │  └─ knowledge.js 法规库（自动生成）
│  ├─ prompts.js      提示词构建
│  ├─ llm.js          服务商预设 + 调用 + JSON 修复
│  ├─ pipeline.js     5 步流水线 + 本地评分 + 报告渲染
│  ├─ file_parser.js  PDF / DOCX / TXT 本地解析
│  ├─ storage.js      IndexedDB（失败回退 localStorage）
│  └─ app.js          UI 逻辑
├─ vendor/            pdf.js / mammoth（含 LICENSE）
├─ build.py           零依赖构建脚本
├─ scripts/           冒烟 / 真调 / 解析 / 验收脚本
├─ tests/             pytest + 解析夹具
└─ dist/index.html    交付物
```

---

## 关键设计

- **规则数据化**：规则存在 `RULES` 数组里，提示词由代码拼装；V1.5 加规则编辑器时不用改审查链路。
- **5 步流水线**：抽取（LLM）→ 法条（本地 BM25）→ 评估（LLM）→ 复核（本地 + 轻量 LLM）→ 报告（本地模板）。
- **报告不交给 LLM 排版**：LLM 只吐结构化 JSON，六段式报告由本地模板渲染，格式稳定。
- **评级确定性**：任一维度 ≥4 → 高；任一 =3 → 中；均 ≤2 → 低。
- **综合评分**：`min(100, 高×15 + 中×6 + 低×1)`。
- **脱敏**：身份证 / 手机号 / 银行卡 / 邮箱正则 + 用户自填名称列表；默认开启。
- **单文件交付**：零外链、零 CDN、零外部字体；`file://` 下 IndexedDB / 剪贴板 / PDF / DOCX 解析实测可用。
- **解析器内联**：PDF.js 与 Mammoth 以 base64 / 源码形式打进单文件，运行时零网络请求；当前交付物体积约 2.9MB。
- **单槽恢复**：当前审查结果存 IndexedDB，刷新不丢；不做历史列表。
- **高风险定位**：点风险清单里的高风险条目，原文对应条款出现旋转光束描边（参考问数精灵登录按钮的 BorderBeam，沿用 ocean 蓝紫配色；长条款上转速放缓到 3.1s）；中/低风险仍用闪烁定位。

---

## 已知限制（MVP）

- 不做 OCR：扫描版 PDF 请先转文字或换 DOCX
- 不做台账、提醒、文书、历史记录、规则编辑 UI、立场切换 UI
- 浏览器直连仅支持 DashScope / DeepSeek；Ollama 预设不在 MVP
- 单次输入上限 5 万字（3 万字起提示）
- 单文件构建产物上限 4MB；当前约 2.9MB
- AI 输出仅供参考，不构成法律意见；正式签署前请由执业律师复核

---

关联文档：

- `PRD-合同工作台个人版.md`
- `docs/superpowers/specs/2026-11-19-contract-workbench-mvp-design.md`
