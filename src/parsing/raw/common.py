# -*- coding: utf-8 -*-
# 解析层公共契约：RawDocMeta（声明头四字段）+ PageContent（单页块列表）
# 块元素为 str（文本段落 / Markdown 表格）或 DrawingRef（插图指引）
# build_markdown 为统一出口，输出符合既有 Markdown 契约的文本：
#   声明头（doc/model/version/status 注释）+ 每页 <!-- page: N --> + 块内容
from dataclasses import dataclass


@dataclass
class RawDocMeta:
    doc: str
    model: str
    version: str
    status: str


@dataclass
class DrawingRef:
    # 插图指引：caption 为图注文本，drawing_no 为图号，path 为原图 POSIX 相对路径
    caption: str
    drawing_no: str
    path: str


@dataclass
class PageContent:
    page_no: int                     # 1 起
    blocks: list[str | DrawingRef]   # 文本段落 / 完整 Markdown 表格 / 插图指引


def build_markdown(meta: RawDocMeta, pages: list[PageContent]) -> str:
    # 输出契约 Markdown：声明头 + 每页 '<!-- page: N -->' + 块内容
    lines = [
        f"<!-- doc: {meta.doc} -->",
        f"<!-- model: {meta.model} -->",
        f"<!-- version: {meta.version} -->",
        f"<!-- status: {meta.status} -->",
        "",
    ]
    for page in pages:
        lines.append(f"<!-- page: {page.page_no} -->")
        for block in page.blocks:
            if isinstance(block, DrawingRef):
                # 插图指引渲染为定格式文本行，作为普通文本段落被下游切块
                lines.append(f"[图] {block.caption}（图号 {block.drawing_no}，"
                             f"原图：{block.path}）")
            else:
                lines.append(block)
            lines.append("")  # 块间空行分隔
    return "\n".join(lines).rstrip() + "\n"
