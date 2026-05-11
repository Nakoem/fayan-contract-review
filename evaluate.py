#!/usr/bin/env python
"""
法眼合同审查自动化评估工具。

用法：
    python evaluate.py                           # 评估所有6个样本合同
    python evaluate.py --contract sample_lease.txt  # 评估单个
    python evaluate.py --no-llm                  # 跳过LLM裁判（更快）
    python evaluate.py --output eval_report.json # 输出JSON
    python evaluate.py --verbose                 # 详细输出
"""

import sys
import os
import json
import time
import argparse
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv

from logger import init_logger, logger
from evaluate_helpers import (
    check_report_format, check_risk_coverage, llm_judge,
)
from tests.known_risks.known_risks import RISK_MAP

load_dotenv()


def evaluate_single(contract_path: str, api_key: str,
                    run_llm_judge: bool = True) -> dict | None:
    """评估单个合同。审查 → 格式检查 → 风险覆盖 → LLM裁判。"""
    filename = Path(contract_path).name
    if filename not in RISK_MAP:
        logger.error("未找到 {} 的已知风险定义", filename)
        return None

    contract_type, known_risks = RISK_MAP[filename]
    contract_text = Path(contract_path).read_text(encoding="utf-8")
    if not known_risks:
        logger.warning("{} 无已知风险点定义，跳过", filename)
        return None

    # 1. 运行审查
    from main import review_contract

    logger.info("开始审查: {} ({})", filename, contract_type)
    t0 = time.perf_counter()
    try:
        report = review_contract(contract_text, contract_type, api_key)
    except Exception as e:
        logger.error("审查失败: {}", e)
        return None
    elapsed = time.perf_counter() - t0
    logger.info("审查完成，耗时 {:.1f}s，报告 {} 字符", elapsed, len(report))

    # 2. 格式合规检查
    format_result = check_report_format(report)
    logger.info("格式合规: {} ({:.0%})",
                "✅" if format_result.passed else "❌", format_result.score)

    # 3. 风险覆盖检查
    coverage_result = check_risk_coverage(report, known_risks)
    logger.info("风险覆盖: 召回率 {:.0%} ({}/{})",
                coverage_result.recall, coverage_result.detected,
                coverage_result.total_known)

    # 4. LLM裁判
    judge_result = None
    if run_llm_judge:
        logger.info("LLM裁判打分中...")
        judge_result = llm_judge(report, contract_text, contract_type, api_key)
        if judge_result:
            logger.info("LLM综合评分: {}/10", judge_result.overall)

    return {
        "contract": filename,
        "contract_type": contract_type,
        "elapsed_seconds": round(elapsed, 1),
        "report_length": len(report),
        "format": format_result,
        "coverage": coverage_result,
        "judge": judge_result,
    }


def _serialize_result(r: dict) -> dict:
    """将评估结果序列化为可JSON化的字典。"""
    out = {
        "contract": r["contract"],
        "contract_type": r["contract_type"],
        "elapsed_seconds": r["elapsed_seconds"],
        "report_length": r["report_length"],
    }
    fmt = r["format"]
    out["format"] = {
        "passed": fmt.passed,
        "score": fmt.score,
        "checks": fmt.checks,
    }
    cov = r["coverage"]
    out["coverage"] = {
        "total_known": cov.total_known,
        "detected": cov.detected,
        "missed": cov.missed,
        "recall": cov.recall,
        "precision": cov.precision,
    }
    if r.get("judge"):
        j = r["judge"]
        out["judge"] = {
            "completeness": j.completeness,
            "accuracy": j.accuracy,
            "actionability": j.actionability,
            "format_quality": j.format_quality,
            "overall": j.overall,
            "comments": j.comments,
        }
    return out


def _print_aggregate(results: list[dict]) -> None:
    """打印汇总统计。"""
    n = len(results)
    if n == 0:
        return
    fmt_pass = sum(1 for r in results if r["format"].passed)
    avg_recall = (sum(r["coverage"].recall for r in results) / n
                  if n else 0)
    avg_time = sum(r["elapsed_seconds"] for r in results) / n if n else 0
    judge_results = [r["judge"] for r in results if r.get("judge")]

    print(f"\n{'='*60}")
    print(f"汇总 (n={n})")
    print(f"  格式合规率: {fmt_pass}/{n}")
    print(f"  平均风险召回率: {avg_recall:.1%}")
    print(f"  平均耗时: {avg_time:.0f}s")
    if judge_results:
        avg_overall = sum(j.overall for j in judge_results) / len(judge_results)
        print(f"  平均LLM综合评分: {avg_overall:.1f}/10")


def main():
    parser = argparse.ArgumentParser(description="法眼合同审查评估工具")
    parser.add_argument("--contract", type=str, help="指定单个合同文件路径")
    parser.add_argument("--no-llm", action="store_true", help="跳过LLM裁判打分")
    parser.add_argument("--output", type=str, help="输出JSON报告路径")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    args = parser.parse_args()

    level = "DEBUG" if args.verbose else "INFO"
    init_logger(mode="cli", level=level)

    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        logger.error("请设置 DASHSCOPE_API_KEY 环境变量")
        sys.exit(1)

    sample_dir = Path(__file__).parent

    if args.contract:
        path = Path(args.contract)
        if not path.is_absolute():
            path = sample_dir / path
        result = evaluate_single(str(path), api_key, not args.no_llm)
        results = [result] if result else []
    else:
        all_samples = [
            "sample_lease.txt", "sample_employment.txt",
            "sample_sales.txt", "sample_service.txt",
            "sample_cooperation.txt", "sample_loan.txt",
        ]
        results = []
        for i, filename in enumerate(all_samples, 1):
            path = sample_dir / filename
            if not path.exists():
                logger.warning("跳过不存在的文件: {}", filename)
                continue
            print(f"\n{'='*60}")
            print(f"[{i}/{len(all_samples)}] 评估: {filename}")
            print(f"{'='*60}")
            result = evaluate_single(str(path), api_key, not args.no_llm)
            if result:
                results.append(result)

    _print_aggregate(results)

    if args.output:
        output = {
            "timestamp": datetime.now().isoformat(),
            "results": [_serialize_result(r) for r in results],
        }
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2),
                          encoding="utf-8")
        print(f"\n评估报告已保存至: {args.output}")


if __name__ == "__main__":
    main()
