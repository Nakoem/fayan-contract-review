# Agent 调用失败 · State 断点恢复计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 利用 LangGraph 内置 Checkpointer 机制，实现多 Agent 审查流程中的 State 断点保存与恢复，确保中间某 Agent 调接口失败后可从最近成功节点恢复，不重复执行已完成工作。

**Architecture:** `SqliteSaver` 作为 checkpointer，编译图时注入。每个 Agent 节点执行完毕后自动全量快照 State → SQLite。恢复时使用相同 `thread_id` 重新 invoke，LangGraph 自动识别已完成的 checkpoint 并跳过。

**Tech Stack:** LangGraph Checkpointer API, SqliteSaver, SQLite

---

### Task 1: 引入 SqliteSaver 并改造图编译

**Files:**
- Modify: `agent_langgraph.py`（`_build_graph()` 函数 + `_get_graph()` 缓存逻辑）

- [ ] **Step 1: 添加 SqliteSaver 导入**

在 `agent_langgraph.py` 顶部导入区添加：

```python
from langgraph.checkpoint.sqlite import SqliteSaver
```

- [ ] **Step 2: 改造 `_build_graph()` — 编译时注入 checkpointer**

```python
def _build_graph():
    """构建多Agent图 + SqliteSaver checkpointer。

    START → extraction → regulation → assessment ↔ reflection → report → END
                                  ↑__________________________| (passed=false & round<3)
    """
    graph = StateGraph(MultiAgentState)

    graph.add_node("extraction_agent", _extraction_agent)
    graph.add_node("regulation_agent", _regulation_agent)
    graph.add_node("assessment_agent", _assessment_agent)
    graph.add_node("reflection_agent", _reflection_agent)
    graph.add_node("report_agent", _report_agent)

    graph.add_edge(START, "extraction_agent")
    graph.add_edge("extraction_agent", "regulation_agent")
    graph.add_edge("regulation_agent", "assessment_agent")
    graph.add_edge("assessment_agent", "reflection_agent")

    graph.add_conditional_edges(
        "reflection_agent",
        _supervisor,
        {
            "assessment_agent": "assessment_agent",
            "report_agent": "report_agent",
            END: END,
        },
    )
    graph.add_edge("report_agent", END)

    # 注入 SqliteSaver checkpointer
    checkpointer = SqliteSaver.from_conn_string("checkpoints.db")
    return graph.compile(checkpointer=checkpointer)
```

- [ ] **Step 3: 调整 `_get_graph()` 缓存**

`_get_graph()` 中 graph 实例现在绑定了 SQLite 连接，缓存逻辑需确认连接生命周期不受影响。若 `SqliteSaver` 自带连接池则保持现有 `lru_cache` 即可。

---

### Task 2: 改造 `review_contract_langgraph()` — 支持 thread_id

**Files:**
- Modify: `agent_langgraph.py`（`review_contract_langgraph()` 函数签名 + invoke 调用）

- [ ] **Step 1: 添加 thread_id 参数**

```python
def review_contract_langgraph(
    contract_text: str,
    contract_type: str,
    thread_id: str | None = None,
) -> str:
    """执行完整的合同审查（LangGraph 多Agent版 + Checkpoint 断点恢复）。

    Args:
        contract_text: 合同全文
        contract_type: 合同类型
        thread_id: 会话线程ID。相同 thread_id 可从上次中断的 checkpoint 恢复。
                   为 None 时自动生成新 ID。

    Returns:
        最终审查报告文本
    """
    if thread_id is None:
        thread_id = str(uuid.uuid4())
```

- [ ] **Step 2: invoke 时传入 config 含 thread_id**

```python
    config = {"configurable": {"thread_id": thread_id}}
    graph = _get_graph()
    result = graph.invoke(initial_state, config)
```

- [ ] **Step 3: 返回结果中包含 thread_id（可选）**

考虑将返回值改为 `tuple[str, str]` → `(report, thread_id)`，方便调用方记录 thread_id 用于后续恢复。或新增独立函数 `review_contract_langgraph_with_id()` 返回完整信息。

---

### Task 3: 添加断点恢复入口

**Files:**
- Modify: `agent_langgraph.py`（新增 `resume_review()` 函数）
- Modify: `api.py`（新增 `/api/v1/review/resume` 端点，可选）

- [ ] **Step 1: 新增 `resume_review()` 函数**

```python
def resume_review(thread_id: str) -> str:
    """从指定 thread_id 的最近 checkpoint 恢复审查。

    Args:
        thread_id: 之前中断的会话 ID

    Returns:
        最终审查报告文本

    Raises:
        ValueError: thread_id 对应的 checkpoint 不存在
    """
    config = {"configurable": {"thread_id": thread_id}}
    graph = _get_graph()

    # 检查 checkpoint 是否存在
    state = graph.get_state(config)
    if state is None or state.values.get("current_phase") is None:
        raise ValueError(f"未找到 thread_id={thread_id} 的 checkpoint")

    result = graph.invoke(None, config)  # None = 从最近 checkpoint 恢复
    final_report = result.get("final_report", "")
    return clean_report(final_report, "", "")
```

- [ ] **Step 2: （可选）API 端点**

在 `api.py` 中添加：

```python
@app.post("/api/v1/review/resume")
async def resume_review_endpoint(thread_id: str):
    """从断点恢复审查"""
    try:
        report = resume_review(thread_id)
        return {"status": "success", "report": report, "thread_id": thread_id}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
```

---

### Task 4: 测试 + 验证

- [ ] **Step 1: 单元测试 — checkpoint 写入**

```python
def test_checkpoint_created_after_each_node():
    """验证每个 Agent 节点执行后 checkpoint 写入 SQLite。"""
    ...
```

- [ ] **Step 2: 单元测试 — 断点恢复**

```python
def test_resume_from_checkpoint():
    """模拟中途失败后，用相同 thread_id 恢复，跳过已完成节点。"""
    ...
```

- [ ] **Step 3: 集成测试 — 端到端恢复**

手动场景：
1. 启动一次审查，在 assessment_agent 阶段模拟 LLM 超时
2. 用相同 thread_id 重新 invoke
3. 验证 extraction 和 regulation 不会重复执行（检查 messages 中无重复工具调用）

---

### 关键设计决策

| 决策点 | 选择 | 理由 |
|:---|:---|:---|
| Checkpointer 存储 | SQLite（本地文件） | 零外部依赖，面试展示足够 |
| 序列化方式 | LangGraph 默认 JSON | 自动处理 TypedDict → JSON |
| thread_id 生成 | UUID4 | 无碰撞，无需中心化分配 |
| 恢复粒度 | 节点级 | LangGraph 原生支持，无需手动管理 |
| 失败检测 | 异常抛出 → 调用方 catch → re-invoke | 不侵入图结构 |

---

### 验收清单

| # | 标准 | 状态 |
|---|------|------|
| 1 | 编译图时注入 SqliteSaver，checkpoints.db 正常生成 | ⬜ |
| 2 | 每个 Agent 节点执行后 checkpoint 自动写入 | ⬜ |
| 3 | 模拟中间节点失败，同 thread_id 恢复后从断点继续 | ⬜ |
| 4 | 恢复后已完成节点不重复执行 | ⬜ |
| 5 | 22 个单元测试 + 3 个集成测试全部通过 | ⬜ |
| 6 | `review_contract_langgraph()` 签名向后兼容 | ⬜ |
