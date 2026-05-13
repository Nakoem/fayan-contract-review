"""
混合检索器：向量语义检索 + 关键词匹配兜底 + 去重融合。
"""

from rag.embedder import encode_query
from rag.indexer import build_all_indexes
from rag.vector_store import collection_exists
from rag.vector_store import search as vector_search


def search(
    query: str,
    collection: str,
    top_k: int = 3,
    threshold: float = 0.6,
) -> list[dict]:
    """混合检索主入口。

    Args:
        query: 搜索查询
        collection: 集合名 (regulation / case_law / local_policy / tax_rule / web_kb)
        top_k: 返回条数
        threshold: 向量相似度阈值（低于此值的结果丢弃）

    Returns:
        [{id, document, metadata, distance, score}]
    """
    # 确保索引存在
    if not collection_exists(collection):
        build_all_indexes()

    # 向量检索
    try:
        q_emb = encode_query(query)
        results = vector_search(collection, q_emb, top_k=top_k)
    except Exception:
        results = []

    # 转换 distance → score (cosine distance: 0=identical, 2=opposite)
    for r in results:
        r["score"] = max(0.0, 1.0 - r["distance"] / 2.0)

    # 过滤低分结果
    results = [r for r in results if r.get("score", 0) >= threshold]

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
