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

    def _execute_tool(self, name: str, args: dict) -> str:
        """执行工具调用，返回结果文本。错误会被捕获并作为文本返回。"""
        try:
            if name == "extract_clauses":
                from tools import extract_clauses

                return extract_clauses(
                    self.client,
                    args["contract_text"],
                    args["contract_type"],
                )
            elif name == "search_regulation":
                from tools import search_regulation

                return search_regulation(args["keyword"])
            elif name == "analyze_single_clause":
                from tools import analyze_single_clause

                return analyze_single_clause(
                    self.client,
                    args["clause_text"],
                    args["category"],
                    args.get("contract_type", ""),
                    args.get("clause_position", ""),
                    args.get("regulation_context", ""),
                )
            elif name == "generate_final_report":
                from tools import generate_final_report

                return generate_final_report(
                    self.client,
                    args["risk_findings_json"],
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

        messages = [
            {"role": "system", "content": AGENT_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": AGENT_USER_PROMPT.format(
                    contract_type=contract_type, contract_text=contract_text,
                ),
            },
        ]

        json_retries = 0
        last_report = None  # 缓存 generate_final_report 的输出
        for round_num in range(1, MAX_ITERATIONS + 1):
            try:
                resp = self.client.chat(messages, tools=AGENT_TOOLS)
            except Exception as e:
                err_msg = str(e)
                if ("JSON" in err_msg or "arguments" in err_msg) and json_retries < 3:
                    json_retries += 1
                    if messages and messages[-1].get("role") == "assistant":
                        messages.pop()  # 移除导致错误的上一条
                    messages.append({
                        "role": "user",
                        "content": f"上一次调用失败（JSON 格式错误），请用更简单的参数值重试（第{json_retries}次重试）。",
                    })
                    if self.verbose:
                        print(f"  ⚠️ JSON 格式错误，重试 {json_retries}/3...")
                    continue
                raise

            json_retries = 0  # 重置计数器
            msg = resp.choices[0].message
            messages.append(msg.model_dump(exclude_none=True))

            # 打印模型的"思考"
            thought = msg.content or ""
            if thought and self.verbose:
                print(f"\n┌─ 第 {round_num} 轮 ──────────────────────────────────────┐")
                # 截断过长的思考
                if len(thought) > 500:
                    thought = thought[:500] + "..."
                for line in thought.strip().split("\n"):
                    print(f"│  {line}")

            # 无 tool_calls = 模型认为任务完成
            if not msg.tool_calls:
                if self.verbose:
                    print(f"└{'─' * 60}┘")
                # 如果上一轮有 generate_final_report 结果，优先用工具输出
                if last_report and (not msg.content or len(msg.content) < 200):
                    final = last_report
                else:
                    final = msg.content or ""
                if self.verbose:
                    print(f"\n{'='*60}")
                    print(final)
                return final

            # 执行工具调用
            for tc in msg.tool_calls:
                func_name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}

                args_preview = ", ".join(
                    f"{k}={str(v)[:50]}" for k, v in args.items()
                )
                print(f"│")
                print(f"│  🔧 {func_name}({args_preview})")

                result = self._execute_tool(func_name, args)
                # 截断过长结果
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
