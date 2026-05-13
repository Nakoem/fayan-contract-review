"""
法眼项目共享工具函数。
从 main.py 和 agent_langgraph.py 中抽取，消除代码重复。

包含：
- _repair_json: JSON 格式修复（4种策略）
- _parse_text_tool_calls: 文本模式工具调用解析
- _parse_tool_args: 工具参数安全解析
- _clean_report: 审查报告后处理
"""

import json
import re

# ═══════════════════════════════════════════════════════════
# JSON 修复（qwen-plus 专有补丁）
# ═══════════════════════════════════════════════════════════


def repair_json(text: str) -> str | None:
    """尝试修复 LLM 常见的 JSON 格式错误。修复成功返回字符串，否则 None。

    四种修复策略（按顺序尝试）：
    1. 去掉尾部逗号（最常见的 LLM 错误）
    2. 提取最外层 {...}（模型有时在 JSON 前后加说明文字）
    3. 单引号 → 双引号（模型用 Python dict 风格输出 JSON）
    """
    if not text or not text.strip():
        return None
    text = text.strip()

    # 已经合法
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass

    # 修复1：去掉尾部逗号
    repaired = re.sub(r",\s*([}\]])", r"\1", text)
    try:
        json.loads(repaired)
        return repaired
    except json.JSONDecodeError:
        pass

    # 修复2：提取最外层 {...}
    m = re.search(r"\{.*\}", repaired, re.DOTALL)
    if m:
        extracted = m.group(0)
        try:
            json.loads(extracted)
            return extracted
        except json.JSONDecodeError:
            pass

    # 修复3：单引号 → 双引号
    squoted = repaired.replace("'", '"')
    try:
        json.loads(squoted)
        return squoted
    except json.JSONDecodeError:
        pass

    return None


def parse_text_tool_calls(content: str) -> list[tuple[str, dict]]:
    """从纯文本中提取工具调用。格式：<<TOOL:name>> <<ARGS:{"k":"v"}>>

    用于 qwen-plus Function Calling JSON 错误时的文本模式兜底。
    """
    results = []
    pattern = r"<<TOOL:(\S+)>>\s*\n?\s*<<ARGS:(\{.+?\})>>"
    for m in re.finditer(pattern, content, re.DOTALL):
        name = m.group(1).strip()
        try:
            args = json.loads(m.group(2).strip())
        except json.JSONDecodeError:
            repaired = repair_json(m.group(2).strip())
            if repaired:
                try:
                    args = json.loads(repaired)
                except json.JSONDecodeError:
                    continue
            else:
                continue
        results.append((name, args))
    return results


def parse_tool_args(raw: str) -> dict:
    """解析工具参数 JSON，失败时先尝试修复。返回 dict（失败返回空 dict）。"""
    raw = (raw or "").strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    repaired = repair_json(raw)
    if repaired:
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            pass
    return {}


# ═══════════════════════════════════════════════════════════
# 报告后处理
# ═══════════════════════════════════════════════════════════


def clean_report(report: str, contract_text: str, contract_type: str) -> str:
    """后处理：清理占位文字 + 检查关键条款遗漏。"""
    # 1. 删除占位行
    report = re.sub(
        r"^\d+\.\s*【[^】]+】\s*\n\s*▸\s*原文[：:]\s*(?:该条款)?已在第\d+条[^。]*[去重|重复|列示][^。]*。\s*\n\s*▸\s*风险说明[：:][^。]*[去重|重复|列示][^。]*。\s*\n\s*▸\s*修改建议[：:][^。]*[去重|重复|列示][^。]*。\s*\n*",
        "",
        report,
        flags=re.MULTILINE,
    )
    report = re.sub(
        r"^\d+\.\s*【[^】]+】\s*\n\s*▸\s*原文[：:]\s*(?:该条款)?已在第\d+条[^。]*[去重|重复|列示][^。]*。\s*\n*",
        "",
        report,
        flags=re.MULTILINE,
    )
    report = re.sub(
        r"^\d+\.\s*\n\s*▸\s*原文[：:][^▸]*去重后不[^▸]*\n(?:▸[^▸]*\n)*",
        "",
        report,
        flags=re.MULTILINE,
    )
    report = re.sub(r".*去重后不再重复列出.*\n?", "", report)
    report = re.sub(
        r"^\d+\.\s*【[^】]+】\s*\n\s*▸\s*原文已在第\d+[^\n]*\n(?:\s*▸[^\n]*\n)*",
        "",
        report,
        flags=re.MULTILINE,
    )
    # 2. 清理多余空行
    report = re.sub(r"\n{4,}", "\n\n\n", report)
    # 3. 合作协议 4.2 硬编码兜底
    if contract_type == "合作协议":
        has_42 = bool(
            re.search(
                r"退出.*资产|资产.*(?:归|属于).*(?:联合|实验室|不予退还|不折价)", contract_text
            )
        )
        in_report = bool(re.search(r"4\.2|退出.*资产.*不退|资产.*充公|退出方.*投入.*资产", report))
        if has_42 and not in_report:
            warning = (
                '\n\n⚠️ 补充风险提示（自动检测）：合同第四条4.2——"退出方已投入的资产归联合实验室所有，不予退还，'
                '亦不折价补偿"——属资产无偿充公条款，违反民法典第151条显失公平、第972条利益共享原则。建议标为🔴高风险。'
            )
            report = report.rstrip() + warning
    return report
