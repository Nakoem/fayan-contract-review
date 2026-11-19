# 合同工作台（个人版）· MVP 设计

> 2026-11-19 · 实现设计文档
> 母文档：`PRD-合同工作台个人版.md`
> 状态：已评审（2026-11-19 grilling 后定稿）

---

## 0. 背景与目标

把法眼的内核（审查链路 / 提示词 / 规则 / 六段式报告 / 三维评分）包装成面向个人的单文件产品：**粘贴合同 → 90 秒内出带法条依据的风险报告**。

MVP 只回答一个问题：**"有人愿意用这个审合同吗？"** 因此范围严格限定在「审」，不做台账、文书、历史。

---

## 1. 范围

### 做

- 单文件 `dist/index.html`，双击可用，零外链、零 CDN、零外部字体
- 粘贴文本 / 载入 6 份内置示例合同
- 6 类合同：房屋租赁 / 劳动 / 买卖 / 服务 / 合作 / 借款
- 5 步审查流水线（抽取 → 法条 → 评估 → 复核 → 报告）
- 六段式报告 + 三维评分 + 风险条款正文高亮 + 点条目跳转
- 规则 JSON 数据化（约 66 条），条款库页面复用同一数组
- 服务商预设：DeepSeek（默认）/ DashScope / 智谱（标注"需代理"）
- API Key 本地保存、脱敏开关（默认开启）
- 导出 `.doc` + 浏览器打印
- 设置持久化；当前审查结果单槽持久化（刷新恢复）

### 不做（明确排除）

- PDF / Word 解析、台账 / 提醒、文书起草、历史记录 / 多案件、向量检索、规则编辑 UI、立场切换 UI、Ollama 预设、Lucide 图标
- 自定义合同类型

### 与 PRD 的差异（2026-11-19 定稿）

| # | PRD | 实际决定 | 原因 |
|---|---|---|---|
| 1 | 三个预设：DeepSeek / 智谱 / Ollama | DeepSeek + DashScope + 智谱（需代理），**不做 Ollama** | 用户拍板；智谱 CORS 实测被拦，预设保留但明确提示需本地代理 |
| 2 | "五段式报告" | 沿用 `prompts.py:92-142` 的**六段式**模板 | 手上真实的模板就是六段（概览/高/中/低/优先级/签约建议），不另造 |
| 3 | 立场切换 P1 | MVP 无 UI，规则 schema 保留 `stance` | 符合 P1 定位，避免 V1.5 返工 |
| 4 | 条款高亮 P1 | MVP 做**基础版**（原文查找 + 标色 + 滚动定位） | 是审查台核心体验，成本低 |
| 5 | 条款库 / 规则库分层 | 条款库直接由 `RULES` 渲染 | 一鱼两吃，不维护两份内容 |
| 6 | 历史记录第二阶段 | 当前审查结果单槽保存 | 防手滑刷新，不构成历史功能 |

---

## 2. 技术验证结论（2026-11-19 实测）

| 假设 | 结论 | 方式 |
|---|---|---|
| `file://` 页面可用 IndexedDB | ✅ 可建库、可写入、可持久化读取 | 真 Chrome + CDP 实测 |
| `file://` 页面可用 localStorage | ✅ | 同上 |
| `file://` 页面可用剪贴板 API | ✅ `navigator.clipboard.writeText` 存在 | 同上 |
| `file://` 视为安全上下文 | ✅ `isSecureContext: true`，`origin: "file://"` | 同上 |
| DeepSeek API 浏览器直连 | ✅ `access-control-allow-origin: null` | OPTIONS 预检实测 |
| DashScope API 浏览器直连 | ✅ `access-control-allow-origin: *` | 同上 |
| 智谱 API 浏览器直连 | ❌ 预检无 CORS 头 | 同上 |
| 风险等级映射确定性 | ✅ 已有规则见 `prompts.py:229-231` | 代码确认 |
| `regulation.json` 结构 | ✅ 25 个主题 → 文本块 | 代码确认 |
| Node 24 可用 | ✅ 可用于构建脚本 / 验收脚本 | 环境确认 |

---

## 3. 架构与目录

```
workbench/
├─ src/
│  ├─ index.html          # 页面骨架 + 按顺序引用各脚本
│  ├─ styles.css          # 纸感专业风 + 打印样式
│  ├─ data/
│  │  ├─ rules.js         # WB.RULES —— 规则 JSON（约 66 条，手写源文件）
│  │  ├─ samples.js       # WB.SAMPLES —— 构建时由根目录 sample_*.txt 生成（勿手改）
│  │  └─ knowledge.js     # WB.KNOWLEDGE —— 构建时由 knowledge/*.json 生成（勿手改）
│  ├─ prompts.js          # WB.buildExtractPrompt / buildEvalPrompt / buildReviewPrompt
│  ├─ llm.js              # WB.callLLM / 预设 / JSON 修复
│  ├─ pipeline.js         # WB.runPipeline（无 DOM，可在 Node 中跑）
│  ├─ storage.js          # WB.loadSettings / saveSettings / current review
│  └─ app.js              # DOM 渲染与交互
├─ build.py               # 零依赖：内联 → dist/index.html
├─ scripts/
│  ├─ spike.mjs           # M0 真调验收：耗时 / JSON 成功率 / 风险条数
│  └─ acceptance.mjs      # CDP 端到端验收（5 条标准）
├─ tests/
│  ├─ test_build.py       # 产物检查（体积 / 无外链 / 必备字符串）
│  └─ test_rules.py       # 规则 schema 校验
└─ dist/
   └─ index.html          # 交付物（提交进仓库）
```

### 模块约定（关键）

- 所有 src 逻辑文件采用 **IIFE + `globalThis.WB` 命名空间**，不写 `import/export`：
  ```js
  (function (root) { const WB = root.WB = root.WB || {}; WB.RULES = [...]; })(globalThis);
  ```
- 浏览器开发态：`index.html` 用 `<script src="...">` 按顺序加载
- 构建态：`build.py` 按同一顺序把脚本内联进 `<script>`
- Node 脚本：用 `await import()` 按顺序加载同批文件，共享 `globalThis.WB`，无需打包器
- **DOM 依赖隔离**：`prompts.js` / `llm.js` / `pipeline.js` / `data/*` 不碰 `document`/`window`，保证 Node 可跑

### 构建规则

- `build.py` 读取仓库根目录 `sample_*.txt` 与 `knowledge/*.json`（单一数据源，不复制内容）
- 构建时先**生成** `src/data/samples.js` / `src/data/knowledge.js`（文件头标注 `AUTO-GENERATED，勿手改`），再内联；开发态可直接打开源页面
- 内联顺序固定：rules → samples → knowledge → prompts → llm → pipeline → storage → app
- 输出 `dist/index.html`，体积必须 < 1.5 MB（预计 < 400 KB）
- 构建后自动跑产物检查

---

## 4. 审查流水线

```
① 抽取 ──→ ② 法条 ──→ ③ 评估 ──→ ④ 复核 ──→ ⑤ 报告
   LLM       本地        LLM        本地+LLM      本地
```

| 步 | 输入 | 输出 | 实现 | 预算 |
|---|---|---|---|---|
| ① 抽取 | 合同全文（可能已脱敏） | `clauses[]`：`{index, title, text}` | LLM，JSON | ≤ 20s |
| ② 法条 | `clauses[]` + 合同类型 | `matchedRules[]` + `regSnippets[]` | 本地：规则关键词命中 + 法规库 BM25 top-k | < 1s |
| ③ 评估 | 条款 + 候选规则 + 法条片段 | `findings[]` + `lowRiskClauses[]` + `summary` | LLM，JSON | ≤ 45s |
| ④ 复核 | 全部中间结果 | `{passed, issues[], 修正后的 findings}` | 本地校验 + 轻量 LLM；error 自动重评 1 轮 | ≤ 15s |
| ⑤ 报告 | findings / lowRisk / summary | 六段式报告 HTML | 本地模板 | < 1s |

### 步 ① 抽取

- 输出：
  ```json
  { "clauses": [ { "index": 1, "title": "第一条 房屋基本情况", "text": "逐字原文" } ] }
  ```
- `max_tokens: 3000`（吸取 CLAUDE.md 中 2048 截断的教训）
- 要求逐字提取，不得改写；条款序号按出现顺序

### 步 ② 法条（纯本地）

- 规则筛选：`RULES.filter(r => r.enabled && (r.contractType === type || r.contractType === "通用"))`，再用 `r.keywords` 对条款原文做命中
- 法规检索：把 `regulation.json` 的 25 个主题文本切成段落，建立倒排索引，按规则关键词做 BM25 排序，取 top-3 段落
- 输出给 LLM 的上下文只含命中的规则与法条片段，**不塞全量法规库**

### 步 ③ 评估

- 输出：
  ```json
  {
    "findings": [{
      "rule_id": "r_lease_penalty",
      "clause_index": 7,
      "clause_text": "逐字原文",
      "fairness": 4, "clarity": 3, "exposure": 5,
      "risk_reason": "……",
      "basis": "民法典第 585 条",
      "suggestion": "……"
    }],
    "lowRiskClauses": [ { "clause_index": 2, "clause_text": "……", "reason": "……" } ],
    "summary": "一句话总结合同整体风险"
  }
  ```
- 三维评分 0–5（5 最差），沿用 `prompts.py` 锚点
- **等级不在 LLM 输出中**：本地按确定性规则计算（见 §8）
- 覆盖要求：每条抽取出的条款必须出现在 `findings` 或 `lowRiskClauses` 中

### 步 ④ 复核

本地校验（全部确定性）：

1. 覆盖率：`clauses` 中每条都在 `findings` 或 `lowRiskClauses`
2. 等级映射：按三维分数重算等级，不信任 LLM 自报
3. 去重：同一 `clause_text` 只保留最高等级
4. 法条：`basis` 必须非空且匹配 `/第[一二三四五六七八九十百千\d]+条/`
5. 取值范围：三维分数为 0–5 整数

轻量 LLM 复核（`max_tokens: 800`）：只检查语义层面的漏判/误判，输出 `{passed, issues[]}`。
若存在 `severity: "error"` 且本轮未重评过 → 带 issues 重跑一次步 ③，最多 1 轮，然后无论结果如何继续。

### 步 ⑤ 报告

- 纯本地模板渲染，**不让 LLM 排版**
- 六段：总体概览 / 高风险详解 / 中风险条款 / 低风险条款 / 修改优先级 / 签约建议
- 每段内容来自结构化数据，格式永不漂移

---

## 5. 规则数据化（架构红线）

### Schema

```json
{
  "id": "r_lease_deposit",
  "contractType": "房屋租赁合同",
  "name": "押金条款",
  "keywords": ["押金", "保证金"],
  "condition": "押金超过 2 个月租金或未约定退还期限",
  "level": "高",
  "basis": "民法典第 703 条",
  "advice": "建议押金不超过两个月租金，并写明退还期限",
  "enabled": true,
  "builtin": true,
  "stance": null
}
```

| 字段 | 约定 |
|---|---|
| `contractType` | 六类之一，或 `"通用"` |
| `level` | `高 / 中 / 低`，规则的默认严重度（用于条款库展示与 LLM 缺失时的兜底） |
| `basis` | 必须含具体法条编号；空值规则进不了构建 |
| `stance` | MVP 恒为 `null`（中立口径），V1 再启用 |
| `builtin` | 内置规则 `true`，可停用不可删（MVP 无 UI） |

### 内容量

- 6 类 × 10 条 + 通用 6 条 = **66 条**
- 来源：`prompts.py` 的风险判定要求、`agent_langgraph.py:460` 的 `_REGULATION_CHECKLIST`、`knowledge/regulation.json`
- 每条必须带真实法条；雪玲整理，Nakko 抽查
- 关键词先命中，命中后才交给 LLM 判断（省钱、可控）

### 规则拼装

- `WB.buildEvalPrompt({ contractType, clauses, matchedRules, regSnippets })`
- V1.5 加规则编辑器时只读写 `RULES` 数组，**不改审查链路**

---

## 6. 数据与存储

### IndexedDB

- DB：`contract-workbench`，version 1
- `settings`（key-value）：
  `provider` / `baseUrl` / `model` / `apiKey:<provider>` / `masking` / `hiddenNames` / `contractType`
- `current`（单槽）：`{ contractText, contractType, reportHtml, findings, createdAt }`，刷新后恢复；下一次审查覆盖

### 脱敏（默认开启）

- 发送前替换为占位符，返回后本地换回：
  | 类型 | 规则 | 占位符 |
  |---|---|---|
  | 身份证 | `\d{17}[\dXx]` | `【证件N】` |
  | 手机号 | `1[3-9]\d{9}` | `【手机N】` |
  | 银行卡 | `\d{16,19}`（在身份证之后匹配） | `【账号N】` |
  | 邮箱 | 标准邮箱正则 | `【邮箱N】` |
  | 公司名/人名 | 用户设置里的 `hiddenNames` 精确匹配 | `【主体N】` |
- 提示词中明确要求：**占位符必须原样保留，不得改写**
- 还原顺序：对 LLM 返回的 `clause_text` / `risk_reason` / `suggestion` / `summary` 做反向替换
- 本地规则匹配与正文高亮使用**原文**，不受脱敏影响
- 还原失败的占位符原样展示，不阻断流程

### 导出

- 报告 → `.doc`（HTML 包装，Word 可打开），文件名 `合同审查报告-YYYYMMDD.doc`
- 打印：`window.print()`，专用 `@media print` 样式
- 不做设置导出 / 台账导出

---

## 7. LLM 接口

### 预设

| 名称 | baseURL | 默认模型 | 状态 |
|---|---|---|---|
| DeepSeek | `https://api.deepseek.com` | `deepseek-flash` | ✅ 默认 |
| DashScope | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` | ✅ |
| 智谱 | `https://open.bigmodel.cn/api/paas/v4` | `glm-4.6` | ⚠️ 需本地代理（UI 明确标注） |

- 模型名可编辑，预设只是默认值
- 每家 Key 分开存；切换服务商不丢 Key

### 请求

- OpenAI 兼容 `/chat/completions`
- `temperature: 0`
- 非流式
- 尝试 `response_format: { "type": "json_object" }`；若服务商报错则去掉该字段重试
- 每步 `max_tokens`：抽取 3000 / 评估 4000 / 复核 800
- 超时：单次 120s；网络错误自动重试 1 次（指数退避 1s / 2s）

### JSON 兜底

1. 优先 JSON mode
2. 失败 → `WB.repairJSON()`（移植 `utils.repair_json`：去围栏、修尾逗号、单引号、前后说明文字）
3. 连续 3 次非法 JSON → 该步降级：显示原始文本 + "结构化解析失败，请重试或换模型"，不伪造报告

### 错误分类

| 情况 | 提示 |
|---|---|
| 401 / 403 | "API Key 无效，请到设置检查" |
| 429 | "请求太频繁，稍后再试" |
| 网络失败 | "连接不上服务商，检查网络或代理" |
| 超时 | "响应超时，可重跑该步" |
| 无 Key | 自动打开设置 |

---

## 8. 评分与报告

### 等级映射（确定性，照搬法眼）

- 任一维度 ≥ 4 → **高**
- 任一维度 = 3 且无维度 ≥ 4 → **中**
- 三维度均 ≤ 2 → **低**

### 综合评分（本地计算）

```
score = min(100, high × 15 + mid × 6 + low × 1)
```

越高风险越大。示例：3 高 + 5 中 + 2 低 = 77。
（实测后可微调权重，但必须在文档中留痕。）

### 修改优先级

高 → P0 必须改；中 → P1 建议改；低 → P2 可接受。

### 签约建议

- 高 ≥ 3 条 → ❌ 不建议签
- 高 1–2 条 → ⚠️ 修改后签
- 高 0 条 → ✅ 可签（有中风险时附"留意"提示）

### 报告免责声明

报告页脚与导出文件固定包含：
> 本工具输出为 AI 辅助结果，不构成法律意见。正式签署前请由执业律师复核。

---

## 9. UI 规范

### 布局

- 顶栏 56px：产品名（衬线）/ 合同类型下拉 / 模型状态点 / 设置按钮
- 侧栏 200px：审查台 · 条款库（设置走顶栏抽屉）
- 主内容区：1280px 以上，最小宽度 1100px
- 状态条：可省略（MVP 无台账数据）

### 审查台

- 空状态：合同文本域 + 六份示例 chips + 主按钮「开始审查」
- 类型推荐：粘贴/载入后本地关键词扫描，命中时提示「检测到像 XX 合同，已切换」，用户可手动改回
- 运行中：文本域锁定，底部 5 节点流水线动画；当前节点呼吸灯，完成打勾
- 完成态：左右分栏
  - 左：合同正文，风险条款标黄/标红 + 点击右栏条目滚动定位
  - 右：风险清单（等级形状 + 标题 + 法条 + 折叠建议 + 复制修改条款）
  - 顶部分数条：高风险 X / 中 Y / 低 Z / 综合评分
- 错误态：失败节点标红 + 错误信息 + 「重跑该步」
- 空条款/无风险：明确显示"未发现明显风险"，不编造条目

### 条款库

- 左筛选：6 类 + 通用
- 卡片：条款名 / 关键词 / 判定条件 / 风险等级 / 法条依据 / 替代建议
- 内容直接来自 `WB.RULES`

### 设置（抽屉）

- 服务商选择（含智谱"需本地代理"提示）
- API Key（password 输入，脱敏显示）
- 模型名（可编辑）
- 脱敏开关（默认开）+ 需隐藏名称列表
- 保存全部写 IndexedDB

### 视觉（严格照 PRD §16）

- 纸底 `#FAF9F6`、卡片 `#FFFFFF`、墨 `#17171A`、次级 `#6B6B70`、分割线 `#E3E0D8`
- 高风险 `#B4352A`、中 `#B8873A`、低/通过 `#2F6E58`、按钮 `#1F1F23`
- 标题衬线（Noto Serif SC / 思源宋体 / SimSun / serif），正文黑体（system-ui / Microsoft YaHei）
- 圆角：卡片 6px、按钮 4px、标签 3px
- 阴影 `0 1px 2px rgba(0,0,0,.04)`，主要靠 1px 细线分层
- 图标：**只用自绘** 8 个核心 + 少量自绘补充；不引 Lucide，不做第三方许可声明
- 风险标记：高=实心方块、中=实心菱形、低=空心圆环
- 禁止：紫色、渐变、荧光色、大圆角、卡通插画、弹跳动效

### 打印

- 隐藏侧栏 / 顶栏 / 按钮 / 流水线
- 报告正文 12pt、行高 1.6
- 风险条目 `break-inside: avoid`
- 页脚免责声明

---

## 10. 错误处理与边界

| 情况 | 行为 |
|---|---|
| 输入为空 / 少于 50 字 | 阻止并提示 |
| 超过 3 万字 | 提示"合同较长，审查可能变慢" |
| 超过 5 万字 | 硬上限，阻止提交 |
| 审查中刷新/关闭 | `beforeunload` 确认提示 |
| 重跑某步 | 保留已完成步骤的中间结果，从失败步继续 |
| 关闭脱敏 | 原文直发；设置里明确说明后果 |
| 无网络 | 界面/条款库可用，审查按钮提示需要联网 |
| API Key 未配置 | 点击审查时自动打开设置 |

---

## 11. 测试与验收

### 自动化（轻量）

1. `workbench/tests/test_build.py`
   - 构建成功、`dist/index.html` 存在
   - 体积 < 1.5 MB
   - 无外部 `<script src>` / `<link rel=stylesheet>` / `@import url(http…)`
   - 必备字符串存在：免责声明、示例合同名、RULES 数量 ≥ 60
2. `workbench/tests/test_rules.py`
   - schema 完整、id 唯一、level 合法、contractType 合法
   - `basis` 匹配 `/第[一二三四五六七八九十百千\d]+条/`
   - `keywords` 非空、`id` 非空
3. `workbench/scripts/spike.mjs`（M0 门禁，真调 DashScope）
   - `sample_lease.txt` 全流程 ≤ 90s
   - 风险 ≥ 5 条且每条有法条
   - JSON 一次成功率记录
4. `workbench/scripts/acceptance.mjs`（CDP）
   - 打开 `file://.../dist/index.html`
   - 写入测试 Key → 载入示例 → 运行 → 断言报告与耗时
   - 刷新后断言 Key 与当前结果还在

### 手动验收

- 断网可打开、可看条款库
- `.doc` 导出可被 Word 打开
- 打印预览排版正常（风险条不跨页）
- 六份示例逐一跑通

### PRD 验收标准映射

| PRD # | 标准 | 验证方式 |
|---|---|---|
| 1 | 3000 字租赁合同 90 秒内出报告 | spike + acceptance 计时 |
| 2 | 风险 ≥ 5 条且带法条 | spike 断言 |
| 3 | 断网能开界面、看条款库 | 手动 DevTools Offline |
| 4 | 关浏览器重开 Key 和设置还在 | acceptance 刷新断言 |
| 5 | 单文件 < 1.5 MB | test_build |

---

## 12. 实施里程碑（详细计划见 writing-plans）

| 阶段 | 内容 | 门禁 |
|---|---|---|
| M0 | 规则抽一批 + 提示词 + Node spike 真调 DashScope | 90 秒内、≥5 条风险、JSON 稳定 |
| M1 | 构建骨架 + data 模块 + build.py | 产物可双击打开 |
| M2 | pipeline + llm + 复核 + 报告模板 | Node 里全链路跑通 |
| M3 | 审查台 UI + 流水线动画 + 高亮跳转 | 可视化验收 |
| M4 | 条款库 + 设置 + 脱敏 + 导出 | 功能验收 |
| M5 | 测试 + 打印 + 代码审查 + 最终验收 | 5 条标准全过 |

---

## 13. 风险与对策

| 风险 | 对策 |
|---|---|
| qwen-plus 偶发非法 JSON | JSON mode + repair + 1 次重试 + 3 次降级；M0 实测成功率 |
| 90 秒目标保不住 | M0 先测；超时则压缩复核 max_tokens / 减少法规片段 / 调整抽取 max_tokens |
| 条款高亮找不到原文 | 归一化空白后再匹配；仍找不到则不高亮但保留条目 |
| 脱敏占位符被 LLM 改写 | 提示词强约束 + 还原失败原样展示 + 不阻断 |
| 规则法条不准确 | 全部从 `regulation.json` 摘取；test_rules 校验格式；人工抽查 |
| 智谱预设点了不可用 | UI 明示"需本地代理"，并在错误提示中引导 |
| 综合评分公式不合理 | M0 用示例合同校准权重，留痕后固化 |
| 内置内容体积膨胀 | 构建检查体积；MVP 不嵌 case_law 展示 |

---

## 14. 决策记录

| 日期 | 决策 |
|---|---|
| 2026-11-19 | MVP 测试用 DashScope，界面默认 DeepSeek |
| 2026-11-19 | 界面范围：审查台 + 条款库 + 设置（不做案头首页） |
| 2026-11-19 | 代码组织：分模块源码 + build.py 内联 |
| 2026-11-19 | 预设：DeepSeek + DashScope + 智谱（需代理），不做 Ollama |
| 2026-11-19 | 复核：本地确定性校验 + 轻量 LLM，error 重评 1 轮 |
| 2026-11-19 | 立场切换不做 UI，schema 保留 `stance` |
| 2026-11-19 | 脱敏：正则 + 名称列表，默认开启 |
| 2026-11-19 | 条款高亮做基础版 |
| 2026-11-19 | 测试：轻量自动化 + CDP 验收 |
| 2026-11-19 | 当前审查结果单槽持久化 |
| 2026-11-19 | 合同类型手选 + 关键词推荐 |
| 2026-11-19 | 输入硬上限 5 万字；3 万字提示 |

---

*本文档为 MVP 实现设计，详细任务拆解见后续实现计划。*
