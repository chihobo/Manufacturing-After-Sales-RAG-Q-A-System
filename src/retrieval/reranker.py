# -*- coding: utf-8 -*-
# rerank 客户端：OpenAI 兼容 rerank 端点（POST {base_url}/rerank，
# 请求体 model/query/documents/top_n，兼容 Jina / DashScope 响应格式）
# 与检索解耦：hybrid.search 通过 rerank_fn 参数注入，测试中以 stub 替代
import httpx

from src.config import OPENAI_API_KEY, OPENAI_BASE_URL, RERANK_MODEL

_TIMEOUT = 30.0


def rerank(query: str, documents: list[str], top_n: int) -> list[int]:
    # 调用 rerank 端点精排，返回按相关性排序的原文档下标
    resp = httpx.post(
        f"{OPENAI_BASE_URL}/rerank",
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
        json={
            "model": RERANK_MODEL,
            "query": query,
            "documents": documents,
            "top_n": top_n,
        },
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    # Jina / DashScope 响应均为 results 列表，元素含 index 与 relevance_score，已按分降序
    results = resp.json()["results"]
    return [item["index"] for item in results]
