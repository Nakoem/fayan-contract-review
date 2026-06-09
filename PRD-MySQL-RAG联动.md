# PRD：MySQL + RAG 混合检索 —— 法律问答双引擎

> 基于 grill-me 决策更新版 · 2026-06-09

## Problem Statement

用户在法律问答模块中只能查到法规条文，但无法查询"我审过的合同里发生过什么"。比如问"我之前审的租赁合同押金条款怎么判的"——系统有全部历史数据在 MySQL 里，但法律问答完全用不到。

## Solution

法律问答升级为**轻量对话 Agent**（非完整 ReAct 循环），新增 `query_review_history` 工具：

- **Chroma 向量库** → 法规条文、判例、政策（预检索，必做）
- **MySQL** → 用户的历史审查记录（LLM 按需调用工具查询）

### 回答结构

法规为主，历史数据为辅：

> 根据《民法典》XXX...（法规结论）
> 📊 顺便一提，你审过的 X 份同类合同中...

## User Stories

1. As a 用户, I want to ask "我审过几份合同？平均分多少？", so that I know my usage stats.
2. As a 用户, I want to ask "租赁合同里最常见的风险是什么？", so that I understand risk patterns from my own data.
3. As a 用户, I want to ask "上次审的劳动合同押金条款怎么判的？", so that I can recall specific past review results.
4. As a 用户, I want to ask "得分最低的是哪份合同？", so that I can find problematic contracts.
5. As a 用户, I want to ask "买卖合同里押金相关的问题出现过几次？", so that I can see keyword-specific patterns.
6. As a 用户, I want to upload a contract and hear "你审过这份，上次得分78", so that I don't re-review by mistake.
7. As a 用户, I want to ask "上次报告的审查结论是什么？", so that I can recall full review reports.
8. As a 用户, I want to ask "哪份报告里提到了社保条款？", so that I can search across all review reports by keyword.
9. As a 用户, I want to get answers that combine legal knowledge + personal data in one response.

## Implementation Decisions

### 1. 新增工具函数 `query_review_history`

在 `tools.py` 中新增，6 个 action：

```python
query_review_history(
    action: str,              # "count" | "top_risks" | "list" | "detail" | "match"
    contract_type: str = "",  # 合同类型过滤，留空=全部
    risk_level: str = "",     # "高风险"|"中风险"|"低风险"
    keyword: str = "",        # 模糊关键词搜索（如"押金"）
    limit: int = 3,           # 返回条数，默认3
    sort_by: str = "recent",  # "recent"|"score_asc"|"score_desc"
    fingerprint: str = "",    # SHA256 合同指纹（仅 action="match" 用）
)
```

| action | 功能 | 示例问题 |
|------|------|------|
| `count` | 统计总数 + 平均分 + 按类型分布 | "审了多少份？" |
| `top_risks` | 按 contract_type/risk_level 排风险 Top N | "什么风险最常见？" |
| `list` | 列出最近N份合同（含得分） | "最近审了哪些？" |
| `detail` | 查具体合同的风险详情 | "上次那个押金怎么判的？" |
| `match` | 合同指纹匹配 → 判断是否审过 | "这份审过吗？" |
| `report` | 搜索审查报告全文 | "哪份报告提到了社保？" |

### 2. 法律问答轻量 Agent 改造

在 `chat_engine.py` 中改造 `chat_stream`：

```
用户提问
  → RAG 预检索法规（必做，不等 LLM 判断）
  → LLM 看上下文 + 法规结果 + 工具定义
  → LLM 决定：需要历史数据吗？
      → 需要 → 调 query_review_history → 拿到结果 → 最终回答
      → 不需要 → 直接基于法规回答
```

LLM 最多调一次工具，不是完整 ReAct 循环。

### 3. 合同指纹匹配

上传合同后自动算 SHA256 指纹 → 调 `match` → 注入匹配结果到上下文：

> 📎 已找到历史审查记录 · 得分78 · 3处高风险

（简洁展示，不展开完整报告）

### 4. 数据库连接复用

直接用 `db.py` 的 `get_conn()`。查 `contracts` + `reports` + `risks` 三张表。

### 5. 优雅降级

```python
try:
    conn = get_conn()
    # ... SQL ...
except Exception:
    return {"status": "unavailable", "message": "历史数据暂不可用"}
```

MySQL 挂掉时 LLM 看到"历史数据暂不可用"，自动只答法规，用户无感知。

### 6. 范围限定

- ✅ 法律问答加 `query_review_history`（Function Calling）
- ❌ 合同审查 Agent 不加（审查流程不应被历史数据打断）
- ❌ 不做前端 Dashboard（另开 PRD）

## Testing Decisions

### Testing Philosophy

- 只测试外部行为，不测内部 SQL 语句
- 使用现有 MySQL 中的真实测试数据

### Test Seam

- `query_review_history` 是独立函数，可直接单元测试
- `chat_stream` 是集成测试入口

### Test Cases

1. **count** → 验证返回 `{"total_reviews": N, "avg_score": X, "by_type": {...}}`
2. **top_risks** (contract_type="房屋租赁合同") → 验证返回风险排行
3. **list** (limit=5) → 验证返回最近5条
4. **detail** (contract_id=X) → 验证返回该合同所有风险评估
5. **match** (fingerprint="...") → 已验证匹配/不匹配
6. **降级** → MySQL 不可用时返回 `{"status": "unavailable"}`
7. **集成** → "我审过几份合同？" → LLM 调 count → 回答正确

## Out of Scope

- 合同审查 Agent 的 `AGENT_TOOLS`（不加）
- 多用户隔离（当前只有 "Nakko"）
- 前端 Dashboard 可视化（另开 PRD）
- 数据导出
- MySQL 向量化（继续用 Chroma）

## Further Notes

- 当前 contracts 表只有 1 条测试数据，开发前多跑几次审查
- 简历加分点："法律问答轻量 Agent（Function Calling），Chroma + MySQL 双引擎混合检索"
- 改动 ~100 行，涉及 `tools.py` + `chat_engine.py` + `pages/01_法律问答.py`
