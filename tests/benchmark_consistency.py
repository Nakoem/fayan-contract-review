"""
单Agent一致性基准测试 — 同一合同跑N次，统计检出条款重叠率。

用法：
    python tests/benchmark_consistency.py [回合数] [合同文件] [合同类型]

示例：
    python tests/benchmark_consistency.py 5 sample_lease.txt "房屋租赁合同"
    python tests/benchmark_consistency.py 8 sample_sales.txt "买卖合同"

输出：
    - 每轮报告的指标（风险数、评分、长度）
    - 条款重叠率矩阵（Jaccard pairwise）
    - 平均重叠率及稳定性评级
"""

import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("DASHSCOPE_API_KEY")
if not API_KEY:
    print("❌ 请设置 DASHSCOPE_API_KEY 环境变量")
    sys.exit(1)


def extract_clauses(report: str, section: str = "all") -> list[str]:
    """从报告中提取条款原文（归一化后用作条款指纹）。"""
    # 匹配 ▸ 原文：... 后面的文本
    pattern = r"▸\s*原文[：:](.+)"
    matches = re.findall(pattern, report)

    # 按风险段分区
    if section == "high":
        part = report.split("需关注的中风险条款")[0] if "需关注的中风险条款" in report else report
        matches = re.findall(pattern, part)
    elif section == "medium":
        if "需关注的中风险条款" in report and "修改优先级建议" in report:
            part = report.split("需关注的中风险条款")[1].split("修改优先级建议")[0]
            matches = re.findall(pattern, part)
        elif "需关注的中风险条款" in report:
            part = report.split("需关注的中风险条款")[1]
            matches = re.findall(pattern, part)

    # 归一化：去首尾空白、去尾部标点
    normalized = []
    for m in matches:
        m = m.strip().rstrip("。，；;.,")
        if m and len(m) > 5:  # 过滤太短的
            normalized.append(m)
    return normalized


def jaccard(set_a: set, set_b: set) -> float:
    """两集合的 Jaccard 相似度。"""
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def extract_metrics(report: str) -> dict:
    """提取报告关键指标。"""
    high = len(re.findall(r"🔴\s*高风险", report))
    mid = len(re.findall(r"🟡\s*中风险", report))
    low = len(re.findall(r"🟢\s*低风险", report))

    score_match = re.search(r"综合风险评分[：:](\d+)", report)
    score = int(score_match.group(1)) if score_match else None

    return {"len": len(report), "high": high, "mid": mid, "low": low, "score": score}


def main():
    from main import review_contract

    n_runs = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    contract_path = sys.argv[2] if len(sys.argv) > 2 else "sample_lease.txt"
    contract_type = sys.argv[3] if len(sys.argv) > 3 else "房屋租赁合同"

    contract_text = Path(contract_path).read_text(encoding="utf-8")
    print(f"📄 {contract_path} → {contract_type} ({len(contract_text)} 字符)")
    print(f"🔄 回合数: {n_runs}")
    print(f"{'=' * 70}\n")

    reports = []
    all_metrics = []
    all_clauses = []  # list[set[str]]
    all_clauses_high = []
    all_clauses_medium = []

    for i in range(n_runs):
        print(f"第 {i + 1}/{n_runs} 轮审查中...", end=" ", flush=True)
        t0 = time.time()
        try:
            report = review_contract(contract_text, contract_type, API_KEY)
        except Exception as e:
            print(f"\n❌ 第 {i + 1} 轮失败: {e}")
            continue
        elapsed = time.time() - t0

        metrics = extract_metrics(report)
        clauses = set(extract_clauses(report, "all"))
        clauses_high = set(extract_clauses(report, "high"))
        clauses_medium = set(extract_clauses(report, "medium"))

        all_metrics.append(metrics)
        all_clauses.append(clauses)
        all_clauses_high.append(clauses_high)
        all_clauses_medium.append(clauses_medium)
        reports.append(report)

        print(
            f"⏱ {elapsed:.0f}s | {metrics['len']}字 | "
            f"🔴{metrics['high']} 🟡{metrics['mid']} 🟢{metrics['low']} | "
            f"评分{metrics['score']} | 检出{len(clauses)}条"
        )

    # ── 汇总 ──
    print(f"\n{'=' * 70}")
    print("📊 指标稳定性")
    print(f"{'=' * 70}")

    for field, label in [
        ("high", "高风险数"),
        ("mid", "中风险数"),
        ("low", "低风险数"),
        ("score", "评分"),
    ]:
        vals = [m[field] for m in all_metrics if m[field] is not None]
        if vals:
            print(
                f"  {label}: min={min(vals)} max={max(vals)} mean={sum(vals) / len(vals):.1f} σ={np_std(vals):.1f}"
                if len(vals) > 1
                else f"  {label}: {vals[0]}"
            )

    lengths = [m["len"] for m in all_metrics]
    print(
        f"  报告长度: min={min(lengths)} max={max(lengths)} mean={sum(lengths) / len(lengths):.0f}"
    )

    # ── 重叠率矩阵 ──
    n = len(all_clauses)
    if n < 2:
        print("\n⚠️ 有效报告不足2份，无法计算重叠率")
        return False

    print(f"\n{'=' * 70}")
    print("📊 条款重叠率 (Jaccard)")
    print(f"{'=' * 70}")

    all_pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            jac = jaccard(all_clauses[i], all_clauses[j])
            all_pairs.append(jac)
            print(
                f"  R{i + 1} × R{j + 1}: {jac:.2%} ({len(all_clauses[i] & all_clauses[j])}/{len(all_clauses[i] | all_clauses[j])} 共用/并集)"
            )

    if not all_pairs:
        return False

    avg_jaccard = sum(all_pairs) / len(all_pairs)
    min_jaccard = min(all_pairs)
    max_jaccard = max(all_pairs)

    print(f"\n  平均重叠率: {avg_jaccard:.1%}")
    print(f"  最低 / 最高: {min_jaccard:.1%} / {max_jaccard:.1%}")

    # 稳定性评级
    if avg_jaccard >= 0.80:
        grade = "🟢 优秀"
    elif avg_jaccard >= 0.65:
        grade = "🟡 良好"
    elif avg_jaccard >= 0.50:
        grade = "🟠 一般"
    else:
        grade = "🔴 差"

    print(f"  稳定性: {grade}")

    # ── 高频条款（各轮都出现的 = 核心条款） ──
    print(f"\n{'=' * 70}")
    print("📊 条款出现频率")
    print(f"{'=' * 70}")

    clause_freq = {}
    for clauses in all_clauses:
        for c in clauses:
            clause_freq[c] = clause_freq.get(c, 0) + 1

    always_found = [c for c, f in clause_freq.items() if f == n]
    often_found = [c for c, f in clause_freq.items() if f >= n * 0.6 and f < n]
    rarely_found = [c for c, f in clause_freq.items() if f < n * 0.4]

    print(f"  ✅ 全部轮次检出: {len(always_found)} 条（核心条款）")
    for c in always_found:
        print(f"     ▸ {c[:80]}...")
    print(f"  🟡 多数轮次检出 (≥60%): {len(often_found)} 条")
    for c in often_found:
        print(f"     ▸ {c[:80]}...")
    print(f"  ❌ 少数轮次检出 (<40%): {len(rarely_found)} 条（不稳定）")
    for c in rarely_found:
        print(f"     ▸ {c[:80]}...")

    # 保存所有报告
    out_dir = Path("benchmark_reports")
    out_dir.mkdir(exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    for idx, report in enumerate(reports):
        (out_dir / f"run_{idx + 1:02d}_{ts}.txt").write_text(report, encoding="utf-8")

    print(f"\n📁 报告已保存至 {out_dir}/run_*_{ts}.txt")
    print(f"\n结论: 平均重叠率 {avg_jaccard:.1%} → {grade}")

    return avg_jaccard >= 0.80


def np_std(vals):
    """简易标准差，不依赖 numpy。"""
    mean = sum(vals) / len(vals)
    return (sum((x - mean) ** 2 for x in vals) / (len(vals) - 1)) ** 0.5


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
