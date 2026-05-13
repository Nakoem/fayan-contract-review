"""
知识库索引构建脚本

用法：
  python knowledge/build_index.py           # 增量构建（已有索引跳过）
  python knowledge/build_index.py --force   # 强制重建
  python knowledge/build_index.py --list    # 列出各库条目数

从 knowledge/*.json 读取数据 → 分块 → embedding → 写入 ChromaDB。
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

KNOWLEDGE_DIR = Path(__file__).parent
COLLECTION_MAP = {
    "regulation.json": "regulation",
    "case_law.json": "case_law",
    "local_policy.json": "local_policy",
    "tax_rule.json": "tax_rule",
    "web_kb.json": "web_kb",
}


def load_json(filename: str) -> dict[str, str]:
    path = KNOWLEDGE_DIR / filename
    if not path.exists():
        print(f"  [SKIP] {filename} 不存在")
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def list_collections():
    print("知识库概况：")
    total = 0
    for filename, collection in COLLECTION_MAP.items():
        db = load_json(filename)
        chars = sum(len(v) for v in db.values())
        print(f"  {collection:15s}  {len(db):3d} 条  {chars:6,d} 字  ({filename})")
        total += len(db)
    print(f"  {'总计':15s}  {total:3d} 条")


def build(force: bool = False):
    from rag.embedder import encode
    from rag.indexer import build_all_indexes
    from rag.vector_store import collection_exists, get_collection

    if force:
        print("强制重建所有索引...")
        import shutil

        rag_dir = Path(__file__).parent.parent / "rag_index"
        if rag_dir.exists():
            shutil.rmtree(rag_dir)
            print("  已清除旧索引")
        build_all_indexes(force=True)
        print("  索引重建完成")
        return

    # 增量模式
    print("知识库 → ChromaDB 增量索引")
    for filename, collection in COLLECTION_MAP.items():
        db = load_json(filename)
        if not db:
            continue

        if collection_exists(collection):
            col = get_collection(collection)
            existing = col.count()
            if existing >= len(db):
                print(f"  {collection}: {existing} 条（无需更新）")
                continue

        # 需要构建
        print(f"  {collection}: 构建 {len(db)} 条...")
        from rag.indexer import _split_by_paragraphs

        ids = []
        documents = []
        metadatas = []
        for key, content in db.items():
            chunks = _split_by_paragraphs(content)
            for i, chunk in enumerate(chunks):
                chunk_id = f"{key}__{i}"
                ids.append(chunk_id)
                documents.append(chunk)
                metadatas.append({"source": key, "type": collection, "chunk": i})

        if not ids:
            continue

        embeddings = encode(documents)
        col = get_collection(collection)
        col.upsert(ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings)
        print(f"    完成 {len(ids)} 个分块")

    print("索引更新完成")


if __name__ == "__main__":
    if "--list" in sys.argv:
        list_collections()
    else:
        build(force="--force" in sys.argv)
