# -*- coding: utf-8 -*-
# 手册解析切块模块测试：覆盖 metadata 完整性、页码抽取、表格整块保留、
# 文本按页切块不跨页、chunk_id 稳定唯一、全目录解析覆盖
import re

from src.config import MANUALS_DIR
from src.parsing.parser import parse_all, parse_manual

A160_V30 = MANUALS_DIR / "A-160操作手册_V3.0.md"
B200 = MANUALS_DIR / "B-200操作手册.md"

METADATA_FIELDS = ("chunk_id", "doc", "model", "page", "version", "status")


def test_parse_single_manual_metadata_complete():
    chunks = parse_manual(A160_V30)
    assert chunks, "解析结果不应为空"
    for chunk in chunks:
        meta = chunk["metadata"]
        for field in METADATA_FIELDS:
            assert field in meta, f"metadata 缺字段 {field}"
            assert meta[field] is not None and meta[field] != "", f"{field} 不应为空"
        assert meta["doc"] == "A-160操作手册"
        assert meta["model"] == "A-160"
        assert meta["version"] == "V3.0"
        assert meta["status"] == "active"
        assert isinstance(chunk["text"], str) and chunk["text"].strip()


def test_page_marker_extraction():
    chunks = parse_manual(A160_V30)
    pages = {c["metadata"]["page"] for c in chunks}
    assert pages == {85, 86, 87, 88, 89, 90, 91, 92}
    for c in chunks:
        assert isinstance(c["metadata"]["page"], int)
    # 技术参数表（表格 chunk）所在页，页码应为 87
    table_chunks = [
        c for c in chunks
        if "液压系统压力上限" in c["text"] and c["text"].lstrip().startswith("|")
    ]
    assert len(table_chunks) == 1 and table_chunks[0]["metadata"]["page"] == 87


def test_table_preserved_as_single_chunk():
    chunks = parse_manual(A160_V30)
    table_chunks = [
        c for c in chunks
        if c["metadata"]["page"] == 87 and c["text"].lstrip().startswith("|")
    ]
    assert len(table_chunks) == 1, "参数表应整块成为一个 chunk"
    text = table_chunks[0]["text"]
    # 表头、分隔行、首行、末行均完整保留
    assert "| 参数名称 | 数值 | 单位 | 备注 |" in text
    assert "| --- | --- | --- | --- |" in text
    assert "| 锁模力 | 1600 | kN | 四拉杆直压式锁模 |" in text
    assert "| 整机重量 | 约 5.2 | t | 不含液压油与模具 |" in text
    # 表头 + 分隔行 + 15 行数据 = 17 行表格行，不得被按行切开
    table_lines = [ln for ln in text.splitlines() if ln.strip().startswith("|")]
    assert len(table_lines) == 17

    # B-200 第 94 页为「文本 + 表格 + 文本」结构：表格同样整块保留且独立成块
    b_chunks = parse_manual(B200)
    p94 = [c for c in b_chunks if c["metadata"]["page"] == 94]
    p94_tables = [c for c in p94 if c["text"].lstrip().startswith("|")]
    assert len(p94_tables) == 1
    t = p94_tables[0]["text"]
    assert "| 异响原因 | 判别特征 | 处理步骤 |" in t
    assert "系统压力设定超限" in t
    assert "排查注意事项" not in t, "表后文本不应并入表格块"


def test_text_chunked_within_page_not_across_pages():
    chunks = parse_manual(A160_V30)
    p88 = [c for c in chunks if c["metadata"]["page"] == 88]
    p89 = [c for c in chunks if c["metadata"]["page"] == 89]
    assert len(p88) == 1 and "合上车间配电柜" in p88[0]["text"]
    assert len(p89) == 1 and "停止自动循环" in p89[0]["text"]
    # 不同页内容不得合并进同一 chunk
    for c in chunks:
        assert not ("合上车间配电柜" in c["text"] and "停止自动循环" in c["text"])


def test_chunk_id_unique_stable_and_wellformed():
    chunks1 = parse_manual(A160_V30)
    chunks2 = parse_manual(A160_V30)
    ids1 = [c["metadata"]["chunk_id"] for c in chunks1]
    ids2 = [c["metadata"]["chunk_id"] for c in chunks2]
    assert ids1 == ids2, "重跑结果应一致"
    assert len(ids1) == len(set(ids1)), "单文件内 chunk_id 不应重复"
    for cid in ids1:
        assert re.fullmatch(r"A160_V30_p\d+_c\d+", cid), f"chunk_id 格式异常: {cid}"
    # 页内序号从 1 开始连续编号
    p87_ids = [c["metadata"]["chunk_id"] for c in chunks1 if c["metadata"]["page"] == 87]
    assert p87_ids == ["A160_V30_p87_c1", "A160_V30_p87_c2"]


def test_parse_all_manuals_full_coverage_unique_ids():
    chunks = parse_all(MANUALS_DIR)
    assert chunks
    pairs = {(c["metadata"]["doc"], c["metadata"]["version"]) for c in chunks}
    assert pairs == {
        ("A-160操作手册", "V2.1"),
        ("A-160操作手册", "V3.0"),
        ("B-200操作手册", "V3.0"),
        ("C-320操作手册", "V3.0"),
        ("故障代码表", "V3.0"),
    }, "5 个手册文件应全部被覆盖"
    ids = [c["metadata"]["chunk_id"] for c in chunks]
    assert len(ids) == len(set(ids)), "全局 chunk_id 不应重复"
