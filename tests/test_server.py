# -*- coding: utf-8 -*-
# FastAPI 服务测试：/health 返回服务与索引加载状态；/ask 问答闭环
# （answer + sources 字段齐全、页码取自 metadata）；空问题与缺字段返回 422
# 问答依赖（pipeline kwargs）经工厂参数注入 stub，索引用内置手册 + stub embedding
# 在 tmp_path 真建库，chat / embed / rerank 均为 stub，不依赖真实 API 与网络
import hashlib

import numpy as np
import pytest
from fastapi.testclient import TestClient

from src.config import MANUALS_DIR
from src.indexing.builder import build_index, load_index
from src.parsing.parser import parse_all
from src.retrieval.hybrid import KnowledgeBase
from src.retrieval.lexicon import build_error_code_set, build_model_set
from src.server.main import create_app

STUB_DIM = 32


def stub_embed(texts):
    # 确定性 stub：同一文本恒得同一向量（与 test_generation 口径一致）
    vecs = []
    for t in texts:
        seed = int(hashlib.md5(t.encode("utf-8")).hexdigest(), 16) % (2**32)
        rng = np.random.default_rng(seed)
        vecs.append(rng.standard_normal(STUB_DIM))
    return np.array(vecs, dtype=np.float32)


def identity_rerank(query, documents, top_n):
    # 恒等精排 stub：按原顺序取前 top_n 个下标
    return list(range(min(top_n, len(documents))))


def stub_chat(messages):
    # chat stub：返回固定回复，不调用真实 API
    return "液压压力上限为 16MPa [来源：A-160操作手册 P87]"


@pytest.fixture(scope="module")
def pipeline(tmp_path_factory):
    # 组装 answer() 的关键字参数包（与 build_pipeline 同构，外部客户端全部 stub）
    chunks = parse_all(MANUALS_DIR)
    kb_dir = tmp_path_factory.mktemp("kb_server")
    build_index(chunks, stub_embed, kb_dir)
    kb = KnowledgeBase(*load_index(kb_dir))
    return {
        "kb": kb,
        "embed_fn": stub_embed,
        "rerank_fn": identity_rerank,
        "chat_fn": stub_chat,
        "model_set": build_model_set(kb.chunks),
        "error_code_set": build_error_code_set(kb.chunks),
    }


@pytest.fixture(scope="module")
def client(pipeline):
    return TestClient(create_app(pipeline))


def test_health_returns_index_status(client, pipeline):
    # GET /health：200，返回服务状态与已加载 chunk 数，数量与注入的索引一致
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["chunks"] == len(pipeline["kb"].chunks)
    assert body["chunks"] > 0


def test_ask_returns_answer_and_sources(client):
    # POST /ask 合法问题：200，响应 {"answer": str, "sources": [{"doc","page","model"}]}，
    # 字段齐全，sources 非空且页码为 metadata 中的整数页码
    resp = client.post("/ask", json={"question": "A-160 的液压系统压力上限是多少"})
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"answer", "sources"}
    assert isinstance(body["answer"], str) and body["answer"]
    assert isinstance(body["sources"], list) and body["sources"]
    for s in body["sources"]:
        assert set(s.keys()) == {"doc", "page", "model"}
        assert isinstance(s["doc"], str) and s["doc"]
        assert isinstance(s["page"], int)
        assert isinstance(s["model"], str) and s["model"]


def test_ask_empty_question_rejected(client):
    # POST /ask 空问题：空字符串或缺 question 字段均返回 422 参数校验失败
    assert client.post("/ask", json={"question": ""}).status_code == 422
    assert client.post("/ask", json={}).status_code == 422
