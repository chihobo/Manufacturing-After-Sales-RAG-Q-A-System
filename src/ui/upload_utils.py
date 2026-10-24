# -*- coding: utf-8 -*-
# 手册上传辅助逻辑：文件头声明注释的补写与替换（不依赖 streamlit，可独立测试）
# 规则：表单填写的 doc / model / version / status 以四个 <!-- key: value --> 注释
# 固定在内容头部；若文件内已有同名字段声明（无论位置），一律以表单为准替换
import re

# 匹配整行的头部声明注释（允许前导空白），四个字段名与 parser._HEADER_RE 对齐
_DECL_LINE_RE = re.compile(
    r"^\s*<!--\s*(doc|model|version|status)\s*:.*?-->\s*$")


def apply_header_declarations(content: str, doc: str, model: str,
                              version: str, status: str) -> str:
    # 剔除文件中已有的四个字段声明行（表单为准），再在内容头部按固定顺序补写
    kept = [ln for ln in content.splitlines() if not _DECL_LINE_RE.match(ln)]
    # 去掉剔除声明后头部残留的空行，保证声明紧贴文件开头
    while kept and not kept[0].strip():
        kept.pop(0)
    header = [
        f"<!-- doc: {doc} -->",
        f"<!-- model: {model} -->",
        f"<!-- version: {version} -->",
        f"<!-- status: {status} -->",
        "",
    ]
    return "\n".join(header + kept) + "\n"
