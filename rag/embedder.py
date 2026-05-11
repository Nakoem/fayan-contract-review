"""
Embedding 封装。使用 DashScope text-embedding API（通过 OpenAI 兼容 SDK）。
"""

from llm_client import LLMClient

_embedding_model = "text-embedding-v1"
_client: LLMClient | None = None


def _get_client() -> LLMClient:
    global _client
    if _client is None:
        import os
        from dotenv import load_dotenv

        load_dotenv()
        api_key = os.getenv("DASHSCOPE_API_KEY", "")
        _client = LLMClient(api_key=api_key, model=_embedding_model)
    return _client


def encode(texts: list[str]) -> list[list[float]]:
    """将文本列表编码为向量（批量）。"""
    client = _get_client()
    embeddings = []
    # DashScope embedding 每次最多 25 条
    batch_size = 25
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        resp = client.client.embeddings.create(
            model=_embedding_model,
            input=batch,
        )
        embeddings.extend([d.embedding for d in resp.data])
    return embeddings


def encode_query(query: str) -> list[float]:
    """将查询文本编码为向量。"""
    return encode([query])[0]
