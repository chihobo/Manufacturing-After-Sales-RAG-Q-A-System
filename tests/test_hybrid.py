# -*- coding: utf-8 -*-
# 混合检索与 Pre-filtering 测试：单型号限定 / active 优先 / 无型号全库 /
# 多型号并集 / 故障代码不触发型号过滤 / 双路合并去重 / rerank 精排取 top10
# embedding 与 rerank 一律使用确定性 stub，不依赖真实 API 与网络；
# 测试数据用解析器 parse_all 解析真实示例手册后建库到 tmp_path
import hashlib

import numpy as np
import pytest

from src.config import MANUALS_DIR
from src.indexing.builder import build_index, load_index
from src.parsing.parser import parse_all
from src.retrieval.hybrid import KnowledgeBase, search
from src.retrieval.lexicon import (
    DEFAULT_ALIASES,
    build_error_code_set,
    build_model_set,
)

STUB_DIM = 32


def stub_embed(texts):
    # 确定性 stub：同一文本恒得同一向量（与 test_indexing 口径一致）
    vecs = []
    for t in texts:
        seed = int(hashlib.md5(t.encode("utf-8")).hexdigest(), 16) % (2**32)
        rng = np.random.default_rng(seed)
        vecs.append(rng.standard_normal(STUB_DIM))
    return np.array(vecs, dtype=np.float32)


class RecordingRerank:
    # 恒等精排 stub：记录每次收到的候选文本，按原顺序取前 top_n 个下标，
    # 便于断言「进入 rerank 的候选构成」（即 Pre-filtering 与双路合并的结果）
    def __init__(self):
        self.captured: list[list[str]] = []

    def __call__(self, query, documents, top_n):
        self.captured.append(list(documents))
        return list(range(min(top_n, len(documents))))


@pytest.fixture(scope="module")
def chunks():
    return parse_all(MANUALS_DIR)


@pytest.fixture(scope="module")
def kb(tmp_path_factory, chunks):
    kb_dir = tmp_path_factory.mktemp("kb")
    build_index(chunks, stub_embed, kb_dir)
    return KnowledgeBase(*load_index(kb_dir))


@pytest.fixture(scope="module")
def model_set(chunks):
    return build_model_set(chunks)


@pytest.fixture(scope="module")
def error_code_set(chunks):
    return build_error_code_set(chunks)


def _candidates_of(rerank: RecordingRerank, kb: KnowledgeBase) -> list[dict]:
    # 将 rerank 收到的候选文本映射回 chunk
    # 注意：不同手册存在文本完全相同的 chunk（如「# 技术参数表」标题块），
    # 不能按文本内容映射；rerank 收到的是 kb.chunks 中同一 str 对象，按对象身份映射
    by_obj = {id(c["text"]): c for c in kb.chunks}
    return [by_obj[id(t)] for t in rerank.captured[0]]


def test_single_model_prefiltering(kb, chunks, model_set, error_code_set):
    # 单型号提问：召回候选全部来自 model=A-160，B-200 / C-320 不进入候选
    rerank = RecordingRerank()
    results = search("A-160 的液压系统压力上限是多少", kb, stub_embed, rerank,
                     model_set, error_code_set, DEFAULT_ALIASES)
    candidates = _candidates_of(rerank, kb)
    assert candidates, "应有候选进入 rerank"
    assert {c["metadata"]["model"] for c in candidates} == {"A-160"}, \
        "单型号提问时候选应全部来自 A-160"
    assert all(c["metadata"]["model"] == "A-160" for c in results)


def test_active_preferred_over_archived(kb, chunks, model_set, error_code_set):
    # active 优先：候选中不含 status=archived，A-160 命中 V3.0 而非 V2.1
    rerank = RecordingRerank()
    search("A-160 的液压系统压力上限是多少", kb, stub_embed, rerank,
           model_set, error_code_set, DEFAULT_ALIASES)
    candidates = _candidates_of(rerank, kb)
    assert all(c["metadata"]["status"] == "active" for c in candidates), \
        "归档（archived）版本不应进入候选"
    ids = {c["metadata"]["chunk_id"] for c in candidates}
    assert any(cid.startswith("A160_V30") for cid in ids), "应命中 V3.0 的 chunk"
    assert not any(cid.startswith("A160_V21") for cid in ids), \
        "V2.1 为归档版本，不应进入候选"


def test_no_model_searches_whole_corpus(kb, chunks, model_set, error_code_set):
    # 无型号全库检索：不提型号时不过滤，多型号 chunk 均可进入候选
    rerank = RecordingRerank()
    search("液压系统压力上限是多少", kb, stub_embed, rerank,
           model_set, error_code_set, DEFAULT_ALIASES)
    candidates = _candidates_of(rerank, kb)
    models = {c["metadata"]["model"] for c in candidates}
    assert len(models) >= 2, "不提型号时不做型号过滤，候选应覆盖多个型号"


def test_multi_model_union(kb, chunks, model_set, error_code_set):
    # 多型号并集：候选只含 A-160 与 B-200，C-320 不进入候选
    rerank = RecordingRerank()
    search("A-160 和 B-200 的锁模力差多少", kb, stub_embed, rerank,
           model_set, error_code_set, DEFAULT_ALIASES)
    candidates = _candidates_of(rerank, kb)
    models = {c["metadata"]["model"] for c in candidates}
    assert models == {"A-160", "B-200"}, \
        "多型号提问时候选应为这两个型号 chunk 的并集"


def test_error_code_query_not_model_filtered(kb, chunks, model_set,
                                             error_code_set):
    # 故障代码查询：E-102 属故障代码词表，不触发型号过滤；
    # 候选含故障代码表 chunk（model=COMMON），且候选覆盖多个型号
    rerank = RecordingRerank()
    search("E-102 报警怎么处理", kb, stub_embed, rerank,
           model_set, error_code_set, DEFAULT_ALIASES)
    candidates = _candidates_of(rerank, kb)
    assert any(c["metadata"]["model"] == "COMMON" and "E-102" in c["text"]
               for c in candidates), "候选应包含故障代码表中 E-102 所在 chunk"
    models = {c["metadata"]["model"] for c in candidates}
    assert len(models) >= 2, "故障代码查询不应按型号过滤"


def test_dual_recall_merge_dedup(kb, chunks, model_set, error_code_set):
    # 双路合并去重：向量 top20 与 BM25 top20 有重叠时，进入 rerank 的候选无重复
    rerank = RecordingRerank()
    search("液压系统压力上限是多少", kb, stub_embed, rerank,
           model_set, error_code_set, DEFAULT_ALIASES)
    documents = rerank.captured[0]
    # 语料中存在文本相同的 chunk，须按对象身份判重：同一下标重复进入候选
    # 时对应同一 str 对象，不同 chunk 即使文本相同也是不同对象
    assert len(documents) == len({id(d) for d in documents}), \
        "双路合并后的候选不得有重复下标"
    assert len(documents) <= 40, "候选规模上限为向量 top20 与 BM25 top20 之和"


def test_rerank_decides_order_and_top10(kb, model_set, error_code_set):
    # rerank 精排取 top10：stub 将候选逆序返回，
    # 最终结果必须完全按 rerank 给出的下标顺序，且最多 10 条
    captured: dict = {}

    def reverse_rerank(query, documents, top_n):
        captured["docs"] = list(documents)
        n = min(top_n, len(documents))
        return [n - 1 - i for i in range(n)]

    results = search("液压系统压力上限是多少", kb, stub_embed, reverse_rerank,
                     model_set, error_code_set, DEFAULT_ALIASES)
    docs = captured["docs"]
    n = min(10, len(docs))
    expected_texts = [docs[n - 1 - i] for i in range(n)]
    assert [r["text"] for r in results] == expected_texts, \
        "最终结果顺序应由 rerank 裁决"
    assert len(results) <= 10, "最终结果最多 10 条"
    assert all("metadata" in r for r in results), "返回 chunk 应携带 metadata"
