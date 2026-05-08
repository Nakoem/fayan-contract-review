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
import re
import sys
import os
from datetime import date
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass  # Streamlit 环境里 stdout 不支持 reconfigure，忽略

from dotenv import load_dotenv

from llm_client import LLMClient
from prompts import AGENT_SYSTEM_PROMPT, AGENT_USER_PROMPT

load_dotenv()

MAX_ITERATIONS = 20
TOOL_RESULT_MAX_CHARS = 4000


class ContractReviewAgent:
    """ReAct Agent：自主决定审查步骤，循环 思考→行动→观察。"""

    def __init__(self, api_key: str, verbose: bool = True):
        self.client = LLMClient(api_key=api_key)
        self.verbose = verbose
        self._contract_text = ""  # 缓存合同原文
        self._risk_findings: list[dict] = []  # 累积所有 analyze_single_clause 结果

    # ── JSON 修复 ───────────────────────────────────────────
    @staticmethod
    def _repair_json(text: str) -> str | None:
        """尝试修复 LLM 常见的 JSON 格式错误。修复成功返回字符串，否则 None。"""
        if not text or not text.strip():
            return None
        text = text.strip()

        # 已经合法
        try:
            json.loads(text)
            return text
        except json.JSONDecodeError:
            pass

        # 修复1：去掉尾部逗号 (最常见的LLM错误)
        repaired = re.sub(r",\s*([}\]])", r"\1", text)
        try:
            json.loads(repaired)
            return repaired
        except json.JSONDecodeError:
            pass

        # 修复2：提取最外层 {...}（模型有时在JSON前后加说明文字）
        m = re.search(r"\{.*\}", repaired, re.DOTALL)
        if m:
            extracted = m.group(0)
            try:
                json.loads(extracted)
                return extracted
            except json.JSONDecodeError:
                pass

        # 修复3：单引号 → 双引号（模型用Python dict风格输出JSON）
        # 中文合同中单引号作为引号使用较少，此替换相对安全
        squoted = repaired.replace("'", '"')
        try:
            json.loads(squoted)
            return squoted
        except json.JSONDecodeError:
            pass

        # 修复4：中文书名号/引号导致的值内未转义双引号（常见于合同文本）
        # 模式：在字符串值内部出现未转义的双引号
        # e.g. {"text": "甲方须在收到"通知"后"} → 需要转义内部双引号
        # 此修复较复杂，跳过；交给模型重试

        return None

    def _parse_tool_args(self, raw: str) -> dict | None:
        """解析工具参数 JSON，失败时先尝试修复。返回 None 表示无法解析。"""
        raw = (raw or "").strip()
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
        repaired = self._repair_json(raw)
        if repaired:
            try:
                if self.verbose:
                    print(f"  🔧 JSON已自动修复")
                return json.loads(repaired)
            except json.JSONDecodeError:
                pass
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
                    parsed = json.loads(result.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip())
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

        self._contract_text = contract_text
        self._risk_findings = []  # 重置会话存储

        messages = [
            {"role": "system", "content": AGENT_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": AGENT_USER_PROMPT.format(
                    contract_type=contract_type, contract_text=contract_text,
                ),
            },
        ]

        api_retries = 0
        last_report = None
        for round_num in range(1, MAX_ITERATIONS + 1):
            # ── 调用 LLM ──
            try:
                resp = self.client.chat(messages, tools=AGENT_TOOLS)
            except Exception as e:
                err_msg = str(e)
                is_json_err = "function.arguments" in err_msg and "JSON" in err_msg
                if api_retries < 3:
                    api_retries += 1
                    if is_json_err:
                        messages.append({
                            "role": "user",
                            "content": (
                                f"你上一次工具调用的参数JSON格式有误，被服务端拒绝了。"
                                f"请务必：1) 所有参数值尽量简短（<200字）；"
                                f"2) 字符串内的双引号用 \\\" 转义；3) 不要用单引号；"
                                f"4) 不要在JSON参数中嵌套复杂结构。请重试。（{api_retries}/3）"
                            ),
                        })
                    else:
                        messages.append({
                            "role": "user",
                            "content": f"API调用失败（{err_msg[:200]}），请重试。（{api_retries}/3）",
                        })
                    if self.verbose:
                        print(f"  ⚠️ API失败({api_retries}/3): {err_msg[:120]}")
                    continue
                # 3次重试后仍失败 → JSON格式问题则去掉tools，纯文本兜底
                if is_json_err:
                    if self.verbose:
                        print(f"  🔄 工具调用持续JSON错误，切换到纯文本模式...")
                    messages.append({
                        "role": "user",
                        "content": "由于工具调用参数格式持续出错，请直接以文本形式输出最终审查报告全文，不要再调用任何工具函数。报告须包含：总体风险概览、高风险条款详解、中风险条款、修改建议、签约建议。",
                    })
                    try:
                        resp = self.client.chat(messages, tools=None)
                    except Exception:
                        raise e
                    final_msg = resp.choices[0].message
                    print(f"\n{'='*60}")
                    print(final_msg.content or "")
                    return final_msg.content or ""
                raise

            api_retries = 0
            msg = resp.choices[0].message
            messages.append(msg.model_dump(exclude_none=True))

            # ── 打印思考 ──
            thought = msg.content or ""
            if thought and self.verbose:
                print(f"\n┌─ 第 {round_num} 轮 ──────────────────────────────────────┐")
                if len(thought) > 500:
                    thought = thought[:500] + "..."
                for line in thought.strip().split("\n"):
                    print(f"│  {line}")

            # ── 无 tool_calls → 任务完成 ──
            if not msg.tool_calls:
                if self.verbose:
                    print(f"└{'─' * 60}┘")
                if last_report and (not msg.content or len(msg.content) < 200):
                    final = last_report
                else:
                    final = msg.content or ""
                if self.verbose:
                    print(f"\n{'='*60}")
                    print(final)
                return final

            # ── 执行工具调用 ──
            for tc in msg.tool_calls:
                func_name = tc.function.name
                raw_args = tc.function.arguments or "{}"

                args = self._parse_tool_args(raw_args)
                if args is None:
                    # JSON 无法解析 → 工具报错协议，模型下轮自动修正
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": (
                            f"参数JSON格式错误：{raw_args[:300]}\n"
                            f"请用合法JSON重新调用 {func_name}（所有字符串用双引号包裹，"
                            f"内容中的双引号用反斜杠转义，不要使用单引号作为键名）。"
                        ),
                    })
                    if self.verbose:
                        print(f"│  ⚠️ {func_name}: JSON解析失败，已反馈给模型重试")
                    continue

                args_preview = ", ".join(
                    f"{k}={str(v)[:50]}" for k, v in args.items()
                )
                print(f"│")
                print(f"│  🔧 {func_name}({args_preview})")

                result = self._execute_tool(func_name, args)
                if len(result) > TOOL_RESULT_MAX_CHARS:
                    result = result[:TOOL_RESULT_MAX_CHARS] + "\n...（结果已截断）"
                print(f"│  📋 返回 {len(result)} 字符")

                if func_name == "generate_final_report":
                    last_report = result

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })

            print(f"└{'─' * 60}┘")

        # 兜底：达到最大轮次，强制要求输出
        messages.append({
            "role": "user",
            "content": "已达到最大轮次。请立即调用 generate_final_report 生成最终审查报告，然后输出报告全文。",
        })
        final_resp = self.client.chat(messages, tools=AGENT_TOOLS)
        final_msg = final_resp.choices[0].message

        # 如果模型还要调工具，忽略，直接要求纯文本回答
        if final_msg.tool_calls:
            messages.append(final_msg.model_dump(exclude_none=True))
            messages.append({
                "role": "user",
                "content": "请直接输出最终审查报告，不要再调用工具。",
            })
            final_resp = self.client.chat(messages, tools=None)
            final_msg = final_resp.choices[0].message

        print(f"\n{'='*60}")
        print(final_msg.content or "")
        return final_msg.content or ""


def review_contract(contract_text: str, contract_type: str, api_key: str) -> str:
    """执行完整的合同审查（Agent 模式）。"""
    agent = ContractReviewAgent(api_key=api_key)
    return agent.run(contract_text, contract_type)


def main():
    if len(sys.argv) < 3:
        print("用法: python main.py <合同文件> <合同类型> [--output 输出文件]")
        print('示例: python main.py contract.txt "房屋租赁合同" --output report.txt')
        sys.exit(1)

    filepath = Path(sys.argv[1])
    contract_type = sys.argv[2]
    output_path = None

    if "--output" in sys.argv:
        idx = sys.argv.index("--output")
        if idx + 1 < len(sys.argv):
            output_path = sys.argv[idx + 1]

    if not filepath.exists():
        print(f"文件不存在: {filepath}")
        sys.exit(1)

    contract_text = filepath.read_text(encoding="utf-8")
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        print("请设置环境变量 DASHSCOPE_API_KEY，或在 .env 文件中写入")
        sys.exit(1)

    print(f"\n[Agent 模式启动]")
    print(f"审查合同类型: {contract_type}")
    print(f"合同来源: {filepath}")
    print(f"{'='*60}")

    report = review_contract(contract_text, contract_type, api_key)

    if output_path:
        Path(output_path).write_text(report, encoding="utf-8")
        print(f"\n报告已保存至: {output_path}")


if __name__ == "__main__":
    main()
