"""
混合检索器：向量语义检索 + 关键词全文匹配 + RRF 融合去重 + Query Rewrite + 分类加权。
"""

from rag.embedder import encode_query
from rag.indexer import build_all_indexes
from rag.vector_store import collection_exists, get_collection
from rag.vector_store import search as vector_search

# ═══════════════════════════════════════════════════════════
# Query Rewrite: 搜索关键词 → 扩展查询（同义词 + 相关术语）
# ═══════════════════════════════════════════════════════════

_QUERY_EXPANSIONS: dict[str, str] = {
    "押金": "押金 退还 扣留 监管账户 罚没",
    "违约金": "违约金 过高 司法调减 实际损失 30% 逾期",
    "加班费": "加班 工资 延长 工时 150% 200% 300% 补休",
    "竞业限制": "竞业限制 补偿金 商业秘密 高级管理人员 两年",
    "试用期": "试用期 期限 工资80% 最低工资 解除 赔偿金",
    "解除合同": "解除 单方解约 赔偿 补偿金 通知期 解除权",
    "转租": "转租 书面同意 优先权 群租 备案",
    "利率": "利率 LPR 4倍 民间借贷 砍头息 逾期罚息",
    "社保": "社保 社会保险 缴纳 基数 费率 公积金",
    "格式条款": "格式条款 无效 公平性 合理抗辩 消费者 行业惯例",
    "知识产权": "知识产权 归属 专利 著作权 商标 技术开发",
    "不可抗力": "不可抗力 情势变更 免责 合同僵局 疫情影响",
    "验收": "验收 检验期限 质量不符 通知义务 保质期",
    "担保": "担保 连带保证 抵押 质押 定金罚则 一般保证",
    "劳动合同": "劳动合同 双倍工资 书面形式 无固定期限 解约 调岗",
    "合伙": "合伙 出资 利润分配 亏损分担 无限连带 退伙",
    "税务": "税务 增值税 个税 印花税 专票 所得税 税前扣除",
    "买卖合同": "买卖合同 质量 瑕疵 退货 赔偿 风险转移 孳息",
    "服务合同": "服务合同 承揽 验收 解除权 中途解约 预付",
    "借款合同": "借款合同 民间借贷 利率上限 担保 逾期 违约责任",
}

# ═══════════════════════════════════════════════════════════
# 合同类型 → 相关关键词加权（分类搜索）
# ═══════════════════════════════════════════════════════════

_CONTRACT_CATEGORY_BOOST: dict[str, list[str]] = {
    "房屋租赁合同": [
        "租赁",
        "押金",
        "租金",
        "转租",
        "出租",
        "承租",
        "房东",
        "房客",
        "房屋租赁",
        "备案",
        "维修",
        "取暖",
        "物业",
    ],
    "劳动合同": [
        "劳动",
        "试用期",
        "加班",
        "竞业",
        "社保",
        "工资",
        "解除劳动",
        "赔偿金",
        "双倍工资",
        "调岗",
        "补偿金",
        "离职",
        "工伤",
    ],
    "买卖合同": [
        "买卖",
        "出卖",
        "买受",
        "质量",
        "瑕疵",
        "退货",
        "价款",
        "检验",
        "风险转移",
        "孳息",
        "产品质量",
    ],
    "服务合同": [
        "服务",
        "承揽",
        "定作",
        "验收",
        "中途",
        "预付",
        "技术",
        "仲介",
        "委托",
        "居间",
    ],
    "合作协议": [
        "合作",
        "合伙",
        "出资",
        "利润",
        "分配",
        "退伙",
        "知识产权",
        "技术成果",
        "商业秘密",
        "竞业",
    ],
    "借款合同": [
        "借款",
        "借贷",
        "利息",
        "利率",
        "砍头息",
        "逾期",
        "担保",
        "抵押",
        "质押",
        "保证",
        "LPR",
    ],
}


def expand_query(query: str) -> str:
    """Query Rewrite: 扩展搜索词，命中同义术语时追加相关词。

    例: "押金" → "押金 退还 扣留 监管账户 罚没"
    """
    parts = [query]
    for keyword, expansion in _QUERY_EXPANSIONS.items():
        if keyword in query:
            # 避免重复添加
            for term in expansion.split():
                if term not in query:
                    parts.append(term)
            break  # 只匹配第一个映射，避免过度扩展
    return " ".join(parts)


def _category_boost_score(results: list[dict], contract_type: str) -> list[dict]:
    """分类加权：与合同类型相关的条目 +10% 分数。"""
    if not contract_type or contract_type not in _CONTRACT_CATEGORY_BOOST:
        return results
    boost_terms = _CONTRACT_CATEGORY_BOOST[contract_type]
    for r in results:
        meta_source = r.get("metadata", {}).get("source", "")
        doc_text = r.get("document", "")
        combined = f"{meta_source} {doc_text}"
        if any(term in combined for term in boost_terms):
            r["score"] = r.get("score", 0) * 1.10
    # 重新排序
    results.sort(key=lambda r: r.get("score", 0), reverse=True)
    return results


def _keyword_score(query: str, document: str) -> float:
    """基于关键词覆盖度的简单评分。"""
    query_terms = set(query)
    doc_text = document.lower()
    hits = sum(1 for t in query_terms if t in doc_text)
    return hits / max(len(query_terms), 1)


def keyword_search(
    query: str,
    collection: str,
    top_k: int = 5,
) -> list[dict]:
    """关键词全文检索：扫描 collection 中所有文档，按关键词覆盖度评分。"""
    if not collection_exists(collection):
        build_all_indexes()

    try:
        col = get_collection(collection)
        all_docs = col.get()
    except Exception:
        return []

    if not all_docs or not all_docs.get("ids"):
        return []

    results = []
    for i, doc_id in enumerate(all_docs["ids"]):
        doc = all_docs["documents"][i] if all_docs["documents"] else ""
        meta = all_docs["metadatas"][i] if all_docs["metadatas"] else {}
        score = _keyword_score(query, doc)
        if score > 0:
            results.append({"id": doc_id, "document": doc, "metadata": meta, "score": score})

    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:top_k]


def rrf_fusion(
    vector_results: list[dict],
    keyword_results: list[dict],
    k: int = 60,
    top_k: int = 5,
) -> list[dict]:
    """RRF (Reciprocal Rank Fusion) 融合两路结果。"""
    score_map: dict[str, dict] = {}
    for rank, r in enumerate(vector_results):
        rid = r["id"]
        score_map[rid] = dict(r)
        score_map[rid]["rrf_score"] = 1.0 / (k + rank + 1)
    for rank, r in enumerate(keyword_results):
        rid = r["id"]
        if rid in score_map:
            score_map[rid]["rrf_score"] += 1.0 / (k + rank + 1)
        else:
            score_map[rid] = dict(r)
            score_map[rid]["rrf_score"] = 1.0 / (k + rank + 1)

    merged = sorted(score_map.values(), key=lambda r: r.get("rrf_score", 0), reverse=True)
    for r in merged:
        r["score"] = r.get("rrf_score", r.get("score", 0))
    return merged[:top_k]


def search(
    query: str,
    collection: str,
    top_k: int = 3,
    threshold: float = 0.6,
    contract_type: str = "",
) -> list[dict]:
    """混合检索主入口：Query Rewrite → 向量 + 关键词 → RRF → 分类加权。

    Args:
        query: 搜索查询
        collection: 集合名 (regulation / case_law / local_policy / tax_rule / web_kb)
        top_k: 返回条数
        threshold: 最低相似度阈值
        contract_type: 可选，合同类型（用于分类加权）

    Returns:
        [{id, document, metadata, score}]
    """
    # 确保索引存在
    if not collection_exists(collection):
        build_all_indexes()

    # Query Rewrite: 扩展搜索词
    expanded_query = expand_query(query)

    # 向量检索（用扩展后的查询，召回更多）
    try:
        q_emb = encode_query(expanded_query)
        vec_results = vector_search(collection, q_emb, top_k=top_k * 2)
    except Exception:
        vec_results = []

    # 转换 distance → score
    for r in vec_results:
        r["score"] = max(0.0, 1.0 - r["distance"] / 2.0)

    # 关键词检索（也搜扩展查询）
    kw_results = keyword_search(expanded_query, collection, top_k=top_k)

    # RRF 融合
    results = rrf_fusion(vec_results, kw_results, top_k=top_k)

    # 分类加权
    if contract_type:
        results = _category_boost_score(results, contract_type)

    # 过滤低分
    results = [r for r in results if r.get("score", 0) >= threshold / 4.0]

    return results


def format_results(results: list[dict]) -> str:
    """将检索结果格式化为 Agent 可读文本。"""
    if not results:
        return ""

    # 按 source 分组
    grouped: dict[str, list[str]] = {}
    for r in results:
        src = r["metadata"].get("source", "未知")
        if src not in grouped:
            grouped[src] = []
        grouped[src].append(r["document"])

    parts = []
    for src, docs in grouped.items():
        text = "\n".join(docs)
        parts.append(f"【匹配：{src}】\n{text}")

    return "\n\n────────────────────────\n\n".join(parts)
