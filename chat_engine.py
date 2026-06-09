"""
法律问答对话引擎。RAG检索 + LLM回复 + 对话记忆 + 流式输出。
"""

from rag.retriever import format_results, search

SYSTEM_PROMPT = """你是法眼法律助手，基于中国法律法规知识库为用户提供法律咨询。

规则：
1. 你有一个工具 `query_review_history` 可以查询用户的历史合同审查数据（MySQL）。当用户询问审查历史、风险详情、合同统计等问题时，必须优先调用该工具，不要仅凭参考资料回答。
2. 参考资料（RAG）中的法规条文是补充信息，历史数据工具返回的结果才是用户问的实际数据。
3. ⚠️ 禁止编造任何数字、百分比、金额、日期——包括举例中的数字（如"日息0.1%""年化36%"等）。工具返回什么就引用什么，工具没返回的数据不能说，连"例如XX%"这种举例也不行。
4. 引用法条或判例时，必须注明出处（如"根据《民法典》第585条"）。
5. 回答简洁、通俗，让非法律专业人士也能听懂。末尾可附1-2条实操建议。
6. 如果用户上传了合同并针对合同提问，结合合同内容和法规分析。
7. 不做具体法律建议，提醒用户重大事项咨询专业律师。

{contract_context}
"""


def search_all(query: str, top_k: int = 3) -> dict[str, list[dict]]:
    """跨所有知识库检索。"""
    collections = {
        "regulation": "法规",
        "case_law": "判例",
        "local_policy": "地方政策",
        "tax_rule": "税务",
        "web_kb": "资讯",
    }
    all_results = {}
    for col_name, col_label in collections.items():
        results = search(query, col_name, top_k=top_k)
        if results:
            all_results[col_label] = results
    return all_results


def build_context(
    query: str,
    history: list[dict],
    contract_text: str = "",
    max_history: int = 10,
) -> tuple[str, str]:
    """构建 LLM 上下文：RAG参考资料 + 对话历史。"""
    # RAG 检索
    all_results = search_all(query)

    # 格式化参考资料
    ref_parts = []
    for col_label, results in all_results.items():
        ref_parts.append(f"【{col_label}】\n{format_results(results)}")
    reference = "\n\n".join(ref_parts) if ref_parts else "暂无直接匹配的法律资料。"

    # 对话历史
    recent = history[-max_history:] if len(history) > max_history else history
    history_text = ""
    for h in recent:
        history_text += f"用户：{h['user']}\n助手：{h['assistant']}\n\n"

    # 合同上下文
    contract_context = ""
    if contract_text.strip():
        contract_context = f"用户上传了以下合同：\n```\n{contract_text[:3000]}\n```\n请结合合同内容回答用户的问题。"

    system = SYSTEM_PROMPT.format(contract_context=contract_context)

    user = f"""参考资料：
{reference}

对话历史：
{history_text}

用户最新问题：{query}

请回答（基于参考资料，注明出处）："""

    return system, user


def chat_stream(
    query: str,
    history: list[dict],
    contract_text: str = "",
    api_key: str = "",
    enable_tools: bool = False,
) -> str:
    """流式对话：逐 chunk 返回 LLM 回复。

    Args:
        query: 用户问题
        history: [{"user": "...", "assistant": "..."}, ...]
        contract_text: 可选的合同全文
        api_key: DashScope API Key
        enable_tools: 是否启用历史数据查询工具（轻量 Agent 模式）

    Yields:
        文本 chunk
    """
    import json

    from llm_client import LLMClient

    system, user = build_context(query, history, contract_text)

    client = LLMClient(api_key=api_key, model="qwen-plus")

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    # ── 轻量 Agent：LLM 决定是否调工具 ──
    if enable_tools:
        from tools import QA_TOOL, query_review_history

        # 第一步：LLM 看上下文 + 工具定义，决定要不要调
        tool_response = client.client.chat.completions.create(
            model="qwen-plus",
            messages=messages,
            tools=[QA_TOOL],
            tool_choice="auto",
            max_tokens=512,
            temperature=0.1,
        )

        tool_calls = getattr(tool_response.choices[0].message, "tool_calls", None)

        if tool_calls and len(tool_calls) > 0:
            # LLM 决定查历史数据 → 执行工具
            tool_call = tool_calls[0]
            args = json.loads(tool_call.function.arguments)
            tool_result = query_review_history(**args)

            # 把工具调用和结果追加到对话
            messages.append(tool_response.choices[0].message)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_result,
                }
            )

    # ── 最终流式输出 ──
    response = client.client.chat.completions.create(
        model="qwen-plus",
        messages=messages,
        stream=True,
        max_tokens=2048,
        temperature=0.3,
    )

    full_response = ""
    for chunk in response:
        if chunk.choices and chunk.choices[0].delta.content:
            text = chunk.choices[0].delta.content
            full_response += text
            yield text

    return full_response
