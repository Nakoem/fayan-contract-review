# 合同工作台（个人版）· MVP

> 法眼企业版的 C 端产品线：同一套审查内核，另一种包装。
> 给没有法务部的人，一个「一个人的法务部」。

---

## 快速开始

1. 双击 `dist/index.html`（Chrome / Edge，1280px 以上）
2. 右上角「设置」→ 选服务商 → 填 API Key → 保存
3. 粘贴合同，或点一份示例合同 → 「开始审查」

首次使用必须配置自己的模型 Key。合同原文只会发送给你选择的模型服务商；其余数据留在本机浏览器。

### 服务商

| 服务商 | 默认模型 | 浏览器直连 |
|---|---|---|
| DeepSeek | `deepseek-flash` | ✅ |
| DashScope（通义） | `qwen-plus` | ✅ |
| 智谱 | `glm-4.6` | ⚠️ 被 CORS 拦截，需要本地代理 |

模型名可编辑；Key 分服务商保存在 IndexedDB。

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

# 单份示例真调模型（量耗时与 JSON 稳定性）
node workbench/scripts/spike.mjs --sample=lease --provider=dashscope

# PRD 验收（真调模型，检查 90 秒 / ≥5 条风险 / 持久化）
node workbench/scripts/acceptance.mjs --provider=dashscope
```

真调脚本从仓库根目录 `.env` 读取 `DASHSCOPE_API_KEY` / `DEEPSEEK_API_KEY` / `ZHIPU_API_KEY`。

---

## 目录

```
workbench/
├─ src/
│  ├─ index.html      页面骨架
│  ├─ styles.css      纸感专业风 + 打印样式
│  ├─ data/
│  │  ├─ rules.js     66 条审查规则（手写源）
│  │  ├─ samples.js   6 份示例合同（自动生成）
│  │  └─ knowledge.js 法规库（自动生成）
│  ├─ prompts.js      提示词构建
│  ├─ llm.js          服务商预设 + 调用 + JSON 修复
│  ├─ pipeline.js     5 步流水线 + 本地评分 + 报告渲染
│  ├─ storage.js      IndexedDB（失败回退 localStorage）
│  └─ app.js          UI 逻辑
├─ build.py           零依赖构建脚本
├─ scripts/           冒烟 / 真调 / 验收脚本
├─ tests/             pytest
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
- **单文件交付**：零外链、零 CDN、零外部字体；`file://` 下 IndexedDB / 剪贴板实测可用。
- **单槽恢复**：当前审查结果存 IndexedDB，刷新不丢；不做历史列表。

---

## 已知限制（MVP）

- 不做 PDF / Word 解析、台账、提醒、文书、历史记录、规则编辑 UI、立场切换 UI
- 智谱浏览器直连不可用（需代理）；Ollama 预设不在 MVP
- 单次输入上限 5 万字（3 万字起提示）
- AI 输出仅供参考，不构成法律意见；正式签署前请由执业律师复核

---

关联文档：

- `PRD-合同工作台个人版.md`
- `docs/superpowers/specs/2026-11-19-contract-workbench-mvp-design.md`
