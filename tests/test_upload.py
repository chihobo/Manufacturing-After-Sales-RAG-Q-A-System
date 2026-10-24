# -*- coding: utf-8 -*-
# 手册上传辅助逻辑测试：无声明时补写、有冲突声明时以表单为准替换、
# 补写后的文件经 parse_manual 解析出的 metadata 与表单填写一致
from src.parsing.parser import parse_manual
from src.ui.upload_utils import apply_header_declarations

SAMPLE_BODY = """<!-- page: 1 -->
# X-100 注塑机操作手册

本手册为 X-100 型注塑机随机资料。

<!-- page: 2 -->
# 技术参数表

| 参数名称 | 数值 | 单位 |
| --- | --- | --- |
| 液压系统压力上限 | 15 | MPa |
"""

FORM = {"doc": "X-100操作手册", "model": "X-100",
        "version": "V1.0", "status": "active"}


def test_apply_declarations_when_absent():
    # 文件内原本没有任何声明：应在头部按固定顺序补写四个声明
    result = apply_header_declarations(SAMPLE_BODY, **FORM)
    lines = result.splitlines()
    assert lines[0] == "<!-- doc: X-100操作手册 -->"
    assert lines[1] == "<!-- model: X-100 -->"
    assert lines[2] == "<!-- version: V1.0 -->"
    assert lines[3] == "<!-- status: active -->"
    # 原正文内容不丢失
    assert "<!-- page: 1 -->" in result
    assert "液压系统压力上限" in result


def test_apply_declarations_overrides_conflicting():
    # 文件内已有与表单冲突的声明：一律以表单为准替换，旧声明行不得残留
    conflicting = (
        "<!-- doc: 旧手册名 -->\n"
        "<!-- model: Y-999 -->\n"
        "<!-- version: V9.9 -->\n"
        "<!-- status: archived -->\n"
        "\n" + SAMPLE_BODY
    )
    result = apply_header_declarations(conflicting, **FORM)
    assert "Y-999" not in result
    assert "旧手册名" not in result
    assert "V9.9" not in result
    lines = result.splitlines()
    assert lines[0] == "<!-- doc: X-100操作手册 -->"
    assert lines[1] == "<!-- model: X-100 -->"
    assert lines[2] == "<!-- version: V1.0 -->"
    assert lines[3] == "<!-- status: active -->"


def test_parsed_metadata_matches_form(tmp_path):
    # 补写声明后的文件落盘解析，每条 chunk 的 metadata 应与表单填写一致
    result = apply_header_declarations(SAMPLE_BODY, **FORM)
    path = tmp_path / "X-100操作手册_V1.0.md"
    path.write_text(result, encoding="utf-8")

    chunks = parse_manual(path)
    assert chunks, "解析结果不应为空"
    for chunk in chunks:
        meta = chunk["metadata"]
        assert meta["doc"] == "X-100操作手册"
        assert meta["model"] == "X-100"
        assert meta["version"] == "V1.0"
        assert meta["status"] == "active"
