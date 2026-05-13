"""
法眼双版本一致性测试脚本。

用法：
    python tests/benchmark_consistency.py

用 3 份不同合同分别跑原版和 LangGraph 版，对比：
    - 综合风险评分偏差（应 ≤ 5 分）
    - 高风险条款数偏差（应 ≤ 2 条）
    - 报告长度偏差（应 ≤ 30%）
    - 报告结构完整性
"""

import os
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("DASHSCOPE_API_KEY")
if not API_KEY:
    print("❌ 请设置 DASHSCOPE_API_KEY 环境变量")
    sys.exit(1)

# ── 测试合同 ──
TEST_CASES = [
    ("sample_lease.txt", "房屋租赁合同"),
    ("sample_employment.txt", "劳动合同"),
    ("sample_service.txt", "服务合同"),
]


def extract_metrics(report: str) -> dict:
    """从审查报告中提取关键指标。"""
    high = len(re.findall(r"🔴\s*高风险", report))
    mid = len(re.findall(r"🟡\s*中风险", report))
    low = len(re.findall(r"🟢\s*低风险", report))

    score_match = re.search(r"综合风险评分[：:](\d+)", report)
    score = int(score_match.group(1)) if score_match else None

    p0 = len(re.findall(r"P0\s+必须改", report))
    p1 = len(re.findall(r"P1\s+建议改", report))

    has_overview = "总体风险概览" in report
    has_detail = "高风险条款详解" in report
    has_priority = "修改优先级" in report
    has_advice = "签约建议" in report

    return {
        "len": len(report),
        "high": high,
        "mid": mid,
        "low": low,
        "score": score,
        "p0": p0,
        "p1": p1,
        "overview": has_overview,
        "detail": has_detail,
        "priority": has_priority,
        "advice": has_advice,
    }


def main():
    from main import review_contract
    from agent_langgraph import review_contract_langgraph

    results = []

    for filename, contract_type in TEST_CASES:
        text = Path(filename).read_text(encoding="utf-8")
        print(f"\n{'='*60}")
        print(f"📄 {filename} ({contract_type}) — {len(text)} 字符")
        print(f"{'='*60}")

        # 原版
        print("  原版 (main.py)...")
        t0 = time.time()
        r1 = review_contract(text, contract_type, API_KEY)
        t1 = time.time()
        m1 = extract_metrics(r1)
        print(f"    耗时 {t1-t0:.0f}s | {m1['len']}字 | 🔴{m1['high']} 🟡{m1['mid']} 🟢{m1['low']} | 评分{m1['score']}")

        # LangGraph版
        print("  LangGraph版 (agent_langgraph.py)...")
        t2 = time.time()
        r2 = review_contract_langgraph(text, contract_type)
        t3 = time.time()
        m2 = extract_metrics(r2)
        print(f"    耗时 {t3-t2:.0f}s | {m2['len']}字 | 🔴{m2['high']} 🟡{m2['mid']} 🟢{m2['low']} | 评分{m2['score']}")

        # 偏差
        score_dev = abs((m1["score"] or 0) - (m2["score"] or 0))
        high_dev = abs(m1["high"] - m2["high"])
        len_dev = abs(m1["len"] - m2["len"]) / max(m1["len"], m2["len"]) * 100

        status = "✅" if score_dev <= 5 and high_dev <= 2 and len_dev <= 30 else "⚠️"
        print(f"  {status} 评分偏差={score_dev} | 高风险偏差={high_dev} | 长度偏差={len_dev:.1f}%")

        results.append({
            "file": filename,
            "type": contract_type,
            "score_dev": score_dev,
            "high_dev": high_dev,
            "len_dev": len_dev,
            "status": status,
            "m1": m1,
            "m2": m2,
        })

    # ── 汇总 ──
    print(f"\n{'='*60}")
    print("📊 汇总")
    print(f"{'='*60}")
    for r in results:
        print(f"  {r['status']} {r['file']:25s} 评分偏差={r['score_dev']}  高风险偏差={r['high_dev']}  长度偏差={r['len_dev']:.1f}%")

    all_pass = all(r["status"] == "✅" for r in results)
    print(f"\n{'✅ 全部通过' if all_pass else '⚠️ 部分偏差超出阈值，需人工复核'}")
    return all_pass


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
