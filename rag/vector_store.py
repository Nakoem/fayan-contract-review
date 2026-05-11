"""
Chroma 向量存储管理。每个知识库一个 Collection。
"""

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import chromadb

_client: "chromadb.API | None" = None

COLLECTIONS = ["regulation", "case_law", "local_policy", "tax_rule", "web_kb"]

_INDEX_DIR = Path(__file__).parent.parent / "rag_index"


def _get_client() -> "chromadb.PersistentClient":
    global _client
    if _client is None:
        import chromadb

        _INDEX_DIR.mkdir(exist_ok=True)
        _client = chromadb.PersistentClient(
            path=str(_INDEX_DIR),
            settings=chromadb.Settings(anonymized_telemetry=False),
        )
    return _client


def get_collection(name: str):
    """获取指定集合，不存在则创建（使用 cosine 距离）。"""
    client = _get_client()
    try:
        col = client.get_collection(name)
        # 如果已存在但距离度量不对，删除重建
        if col.metadata is None or col.metadata.get("hnsw:space") != "cosine":
            client.delete_collection(name)
            raise Exception("重建")
        return col
    except Exception:
        return client.create_collection(
            name,
            metadata={"hnsw:space": "cosine"},
        )


def index_documents(
    collection_name: str,
    ids: list[str],
    documents: list[str],
    metadatas: list[dict],
    embeddings: list[list[float]],
) -> None:
    """将文档和向量写入 Chroma 集合。"""
    col = get_collection(collection_name)
    col.upsert(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
        embeddings=embeddings,
    )


def search(
    collection_name: str,
    query_embedding: list[float],
    top_k: int = 3,
) -> list[dict]:
    """向量检索，返回 top_k 结果。"""
    col = get_collection(collection_name)
    results = col.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )
    out = []
    if results["ids"] and results["ids"][0]:
        for i in range(len(results["ids"][0])):
            out.append({
                "id": results["ids"][0][i],
                "document": results["documents"][0][i] if results["documents"] else "",
                "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                "distance": results["distances"][0][i] if results["distances"] else 1.0,
            })
    return out


def collection_exists(name: str) -> bool:
    """检查集合是否已建索引。"""
    client = _get_client()
    try:
        client.get_collection(name)
        return True
    except Exception:
        return False
