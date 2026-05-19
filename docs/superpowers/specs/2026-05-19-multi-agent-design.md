# 多Agent协作改造 · 设计文档

**日期**: 2026-05-19
**状态**: 待确认
**范围**: `agent_langgraph.py`

---

## 一、改动概要

将当前单Agent ReAct循环拆分为 5个专职Agent节点 + 1个纯规则Supervisor路由，流程控制权从LLM手中收到代码手中。

## 二、架构对比

### 改前

```
1个Agent (agent_node)
├── 1个超长System Prompt（7步指令 + 6种合同红线规则）
├── 11个工具（全部可见）
├── 全局变量 _risk_findings 累积结果
└── 图结构: agent ↔ tools（简单循环，无顺序保证）
```

流程顺序全靠自然语言"建议"，LLM偶尔跳过步骤或调错工具。

### 改后

```
5个Agent + 1个Supervisor（规则函数，不调LLM）
├── extraction_agent  → extract_clauses（1个工具）
├── regulation_agent  → search_regulation等（5个检索工具）
├── assessment_agent  → analyze_single_clause（1个工具）
├── reflection_agent  → check_completeness + self_reflection（2个工具）
├── report_agent      → generate_final_report（1个工具）
└── Supervisor        → 纯Python if-else，不调LLM
```

每个Agent有独立System Prompt和工具子集，通过State传递中间结果。

## 三、State 设计

```python
class MultiAgentState(TypedDict):
    # 消息历史（所有Agent共享，LangGraph Addable）
    messages: Annotated[list[BaseMessage], add_messages]

    # 输入参数
    contract_type: str
    contract_text: str

    # Agent间传递的中间产出
    clauses_json: str              # extraction_agent → 产出
    regulation_context: str         # regulation_agent → 产出（拼接所有检索结果）
    risk_findings: list[dict]       # assessment_agent → 产出
    completeness_result: str        # reflection_agent → 产出
    reflection_result: dict         # reflection_agent → 产出 {"passed": bool, "score": int}
    reflection_round: int           # 当前反思轮次

    # 最终产出
    final_report: str

    # 容错
    current_phase: str              # supervisor 路由用
    use_text_mode: bool
    text_mode_triggered: bool
```

全局变量 `_risk_findings` 废弃，改用 State 内字段传递。

## 四、5个Agent节点

### 4.1 extraction_agent
- **工具**: `extract_clauses`（1个）
- **Prompt**: 只含条款提取规则（来自 `EXTRACT_CLAUSES_SYSTEM`）
- **输入**: `contract_text`, `contract_type`
- **输出**: `clauses_json` (str)
- **结束条件**: LLM不继续调工具 → 本轮完成

### 4.2 regulation_agent
- **工具**: `search_regulation`, `search_case_law`, `check_local_policy`, `lookup_tax_rule`, `web_search`（5个）
- **Prompt**: 只含当前合同类型的法规检索清单（从 `AGENT_SYSTEM_PROMPT` 第2步抽取）
- **输入**: `contract_type`, `clauses_json`（知道合同有哪些条款，决定搜什么）
- **输出**: `regulation_context`（str，拼接所有检索结果）
- **结束条件**: LLM不继续调工具 → 本轮完成

### 4.3 assessment_agent
- **工具**: `analyze_single_clause`（1个）
- **Prompt**: 来自 `ANALYZE_SINGLE_CLAUSE_SYSTEM`（评分规则 + 红线清单）
- **输入**: `clauses_json`, `regulation_context`, `contract_type`
- **输出**: `risk_findings` (list[dict])
- **结束条件**: LLM判断所有条款都已分析 → 停止调工具

### 4.4 reflection_agent
- **工具**: `check_completeness`, `self_reflection`（2个）
- **Prompt**: 来自 `SELF_REFLECTION_SYSTEM` + `CHECK_COMPLETENESS_SYSTEM`
- **输入**: `clauses_json`, `risk_findings`, `contract_type`
- **输出**: `completeness_result`, `reflection_result`, `reflection_round += 1`
- **工具调用顺序**: 先 `check_completeness` → 再 `self_reflection`
- **结束条件**: 两个工具都调用完 → 完成

### 4.5 report_agent
- **工具**: `generate_final_report`（1个）
- **Prompt**: 来自 `GENERATE_REPORT_SYSTEM`
- **输入**: `risk_findings`, `contract_type`, `completeness_result`
- **输出**: `final_report` (str)
- **结束条件**: 调完 `generate_final_report` → 完成

## 五、Supervisor 路由

```python
def supervisor(state: MultiAgentState) -> str:
    phase = state["current_phase"]

    if phase == "extraction":
        return "regulation_agent"

    elif phase == "regulations":
        return "assessment_agent"

    elif phase == "assessment":
        return "reflection_agent"

    elif phase == "reflection":
        r = state.get("reflection_result", {})
        if not r.get("passed") and state["reflection_round"] < 3:
            return "assessment_agent"    # 回退修正
        return "report_agent"

    elif phase == "report":
        return END

    # 默认：按固定顺序推进
    return END
```

路由逻辑纯规则，不调LLM，消除路由不确定性的来源。

## 六、图结构

```
START
  │
  ▼
extraction_agent ──→ regulation_agent ──→ assessment_agent
                                               ▲        │
                                               │        ▼
                                               │   reflection_agent
                                               │        │
                                               │   passed=false && round<3 ?
                                               │        │
                                               └────────┘   yes
                                                               │ no
                                                               ▼
                                                         report_agent ──→ END
```

- 每个Agent节点内部仍是 ReAct 循环（LLM ↔ 工具），这是每条水平线上的自环
- Node间路由由 Supervisor（规则函数）驱动
- 质量回退是一个固定的条件边，不由 LLM 决定

## 七、每个Agent的内部结构

每个Agent节点函数遵循相同的模式：

```python
def xxx_agent(state: MultiAgentState) -> dict:
    # 1. 从 State 取上游产出
    # 2. 构造专属 System Prompt
    # 3. 初始化 messages（System + 上下文）
    # 4. ReAct 循环：调 LLM → 解析 tool_calls → 执行工具 → 收集结果
    # 5. 写回 State（产出 + current_phase）
    return {"key": value, "current_phase": "next"}
```

具体实现复用 `_call_agent_impl()` 中的 qwen JSON修复 + 文本模式兜底逻辑。

## 八、工具分配一览

| 工具 | extraction | regulation | assessment | reflection | report |
|:---|:---:|:---:|:---:|:---:|:---:|
| `extract_clauses` | ✅ | | | | |
| `search_regulation` | | ✅ | | | |
| `search_case_law` | | ✅ | | | |
| `check_local_policy` | | ✅ | | | |
| `lookup_tax_rule` | | ✅ | | | |
| `web_search` | | ✅ | | | |
| `analyze_single_clause` | | | ✅ | | |
| `check_completeness` | | | | ✅ | |
| `self_reflection` | | | | ✅ | |
| `switch_perspective` | | | | | |
| `generate_final_report` | | | | | ✅ |

`switch_perspective` 暂不分配，功能后续按需挂入 reflection 或 assessment 阶段。

## 九、兼容性

### 保持不变
- `tools.py` 所有工具函数不改
- `prompts.py` 提示词内容不改，只调整在哪个Agent中使用
- `review_contract_langgraph(contract_text, contract_type)` 对外接口不变
- `main.py`（手写 ReAct 版）不受任何影响
- `llm_client.py` 不改

### 变更范围
- **`agent_langgraph.py`**：重写 Agent 节点 + Supervisor + 图结构
- **`prompts.py`**（可选微调）：为每个 Agent 拆分/精简独立的 System Prompt

### 流式（SSE）
- 先做非流式版（`review_contract_langgraph()`），稳定后改 `app.py` 的 SSE 路径
- 流式改造留作后续任务

## 十、实现步骤

1. **State 定义** — 新增 `MultiAgentState`
2. **5个 Agent 节点** — 每个按模式实现（取上游 → ReAct循环 → 写回）
3. **Supervisor 函数** — 纯规则路由
4. **图搭建** — `_build_graph()` 组装节点和边
5. **对外接口适配** — `review_contract_langgraph()` 换新图
6. **冒烟测试** — `pytest tests/test_smoke.py -v` 全部通过
