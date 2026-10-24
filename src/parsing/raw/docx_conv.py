# -*- coding: utf-8 -*-
# Word DOCX 解析：python-docx 按 body 元素顺序遍历
#   - 段落 -> 文本块（段落内显式分页符 WD_BREAK.PAGE 映射为页码递增）
#   - 表格 -> Markdown 表格
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

from .common import RawDocMeta, PageContent, build_markdown


def _iter_block_items(document):
    # 按文档顺序产出 body 下的段落与表格
    for child in document.element.body.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, document)
        elif child.tag == qn("w:tbl"):
            yield Table(child, document)


def _split_by_page_breaks(para: Paragraph) -> list[str]:
    # 按显式分页符把段落文本切成多段：len > 1 时表示发生了 len-1 次分页
    parts: list[list[str]] = [[]]
    for run in para.runs:
        for node in run._element:
            if node.tag == qn("w:br") and node.get(qn("w:type")) == "page":
                parts.append([])
            elif node.tag == qn("w:t"):
                parts[-1].append(node.text or "")
    return ["".join(p).strip() for p in parts]


def _table_to_markdown(table: Table) -> str:
    # docx 表格转 Markdown 表格（首行表头 + 分隔行 + 数据行）
    lines: list[str] = []
    for i, row in enumerate(table.rows):
        cells = [" ".join(cell.text.split()).replace("|", " ").strip()
                 for cell in row.cells]
        lines.append("| " + " | ".join(cells) + " |")
        if i == 0:
            lines.append("| " + " | ".join(["---"] * len(cells)) + " |")
    return "\n".join(lines)


def convert_docx(docx_path: Path, meta: RawDocMeta) -> str:
    document = Document(str(docx_path))
    pages: list[PageContent] = [PageContent(page_no=1, blocks=[])]
    for block in _iter_block_items(document):
        if isinstance(block, Paragraph):
            texts = _split_by_page_breaks(block)
            for i, text in enumerate(texts):
                if i > 0:
                    # 分页符：新起一页，页码随列表长度递增
                    pages.append(PageContent(page_no=len(pages) + 1, blocks=[]))
                if text:
                    pages[-1].blocks.append(text)
        else:
            pages[-1].blocks.append(_table_to_markdown(block))
    return build_markdown(meta, pages)
