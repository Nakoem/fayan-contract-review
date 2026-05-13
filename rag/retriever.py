"""
混合检索器：向量语义检索 + 关键词全文匹配 + RRF 融合去重。
"""

from rag.embedder import encode_query
from rag.indexer import build_all_indexes
from rag.vector_store import collection_exists, get_collection
from rag.vector_store import search as vector_search


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
    """关键词全文检索：扫描 collection 中所有文档，按关键词覆盖度评分。

    返回 [{id, document, metadata, score}]，score 0-1。
    """
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
) -> list[dict]:
    """混合检索主入口：向量语义 + 关键词全文 + RRF 融合。

    Args:
        query: 搜索查询
        collection: 集合名 (regulation / case_law / local_policy / tax_rule / web_kb)
        top_k: 返回条数
        threshold: 最低相似度阈值

    Returns:
        [{id, document, metadata, distance, score}]
    """
    # 确保索引存在
    if not collection_exists(collection):
        build_all_indexes()

    # 向量检索
    try:
        q_emb = encode_query(query)
        vec_results = vector_search(collection, q_emb, top_k=top_k)
    except Exception:
        vec_results = []

    # 转换 distance → score
    for r in vec_results:
        r["score"] = max(0.0, 1.0 - r["distance"] / 2.0)

    # 关键词检索
    kw_results = keyword_search(query, collection, top_k=top_k)

    # RRF 融合
    results = rrf_fusion(vec_results, kw_results, top_k=top_k)

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
