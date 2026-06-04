"""
合同审查助手 —— LangGraph 版（自定义 StateGraph + qwen 修复）

与 create_react_agent 不同，这里手动搭建图结构，
保留 LLMClient 的 qwen 专属修复：JSON修复 / 文本模式兜底 / API重试。

用法：
    from agent_langgraph import review_contract_langgraph
    report, thread_id = review_contract_langgraph(contract_text, "房屋租赁合同")
"""

import json
import os
import sqlite3
import sys
import threading
import uuid
from typing import Annotated, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from llm_client import LLMClient
from tools import AGENT_TOOLS as ALL_TOOLS_OAI
from utils import clean_report, parse_text_tool_calls, parse_tool_args

load_dotenv()


def _get_client() -> LLMClient:
    return LLMClient(api_key=os.getenv("DASHSCOPE_API_KEY"))


# ═══════════════════════════════════════════════════════════
# 工具定义（@tool 装饰器，供 Agent 节点内部 ReAct 循环使用）
# ═══════════════════════════════════════════════════════════


@tool
def search_regulation(keyword: str) -> str:
    """查询中国法律法规原文和司法实践。在对任何条款下结论之前，必须先调用此函数获取法规依据。"""
    from tools import search_regulation as _fn

    return _fn(keyword)


@tool
def search_case_law(keyword: str) -> str:
    """搜索相关法院判例，了解类似纠纷法院怎么判。"""
    from tools import search_case_law as _fn

    return _fn(keyword)


@tool
def check_local_policy(city: str, keyword: str = "") -> str:
    """查询特定城市的房屋租赁地方政策。"""
    from tools import check_local_policy as _fn

    return _fn(city, keyword)


@tool
def lookup_tax_rule(topic: str) -> str:
    """查询与合同相关的税务规则。"""
    from tools import lookup_tax_rule as _fn

    return _fn(topic)


@tool
def web_search(keyword: str) -> str:
    """联网搜索最新法规动态和行业资讯。"""
    from tools import web_search as _fn

    return _fn(keyword)


@tool
def extract_clauses(contract_type: str, contract_text: str = "") -> str:
    """从合同全文提取关键条款，按类别整理为结构化 JSON。审查合同的第一步。"""
    from tools import extract_clauses as _fn

    text = contract_text or _get_contract_text()
    return _fn(_get_client(), text, contract_type)


@tool
def analyze_single_clause(
    clause_text: str,
    category: str,
    contract_type: str,
    clause_position: str = "",
    regulation_context: str = "",
) -> str:
    """对单条合同条款做深度风险分析。建议先查法规再调用此函数。"""
    from tools import analyze_single_clause as _fn

    result = _fn(
        _get_client(), clause_text, category, contract_type, clause_position, regulation_context
    )
    try:
        cleaned = (
            result.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        )
        parsed = json.loads(cleaned)
        _get_risk_findings().append(parsed)
    except (json.JSONDecodeError, AttributeError):
        pass
    return result


@tool
def generate_final_report(contract_type: str, risk_findings_json: str = "") -> str:
    """汇总所有风险分析发现，生成格式化的最终审查报告。
    risk_findings_json 可传空字符串——系统自动使用累积结果。"""
    from tools import generate_final_report as _fn

    rf = _get_risk_findings()
    if (not risk_findings_json or len(risk_findings_json) < 100) and rf:
        risk_findings_json = json.dumps(rf, ensure_ascii=False)
    elif not risk_findings_json:
        risk_findings_json = "[]"
    return _fn(_get_client(), risk_findings_json, contract_type)


@tool
def check_completeness(clauses_json: str, contract_type: str) -> str:
    """检查合同条款是否完整，找出缺失的必要条款。必须调用，不可跳过。"""
    from tools import check_completeness as _fn

    return _fn(_get_client(), clauses_json, contract_type)


@tool
def switch_perspective(findings_json: str, perspective: str) -> str:
    """从另一方视角重新审视风险分析结果，发现单视角盲区。"""
    from tools import switch_perspective as _fn

    return _fn(_get_client(), findings_json, perspective)


@tool
def self_reflection(
    clauses_json: str = "",
    findings_json: str = "",
    completeness_result: str = "",
    contract_type: str = "",
) -> str:
    """全局质量审核——对审查分析结果做一致性、覆盖性和评分合规检查。"""
    from tools import self_reflection as _fn

    return _fn(
        _get_client(),
        clauses_json,
        findings_json,
        completeness_result,
        contract_type,
    )


# 线程安全的风险发现存储（替代 module-level list，防止并发请求干扰）
_risk_findings_local = threading.local()

# 模块级合同文本存储（供 extract_clauses 工具回退使用）
# 注意：不能用 thread-local，因为 StreamingReviewRunner 在单独线程中运行 graph
_contract_text: str = ""


def _get_risk_findings() -> list[dict]:
    if not hasattr(_risk_findings_local, "data"):
        _risk_findings_local.data = []
    return _risk_findings_local.data


def _clear_risk_findings():
    _risk_findings_local.data = []


def _set_contract_text(text: str):
    global _contract_text
    _contract_text = text


def _get_contract_text() -> str:
    return _contract_text


# ═══════════════════════════════════════════════════════════
# 消息格式转换
# ═══════════════════════════════════════════════════════════


def _langchain_to_openai(messages: list) -> list[dict]:
    """LangChain 消息 → OpenAI 兼容格式（供 LLMClient.chat() 使用）。"""
    result = []
    for msg in messages:
        if isinstance(msg, SystemMessage):
            result.append({"role": "system", "content": msg.content})
        elif isinstance(msg, HumanMessage):
            result.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            d = {"role": "assistant", "content": msg.content or ""}
            if getattr(msg, "tool_calls", None):
                d["tool_calls"] = []
                for tc in msg.tool_calls:
                    d["tool_calls"].append(
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": json.dumps(tc["args"], ensure_ascii=False),
                            },
                        }
                    )
            result.append(d)
        elif isinstance(msg, ToolMessage):
            result.append(
                {
                    "role": "tool",
                    "tool_call_id": msg.tool_call_id,
                    "content": msg.content,
                }
            )
    return result


def _openai_to_ai_message(msg) -> AIMessage:
    """OpenAI ChatCompletionMessage → LangChain AIMessage。"""
    content = msg.content or ""
    tool_calls = getattr(msg, "tool_calls", None)

    if not tool_calls:
        return AIMessage(content=content)

    lc_tool_calls = []
    for tc in tool_calls:
        args = parse_tool_args(tc.function.arguments)
        lc_tool_calls.append(
            {
                "name": tc.function.name,
                "args": args,
                "id": tc.id,
            }
        )
    return AIMessage(content=content, tool_calls=lc_tool_calls)


# ═══════════════════════════════════════════════════════════
# 工具分组：每个Agent只能看到自己的工具子集
# ═══════════════════════════════════════════════════════════

# 可调用工具映射（名字 → @tool函数，供内部ReAct循环执行）
_AGENT_TOOL_FNS: dict[str, callable] = {
    "extract_clauses": extract_clauses,
    "search_regulation": search_regulation,
    "search_case_law": search_case_law,
    "check_local_policy": check_local_policy,
    "lookup_tax_rule": lookup_tax_rule,
    "web_search": web_search,
    "analyze_single_clause": analyze_single_clause,
    "check_completeness": check_completeness,
    "self_reflection": self_reflection,
    "generate_final_report": generate_final_report,
    "switch_perspective": switch_perspective,
}

# OpenAI格式工具描述（按Agent分组，供LLM Function Calling使用）
_EXTRACTION_OAI_TOOLS = [t for t in ALL_TOOLS_OAI if t["function"]["name"] == "extract_clauses"]
_REGULATION_OAI_TOOLS = [
    t
    for t in ALL_TOOLS_OAI
    if t["function"]["name"]
    in {
        "search_regulation",
        "search_case_law",
        "check_local_policy",
        "lookup_tax_rule",
        "web_search",
    }
]
_ASSESSMENT_OAI_TOOLS = [
    t for t in ALL_TOOLS_OAI if t["function"]["name"] == "analyze_single_clause"
]
_REFLECTION_OAI_TOOLS = [
    t for t in ALL_TOOLS_OAI if t["function"]["name"] in {"check_completeness", "self_reflection"}
]
_REPORT_OAI_TOOLS = [t for t in ALL_TOOLS_OAI if t["function"]["name"] == "generate_final_report"]


# ═══════════════════════════════════════════════════════════
# 内部ReAct循环：Agent节点复用的 LLM ↔ 工具 执行器
# ═══════════════════════════════════════════════════════════


def _run_agent_loop(
    messages: list[BaseMessage],
    tool_names: set[str],
    oai_tools: list[dict],
    max_iterations: int = 30,
) -> list[BaseMessage]:
    """在给定的消息上下文中运行 ReAct 循环，直到LLM不再调用工具。

    Args:
        messages: 初始消息列表（含 SystemMessage + 上下文 HumanMessage）
        tool_names: 本Agent允许调用的工具名集合
        oai_tools: 对应的OpenAI格式工具定义列表
        max_iterations: 最大循环次数，防止死循环

    Returns:
        追加了所有AI消息和ToolMessage的完整消息列表
    """
    use_text = False

    for _ in range(max_iterations):
        openai_msgs = _langchain_to_openai(messages)
        resp, use_text = _call_agent_impl(openai_msgs, use_text, oai_tools)
        msg = resp.choices[0].message

        if use_text:
            content = msg.content or ""
            text_calls = parse_text_tool_calls(content)
            if not text_calls:
                messages.append(AIMessage(content=content))
                break

            messages.append(AIMessage(content=content))
            for i, (name, args) in enumerate(text_calls):
                fn = _AGENT_TOOL_FNS.get(name)
                if fn and name in tool_names:
                    try:
                        result = fn.invoke(args)
                    except Exception:
                        result = f"工具执行失败: {name}"
                else:
                    result = f"工具 {name} 不可用或未授权"
                messages.append(
                    ToolMessage(
                        content=str(result),
                        name=name,
                        tool_call_id=f"text_{i}_{name}",
                    )
                )
        else:
            ai_msg = _openai_to_ai_message(msg)
            messages.append(ai_msg)

            if not msg.tool_calls:
                break

            for tc in msg.tool_calls:
                name = tc.function.name
                fn = _AGENT_TOOL_FNS.get(name)
                if fn and name in tool_names:
                    try:
                        args = parse_tool_args(tc.function.arguments)
                        result = fn.invoke(args)
                    except Exception:
                        result = f"工具执行失败: {name}"
                else:
                    result = f"工具 {name} 不可用或未授权"
                messages.append(
                    ToolMessage(
                        content=str(result),
                        name=name,
                        tool_call_id=tc.id,
                    )
                )

    return messages


# ═══════════════════════════════════════════════════════════
# 全局状态
# ═══════════════════════════════════════════════════════════


class MultiAgentState(TypedDict):
    """多Agent协作的全局状态。"""

    messages: Annotated[list[BaseMessage], add_messages]
    contract_type: str
    contract_text: str

    # Agent间传递的中间产出
    clauses_json: str
    regulation_context: str
    risk_findings: list[dict]
    completeness_result: str
    reflection_result: dict
    reflection_round: int

    # 最终产出
    final_report: str

    # 路由 + 容错
    current_phase: str
    use_text_mode: bool
    text_mode_triggered: bool


# ═══════════════════════════════════════════════════════════
# Agent 节点 1：条款提取
# ═══════════════════════════════════════════════════════════

_EXTRACTION_SYSTEM = """你是资深法务合同审查师。请调用 extract_clauses 工具从合同中提取所有关键条款。

调用参数：
- contract_type: 合同类型
- contract_text: 留空即可（系统会自动注入合同全文）

提取完条款后，用中文简要说明提取了哪些类别的条款。不要继续调用其他工具。"""


def _extraction_agent(state: MultiAgentState) -> dict:
    """提取合同条款 → 产出 clauses_json。"""
    user_msg = f"合同类型：{state['contract_type']}\n\n合同全文：\n{state['contract_text']}"
    messages: list[BaseMessage] = [
        SystemMessage(content=_EXTRACTION_SYSTEM),
        HumanMessage(content=user_msg),
    ]

    messages = _run_agent_loop(
        messages,
        tool_names={"extract_clauses"},
        oai_tools=_EXTRACTION_OAI_TOOLS,
    )

    # 提取 clauses_json：取最后一个 ToolMessage（extract_clauses 的返回）
    clauses_json = ""
    for msg in reversed(messages):
        if isinstance(msg, ToolMessage) and msg.name == "extract_clauses":
            clauses_json = msg.content or ""
            break

    return {
        "messages": messages,
        "clauses_json": clauses_json,
        "current_phase": "extraction",
    }


# ═══════════════════════════════════════════════════════════
# Agent 节点 2：法规检索
# ═══════════════════════════════════════════════════════════

# 按合同类型的法规检索清单
_REGULATION_CHECKLIST: dict[str, list[str]] = {
    "房屋租赁合同": [
        "住房租赁条例",
        "租赁押金退还",
        "租赁违约金",
        "租赁期限与维修义务",
        "转租与优先购买权优先承租权",
        "合同争议解决",
    ],
    "劳动合同": [
        "劳动争议司法解释",
        "劳动合同试用期",
        "劳动报酬与加班费",
        "社会保险社保与违约金",
        "劳动关系与竞业限制",
        "劳动合同解除调岗与补偿",
        "合同争议解决",
    ],
    "买卖合同": [
        "买卖合同",
        "格式条款",
        "不可抗力与情势变更",
        "知识产权归属",
        "合同争议解决",
        "合同无效情形",
    ],
    "服务合同": [
        "预付式消费",
        "服务合同",
        "格式条款",
        "知识产权归属",
        "合同争议解决",
    ],
    "合作协议": [
        "合作协议",
        "知识产权归属",
        "格式条款",
        "合同争议解决",
        "不可抗力与情势变更",
        "合同无效情形",
        "劳动关系与竞业限制",
    ],
    "借款合同": [
        "民间借贷利率",
        "借款合同",
        "担保规则",
        "合同争议解决",
        "合同无效情形",
    ],
}


def _regulation_agent(state: MultiAgentState) -> dict:
    """按合同类型逐项检索法规 → 产出 regulation_context。"""
    ct = state["contract_type"]
    checklist = _REGULATION_CHECKLIST.get(ct, ["合同争议解决", "格式条款"])
    keywords = "、".join(checklist)

    system = (
        f"你是法规检索专家。当前合同类型为「{ct}」，你必须按以下清单逐条调用 "
        f"search_regulation 工具，不可跳过任何一条：\n\n"
        + "\n".join(f'  - search_regulation("{kw}")' for kw in checklist)
        + "\n\n还可按需调用 search_case_law、check_local_policy、lookup_tax_rule、web_search。"
        "\n查完所有法规后，用中文输出「法规检索完成」，列出已查关键词。"
    )
    user_msg = (
        f"合同类型：{ct}\n"
        f"已提取的条款摘要：\n{state['clauses_json'][:3000]}\n\n"
        f"请逐条检索以下关键词：{keywords}"
    )
    messages: list[BaseMessage] = [
        SystemMessage(content=system),
        HumanMessage(content=user_msg),
    ]

    messages = _run_agent_loop(
        messages,
        tool_names={
            "search_regulation",
            "search_case_law",
            "check_local_policy",
            "lookup_tax_rule",
            "web_search",
        },
        oai_tools=_REGULATION_OAI_TOOLS,
    )

    # 拼接所有检索结果
    parts: list[str] = []
    for msg in messages:
        if isinstance(msg, ToolMessage) and msg.name in {
            "search_regulation",
            "search_case_law",
            "check_local_policy",
            "lookup_tax_rule",
            "web_search",
        }:
            name = msg.name or "unknown"
            content = (msg.content or "")[:2000]
            parts.append(f"【{name}】\n{content}")

    return {
        "messages": messages,
        "regulation_context": "\n\n".join(parts),
        "current_phase": "regulation",
    }


# ═══════════════════════════════════════════════════════════
# Agent 节点 3：风险评估
# ═══════════════════════════════════════════════════════════

_ASSESSMENT_SYSTEM = """你是合同风险分析师。请逐条调用 analyze_single_clause 工具分析合同条款。

对每条条款调用一次 analyze_single_clause。参数直接从下方"已提取的条款"中对应条目提取：
- clause_text: 填入对应条目的"原文："行（逐字复制，不要改写）
- category: 填入对应条目的"类别："行
- contract_type: 合同类型
- clause_position: 填入对应条目的"位置："信息
- regulation_context: 已查到的法规上下文

所有条款分析完毕后，用中文输出"风险评估完成"，列出分析了多少条条款。"""


def _assessment_agent(state: MultiAgentState) -> dict:
    """逐条分析条款风险 → 产出 risk_findings。"""
    # 将 clauses_json 解析为逐条的"原文：XXX"格式，防止LLM把类别名当原文
    clauses_text = _format_clauses_for_assessment(state["clauses_json"])

    user_msg = (
        f"合同类型：{state['contract_type']}\n\n"
        f"已提取的条款（逐条列出，每条包含类别、位置和真实原文）：\n{clauses_text}\n\n"
        f"法规检索结果：\n{state.get('regulation_context', '无')[:4000]}"
    )
    messages: list[BaseMessage] = [
        SystemMessage(content=_ASSESSMENT_SYSTEM),
        HumanMessage(content=user_msg),
    ]

    messages = _run_agent_loop(
        messages,
        tool_names={"analyze_single_clause"},
        oai_tools=_ASSESSMENT_OAI_TOOLS,
    )

    # 收集所有 analyze_single_clause 返回的风险发现
    risk_findings: list[dict] = []
    for msg in messages:
        if isinstance(msg, ToolMessage) and msg.name == "analyze_single_clause":
            try:
                content = (msg.content or "").strip()
                content = (
                    content.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
                )
                parsed = json.loads(content)
                risk_findings.append(parsed)
            except (json.JSONDecodeError, AttributeError):
                pass

    return {
        "messages": messages,
        "risk_findings": risk_findings,
        "current_phase": "assessment",
    }


def _format_clauses_for_assessment(clauses_json: str) -> str:
    """将提取的条款JSON解析为逐条明文，清晰分离类别与原文。
    兼容新旧两种格式：旧格式{类别: [...]}, 新格式[{category, clause_text, ...}]。
    """
    if not clauses_json:
        return "（无条款）"
    try:
        data = json.loads(clauses_json)
    except json.JSONDecodeError:
        from utils import repair_json

        fixed = repair_json(clauses_json)
        if fixed:
            try:
                data = json.loads(fixed)
            except json.JSONDecodeError:
                return clauses_json
        else:
            return clauses_json

    lines: list[str] = []
    idx = 0

    # 新格式：扁平数组 [{category, clause_text, ...}]
    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            idx += 1
            cat = item.get("category", "")
            ct = item.get("clause_text", "")
            pos = item.get("position", "")
            simplified = item.get("simplified", "")
            pos_str = f" [位置：{pos}]" if pos else ""
            lines.append(f"--- 条款 {idx} ---")
            lines.append(f"类别：{cat}{pos_str}")
            lines.append(f"原文：{ct}")
            if simplified:
                lines.append(f"摘要：{simplified}")
    # 旧格式：{类别: [{clause_text, ...}]}
    elif isinstance(data, dict):
        for category, items in data.items():
            cat_name = category.lstrip("0123456789. ").strip()
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                idx += 1
                ct = item.get("clause_text", "")
                pos = item.get("position", "")
                simplified = item.get("simplified", "")
                pos_str = f" [位置：{pos}]" if pos else ""
                lines.append(f"--- 条款 {idx} ---")
                lines.append(f"类别：{cat_name}{pos_str}")
                lines.append(f"原文：{ct}")
                if simplified:
                    lines.append(f"摘要：{simplified}")

    if not lines:
        return clauses_json
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════
# Agent 节点 4：质量审核
# ═══════════════════════════════════════════════════════════

_REFLECTION_SYSTEM = """你是合同审查质量审核员。请依次调用以下两个工具：

1. 先调用 check_completeness —— 检查已提取的条款是否有缺失
2. 再调用 self_reflection —— 对分析结果做一致性、覆盖性、评分合规检查

两个工具都调用完毕后，用中文输出审核结论。"""


def _reflection_agent(state: MultiAgentState) -> dict:
    """完整性检查 + 质量审核 → 产出 completeness_result + reflection_result。"""
    findings_json = json.dumps(state.get("risk_findings", []), ensure_ascii=False)
    user_msg = (
        f"合同类型：{state['contract_type']}\n\n"
        f"已提取的条款：\n{state['clauses_json'][:2000]}\n\n"
        f"风险分析结果：\n{findings_json[:3000]}\n\n"
        f"请先调用 check_completeness，再调用 self_reflection。"
    )
    messages: list[BaseMessage] = [
        SystemMessage(content=_REFLECTION_SYSTEM),
        HumanMessage(content=user_msg),
    ]

    messages = _run_agent_loop(
        messages,
        tool_names={"check_completeness", "self_reflection"},
        oai_tools=_REFLECTION_OAI_TOOLS,
    )

    # 提取结果
    completeness_result = ""
    reflection_result: dict = {"passed": True, "score": 10, "issues": []}

    for msg in messages:
        if isinstance(msg, ToolMessage):
            if msg.name == "check_completeness":
                completeness_result = msg.content or ""
            elif msg.name == "self_reflection":
                try:
                    content = (msg.content or "").strip()
                    content = (
                        content.removeprefix("```json")
                        .removeprefix("```")
                        .removesuffix("```")
                        .strip()
                    )
                    reflection_result = json.loads(content)
                except (json.JSONDecodeError, AttributeError):
                    pass

    current_round = state.get("reflection_round", 0) + 1

    return {
        "messages": messages,
        "completeness_result": completeness_result,
        "reflection_result": reflection_result,
        "reflection_round": current_round,
        "current_phase": "reflection",
    }


# ═══════════════════════════════════════════════════════════
# Agent 节点 5：报告生成
# ═══════════════════════════════════════════════════════════

_REPORT_SYSTEM = """你是法务报告编辑。请调用 generate_final_report 工具生成审查报告。

参数：
- contract_type: 合同类型
- risk_findings_json: 传空字符串""即可（系统会自动使用累积的风险分析结果）

调用完毕后，你的工作就完成了。"""


def _report_agent(state: MultiAgentState) -> dict:
    """汇总生成最终报告 → 产出 final_report。"""
    findings_json = json.dumps(state.get("risk_findings", []), ensure_ascii=False)
    user_msg = (
        f"合同类型：{state['contract_type']}\n\n"
        f"风险发现：\n{findings_json[:6000]}\n\n"
        f"完整性检查结果：\n{state.get('completeness_result', '无')[:1000]}\n\n"
        f"请调用 generate_final_report 生成最终报告。"
    )
    messages: list[BaseMessage] = [
        SystemMessage(content=_REPORT_SYSTEM),
        HumanMessage(content=user_msg),
    ]

    messages = _run_agent_loop(
        messages,
        tool_names={"generate_final_report"},
        oai_tools=_REPORT_OAI_TOOLS,
    )

    # 提取报告
    final_report = ""
    for msg in reversed(messages):
        if isinstance(msg, ToolMessage) and msg.name == "generate_final_report":
            final_report = msg.content or ""
            break

    # 回退：取最后一条有实质内容的 AI 消息
    if not final_report:
        for msg in reversed(messages):
            content = getattr(msg, "content", None)
            tc = getattr(msg, "tool_calls", None)
            if content and not tc and isinstance(content, str) and len(content) > 100:
                final_report = content
                break

    return {
        "messages": messages,
        "final_report": final_report,
        "current_phase": "report",
    }


# ═══════════════════════════════════════════════════════════
# Supervisor 路由（纯规则，不调LLM）
# ═══════════════════════════════════════════════════════════


def _supervisor(state: MultiAgentState) -> str:
    """纯规则路由：仅从 reflection_agent 调用，判断质量是否通过。"""
    r = state.get("reflection_result", {})
    if not r.get("passed") and state.get("reflection_round", 0) < 1:
        return "assessment_agent"
    return "report_agent"


def _call_agent_impl(
    openai_msgs: list[dict], use_text: bool, oai_tools: list[dict] | None = None
) -> tuple:
    """调用 LLMClient，返回 (response, used_text_mode)。带 JSON 修复 + 重试。"""
    if oai_tools is None:
        oai_tools = ALL_TOOLS_OAI
    client = _get_client()

    for attempt in range(4):
        try:
            if use_text:
                resp = client.chat(openai_msgs, tools=None)
            else:
                resp = client.chat(openai_msgs, tools=oai_tools)
            return resp, use_text
        except Exception as e:
            err = str(e)
            # qwen JSON 参数格式错误 → 切换到文本模式
            if "function.arguments" in err and "JSON" in err:
                use_text = True
                continue
            # 一般网络/API错误 → 重试
            if attempt < 3:
                continue
            raise
    raise RuntimeError("LLM 调用失败：超过最大重试次数")


# ═══════════════════════════════════════════════════════════
# 搭建图
# ═══════════════════════════════════════════════════════════

# SQLite 连接 + Checkpointer（模块级，保持连接存活）
_checkpoint_conn: sqlite3.Connection | None = None


def _build_graph():
    """构建多Agent图：5个Agent节点 + Supervisor路由 + SqliteSaver断点。

    START → extraction → regulation → assessment ↔ reflection → report → END
                                  ↑__________________________| (passed=false & round<3)

    每个节点执行完毕后自动 checkpoint → checkpoints.db。
    """
    global _checkpoint_conn

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

    # reflection → assessment（回退）or report → END
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
    try:
        _checkpoint_conn = sqlite3.connect("checkpoints.db", check_same_thread=False)
    except sqlite3.Error as e:
        raise RuntimeError(
            f"无法创建 checkpoint 数据库 checkpoints.db：{e}。请检查磁盘空间和目录写入权限。"
        ) from e
    checkpointer = SqliteSaver(_checkpoint_conn)
    return graph.compile(checkpointer=checkpointer)


_compiled_graph = None
_graph_lock = threading.Lock()


def _get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        with _graph_lock:
            if _compiled_graph is None:
                _compiled_graph = _build_graph()
    return _compiled_graph


# ═══════════════════════════════════════════════════════════
# 公开接口
# ═══════════════════════════════════════════════════════════


def _extract_final_report(result: dict) -> str:
    """从 graph.invoke() 结果中提最终报告，带多级回退。"""
    final_report = result.get("final_report", "")

    if not final_report:
        for msg in reversed(result.get("messages", [])):
            if isinstance(msg, ToolMessage) and msg.name == "generate_final_report":
                final_report = msg.content or ""
                break

    if not final_report:
        for msg in reversed(result.get("messages", [])):
            content = getattr(msg, "content", None)
            tc = getattr(msg, "tool_calls", None)
            if content and not tc and isinstance(content, str) and len(content) > 100:
                final_report = content
                break

    if not final_report and result.get("messages"):
        last = result["messages"][-1]
        final_report = getattr(last, "content", "") or ""

    return final_report


def review_contract_langgraph(
    contract_text: str,
    contract_type: str,
    thread_id: str | None = None,
) -> tuple[str, str]:
    """执行完整的合同审查（LangGraph 多Agent版 + Checkpoint 断点恢复）。

    Args:
        contract_text: 合同全文
        contract_type: 合同类型（如"房屋租赁合同"）
        thread_id: 会话线程ID。相同 thread_id 可从中断的 checkpoint 恢复。
                   为 None 时自动生成新 ID。

    Returns:
        (最终审查报告文本, thread_id)
        — thread_id 可用于后续 resume_review() 恢复
    """
    _clear_risk_findings()
    _set_contract_text(contract_text)

    if thread_id is None:
        thread_id = str(uuid.uuid4())

    initial_state: MultiAgentState = {
        "messages": [],
        "contract_type": contract_type,
        "contract_text": contract_text,
        "clauses_json": "",
        "regulation_context": "",
        "risk_findings": [],
        "completeness_result": "",
        "reflection_result": {},
        "reflection_round": 0,
        "final_report": "",
        "current_phase": "extraction",
        "use_text_mode": False,
        "text_mode_triggered": False,
    }

    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 120}
    graph = _get_graph()
    result = graph.invoke(initial_state, config)

    return clean_report(_extract_final_report(result), contract_text, contract_type), thread_id


_phase_labels: dict[str, str] = {
    "extraction_agent": "正在提取合同条款...",
    "regulation_agent": "正在检索法规依据...",
    "assessment_agent": "正在逐条风险评估...",
    "reflection_agent": "正在反思审核...",
    "report_agent": "正在生成审查报告...",
}


def review_contract_langgraph_stream(
    contract_text: str,
    contract_type: str,
    thread_id: str | None = None,
):
    """流式版 LangGraph 多Agent审查。yield 结构化事件供 UI 实时展示。

    事件类型：
        {"type": "phase_start", "phase": "extraction_agent", "label": "..."}
        {"type": "thinking_delta", "content": "..."}
        {"type": "tool_start", "name": "..."}
        {"type": "tool_result", "name": "...", "result_len": N}
        {"type": "done", "report": "..."}
        {"type": "error", "message": "..."}
    """
    import queue
    import threading

    _clear_risk_findings()
    _set_contract_text(contract_text)

    if thread_id is None:
        thread_id = str(uuid.uuid4())

    initial_state: MultiAgentState = {
        "messages": [],
        "contract_type": contract_type,
        "contract_text": contract_text,
        "clauses_json": "",
        "regulation_context": "",
        "risk_findings": [],
        "completeness_result": "",
        "reflection_result": {},
        "reflection_round": 0,
        "final_report": "",
        "current_phase": "extraction",
        "use_text_mode": False,
        "text_mode_triggered": False,
    }

    config: RunnableConfig = {"configurable": {"thread_id": thread_id}, "recursion_limit": 120}
    graph = _get_graph()

    event_queue: queue.Queue = queue.Queue()

    def _run():
        try:
            for chunk in graph.stream(initial_state, config, stream_mode="updates"):
                for node_name, node_output in chunk.items():
                    if node_name in _phase_labels:
                        event_queue.put(
                            {
                                "type": "phase_start",
                                "phase": node_name,
                                "label": _phase_labels[node_name],
                            }
                        )
                    # 提取节点产出的新消息
                    msgs = node_output.get("messages", [])
                    for m in msgs:
                        if isinstance(m, AIMessage):
                            content = m.content or ""
                            # 工具调用已在 AIMessage 中
                            if hasattr(m, "tool_calls") and m.tool_calls:
                                for tc in m.tool_calls:
                                    event_queue.put(
                                        {
                                            "type": "tool_start",
                                            "name": tc.get("name", ""),
                                        }
                                    )
                            elif content.strip():
                                event_queue.put(
                                    {
                                        "type": "thinking_delta",
                                        "content": content,
                                    }
                                )
                        elif isinstance(m, ToolMessage):
                            event_queue.put(
                                {
                                    "type": "tool_result",
                                    "name": m.name if hasattr(m, "name") else "",
                                    "result_len": len(str(m.content)) if m.content else 0,
                                }
                            )
            # 获取最终结果
            final_state = graph.get_state(config)
            if final_state and final_state.values:
                report = clean_report(
                    _extract_final_report(final_state.values), contract_text, contract_type
                )
            else:
                report = ""
            event_queue.put({"type": "done", "report": report, "thread_id": thread_id})
        except Exception:
            import traceback

            event_queue.put(
                {"type": "error", "message": traceback.format_exc(), "thread_id": thread_id}
            )

    t = threading.Thread(target=_run, daemon=True)
    t.start()

    while t.is_alive() or not event_queue.empty():
        try:
            yield event_queue.get(timeout=0.1)
        except queue.Empty:
            pass


def resume_review(thread_id: str) -> str:
    """从指定 thread_id 的最近 checkpoint 恢复审查。

    中间某 Agent 调接口失败后，用相同 thread_id 调用此函数，
    LangGraph 自动从最近一次成功的 checkpoint 恢复 State，跳过已完成节点。

    Args:
        thread_id: 之前中断的会话 ID

    Returns:
        最终审查报告文本

    Raises:
        ValueError: thread_id 对应的 checkpoint 不存在
    """
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}, "recursion_limit": 120}
    graph = _get_graph()

    state = graph.get_state(config)
    if state is None or not state.values:
        raise ValueError(f"未找到 thread_id='{thread_id}' 的 checkpoint，请先发起一次审查")

    # 从 checkpoint state 中恢复合同信息，确保 clean_report 后处理正确
    contract_text = state.values.get("contract_text", "")
    contract_type = state.values.get("contract_type", "")

    result = graph.invoke(None, config)

    return clean_report(_extract_final_report(result), contract_text, contract_type)


# ── 命令行入口 ──
if __name__ == "__main__":
    from pathlib import Path

    from logger import init_logger, logger

    init_logger(mode="cli")

    if len(sys.argv) < 3:
        logger.info("用法: python agent_langgraph.py <合同文件> <合同类型> [--output 输出文件]")
        logger.info(
            '示例: python agent_langgraph.py sample_lease.txt "房屋租赁合同" --output report.txt'
        )
        sys.exit(1)

    filepath = Path(sys.argv[1])
    ct = sys.argv[2]
    output_path = None

    if "--output" in sys.argv:
        idx = sys.argv.index("--output")
        if idx + 1 < len(sys.argv):
            output_path = sys.argv[idx + 1]

    if not filepath.exists():
        logger.error("文件不存在: {}", filepath)
        sys.exit(1)

    contract_text = filepath.read_text(encoding="utf-8")

    if not os.getenv("DASHSCOPE_API_KEY"):
        logger.error("请设置环境变量 DASHSCOPE_API_KEY，或在 .env 文件中写入")
        sys.exit(1)

    logger.info("")
    logger.info("[LangGraph 自定义图模式]")
    logger.info("审查合同类型: {}", ct)
    logger.info("合同来源: {}", filepath)
    logger.info("=" * 60)

    report, thread_id = review_contract_langgraph(contract_text, ct)

    if output_path:
        Path(output_path).write_text(report, encoding="utf-8")
        logger.info("")
        logger.info("报告已保存至: {}", output_path)
        logger.info("thread_id: {}（可用于 resume_review 断点恢复）", thread_id)
    else:
        logger.info("=" * 60)
        logger.info("{}", report)
        logger.info("")
        logger.info("thread_id: {}（可用于 resume_review 断点恢复）", thread_id)
