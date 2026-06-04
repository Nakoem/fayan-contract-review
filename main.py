"""
合同审查助手 —— CLI 入口（LangGraph Supervisor 多Agent 引擎）

用法：
    python main.py <合同文件路径> <合同类型>

示例：
    python main.py sample_lease.txt "房屋租赁合同"
    python main.py contract.txt "劳动合同" --output report.txt

引擎：
    Supervisor 协调 5 个专业 Agent（提取→法规→评估→反思→报告）
    支持断点恢复（SqliteSaver checkpoint）
"""

import os
import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

from dotenv import load_dotenv

from logger import init_logger, logger

load_dotenv()


def main():
    """CLI 入口：读取合同文件 → LangGraph 多Agent 审查 → 输出报告。"""
    from agent_langgraph import review_contract_langgraph

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
    logger.info("[LangGraph 多Agent 模式启动]")
    logger.info("审查合同类型: {}", contract_type)
    logger.info("合同来源: {}", filepath)
    logger.info("=" * 60)

    from cache import contract_cache_key, get_cache

    cache = get_cache()
    ck = contract_cache_key(contract_text, contract_type)
    cached = cache.get(ck)
    if cached:
        logger.info("[缓存命中] 直接返回，跳过 LLM 审查")
        report = cached
    else:
        report, thread_id = review_contract_langgraph(contract_text, contract_type)
        if report:
            cache.set(ck, report)

    if output_path:
        Path(output_path).write_text(report, encoding="utf-8")
        logger.info("")
        logger.info("报告已保存至: {}", output_path)
    else:
        print(report)


if __name__ == "__main__":
    main()
