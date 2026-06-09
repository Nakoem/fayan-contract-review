# 法眼 · MySQL+RAG 混合检索 实施任务清单

> 基于 [PRD-MySQL-RAG联动.md](PRD-MySQL-RAG联动.md) · grill-me 决策后拆分
>
> 4 个 AFK 垂直切片，按依赖顺序排列

---

## 📋 总览

| # | Issue | 依赖 | 预估 |
|---|-------|------|------|
| 1 | 核心骨架 + count 统计 | 无 | 40min |
| 2 | top_risks + list | #1 | 25min |
| 3 | detail + report 查询 | #1 | 25min |
| 4 | 指纹匹配 + UI | #1 | 20min |

---

## #1 ─ 核心骨架 + count 统计

**类型：** AFK（无人工依赖）

**阻塞：** 无 — 可立即开始

**覆盖 User Story：** US-1（"我审过几份合同？平均分多少？"）

### What to build

1. 在 `tools.py` 新增 `query_review_history` 函数骨架 + count action
2. 在 `tools.py` 新增工具 Function Calling 定义（给法律问答用）
3. 改造 `chat_engine.py`：RAG 预检索（必做）→ 注入工具定义 → LLM 决定是否调工具 → 最多一次工具调用 → 最终输出

### Acceptance Criteria

- [ ] 在问答页面问"我审过几份合同？"→ 返回正确数量
- [ ] 问"平均分多少？"→ 返回正确平均值
- [ ] MySQL 连不上时 → LLM 正常回答法规（降级成功）
- [ ] 不涉及历史数据的问题（如"民法典押金条款"）→ 行为不变，不调工具

---

## #2 ─ top_risks + list

**类型：** AFK（无人工依赖）

**阻塞：** #1（需要 `query_review_history` 函数骨架 + 工具定义已存在）

**覆盖 User Story：** US-2（"租赁合同最常见风险？"）、US-4（"得分最低的是哪份？"）

### What to build

1. `query_review_history` 新增 top_risks action — 按 contract_type + risk_level 统计风险排行
2. `query_review_history` 新增 list action — 返回最近 N 份合同（含得分），支持 sort_by

### Acceptance Criteria

- [ ] 问"租赁合同最常见风险？"→ 返回 Top 3 风险排行
- [ ] 问"最近审了哪些？"→ 返回合同列表（含得分）
- [ ] 问"得分最低的是哪份？"→ sort_by="score_asc" 返回最低分合同
- [ ] 无匹配数据时 → 降级返回"暂无历史数据"

---

## #3 ─ detail + report 查询

**类型：** AFK（无人工依赖）

**阻塞：** #1（需要 `query_review_history` 函数骨架 + 工具定义已存在）

**覆盖 User Story：** US-3（"上次押金怎么判的？"）、US-5（"买卖合同里押金问题出现过几次？"）、US-7（"上次报告结论是什么？"）、US-8（"哪份报告提到社保？"）

### What to build

1. `query_review_history` 新增 detail action — 按合同 ID 查该合同所有风险详情（等级 + 条款名 + 原文 + 建议）
2. `query_review_history` 新增 report action — 按 keyword 搜索 reviews 表的 full_report 全文
3. 支持 keyword 参数模糊匹配风险条款和报告内容

### Acceptance Criteria

- [ ] 问"上次审的租赁合同押金怎么判的？"→ 返回该合同所有押金相关风险详情
- [ ] 问"验收条款出现过几次高风险？"→ keyword="验收" → 返回匹配的风险列表
- [ ] 问"哪份报告里提到了社保？"→ keyword="社保" 搜索报告全文 → 返回匹配的报告
- [ ] 问"上次报告的审查结论是什么？"→ 返回最近一份报告的摘要
- [ ] 合同不存在时 → 降级返回"未找到该合同"
- [ ] 报告无匹配时 → 降级返回"未找到相关报告"

---

## #4 ─ 指纹匹配 + UI

**类型：** AFK（无人工依赖）

**阻塞：** #1（需要 `query_review_history` 函数骨架 + 工具定义已存在）

**覆盖 User Story：** US-6（上传合同 → "你审过这份"）

### What to build

1. `query_review_history` 新增 match action — SHA256 指纹匹配
2. `pages/01_法律问答.py` 上传合同后自动算指纹 → 调 match → 显示匹配结果

### Acceptance Criteria

- [ ] 上传已审过的合同 → 显示 `📎 已找到历史审查记录 · 得分78 · 3处高风险`
- [ ] 上传新合同 → 显示 `📎 新合同，未审过`
- [ ] 匹配失败/指纹为空 → 不显示任何提示（安静降级）
- [ ] 不影响正常问答流程

---

## 📊 完成标准

全部 4 个 Issue 通过后，以下对话场景应全部可用：

- [ ] "我总共审了多少份合同？"
- [ ] "平均分多少？"
- [ ] "租赁合同最常见风险是什么？"
- [ ] "得分最低的是哪份合同？"
- [ ] "最近审了哪些合同？"
- [ ] "上次那份租赁合同押金条款怎么判的？"
- [ ] "买卖合同里验收相关的问题出现过吗？"
- [ ] "上次报告的审查结论是什么？"
- [ ] "哪份报告里提到了社保条款？"
- [ ] 上传审过的合同 → "你审过这份"
- [ ] 纯法规问题（不涉及历史）→ 行为不变
- [ ] MySQL 挂掉 → 法规问答不受影响
