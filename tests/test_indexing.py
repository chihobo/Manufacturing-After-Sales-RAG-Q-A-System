# -*- coding: utf-8 -*-
# 索引构建与持久化模块测试：FAISS 下标与 chunk 一一对应、三产物持久化、
# 加载后顺序与检索结果不变、BM25 精确召回、增量入库
# embedding 一律使用确定性 stub（按文本 hash 生成固定维度向量），不依赖真实 API
import hashlib

import jieba
import numpy as np

from src.indexing.builder import append_chunks, build_index, load_index

STUB_DIM = 32


def stub_embed(texts):
    # 确定性 stub：同一文本恒得同一向量，不同文本近乎正交，可支撑检索断言
    vecs = []
    for t in texts:
        seed = int(hashlib.md5(t.encode("utf-8")).hexdigest(), 16) % (2**32)
        rng = np.random.default_rng(seed)
        vecs.append(rng.standard_normal(STUB_DIM))
    return np.array(vecs, dtype=np.float32)


def _norm(vecs):
    # 与建库口径一致：L2 归一化后内积即余弦相似度
    return (vecs / np.linalg.norm(vecs, axis=1, keepdims=True)).astype(np.float32)


def _make_chunk(chunk_id, text, model="A-160", page=1):
    return {
        "text": text,
        "metadata": {
            "chunk_id": chunk_id,
            "doc": "测试手册",
            "model": model,
            "page": page,
            "version": "V3.0",
            "status": "active",
        },
    }


CHUNKS = [
    _make_chunk("A160_p1_c1", "液压系统压力上限为 16MPa，严禁超压运行", page=1),
    _make_chunk("A160_p2_c1", "开机前检查油箱油位，确认在安全线以上", page=2),
    _make_chunk("A160_p3_c1", "E-102 报警表示液压油温度异常，需检查冷却器水路", page=3),
]


def test_build_index_count_and_alignment(tmp_path):
    index, chunks, _, _ = build_index(CHUNKS, stub_embed, tmp_path)
    assert index.ntotal == len(CHUNKS), "索引条数应与 chunk 数一致"
    assert chunks == CHUNKS
    expected = _norm(stub_embed([c["text"] for c in CHUNKS]))
    for i in range(len(CHUNKS)):
        row = index.reconstruct(i)
        assert np.allclose(row, expected[i], atol=1e-5), \
            f"FAISS 第 {i} 行向量应与第 {i} 条 chunk 一一对应"


def test_persist_artifacts_created(tmp_path):
    build_index(CHUNKS, stub_embed, tmp_path)
    assert (tmp_path / "kb.faiss").is_file(), "缺少 kb.faiss"
    assert (tmp_path / "chunks.json").is_file(), "缺少 chunks.json"
    assert (tmp_path / "bm25.pkl").is_file(), "缺少 bm25.pkl"


def test_load_preserves_order_and_search_results(tmp_path):
    index, _, _, _ = build_index(CHUNKS, stub_embed, tmp_path)
    query = _norm(stub_embed([CHUNKS[2]["text"]]))
    scores_before, ids_before = index.search(query, len(CHUNKS))

    index2, chunks2, _, tokenized2 = load_index(tmp_path)
    assert chunks2 == CHUNKS, "加载后 chunk 顺序与内容应与建库时一致"
    assert index2.ntotal == len(CHUNKS)
    assert len(tokenized2) == len(CHUNKS)

    scores_after, ids_after = index2.search(query, len(CHUNKS))
    assert ids_after.tolist() == ids_before.tolist(), "加载后检索下标序列应不变"
    assert np.allclose(scores_before, scores_after, atol=1e-5)
    # 用 chunk 原文向量检索，top1 应命中其自身下标
    _, ids_self = index2.search(query, 1)
    assert ids_self[0][0] == 2


def test_bm25_exact_code_recall(tmp_path):
    build_index(CHUNKS, stub_embed, tmp_path)
    _, chunks, bm25, tokenized = load_index(tmp_path)
    scores = bm25.get_scores(list(jieba.cut("E-102 报警怎么处理")))
    top = int(np.argmax(scores))
    assert chunks[top]["metadata"]["chunk_id"] == "A160_p3_c1", \
        "精确故障代码 E-102 应被 BM25 召回"
    assert "E-102" in chunks[top]["text"]


def test_append_chunks_incremental(tmp_path):
    index_old, _, _, _ = build_index(CHUNKS, stub_embed, tmp_path)
    old_n = index_old.ntotal
    old_rows = [index_old.reconstruct(i) for i in range(old_n)]

    new_chunks = [
        _make_chunk("B200_p1_c1", "B-200 液压系统压力上限为 17.5MPa",
                    model="B-200", page=1),
    ]
    index_new, chunks_new, _, _ = append_chunks(new_chunks, stub_embed, tmp_path)

    assert index_new.ntotal == old_n + len(new_chunks), "追加后索引条数应增加"
    assert chunks_new == CHUNKS + new_chunks
    for i in range(old_n):
        assert np.allclose(index_new.reconstruct(i), old_rows[i], atol=1e-5), \
            f"旧下标 {i} 的向量不应变化"
    # 新 chunk 可被向量检索命中，下标为追加位置
    q = _norm(stub_embed([new_chunks[0]["text"]]))
    _, ids = index_new.search(q, 1)
    assert ids[0][0] == old_n

    # 重新持久化后可加载，且向量与 BM25 均覆盖新 chunk
    index_l, chunks_l, bm25_l, _ = load_index(tmp_path)
    assert index_l.ntotal == old_n + len(new_chunks)
    assert chunks_l == CHUNKS + new_chunks
    _, ids_l = index_l.search(q, 1)
    assert ids_l[0][0] == old_n
    scores = bm25_l.get_scores(list(jieba.cut("B-200 压力上限")))
    top = int(np.argmax(scores))
    assert chunks_l[top]["metadata"]["chunk_id"] == "B200_p1_c1"
