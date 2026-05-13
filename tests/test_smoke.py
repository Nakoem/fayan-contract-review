"""
冒烟测试：核心工具函数 + 模块导入 + 集成骨架。

运行方式：
    pytest tests/test_smoke.py -v
    python -m pytest tests/test_smoke.py -v
"""

import json
import os
import sys

import pytest

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ═══════════════════════════════════════════════════════════
# 1. JSON 修复（4种策略）
# ═══════════════════════════════════════════════════════════


class TestRepairJson:
    """验证 repair_json 能修复 qwen-plus 常见的 4 种 JSON 错误。"""

    def test_valid_json_passthrough(self):
        from utils import repair_json

        valid = '{"key": "value"}'
        assert repair_json(valid) == valid

    def test_trailing_comma(self):
        from utils import repair_json

        result = repair_json('{"key": "value",}')
        assert result is not None
        data = json.loads(result)
        assert data == {"key": "value"}

    def test_extract_json_from_noisy_text(self):
        from utils import repair_json

        result = repair_json('好的，分析结果如下：\n{"key": "value"}\n以上是分析结果。')
        assert result is not None
        data = json.loads(result)
        assert data == {"key": "value"}

    def test_single_quotes_to_double(self):
        from utils import repair_json

        result = repair_json("{'key': 'value'}")
        assert result is not None
        data = json.loads(result)
        assert data == {"key": "value"}

    def test_empty_input(self):
        from utils import repair_json

        assert repair_json("") is None
        assert repair_json(None) is None

    def test_malformed_unrecoverable(self):
        from utils import repair_json

        assert repair_json("这不是JSON") is None


# ═══════════════════════════════════════════════════════════
# 2. 文本模式工具调用解析
# ═══════════════════════════════════════════════════════════


class TestParseTextToolCalls:
    """验证文本模式 <<TOOL>> 标签解析。"""

    def test_single_tool_call(self):
        from utils import parse_text_tool_calls

        content = '<<TOOL:search_regulation>>\n<<ARGS:{"keyword": "押金退还"}>>'
        results = parse_text_tool_calls(content)
        assert len(results) == 1
        assert results[0] == ("search_regulation", {"keyword": "押金退还"})

    def test_multiple_tool_calls(self):
        from utils import parse_text_tool_calls

        content = (
            '<<TOOL:extract_clauses>>\n<<ARGS:{"contract_type": "房屋租赁合同"}>>\n'
            '<<TOOL:search_regulation>>\n<<ARGS:{"keyword": "违约金"}>>'
        )
        results = parse_text_tool_calls(content)
        assert len(results) == 2
        assert results[0][0] == "extract_clauses"
        assert results[1][0] == "search_regulation"

    def test_no_tool_calls(self):
        from utils import parse_text_tool_calls

        results = parse_text_tool_calls("这是普通文本回复，没有工具调用。")
        assert results == []

    def test_broken_json_repair(self):
        from utils import parse_text_tool_calls

        content = "<<TOOL:search_regulation>>\n<<ARGS:{'keyword': '违约金上限',}>>"
        results = parse_text_tool_calls(content)
        assert len(results) == 1
        assert results[0][0] == "search_regulation"
        assert "keyword" in results[0][1]


# ═══════════════════════════════════════════════════════════
# 3. 工具参数解析
# ═══════════════════════════════════════════════════════════


class TestParseToolArgs:
    def test_valid_json(self):
        from utils import parse_tool_args

        result = parse_tool_args('{"key": "value"}')
        assert result == {"key": "value"}

    def test_empty_string(self):
        from utils import parse_tool_args

        assert parse_tool_args("") == {}

    def test_broken_json_repair(self):
        from utils import parse_tool_args

        result = parse_tool_args('{"key": "value",}')
        assert result == {"key": "value"}


# ═══════════════════════════════════════════════════════════
# 4. 报告后处理
# ═══════════════════════════════════════════════════════════


class TestCleanReport:
    def test_placeholder_removal(self):
        from utils import clean_report

        report = "1. 【金额条款】\n   ▸ 原文：已在第3条去重后不再重复列出。\n正常内容"
        cleaned = clean_report(report, "", "房屋租赁合同")
        assert "去重后不再重复列出" not in cleaned
        assert "正常内容" in cleaned

    def test_cooperation_42_fallback(self):
        from utils import clean_report

        contract = "退出方已投入的资产归联合实验室所有，不予退还，亦不折价补偿。"
        report = "标准报告内容"
        cleaned = clean_report(report, contract, "合作协议")
        assert "补充风险提示" in cleaned
        assert "4.2" in cleaned

    def test_non_cooperation_no_fallback(self):
        from utils import clean_report

        cleaned = clean_report("报告", "", "房屋租赁合同")
        assert "补充风险提示" not in cleaned


# ═══════════════════════════════════════════════════════════
# 5. 模块导入完整性
# ═══════════════════════════════════════════════════════════


class TestImports:
    """确保核心模块能正确导入，没有循环引用或缺失依赖。"""

    def test_llm_client(self):
        from llm_client import LLMClient

        assert LLMClient is not None

    def test_tools(self):
        from tools import AGENT_TOOLS, extract_clauses, search_regulation

        assert len(AGENT_TOOLS) == 10
        assert callable(search_regulation)
        assert callable(extract_clauses)

    def test_prompts(self):
        from prompts import AGENT_SYSTEM_PROMPT, AGENT_USER_PROMPT

        assert len(str(AGENT_SYSTEM_PROMPT)) > 100
        assert "{contract_type}" in str(AGENT_USER_PROMPT)

    def test_main_agent(self):
        from main import ContractReviewAgent, review_contract

        agent = ContractReviewAgent(api_key="test", verbose=False)
        assert agent is not None
        assert callable(review_contract)

    def test_langgraph_agent(self):
        from agent_langgraph import ALL_TOOLS, review_contract_langgraph

        assert len(ALL_TOOLS) == 10
        assert callable(review_contract_langgraph)

    def test_utils(self):
        from utils import clean_report, parse_text_tool_calls, parse_tool_args, repair_json

        assert callable(repair_json)
        assert callable(parse_text_tool_calls)
        assert callable(parse_tool_args)
        assert callable(clean_report)


# ═══════════════════════════════════════════════════════════
# 6. 集成测试（需要 API Key + LLM 调用，默认跳过）
# ═══════════════════════════════════════════════════════════


@pytest.mark.slow
class TestIntegration:
    """需要 DASHSCOPE_API_KEY 环境变量。运行：pytest -m slow"""

    @pytest.fixture
    def contract_text(self):
        path = os.path.join(os.path.dirname(__file__), "..", "sample_lease.txt")
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_full_review_original(self, contract_text):
        """原版 Agent 完整审查冒烟测试。"""
        from dotenv import load_dotenv

        load_dotenv()
        api_key = os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            pytest.skip("DASHSCOPE_API_KEY not set")

        from main import review_contract

        report = review_contract(contract_text, "房屋租赁合同", api_key)
        assert len(report) > 500, f"报告太短: {len(report)} 字符"
        assert "风险" in report
        assert "审查日期" in report

    def test_full_review_langgraph(self, contract_text):
        """LangGraph 版 Agent 完整审查冒烟测试。"""
        from dotenv import load_dotenv

        load_dotenv()
        if not os.getenv("DASHSCOPE_API_KEY"):
            pytest.skip("DASHSCOPE_API_KEY not set")

        from agent_langgraph import review_contract_langgraph

        report = review_contract_langgraph(contract_text, "房屋租赁合同")
        assert len(report) > 500, f"报告太短: {len(report)} 字符"
        assert "风险" in report
        assert "审查日期" in report

    def test_two_versions_consistency(self, contract_text):
        """两版输出一致性检查（宽松标准）。"""
        from dotenv import load_dotenv

        load_dotenv()
        if not os.getenv("DASHSCOPE_API_KEY"):
            pytest.skip("DASHSCOPE_API_KEY not set")

        from agent_langgraph import review_contract_langgraph
        from main import review_contract

        r1 = review_contract(contract_text, "房屋租赁合同", os.getenv("DASHSCOPE_API_KEY"))
        r2 = review_contract_langgraph(contract_text, "房屋租赁合同")

        # 长度偏差 ≤ 50%
        len_diff = abs(len(r1) - len(r2)) / max(len(r1), len(r2))
        assert len_diff < 0.5, f"报告长度偏差过大: {len_diff:.1%}"

        # 都包含关键结构
        for key in ["风险", "合同类型", "审查日期"]:
            assert key in r1, f"原版缺少: {key}"
            assert key in r2, f"LangGraph版缺少: {key}"
