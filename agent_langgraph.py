"""
合同审查助手 —— LangGraph 版（自定义 StateGraph + qwen 修复）

与 create_react_agent 不同，这里手动搭建图结构，
保留 LLMClient 的 qwen 专属修复：JSON修复 / 文本模式兜底 / API重试。

用法：
    from agent_langgraph import review_contract_langgraph
    report = review_contract_langgraph(contract_text, "房屋租赁合同")
"""

import json
import os
import sys
from typing import Annotated, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import tool
from langgraph.graph import START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from llm_client import LLMClient
from prompts import AGENT_SYSTEM_PROMPT, AGENT_USER_PROMPT
from tools import AGENT_TOOLS
from utils import clean_report, parse_text_tool_calls, parse_tool_args

load_dotenv()


# ═══════════════════════════════════════════════════════════
# 全局状态
# ═══════════════════════════════════════════════════════════

_risk_findings: list[dict] = []


def _get_client() -> LLMClient:
    return LLMClient(api_key=os.getenv("DASHSCOPE_API_KEY"))


# ═══════════════════════════════════════════════════════════
# 工具定义（@tool 装饰器，供 ToolNode 使用）
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
    """从合同全文提取关键条款，按类别整理为结构化 JSON。审查合同的第一步。
    contract_text 传空字符串即可——合同已在上下文中。"""
    from tools import extract_clauses as _fn

    return _fn(_get_client(), contract_text or "", contract_type)


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
        _risk_findings.append(parsed)
    except (json.JSONDecodeError, AttributeError):
        pass
    return result


@tool
def generate_final_report(contract_type: str, risk_findings_json: str = "") -> str:
    """汇总所有风险分析发现，生成格式化的最终审查报告。
    risk_findings_json 可传空字符串——系统自动使用累积结果。"""
    from tools import generate_final_report as _fn

    if (not risk_findings_json or len(risk_findings_json) < 100) and _risk_findings:
        risk_findings_json = json.dumps(_risk_findings, ensure_ascii=False)
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


ALL_TOOLS = [
    extract_clauses,
    search_regulation,
    analyze_single_clause,
    generate_final_report,
    search_case_law,
    check_local_policy,
    lookup_tax_rule,
    check_completeness,
    self_reflection,
    switch_perspective,
    web_search,
]

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
# Agent 节点：LLMClient 驱动的思考节点（带 qwen 修复）
# ═══════════════════════════════════════════════════════════


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    use_text_mode: bool
    text_mode_triggered: bool


def _call_agent_impl(openai_msgs: list[dict], use_text: bool) -> tuple:
    """调用 LLMClient，返回 (response, used_text_mode)。带 JSON 修复 + 重试。"""
    client = _get_client()

    for attempt in range(4):
        try:
            if use_text:
                resp = client.chat(openai_msgs, tools=None)
            else:
                resp = client.chat(openai_msgs, tools=AGENT_TOOLS)
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


def agent_node(state: AgentState) -> dict:
    """Agent 思考节点。调用 LLM，返回 AIMessage（可能包含 tool_calls）。"""
    openai_msgs = _langchain_to_openai(state["messages"])
    use_text = state.get("use_text_mode", False)
    resp, use_text = _call_agent_impl(openai_msgs, use_text)
    msg = resp.choices[0].message

    if use_text:
        # 文本模式：尝试从文本中解析工具调用
        content = msg.content or ""
        text_calls = parse_text_tool_calls(content)
        if text_calls:
            lc_tool_calls = []
            for i, (name, args) in enumerate(text_calls):
                lc_tool_calls.append(
                    {
                        "name": name,
                        "args": args,
                        "id": f"text_{i}",
                    }
                )
            ai_msg = AIMessage(content=content, tool_calls=lc_tool_calls)
        else:
            ai_msg = AIMessage(content=content)
    else:
        ai_msg = _openai_to_ai_message(msg)

    result = {"messages": [ai_msg]}
    if use_text and not state.get("text_mode_triggered"):
        result["use_text_mode"] = True
        result["text_mode_triggered"] = True
    return result


# ═══════════════════════════════════════════════════════════
# 后处理
# ═══════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════
# 搭建图
# ═══════════════════════════════════════════════════════════


def _build_graph():
    """构建 Agent 图：agent ↔ tools，直到 agent 不再调工具。"""
    graph = StateGraph(AgentState)

    graph.add_node("agent", agent_node)
    tool_node = ToolNode(ALL_TOOLS)
    graph.add_node("tools", tool_node)

    graph.add_edge(START, "agent")
    # tools_condition: 有 tool_calls → "tools"，无 → "__end__"
    graph.add_conditional_edges("agent", tools_condition)
    graph.add_edge("tools", "agent")

    return graph.compile()


_compiled_graph = None


def _get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = _build_graph()
    return _compiled_graph


# ═══════════════════════════════════════════════════════════
# 公开接口
# ═══════════════════════════════════════════════════════════


def review_contract_langgraph(contract_text: str, contract_type: str) -> str:
    """执行完整的合同审查（LangGraph 版）。

    Args:
        contract_text: 合同全文
        contract_type: 合同类型（如"房屋租赁合同"）

    Returns:
        最终审查报告文本
    """
    global _risk_findings
    _risk_findings = []

    system_prompt = str(AGENT_SYSTEM_PROMPT)
    user_prompt = AGENT_USER_PROMPT.format(
        contract_type=contract_type,
        contract_text=contract_text,
    )

    initial_state: AgentState = {
        "messages": [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ],
        "use_text_mode": False,
        "text_mode_triggered": False,
    }

    graph = _get_graph()
    result = graph.invoke(initial_state, {"recursion_limit": 60})

    # 提取最终报告：优先取 generate_final_report 工具的输出（完整报告本体）
    # 因为工具返回后 Agent 可能只输出一句"报告已生成"的总结语，那不是正式报告
    final_report = ""
    for msg in reversed(result["messages"]):
        if isinstance(msg, ToolMessage) and msg.name == "generate_final_report":
            final_report = msg.content or ""
            break

    # 回退：取最后一条有实质内容的 AI 消息
    if not final_report:
        for msg in reversed(result["messages"]):
            content = getattr(msg, "content", None)
            tc = getattr(msg, "tool_calls", None)
            if content and not tc and isinstance(content, str) and len(content) > 100:
                final_report = content
                break

    if not final_report and result["messages"]:
        last = result["messages"][-1]
        final_report = getattr(last, "content", "") or ""

    return clean_report(final_report, contract_text, contract_type)


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

    report = review_contract_langgraph(contract_text, ct)

    if output_path:
        Path(output_path).write_text(report, encoding="utf-8")
        logger.info("")
        logger.info("报告已保存至: {}", output_path)
    else:
        logger.info("=" * 60)
        logger.info("{}", report)
