"""
知识库分块 + 索引构建。从 tools.py 读取五个知识库，分块 → embedding → Chroma。
"""

import re

from rag.embedder import encode
from rag.vector_store import index_documents, collection_exists


def _split_by_paragraphs(text: str) -> list[str]:
    """按段落分块，过滤空行。"""
    parts = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    if not parts:
        return [text.strip()]
    return parts


def _build_regulation_chunks(db: dict) -> tuple[list[str], list[str], list[dict]]:
    """法规库分块：每条法规按段落分块，保留法规标题元数据。"""
    ids, docs, metas = [], [], []
    for key, content in db.items():
        paragraphs = _split_by_paragraphs(content)
        for i, para in enumerate(paragraphs):
            ids.append(f"reg_{key}_{i}")
            docs.append(para)
            metas.append({"source": key, "type": "regulation", "chunk": i})
    return ids, docs, metas


def _build_simple_chunks(db: dict, source_type: str) -> tuple[list[str], list[str], list[dict]]:
    """简单分块：每个条目作为一个chunk。"""
    ids, docs, metas = [], [], []
    for key, content in db.items():
        paragraphs = _split_by_paragraphs(content)
        if len(paragraphs) <= 2:
            # 短文本整段索引
            ids.append(f"{source_type}_{key}_0")
            docs.append(content.strip())
            metas.append({"source": key, "type": source_type, "chunk": 0})
        else:
            for i, para in enumerate(paragraphs):
                ids.append(f"{source_type}_{key}_{i}")
                docs.append(para)
                metas.append({"source": key, "type": source_type, "chunk": i})
    return ids, docs, metas


def build_all_indexes(force: bool = False) -> dict[str, int]:
    """构建所有知识库的向量索引。返回 {collection: chunk_count}。"""
    from tools import (
        _REGULATION_DB, _CASE_LAW_DB, _LOCAL_POLICY_DB,
        _TAX_RULE_DB, _WEB_KB,
    )

    # 检查是否已有索引
    if not force and all(collection_exists(c) for c in ["regulation", "case_law", "local_policy", "tax_rule"]):
        return {}

    print("正在构建向量索引，首次运行需下载 embedding 模型...")
    stats = {}

    # 法规库
    ids, docs, metas = _build_regulation_chunks(_REGULATION_DB)
    if docs:
        embs = encode(docs)
        index_documents("regulation", ids, docs, metas, embs)
        stats["regulation"] = len(docs)

    # 判例库
    ids, docs, metas = _build_simple_chunks(_CASE_LAW_DB, "case_law")
    if docs:
        embs = encode(docs)
        index_documents("case_law", ids, docs, metas, embs)
        stats["case_law"] = len(docs)

    # 地方政策库
    ids, docs, metas = _build_simple_chunks(_LOCAL_POLICY_DB, "local_policy")
    if docs:
        embs = encode(docs)
        index_documents("local_policy", ids, docs, metas, embs)
        stats["local_policy"] = len(docs)

    # 税务规则库
    ids, docs, metas = _build_simple_chunks(_TAX_RULE_DB, "tax_rule")
    if docs:
        embs = encode(docs)
        index_documents("tax_rule", ids, docs, metas, embs)
        stats["tax_rule"] = len(docs)

    # 联网知识库
    ids, docs, metas = _build_simple_chunks(_WEB_KB, "web_kb")
    if docs:
        embs = encode(docs)
        index_documents("web_kb", ids, docs, metas, embs)
        stats["web_kb"] = len(docs)

    total = sum(stats.values())
    print(f"索引构建完成：{total} chunks -> {len(stats)} 个集合")
    return stats
