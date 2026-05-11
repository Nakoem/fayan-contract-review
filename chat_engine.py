"""
法律问答对话引擎。RAG检索 + LLM回复 + 对话记忆 + 流式输出。
"""

from rag.retriever import search, format_results

SYSTEM_PROMPT = """你是法眼法律助手，基于中国法律法规知识库为用户提供法律咨询。

规则：
1. 回答必须基于提供的"参考资料"。如果资料中没有相关信息，如实说"根据现有知识库，我暂无法回答这个问题"，然后给出现有知识库中最相关的建议。
2. 引用法条或判例时，必须注明出处（如"根据《民法典》第585条"）。
3. 回答简洁、通俗，让非法律专业人士也能听懂。末尾可附1-2条实操建议。
4. 如果用户上传了合同并针对合同提问，结合合同内容和法规分析。
5. 不做具体法律建议，提醒用户重大事项咨询专业律师。

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
) -> str:
    """流式对话：逐 chunk 返回 LLM 回复。

    Args:
        query: 用户问题
        history: [{"user": "...", "assistant": "..."}, ...]
        contract_text: 可选的合同全文
        api_key: DashScope API Key

    Yields:
        文本 chunk
    """
    from llm_client import LLMClient

    system, user = build_context(query, history, contract_text)

    client = LLMClient(api_key=api_key, model="qwen-plus")

    # 用 OpenAI SDK 的 stream 模式
    response = client.client.chat.completions.create(
        model="qwen-plus",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
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
