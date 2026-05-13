"""
合同审查助手 —— Agent 版（ReAct 模式）

用法：
    python main.py <合同文件路径> <合同类型>

示例：
    python main.py sample_lease.txt "房屋租赁合同"
    python main.py contract.txt "劳动合同" --output report.txt

环境变量：
    在项目根目录创建 .env 文件，写入 DASHSCOPE_API_KEY=你的key

与旧版区别：
    旧版是固定三步流水线（提取→分析→报告），Agent 版使用 ReAct 循环，
    AI 自主决定每一步调用哪个工具，直到生成最终报告。
"""

import json
import os
import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass  # Streamlit 环境里 stdout 不支持 reconfigure，忽略

from dotenv import load_dotenv

from llm_client import LLMClient
from logger import init_logger, logger
from prompts import AGENT_SYSTEM_PROMPT, AGENT_USER_PROMPT
from utils import clean_report, parse_text_tool_calls, parse_tool_args, repair_json

load_dotenv()

MAX_ITERATIONS = 20
TOOL_RESULT_MAX_CHARS = 4000
FINAL_REPORT_MAX_CHARS = 12000  # 最终报告不截断


def _filter_tools(tools: list[dict], enable_reflection: bool) -> list[dict]:
    """根据开关过滤工具列表。关闭反思时移除 self_reflection。"""
    if enable_reflection:
        return tools
    return [t for t in tools if t.get("function", {}).get("name") != "self_reflection"]


class ContractReviewAgent:
    """ReAct Agent：自主决定审查步骤，循环 思考→行动→观察。"""

    def __init__(self, api_key: str, verbose: bool = True, enable_reflection: bool = True):
        self.client = LLMClient(api_key=api_key)
        self.verbose = verbose
        self.enable_reflection = enable_reflection
        self._contract_text = ""
        self._risk_findings: list[dict] = []

    # ── JSON 修复（委托给 utils.py）─────────────────────
    @staticmethod
    def _repair_json(text: str) -> str | None:
        return repair_json(text)

    @staticmethod
    def _parse_text_tool_calls(content: str) -> list[tuple[str, dict]]:
        return parse_text_tool_calls(content)

    def _parse_tool_args(self, raw: str) -> dict | None:
        """解析工具参数 JSON，失败时先尝试修复。返回 None 表示无法解析。"""
        raw = (raw or "").strip()
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
        result = parse_tool_args(raw)
        if result:
            if self.verbose:
                logger.debug("  🔧 JSON已自动修复")
            return result
        return None

    def _execute_tool(self, name: str, args: dict) -> str:
        """执行工具调用，返回结果文本。错误会被捕获并作为文本返回。"""
        try:
            if name == "extract_clauses":
                from tools import extract_clauses

                ct = args.get("contract_text", "")
                # 模型传了空值或占位符 → 用缓存的合同原文
                if not ct or len(ct) < 50:
                    ct = self._contract_text
                return extract_clauses(
                    self.client,
                    ct,
                    args["contract_type"],
                )
            elif name == "search_regulation":
                from tools import search_regulation

                return search_regulation(args["keyword"])
            elif name == "analyze_single_clause":
                from tools import analyze_single_clause

                result = analyze_single_clause(
                    self.client,
                    args["clause_text"],
                    args["category"],
                    args.get("contract_type", ""),
                    args.get("clause_position", ""),
                    args.get("regulation_context", ""),
                )
                # 解析分析结果，累积到会话存储
                try:
                    parsed = json.loads(
                        result.strip()
                        .removeprefix("```json")
                        .removeprefix("```")
                        .removesuffix("```")
                        .strip()
                    )
                    self._risk_findings.append(parsed)
                except (json.JSONDecodeError, AttributeError):
                    pass  # 无法解析也不影响流程
                return result
            elif name == "generate_final_report":
                from tools import generate_final_report

                risk_json = args.get("risk_findings_json", "")
                # 模型传空值或占位符 → 用会话累积的分析结果
                if (not risk_json or len(risk_json) < 100) and self._risk_findings:
                    risk_json = json.dumps(self._risk_findings, ensure_ascii=False)
                elif not risk_json:
                    risk_json = "[]"
                return generate_final_report(
                    self.client,
                    risk_json,
                    args.get("contract_type", ""),
                )
            elif name == "search_case_law":
                from tools import search_case_law

                return search_case_law(args["keyword"])
            elif name == "check_local_policy":
                from tools import check_local_policy

                return check_local_policy(
                    args["city"],
                    args.get("keyword", ""),
                )
            elif name == "lookup_tax_rule":
                from tools import lookup_tax_rule

                return lookup_tax_rule(args["topic"])
            elif name == "check_completeness":
                from tools import check_completeness

                return check_completeness(
                    self.client,
                    args["clauses_json"],
                    args.get("contract_type", ""),
                )
            elif name == "switch_perspective":
                from tools import switch_perspective

                return switch_perspective(
                    self.client,
                    args["findings_json"],
                    args["perspective"],
                )
            elif name == "web_search":
                from tools import web_search

                return web_search(args["keyword"])
            elif name == "self_reflection":
                from tools import self_reflection

                return self_reflection(
                    self.client,
                    args.get("clauses_json", ""),
                    args.get("findings_json", ""),
                    args.get("completeness_result", ""),
                    args.get("contract_type", ""),
                )
            else:
                return f"未知工具: {name}"
        except Exception as e:
            return f"工具执行出错: {type(e).__name__}: {e}"

    def _format_box(self, title: str, content: str) -> str:
        """格式化输出框。"""
        w = 60
        lines = [f"┌─ {title} {'─' * (w - len(title) - 4)}┐"]
        for line in content.split("\n"):
            lines.append(f"│  {line}")
        lines.append(f"└{'─' * (w + 2)}┘")
        return "\n".join(lines)

    def run(self, contract_text: str, contract_type: str) -> str:
        """主 ReAct 循环。返回最终报告。"""
        from tools import AGENT_TOOLS

        tools_list = _filter_tools(AGENT_TOOLS, self.enable_reflection)

        self._contract_text = contract_text
        self._risk_findings = []  # 重置会话存储

        messages = [
            {"role": "system", "content": str(AGENT_SYSTEM_PROMPT)},
            {
                "role": "user",
                "content": AGENT_USER_PROMPT.format(
                    contract_type=contract_type,
                    contract_text=contract_text,
                ),
            },
        ]

        api_retries = 0
        last_report = None
        use_text_mode = False
        json_error_count = 0  # JSON错误计数器，防止死循环
        for round_num in range(1, MAX_ITERATIONS + 1):
            # ── 调用 LLM ──
            try:
                if use_text_mode:
                    resp = self.client.chat(messages, tools=None)
                else:
                    resp = self.client.chat(messages, tools=tools_list)
            except Exception as e:
                err_msg = str(e)
                if "function.arguments" in err_msg and "JSON" in err_msg:
                    json_error_count += 1
                    use_text_mode = True
                    if json_error_count >= 3:
                        # 连续JSON错误 → 强制纯文本输出报告
                        messages.append(
                            {
                                "role": "user",
                                "content": (
                                    "JSON格式持续错误。请不要调用任何工具，直接以纯文本输出最终审查报告"
                                    "（从「合同审查报告」标题开始，包含风险概览+详解+修改建议+综合评分）。"
                                ),
                            }
                        )
                        try:
                            fallback_resp = self.client.chat(messages, tools=None)
                            return fallback_resp.choices[0].message.content or ""
                        except Exception:
                            return last_report or ""
                    if self.verbose:
                        logger.warning("  🔄 JSON错误，切换文本格式工具调用模式")
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                "函数调用功能暂时不可用。请用以下文本格式调用工具（可一次调用多个）：\n\n"
                                '<<TOOL:extract_clauses>>\n<<ARGS:{"contract_type": "服务合同"}>>\n\n'
                                '<<TOOL:search_regulation>>\n<<ARGS:{"keyword": "违约金"}>>\n\n'
                                "请继续审查流程。"
                            ),
                        }
                    )
                    continue

                if api_retries < 3:
                    api_retries += 1
                    messages.append(
                        {
                            "role": "user",
                            "content": f"API调用失败（{err_msg[:200]}），请重试。（{api_retries}/3）",
                        }
                    )
                    if self.verbose:
                        logger.warning("  ⚠️ API失败({}/3): {}", api_retries, err_msg[:120])
                    continue
                raise

            api_retries = 0
            msg = resp.choices[0].message
            messages.append(msg.model_dump(exclude_none=True))

            # ── 打印思考 ──
            thought = msg.content or ""
            if thought and self.verbose:
                logger.info("")
                logger.info("┌─ 第 {} 轮 {}", round_num, "─" * 30)
                if len(thought) > 500:
                    thought = thought[:500] + "..."
                for line in thought.strip().split("\n"):
                    logger.info("│  {}", line)

            # ── 文本模式：解析 <<TOOL>> 标签 ──
            if use_text_mode:
                text_calls = self._parse_text_tool_calls(msg.content or "")
                if not text_calls:
                    # 无工具调用 → 任务完成
                    if self.verbose:
                        logger.info("└" + "─" * 60 + "┘")
                    final = last_report if last_report else (msg.content or "")
                    if self.verbose:
                        logger.info("=" * 60)
                        logger.info("{}", final)
                    return final
                # 执行文本格式的工具调用
                for func_name, args in text_calls:
                    args_preview = ", ".join(f"{k}={str(v)[:50]}" for k, v in args.items())
                    logger.info("│")
                    logger.info("│  🔧 [文本] {}({})", func_name, args_preview)
                    result = self._execute_tool(func_name, args)
                    if len(result) > TOOL_RESULT_MAX_CHARS:
                        result = result[:TOOL_RESULT_MAX_CHARS] + "\n...（结果已截断）"
                    logger.info("│  📋 返回 {} 字符", len(result))
                    if func_name == "generate_final_report":
                        last_report = result
                    messages.append(
                        {
                            "role": "user",
                            "content": f"[工具 {func_name} 的执行结果]\n{result}",
                        }
                    )
                logger.info("└" + "─" * 60 + "┘")
                continue

            # ── 无 tool_calls → 任务完成 ──
            if not msg.tool_calls:
                if self.verbose:
                    logger.info("└" + "─" * 60 + "┘")
                if last_report:
                    final = last_report
                else:
                    final = msg.content or ""
                if self.verbose:
                    logger.info("=" * 60)
                    logger.info("{}", final)
                return final

            # ── 执行工具调用（标准函数调用路径）──
            for tc in msg.tool_calls:
                func_name = tc.function.name
                raw_args = tc.function.arguments or "{}"

                args = self._parse_tool_args(raw_args)
                if args is None:
                    # JSON 无法解析 → 工具报错协议，模型下轮自动修正
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": (
                                f"参数JSON格式错误：{raw_args[:300]}\n"
                                f"请用合法JSON重新调用 {func_name}（所有字符串用双引号包裹，"
                                f"内容中的双引号用反斜杠转义，不要使用单引号作为键名）。"
                            ),
                        }
                    )
                    if self.verbose:
                        logger.warning("│  ⚠️ {}: JSON解析失败，已反馈给模型重试", func_name)
                    continue

                args_preview = ", ".join(f"{k}={str(v)[:50]}" for k, v in args.items())
                logger.info("│")
                logger.info("│  🔧 {}({})", func_name, args_preview)

                result = self._execute_tool(func_name, args)
                max_chars = (
                    FINAL_REPORT_MAX_CHARS
                    if func_name == "generate_final_report"
                    else TOOL_RESULT_MAX_CHARS
                )
                if len(result) > max_chars:
                    result = result[:max_chars] + "\n...（结果已截断）"
                logger.info("│  📋 返回 {} 字符", len(result))

                if func_name == "generate_final_report":
                    last_report = result

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    }
                )

            logger.info("└" + "─" * 60 + "┘")

        # 兜底：达到最大轮次，强制要求输出
        messages.append(
            {
                "role": "user",
                "content": "已达到最大轮次。请立即调用 generate_final_report 生成最终审查报告，然后输出报告全文。",
            }
        )
        final_resp = self.client.chat(messages, tools=tools_list)
        final_msg = final_resp.choices[0].message

        # 如果模型还要调工具，忽略，直接要求纯文本回答
        if final_msg.tool_calls:
            messages.append(final_msg.model_dump(exclude_none=True))
            messages.append(
                {
                    "role": "user",
                    "content": "请直接输出最终审查报告，不要再调用工具。",
                }
            )
            final_resp = self.client.chat(messages, tools=None)
            final_msg = final_resp.choices[0].message

        logger.info("=" * 60)
        logger.info("{}", final_msg.content or "")
        return final_msg.content or ""

    def run_stream(self, contract_text: str, contract_type: str):
        """流式版 ReAct 循环。yield 结构化事件供 UI 实时展示。"""
        try:
            yield from self._run_stream_impl(contract_text, contract_type)
        except Exception as e:
            import traceback

            yield {
                "type": "error",
                "message": f"{type(e).__name__}: {e}\n{traceback.format_exc()}",
            }

    def _run_stream_impl(self, contract_text: str, contract_type: str):
        """run_stream 的实现体，外层由 run_stream 兜底异常。"""
        from tools import AGENT_TOOLS

        tools_list = _filter_tools(AGENT_TOOLS, self.enable_reflection)

        self._contract_text = contract_text
        self._risk_findings = []

        messages = [
            {"role": "system", "content": str(AGENT_SYSTEM_PROMPT)},
            {
                "role": "user",
                "content": AGENT_USER_PROMPT.format(
                    contract_type=contract_type,
                    contract_text=contract_text,
                ),
            },
        ]

        api_retries = 0
        last_report = None
        use_text_mode = False
        json_error_count = 0

        for round_num in range(1, MAX_ITERATIONS + 1):
            yield {"type": "round_start", "round": round_num}

            # ── 流式调用 LLM ──
            try:
                tools = None if use_text_mode else tools_list
                stream_events = []
                for event in self.client.stream_chat(messages, tools=tools):
                    if event["type"] == "delta":
                        yield {"type": "thinking_delta", "content": event["content"]}
                    stream_events.append(event)
                last_event = (
                    stream_events[-1]
                    if stream_events
                    else {"type": "finish", "content": "", "tool_calls": None}
                )
                content = last_event.get("content", "")
                tool_calls = last_event.get("tool_calls")
            except Exception as e:
                err_msg = str(e)
                if "function.arguments" in err_msg and "JSON" in err_msg:
                    json_error_count += 1
                    use_text_mode = True
                    if json_error_count >= 3:
                        messages.append(
                            {
                                "role": "user",
                                "content": (
                                    "JSON格式持续错误。请不要调用任何工具，直接以纯文本输出最终审查报告"
                                    "（从「合同审查报告」标题开始，包含风险概览+详解+修改建议+综合评分）。"
                                ),
                            }
                        )
                        try:
                            for evt in self.client.stream_chat(messages, tools=None):
                                if evt["type"] == "delta":
                                    yield {"type": "thinking_delta", "content": evt["content"]}
                                elif evt["type"] == "finish":
                                    yield {
                                        "type": "done",
                                        "report": evt.get("content", "") or last_report or "",
                                    }
                                    return
                        except Exception:
                            yield {"type": "done", "report": last_report or ""}
                            return
                    if self.verbose:
                        logger.warning("  🔄 JSON错误，切换文本格式工具调用模式")
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                "函数调用功能暂时不可用。请用以下文本格式调用工具（可一次调用多个）：\n\n"
                                '<<TOOL:extract_clauses>>\n<<ARGS:{"contract_type": "服务合同"}>>\n\n'
                                '<<TOOL:search_regulation>>\n<<ARGS:{"keyword": "违约金"}>>\n\n'
                                "请继续审查流程。"
                            ),
                        }
                    )
                    continue

                if api_retries < 3:
                    api_retries += 1
                    yield {"type": "retry", "attempt": api_retries, "message": err_msg[:200]}
                    messages.append(
                        {
                            "role": "user",
                            "content": f"API调用失败（{err_msg[:200]}），请重试。（{api_retries}/3）",
                        }
                    )
                    if self.verbose:
                        logger.warning("  ⚠️ API失败({}/3): {}", api_retries, err_msg[:120])
                    continue
                yield {"type": "error", "message": err_msg}
                return

            api_retries = 0

            # 构造 assistant 消息
            assistant_msg = {"role": "assistant", "content": content}
            if tool_calls:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["function"]["name"],
                            "arguments": tc["function"]["arguments"],
                        },
                    }
                    for tc in tool_calls
                ]
            messages.append(assistant_msg)

            # ── 文本模式：解析 <<TOOL>> 标签 ──
            if use_text_mode:
                text_calls = self._parse_text_tool_calls(content or "")
                if not text_calls:
                    final = last_report if last_report else (content or "")
                    yield {"type": "done", "report": final}
                    return
                for func_name, args in text_calls:
                    yield {"type": "tool_start", "name": func_name}
                    result = self._execute_tool(func_name, args)
                    if len(result) > TOOL_RESULT_MAX_CHARS:
                        result = result[:TOOL_RESULT_MAX_CHARS] + "\n...（结果已截断）"
                    yield {"type": "tool_result", "name": func_name, "result_len": len(result)}
                    if func_name == "generate_final_report":
                        last_report = result
                    messages.append(
                        {
                            "role": "user",
                            "content": f"[工具 {func_name} 的执行结果]\n{result}",
                        }
                    )
                continue

            # ── 无 tool_calls → 任务完成 ──
            if not tool_calls:
                final = last_report if last_report else (content or "")
                yield {"type": "done", "report": final}
                return

            # ── 执行工具调用（标准函数调用路径）──
            for tc in tool_calls:
                func_name = tc["function"]["name"]
                raw_args = tc["function"]["arguments"] or "{}"

                args = self._parse_tool_args(raw_args)
                if args is None:
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": (
                                f"参数JSON格式错误：{raw_args[:300]}\n"
                                f"请用合法JSON重新调用 {func_name}（所有字符串用双引号包裹）。"
                            ),
                        }
                    )
                    yield {"type": "tool_error", "name": func_name, "message": "JSON解析失败"}
                    continue

                yield {"type": "tool_start", "name": func_name}
                result = self._execute_tool(func_name, args)
                max_chars = (
                    FINAL_REPORT_MAX_CHARS
                    if func_name == "generate_final_report"
                    else TOOL_RESULT_MAX_CHARS
                )
                if len(result) > max_chars:
                    result = result[:max_chars] + "\n...（结果已截断）"
                yield {"type": "tool_result", "name": func_name, "result_len": len(result)}

                if func_name == "generate_final_report":
                    last_report = result

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result,
                    }
                )

        # 兜底：达到最大轮次
        yield {"type": "round_start", "round": MAX_ITERATIONS + 1}
        messages.append(
            {
                "role": "user",
                "content": "已达到最大轮次。请立即调用 generate_final_report 生成最终审查报告。",
            }
        )
        for event in self.client.stream_chat(messages, tools=tools_list):
            if event["type"] == "delta":
                yield {"type": "thinking_delta", "content": event["content"]}
            elif event["type"] == "finish":
                final = event.get("content", "") or last_report or ""
                yield {"type": "done", "report": final}
                return
        yield {"type": "done", "report": last_report or ""}


def _clean_report(report: str, contract_text: str, contract_type: str) -> str:
    """后处理：清理占位文字 + 检查关键条款遗漏。委托给 utils.py。"""
    return clean_report(report, contract_text, contract_type)


def review_contract(contract_text: str, contract_type: str, api_key: str) -> str:
    """执行完整的合同审查（Agent 模式）。"""
    agent = ContractReviewAgent(api_key=api_key)
    report = agent.run(contract_text, contract_type)
    return _clean_report(report, contract_text, contract_type)


def main():
    init_logger(mode="cli")

    if len(sys.argv) < 3:
        logger.info("用法: python main.py <合同文件> <合同类型> [--output 输出文件]")
        logger.info('示例: python main.py contract.txt "房屋租赁合同" --output report.txt')
        sys.exit(1)

    filepath = Path(sys.argv[1])
    contract_type = sys.argv[2]
    output_path = None

    if "--output" in sys.argv:
        idx = sys.argv.index("--output")
        if idx + 1 < len(sys.argv):
            output_path = sys.argv[idx + 1]

    if not filepath.exists():
        logger.error("文件不存在: {}", filepath)
        sys.exit(1)

    contract_text = filepath.read_text(encoding="utf-8")
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        logger.error("请设置环境变量 DASHSCOPE_API_KEY，或在 .env 文件中写入")
        sys.exit(1)

    logger.info("")
    logger.info("[Agent 模式启动]")
    logger.info("审查合同类型: {}", contract_type)
    logger.info("合同来源: {}", filepath)
    logger.info("=" * 60)

    report = review_contract(contract_text, contract_type, api_key)

    if output_path:
        Path(output_path).write_text(report, encoding="utf-8")
        logger.info("")
        logger.info("报告已保存至: {}", output_path)


if __name__ == "__main__":
    main()
