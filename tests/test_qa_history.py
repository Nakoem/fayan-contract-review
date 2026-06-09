"""
法律问答 · 历史数据查询工具测试。

运行方式：
    pytest tests/test_qa_history.py -v
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ═══════════════════════════════════════════════════════════
# 1. query_review_history — count action
# ═══════════════════════════════════════════════════════════


class TestQueryReviewHistoryCount:
    """验证 count action 返回统计信息。"""

    def test_count_returns_valid_stats(self):
        """count action 返回 total_reviews、avg_score 等字段。"""
        from tools import query_review_history

        result = query_review_history(action="count")
        assert "总共" in result or "total" in result.lower()
        assert "份" in result or "contract" in result.lower()

    def test_count_with_contract_type_filter(self):
        """按合同类型过滤统计。"""
        from tools import query_review_history

        result = query_review_history(action="count", contract_type="房屋租赁合同")
        assert isinstance(result, str)
        assert len(result) > 0


# ═══════════════════════════════════════════════════════════
# 2. query_review_history — top_risks + list
# ═══════════════════════════════════════════════════════════


class TestQueryReviewHistoryTopRisks:
    """验证 top_risks action。"""

    def test_top_risks_returns_ranked_list(self):
        """top_risks 返回风险排行，含条款名和次数。"""
        from tools import query_review_history

        result = query_review_history(action="top_risks")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_top_risks_with_contract_type(self):
        """按合同类型过滤风险排行。"""
        from tools import query_review_history

        result = query_review_history(action="top_risks", contract_type="合作协议")
        assert isinstance(result, str)


class TestQueryReviewHistoryList:
    """验证 list action。"""

    def test_list_returns_recent_contracts(self):
        """list 返回最近N份合同，含得分。"""
        from tools import query_review_history

        result = query_review_history(action="list", limit=3)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_list_sort_by_score(self):
        """sort_by=score_desc 返回最高分优先。"""
        from tools import query_review_history

        result = query_review_history(action="list", sort_by="score_desc")
        assert isinstance(result, str)

    def test_list_empty_with_unknown_type(self):
        """无匹配合同类型时正常返回提示。"""
        from tools import query_review_history

        result = query_review_history(action="list", contract_type="不存在的合同类型")
        assert isinstance(result, str)
        assert "暂无" in result


# ═══════════════════════════════════════════════════════════
# 3. query_review_history — detail + report
# ═══════════════════════════════════════════════════════════


class TestQueryReviewHistoryDetail:
    """验证 detail action。"""

    def test_detail_returns_risk_details(self):
        """detail 返回风险详情。"""
        from tools import query_review_history

        result = query_review_history(action="detail")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_detail_with_keyword(self):
        """keyword 过滤风险详情。"""
        from tools import query_review_history

        result = query_review_history(action="detail", keyword="押金")
        assert isinstance(result, str)

    def test_detail_with_risk_level(self):
        """risk_level 过滤高风险。"""
        from tools import query_review_history

        result = query_review_history(action="detail", risk_level="高风险")
        assert isinstance(result, str)
        assert "高风险" in result or "条风险" in result

    def test_detail_no_match_returns_hint(self):
        """无匹配关键词时返回提示。"""
        from tools import query_review_history

        result = query_review_history(action="detail", keyword="火星条款XYZ不存在")
        assert "未找到" in result or "暂无" in result


class TestQueryReviewHistoryReport:
    """验证 report action。"""

    def test_report_search(self):
        """report 搜索报告全文。"""
        from tools import query_review_history

        result = query_review_history(action="report", keyword="风险")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_report_no_match(self):
        """无匹配报告时返回提示。"""
        from tools import query_review_history

        result = query_review_history(action="report", keyword="xyz123火星关键词")
        assert "未找到" in result or "暂无" in result


# ═══════════════════════════════════════════════════════════
# 4. query_review_history — match
# ═══════════════════════════════════════════════════════════


class TestQueryReviewHistoryMatch:
    """验证 match action。"""

    def test_match_empty_fingerprint(self):
        """空指纹返回提示。"""
        from tools import query_review_history

        result = query_review_history(action="match", fingerprint="")
        assert "指纹" in result or "fingerprint" in result or "未提供" in result


class TestQueryReviewHistoryDegradation:
    """验证 MySQL 不可用时的降级行为。"""

    def test_unavailable_db_returns_fallback(self, monkeypatch):
        """数据库连不上时返回降级提示，不抛异常。"""
        from tools import query_review_history

        def mock_fail(*args, **kwargs):
            raise RuntimeError("Connection refused")

        monkeypatch.setattr("db.get_conn", mock_fail)

        result = query_review_history(action="count")
        assert "暂不可用" in result or "unavailable" in result.lower()


# ═══════════════════════════════════════════════════════════
# 3. query_review_history — 功能导入
# ═══════════════════════════════════════════════════════════


class TestQAToolDefinition:
    """验证工具定义可正确导入。"""

    def test_qa_tool_definition_exists(self):
        """QA_TOOL 是合法的 Function Calling 定义。"""
        from tools import QA_TOOL

        assert QA_TOOL["type"] == "function"
        fn = QA_TOOL["function"]
        assert fn["name"] == "query_review_history"
        assert "action" in str(fn["parameters"])


# ═══════════════════════════════════════════════════════════
# 4. chat_engine — 轻量 Agent 改造
# ═══════════════════════════════════════════════════════════


class TestChatStreamWithTools:
    """验证 chat_stream 工具模式不破坏原有逻辑。"""

    def test_chat_stream_no_tools_unchanged(self):
        """不传 enable_tools 时行为不变（RAG检索+直接回答）。"""
        import dotenv

        dotenv.load_dotenv()
        api_key = os.getenv("DASHSCOPE_API_KEY", "")
        if not api_key:
            pytest.skip("DASHSCOPE_API_KEY not set")

        from chat_engine import chat_stream

        chunks = list(
            chat_stream(
                query="民法典关于押金的规定是什么？",
                history=[],
                contract_text="",
                api_key=api_key,
            )
        )
        full_response = "".join(chunks)
        assert len(full_response) > 20, "should return a meaningful answer"

    def test_chat_stream_with_tools_enabled(self):
        """传入 enable_tools=True 时工具模式正常。"""
        import dotenv

        dotenv.load_dotenv()
        api_key = os.getenv("DASHSCOPE_API_KEY", "")
        if not api_key:
            pytest.skip("DASHSCOPE_API_KEY not set")

        from chat_engine import chat_stream

        chunks = list(
            chat_stream(
                query="我审过几份合同？",
                history=[],
                contract_text="",
                api_key=api_key,
                enable_tools=True,
            )
        )
        full_response = "".join(chunks)
        assert len(full_response) > 10, "should return an answer even if history is empty"
