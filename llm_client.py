import json

from openai import OpenAI

from logger import logger


class LLMClient:
    def __init__(
        self,
        api_key: str,
        model: str = "qwen-plus",
        base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1",
    ):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 4096,
    ):
        """低级 API：发送消息列表，返回原始 ChatCompletion 对象。
        Agent 循环用这个方法，因为它需要检查 tool_calls 并自己处理循环。"""
        kwargs = {"model": self.model, "messages": messages, "max_tokens": max_tokens}
        if tools:
            kwargs["tools"] = tools
            kwargs["temperature"] = 0.0  # 消除随机性，确保审查结果一致
        return self.client.chat.completions.create(**kwargs)

    def stream_chat(
        self, messages: list[dict], tools: list[dict] | None = None, max_tokens: int = 4096
    ):
        """流式版 chat()。yield dict —— {"type":"delta","content":"..."} 或 {"type":"finish","content":"...","tool_calls":[...]}."""
        kwargs = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["temperature"] = 0.0

        response = self.client.chat.completions.create(**kwargs)
        full_content = ""
        accumulated_tool_calls = []

        for chunk in response:
            delta = chunk.choices[0].delta if chunk.choices else None
            if not delta:
                continue
            if delta.content:
                full_content += delta.content
                yield {"type": "delta", "content": delta.content}
            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    while len(accumulated_tool_calls) <= idx:
                        accumulated_tool_calls.append(
                            {"id": "", "function": {"name": "", "arguments": ""}}
                        )
                    if tc_delta.id:
                        accumulated_tool_calls[idx]["id"] = tc_delta.id
                    if tc_delta.function and tc_delta.function.name:
                        accumulated_tool_calls[idx]["function"]["name"] += tc_delta.function.name
                    if tc_delta.function and tc_delta.function.arguments:
                        accumulated_tool_calls[idx]["function"]["arguments"] += (
                            tc_delta.function.arguments
                        )

            if chunk.choices[0].finish_reason:
                yield {
                    "type": "finish",
                    "content": full_content,
                    "tool_calls": accumulated_tool_calls if accumulated_tool_calls else None,
                    "finish_reason": chunk.choices[0].finish_reason,
                }

    def call(self, system_prompt: str, user_prompt: str, max_tokens: int = 4096) -> str:
        resp = self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=0.0,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return resp.choices[0].message.content

    def call_with_tools(
        self,
        system_prompt: str,
        user_prompt: str,
        tools: list[dict],
        max_tokens: int = 4096,
    ) -> str:
        """发送支持工具调用的请求。模型可以自动决定调用 tools 中定义的函数。"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        resp = self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=messages,
            tools=tools,
        )

        # 检查模型是否想调用工具
        choice = resp.choices[0]
        if choice.message.tool_calls:
            from tools import search_regulation

            messages.append(choice.message)

            for tc in choice.message.tool_calls:
                args = json.loads(tc.function.arguments)
                logger.debug("  >> 模型自动调用 search_regulation('{}')", args["keyword"])
                result = search_regulation(**args)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    }
                )

            logger.debug("  >> AI 已收到法规结果，继续分析...")
            final_resp = self.client.chat.completions.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=messages,
            )
            return final_resp.choices[0].message.content

        return choice.message.content

    def extract_json(self, text: str) -> dict:
        """从 LLM 返回的文本中提取 JSON，自动处理 ```json 包裹的情况。"""
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = lines[1:] if lines[0].startswith("```") else lines
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)
        return json.loads(text)
