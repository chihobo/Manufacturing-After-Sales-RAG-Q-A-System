# -*- coding: utf-8 -*-
# 索引构建与持久化模块：FAISS(IndexFlatIP) 向量索引 + jieba 分词 BM25 索引
# 约定：index.add() 顺序与全局 chunk 列表下标一一对应，向量与原文分开存、靠下标关联；
# 向量 L2 归一化后入 IndexFlatIP，内积即余弦相似度
import json
import os
import pickle
import shutil
import tempfile
from pathlib import Path

import faiss
import jieba
import numpy as np
from rank_bm25 import BM25Okapi

# 产物文件名（固定三件套：向量索引 / 原文 + metadata / BM25 索引）
FAISS_NAME = "kb.faiss"
CHUNKS_NAME = "chunks.json"
BM25_NAME = "bm25.pkl"


def _normalize(vectors: np.ndarray) -> np.ndarray:
    # L2 归一化（原地），使 IndexFlatIP 的内积等价于余弦相似度
    vectors = np.ascontiguousarray(vectors, dtype=np.float32)
    faiss.normalize_L2(vectors)
    return vectors


def _tokenize(texts: list[str]) -> list[list[str]]:
    # jieba 分词语料，供 BM25 构建与检索期 query 对齐口径
    return [list(jieba.cut(t)) for t in texts]


def _faiss_write(index, target: Path) -> None:
    # faiss C++ 层 fopen 按 ANSI 码页解释路径，中文路径直接写会 ENOENT，
    # 先写 ASCII 临时文件再拷贝到目标位置（Python 文件 API 支持 Unicode 路径）
    fd, tmp = tempfile.mkstemp(suffix=".faiss")
    os.close(fd)
    try:
        faiss.write_index(index, tmp)
        shutil.copyfile(tmp, target)
    finally:
        os.remove(tmp)


def _faiss_read(source: Path):
    # 与 _faiss_write 同理：中文路径先拷到 ASCII 临时文件再交给 faiss 读取
    fd, tmp = tempfile.mkstemp(suffix=".faiss")
    os.close(fd)
    try:
        shutil.copyfile(source, tmp)
        return faiss.read_index(tmp)
    finally:
        os.remove(tmp)


def _persist(index, chunks, bm25, tokenized, kb_dir: Path) -> None:
    kb_dir = Path(kb_dir)
    kb_dir.mkdir(parents=True, exist_ok=True)
    _faiss_write(index, kb_dir / FAISS_NAME)
    (kb_dir / CHUNKS_NAME).write_text(
        json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8")
    # BM25 对象不保留原始分词语料，需一并持久化供检索期复用
    with open(kb_dir / BM25_NAME, "wb") as f:
        pickle.dump({"bm25": bm25, "tokenized": tokenized}, f)


def build_index(chunks: list[dict], embed_fn, kb_dir: Path):
    # 全量建库：embedding -> 归一化 -> IndexFlatIP 按下标顺序写入 -> BM25 -> 持久化
    texts = [c["text"] for c in chunks]
    vectors = _normalize(embed_fn(texts))
    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)
    tokenized = _tokenize(texts)
    bm25 = BM25Okapi(tokenized)
    _persist(index, chunks, bm25, tokenized, kb_dir)
    return index, chunks, bm25, tokenized


def load_index(kb_dir: Path):
    # 离线加载既有产物，返回 (faiss_index, chunks, bm25, tokenized_corpus)
    kb_dir = Path(kb_dir)
    index = _faiss_read(kb_dir / FAISS_NAME)
    chunks = json.loads((kb_dir / CHUNKS_NAME).read_text(encoding="utf-8"))
    with open(kb_dir / BM25_NAME, "rb") as f:
        data = pickle.load(f)
    return index, chunks, data["bm25"], data["tokenized"]


def append_chunks(new_chunks: list[dict], embed_fn, kb_dir: Path):
    # 增量入库：FAISS 直接追加向量（旧下标不变）；BM25 的 IDF 依赖全量语料，
    # 追加后基于全量文本重建；三者重新持久化
    index, chunks, _, _ = load_index(kb_dir)
    new_vectors = _normalize(embed_fn([c["text"] for c in new_chunks]))
    index.add(new_vectors)
    chunks.extend(new_chunks)
    tokenized = _tokenize([c["text"] for c in chunks])
    bm25 = BM25Okapi(tokenized)
    _persist(index, chunks, bm25, tokenized, kb_dir)
    return index, chunks, bm25, tokenized
