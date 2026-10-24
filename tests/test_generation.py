# -*- coding: utf-8 -*-
# 答案生成模块测试：prompt 组装（上下文注入 + 引用规则）/ 无型号并列展示指令 /
# 故障代码固定核对提示（代码强制拼接）/ 空检索拒答（不调用 chat）/
# 响应组装（answer + sources 去重、页码取自 metadata）
# chat 一律使用 stub，不依赖真实 API 与网络；测试库与 test_hybrid 口径一致
import hashlib

import numpy as np
import pytest

from src.config import MANUALS_DIR
from src.generation.answer import ERROR_CODE_HINT, NO_CONTEXT_REPLY, answer
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
    # 确定性 stub：同一文本恒得同一向量（与 test_hybrid / test_indexing 口径一致）
    vecs = []
    for t in texts:
        seed = int(hashlib.md5(t.encode("utf-8")).hexdigest(), 16) % (2**32)
        rng = np.random.default_rng(seed)
        vecs.append(rng.standard_normal(STUB_DIM))
    return np.array(vecs, dtype=np.float32)


def identity_rerank(query, documents, top_n):
    # 恒等精排 stub：按原顺序取前 top_n 个下标
    return list(range(min(top_n, len(documents))))


class RecordingChat:
    # chat stub：记录每次收到的 messages，返回固定回复
    def __init__(self, reply="液压压力上限为 16MPa [来源：A-160操作手册 P87]"):
        self.calls: list[list[dict]] = []
        self.reply = reply

    def __call__(self, messages):
        self.calls.append(messages)
        return self.reply


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


def _ask(question, kb, model_set, error_code_set, chat, rerank_fn=identity_rerank):
    return answer(question, kb, stub_embed, rerank_fn, chat,
                  model_set, error_code_set, DEFAULT_ALIASES)


def _prompt_text(messages) -> str:
    # 将全部消息内容拼为一段文本，便于断言 prompt 注入情况
    return "\n".join(m["content"] for m in messages)


def test_prompt_injects_context_and_citation_rules(kb, chunks, model_set,
                                                   error_code_set):
    # prompt 组装：精排 top chunk 的文本与来源（doc/page/model）注入上下文；
    # system 中明确要求引用格式 [来源：手册名 P页码] 且禁止编造页码
    chat = RecordingChat()
    question = "A-160 的液压系统压力上限是多少"
    result = _ask(question, kb, model_set, error_code_set, chat)

    assert len(chat.calls) == 1, "有效检索时应恰好调用一次 chat"
    messages = chat.calls[0]
    assert messages[0]["role"] == "system", "首条消息应为 system 提示词"
    system = messages[0]["content"]
    assert "注塑机" in system, "system 应声明注塑机售后知识库助手角色"
    assert "[来源：" in system, "system 应规定引用格式"
    assert "编造" in system and "页码" in system, "system 应明确禁止编造页码"

    user = _prompt_text(messages[1:])
    # 实际进入 top10 的 chunk（同口径重算），其文本与来源信息应注入 prompt
    top_chunks = search(question, kb, stub_embed, identity_rerank,
                        model_set, error_code_set, DEFAULT_ALIASES)
    assert top_chunks, "该问题应检索到上下文"
    for c in top_chunks:
        meta = c["metadata"]
        assert c["text"] in user, "top chunk 文本应注入上下文"
        assert meta["doc"] in user, "chunk 来源手册名应注入上下文"
        assert f"P{meta['page']}" in user, "chunk 页码应注入上下文"
        assert meta["model"] in user, "chunk 型号应注入上下文"
    assert result["answer"] == chat.reply


def test_no_model_query_requests_parallel_listing(kb, model_set, error_code_set):
    # 无型号查询：prompt 中包含并列展示各型号数值并分别标注来源、不猜型号的指令；
    # 带型号查询则不注入该指令
    chat = RecordingChat()
    _ask("液压系统压力上限是多少", kb, model_set, error_code_set, chat)
    text = _prompt_text(chat.calls[0])
    assert "并列展示" in text, "无型号查询应要求并列展示各型号数值"
    assert "不猜" in text, "无型号查询应要求不猜型号"
    assert "标注" in text and "来源" in text, "并列展示时应分别标注来源"

    chat2 = RecordingChat()
    _ask("A-160 的液压系统压力上限是多少", kb, model_set, error_code_set, chat2)
    assert "并列展示" not in _prompt_text(chat2.calls[0]), \
        "已识别型号时不应注入并列展示指令"


def test_error_code_query_appends_fixed_hint(kb, model_set, error_code_set):
    # 故障代码查询：最终答案固定附带「请与手册原件核对代码字样」，
    # 由代码强制拼接，不依赖 LLM 自觉；非故障代码查询不附加
    reply = "E-102 为液压系统压力异常，请检查液压泵与溢流阀 [来源：故障代码表 P3]"
    chat = RecordingChat(reply=reply)
    result = _ask("E-102 报警怎么处理", kb, model_set, error_code_set, chat)
    assert ERROR_CODE_HINT == "请与手册原件核对代码字样"
    assert result["answer"].endswith(ERROR_CODE_HINT), \
        "核对提示应由代码固定拼接到答案末尾"
    assert reply in result["answer"], "LLM 回答主体应保留"

    chat2 = RecordingChat()
    result2 = _ask("A-160 的液压系统压力上限是多少",
                   kb, model_set, error_code_set, chat2)
    assert ERROR_CODE_HINT not in result2["answer"], \
        "非故障代码查询不应附加核对提示"


def test_empty_retrieval_refuses_without_chat(kb, model_set, error_code_set):
    # 拒答：检索结果为空时不调用 chat，直接返回拒答文案，说明未检索到相关内容
    chat = RecordingChat()

    def empty_rerank(query, documents, top_n):
        return []

    result = answer("完全无关的问题", kb, stub_embed, empty_rerank, chat,
                    model_set, error_code_set, DEFAULT_ALIASES)
    assert chat.calls == [], "检索为空时不应调用 chat"
    assert "未检索到" in result["answer"], "拒答文案应说明未检索到相关内容"
    assert result["answer"] == NO_CONTEXT_REPLY
    assert result["sources"] == []


def test_response_sources_from_used_chunks(kb, model_set, error_code_set):
    # 响应组装：返回 {"answer": str, "sources": [{"doc","page","model"}]}，
    # sources 与实际使用的 top chunk 一致、按 (doc, page, model) 去重、页码取自 metadata
    chat = RecordingChat()
    question = "液压系统压力上限是多少"
    result = _ask(question, kb, model_set, error_code_set, chat)

    assert set(result.keys()) == {"answer", "sources"}
    assert isinstance(result["answer"], str) and result["answer"]
    assert isinstance(result["sources"], list) and result["sources"]

    top_chunks = search(question, kb, stub_embed, identity_rerank,
                        model_set, error_code_set, DEFAULT_ALIASES)
    expected = {(c["metadata"]["doc"], c["metadata"]["page"], c["metadata"]["model"])
                for c in top_chunks}
    actual = {(s["doc"], s["page"], s["model"]) for s in result["sources"]}
    assert actual == expected, "sources 应与实际使用的 top chunk 逐一对应"
    assert len(result["sources"]) == len(actual), "sources 应去重，无重复条目"
    assert all(set(s.keys()) == {"doc", "page", "model"} for s in result["sources"])
    assert all(isinstance(s["page"], int) for s in result["sources"]), \
        "页码应直接取自 metadata，不编造"
