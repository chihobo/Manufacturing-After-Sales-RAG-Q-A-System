# -*- coding: utf-8 -*-
# 答案生成模块：编排「识别 -> search -> 组装 prompt -> chat -> 固定提示 -> 响应」
# chat 客户端走 OpenAI 兼容 API（模型名取 src.config.CHAT_MODEL）；
# embed / rerank / chat 均经参数注入，测试中以 stub 替代，不依赖真实 API 与网络
from pathlib import Path

from openai import OpenAI

from src.config import CHAT_MODEL, KB_DIR, OPENAI_API_KEY, OPENAI_BASE_URL
from src.generation.prompts import build_messages
from src.indexing.builder import load_index
from src.indexing.embedder import embed_texts
from src.retrieval.hybrid import KnowledgeBase, search
from src.retrieval.lexicon import (
    DEFAULT_ALIASES,
    build_error_code_set,
    build_model_set,
    extract_error_codes,
    extract_models,
)
from src.retrieval.reranker import rerank

# 检索为空时的固定拒答文案：不调用 LLM，直接返回
NO_CONTEXT_REPLY = (
    "抱歉，现有手册内容中未检索到与您问题相关的内容，"
    "请补充设备型号或更换问法后重试。"
)
# 故障代码类答案的固定核对提示：由代码强制拼接，不依赖 LLM 自觉
ERROR_CODE_HINT = "请与手册原件核对代码字样"


def chat(messages: list[dict]) -> str:
    # 调用 OpenAI 兼容 chat 接口，返回助手回复文本
    client = OpenAI(base_url=OPENAI_BASE_URL, api_key=OPENAI_API_KEY)
    resp = client.chat.completions.create(model=CHAT_MODEL, messages=messages)
    return resp.choices[0].message.content


def _build_sources(chunks: list[dict]) -> list[dict]:
    # 来源列表：来自实际使用的 top chunk，按 (doc, page, model) 去重保序，
    # 页码直接取自 metadata，不编造
    seen: set[tuple] = set()
    sources: list[dict] = []
    for c in chunks:
        meta = c["metadata"]
        key = (meta["doc"], meta["page"], meta["model"])
        if key not in seen:
            seen.add(key)
            sources.append(
                {"doc": meta["doc"], "page": meta["page"], "model": meta["model"]})
    return sources


def answer(question: str, kb: KnowledgeBase, embed_fn, rerank_fn, chat_fn,
           model_set: set[str], error_code_set: set[str],
           aliases: dict | None = None) -> dict:
    # 问答主入口：型号/故障代码识别 -> 混合检索 -> prompt -> chat -> 响应组装
    aliases = DEFAULT_ALIASES if aliases is None else aliases
    models = extract_models(question, model_set, aliases, error_code_set)
    chunks = search(question, kb, embed_fn, rerank_fn,
                    model_set, error_code_set, aliases)

    # 检索为空：拒答，不调用 chat
    if not chunks:
        return {"answer": NO_CONTEXT_REPLY, "sources": []}

    messages = build_messages(question, chunks, models)
    text = chat_fn(messages)

    # 故障代码查询：固定拼接核对提示，由代码保证，不依赖 LLM 自觉
    if extract_error_codes(question, error_code_set):
        text = f"{text}\n\n{ERROR_CODE_HINT}"

    return {"answer": text, "sources": _build_sources(chunks)}


def build_pipeline(kb_dir: Path = KB_DIR) -> dict:
    # 高层入口：从 config 加载建库产物与默认 embed/rerank/chat 客户端及词表，
    # 返回 answer() 的关键字参数包，供 FastAPI / Streamlit / 评估脚本复用：
    #     pipeline = build_pipeline()
    #     result = answer(question, **pipeline)
    kb = KnowledgeBase(*load_index(kb_dir))
    return {
        "kb": kb,
        "embed_fn": embed_texts,
        "rerank_fn": rerank,
        "chat_fn": chat,
        "model_set": build_model_set(kb.chunks),
        "error_code_set": build_error_code_set(kb.chunks),
    }
