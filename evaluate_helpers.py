"""
评估辅助函数：格式合规检查、风险覆盖检查、LLM裁判。
"""

import json
import re
from dataclasses import dataclass


@dataclass
class FormatCheckResult:
    passed: bool
    checks: list[dict]
    score: float  # 0-1


@dataclass
class CoverageResult:
    total_known: int
    detected: int
    missed: list[str]
    precision: float
    recall: float
    details: list[dict]


@dataclass
class JudgeResult:
    completeness: int
    accuracy: int
    actionability: int
    format_quality: int
    overall: int
    comments: str


def check_report_format(report: str) -> FormatCheckResult:
    """检查报告是否符合格式规范。"""
    checks = []

    # 检查1: 禁止 Markdown 语法
    md_checks = {
        "标题#号": r"^#{1,6}\s",
        "加粗**": r"\*\*",
        "表格|": r"^\|.*\|.*\|",
        "代码块```": r"```",
    }
    for name, pattern in md_checks.items():
        found = bool(re.search(pattern, report, re.MULTILINE))
        checks.append(
            {
                "name": f"禁止Markdown-{name}",
                "passed": not found,
                "detail": "未发现" if not found else f"发现{name}格式",
            }
        )

    # 检查2: 五段式结构
    sections = [
        ("一、总体风险概览", "总体风险概览"),
        ("二、高风险条款详解", "高风险条款详解"),
        ("三、需关注的中风险条款", "中风险条款详解"),
        ("四、修改优先级建议", "修改优先级建议"),
        ("五、签约建议", "签约建议"),
    ]
    for marker, name in sections:
        found = marker in report
        checks.append(
            {
                "name": f"段落-{name}",
                "passed": found,
                "detail": "存在" if found else "缺失",
            }
        )

    # 检查3: 禁止占位条目
    placeholder_patterns = [
        "重复项已去重",
        "此处不另列",
        "原文已在第",
        "去重后不再重复",
    ]
    has_placeholder = any(p in report for p in placeholder_patterns)
    checks.append(
        {
            "name": "禁止占位条目",
            "passed": not has_placeholder,
            "detail": "未发现" if not has_placeholder else "发现占位描述",
        }
    )

    # 计算分数
    total = len(checks)
    passed_count = sum(1 for c in checks if c["passed"])
    return FormatCheckResult(
        passed=all(c["passed"] for c in checks),
        checks=checks,
        score=passed_count / total if total > 0 else 0,
    )


def check_risk_coverage(report: str, known_risks: list[dict]) -> CoverageResult:
    """检查报告中是否覆盖了已知风险点。关键词匹配策略。"""
    detected_ids = []
    missed = []
    details = []

    for risk in known_risks:
        hits = sum(1 for kw in risk["keywords"] if kw in report)
        # 至少50%关键词命中才视为检出
        threshold = max(1, len(risk["keywords"]) * 0.5)
        if hits >= threshold:
            detected_ids.append(risk["id"])
            details.append(
                {
                    "id": risk["id"],
                    "detected": True,
                    "hits": hits,
                    "total_keywords": len(risk["keywords"]),
                }
            )
        else:
            missed.append(risk["id"])
            missing_kws = [kw for kw in risk["keywords"] if kw not in report]
            details.append(
                {
                    "id": risk["id"],
                    "detected": False,
                    "hits": hits,
                    "total_keywords": len(risk["keywords"]),
                    "missing_keywords": missing_kws[:5],
                }
            )

    total = len(known_risks)
    detected_count = len(detected_ids)
    return CoverageResult(
        total_known=total,
        detected=detected_count,
        missed=missed,
        precision=detected_count / total if total > 0 else 0,
        recall=detected_count / total if total > 0 else 0,
        details=details,
    )


_JUDGE_SYSTEM_PROMPT = """你是一位资深法务质量审核专家。请对以下合同审查报告从四个维度打分（1-10分，10分最高）：

1. 完整性：报告是否覆盖了合同中所有可识别风险条款？是否有遗漏？
2. 准确性：风险定级(🔴/🟡/🟢)是否合理？法律依据引用是否正确？
3. 可操作性：修改建议是否具体、可执行？还是笼统模糊？
4. 格式规范：是否严格遵守纯文本五段式模板？是否使用了Markdown？

请以JSON格式输出评分。只输出JSON。"""

_JUDGE_USER_PROMPT = """合同类型：{contract_type}

合同原文：
{contract_text}

审查报告：
{report}

请打分。JSON格式：
{{
  "completeness": 1-10,
  "accuracy": 1-10,
  "actionability": 1-10,
  "format_quality": 1-10,
  "overall": 1-10,
  "comments": "总体评语（50字以内）"
}}"""


def llm_judge(
    report: str, contract_text: str, contract_type: str, api_key: str
) -> JudgeResult | None:
    """使用 LLM-as-judge 对报告质量打分。"""
    from llm_client import LLMClient

    client = LLMClient(api_key=api_key, model="qwen-plus")
    try:
        user = _JUDGE_USER_PROMPT.format(
            contract_type=contract_type,
            contract_text=contract_text[:4000],
            report=report[:6000],
        )
        raw = client.call(_JUDGE_SYSTEM_PROMPT, user, max_tokens=512)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        data = json.loads(raw)
        return JudgeResult(
            completeness=int(data.get("completeness", 0)),
            accuracy=int(data.get("accuracy", 0)),
            actionability=int(data.get("actionability", 0)),
            format_quality=int(data.get("format_quality", 0)),
            overall=int(data.get("overall", 0)),
            comments=data.get("comments", ""),
        )
    except Exception as e:
        print(f"LLM裁判打分失败: {e}")
        return None
