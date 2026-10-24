# -*- coding: utf-8 -*-
# 混合检索链路：型号 Pre-filtering（0/1/多型号三分支）→ 向量 top_recall 与
# BM25 top_recall 双路召回 → 合并去重 → rerank 精排取 top_final
# Pre-filtering 用 numpy 掩码矩阵乘实现（等价 FAISS IDSelectorBitmap）：
# 向量与原文靠全局下标关联，候选名单即下标子集，子集矩阵乘后取 top
# 融合不做手工权重调参，排序由 rerank 裁决
from typing import NamedTuple

import faiss
import jieba
import numpy as np
from rank_bm25 import BM25Okapi

from src.retrieval.lexicon import DEFAULT_ALIASES, extract_models


class KnowledgeBase(NamedTuple):
    # load_index 返回的四元组封装：向量索引 / chunk 列表 / BM25 索引 / 分词语料
    index: faiss.IndexFlatIP
    chunks: list[dict]
    bm25: BM25Okapi
    tokenized: list[list[str]]


def _candidate_ids(chunks: list[dict], models: list[str]) -> list[int]:
    # 候选名单：0 个型号=全库；1 个=该型号 chunk 下标；多个=并集
    # 名单内默认排除 status=archived 的 chunk（多版本命中时 active 优先）
    wanted = set(models)
    return [
        i for i, c in enumerate(chunks)
        if c["metadata"]["status"] != "archived"
        and (not wanted or c["metadata"]["model"] in wanted)
    ]


def _vector_recall(kb: KnowledgeBase, q_vec: np.ndarray,
                   candidate_ids: list[int], top_recall: int) -> list[int]:
    # 向量路：q_vec（已归一化）与候选子集矩阵乘，内积即余弦相似度，取 top_recall
    k = min(top_recall, len(candidate_ids))
    mat = np.vstack([kb.index.reconstruct(i) for i in candidate_ids])
    scores = mat @ q_vec[0]
    order = np.argsort(-scores)[:k]
    return [candidate_ids[j] for j in order]


def _bm25_recall(kb: KnowledgeBase, query: str,
                 candidate_ids: list[int], top_recall: int) -> list[int]:
    # BM25 路：jieba 分词后仅在候选名单内打分，取 top_recall
    k = min(top_recall, len(candidate_ids))
    scores = kb.bm25.get_scores(list(jieba.cut(query)))
    return sorted(candidate_ids, key=lambda i: scores[i], reverse=True)[:k]


def search(query: str, kb: KnowledgeBase, embed_fn, rerank_fn,
           model_set: set[str], error_code_set: set[str],
           aliases: dict | None = None,
           top_recall: int = 20, top_final: int = 10) -> list[dict]:
    # 混合检索主入口：返回带 metadata 的 chunk 列表（按 rerank 裁决顺序）
    aliases = DEFAULT_ALIASES if aliases is None else aliases
    models = extract_models(query, model_set, aliases, error_code_set)
    candidate_ids = _candidate_ids(kb.chunks, models)

    # 向量路：query 向量 L2 归一化，与建库口径一致
    q_vec = np.ascontiguousarray(embed_fn([query]), dtype=np.float32)
    faiss.normalize_L2(q_vec)
    vec_hits = _vector_recall(kb, q_vec, candidate_ids, top_recall)
    bm25_hits = _bm25_recall(kb, query, candidate_ids, top_recall)

    # 合并去重（保序），候选文本交 rerank 精排，rerank 返回原文档下标序列
    merged = list(dict.fromkeys(vec_hits + bm25_hits))
    documents = [kb.chunks[i]["text"] for i in merged]
    order = rerank_fn(query, documents, top_final)
    return [kb.chunks[merged[j]] for j in order]
