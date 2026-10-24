# -*- coding: utf-8 -*-
# 电子版 PDF 解析：PyMuPDF 按页抽取
#   - find_tables 识别带框线表格并转为 Markdown 表格
#   - 表格区域内的文本块不再重复进正文块
#   - get_image_info 枚举嵌入图像：显示面积 >= 页面 4% 的抽取存 PNG 并生成 DrawingRef，
#     小于阈值的装饰图丢弃；caption 取图下方最近且以"图"开头的文本块
#   - 文本块、表格与插图指引按 y 坐标混排，保持版面阅读顺序
import re
from pathlib import Path

import pymupdf

from .common import DrawingRef, RawDocMeta, PageContent, build_markdown

# 插图面积阈值：显示面积小于页面面积 4% 视为装饰图，直接丢弃
_MIN_AREA_RATIO = 0.04
# caption 关联阈值：图下方文本块顶边与图底边的最大 y 距离（pt）
_CAPTION_MAX_DIST = 40.0
# caption 中图号提取：如 "图 1-1 液压系统动力单元示意图" -> "1-1"
_DRAWING_NO_RE = re.compile(r"图\s*(\S+)")


def _cell_text(cell: str | None) -> str:
    # 单元格文本清洗：换行折叠为空格，去掉会破坏 Markdown 表格的竖线
    if not cell:
        return ""
    return " ".join(cell.split()).replace("|", " ").strip()


def _table_to_markdown(rows: list[list[str | None]]) -> str:
    # find_tables 抽取结果转 Markdown 表格（首行表头 + 分隔行 + 数据行）
    grid = [[_cell_text(c) for c in row] for row in rows]
    col_count = max(len(row) for row in grid)
    # 列数不齐的行右侧补空，保证 Markdown 表格规整
    grid = [row + [""] * (col_count - len(row)) for row in grid]
    lines = ["| " + " | ".join(grid[0]) + " |",
             "| " + " | ".join(["---"] * col_count) + " |"]
    for row in grid[1:]:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def convert_pdf(pdf_path: Path, meta: RawDocMeta, drawings_dir: Path) -> str:
    doc = pymupdf.open(str(pdf_path))
    pages: list[PageContent] = []
    drawings_dir.mkdir(parents=True, exist_ok=True)
    for page_no, page in enumerate(doc, start=1):
        # 表格：记录 (y0, markdown) 与区域矩形
        table_items: list[tuple[float, str]] = []
        table_rects: list[pymupdf.Rect] = []
        for tab in page.find_tables().tables:
            table_items.append((tab.bbox[1], _table_to_markdown(tab.extract())))
            table_rects.append(pymupdf.Rect(tab.bbox))

        # 文本块：跳过与表格区域相交的块，避免表格文本重复进正文
        text_items: list[tuple[float, str]] = []
        caption_candidates: list[tuple[pymupdf.Rect, str]] = []
        for block in page.get_text("blocks"):
            x0, y0, x1, y1, text = block[:5]
            rect = pymupdf.Rect(x0, y0, x1, y1)
            if any(rect.intersects(r) for r in table_rects):
                continue
            cleaned = " ".join(text.split())
            if cleaned:
                text_items.append((y0, cleaned))
                caption_candidates.append((rect, cleaned))

        # 插图：面积过滤装饰图，合格图存 PNG 并生成 DrawingRef
        # xrefs=True 使返回项带 xref 键，用于按引用抽取嵌入原图
        drawing_items: list[tuple[float, DrawingRef]] = []
        page_area = page.rect.get_area()
        kept = 0  # 页内被抽取图计数，用于无 caption 时的兜底命名
        for info in page.get_image_info(xrefs=True):
            img_rect = pymupdf.Rect(info["bbox"])
            if img_rect.get_area() < page_area * _MIN_AREA_RATIO:
                continue  # 装饰小图：丢弃
            kept += 1
            # caption：图下方最近（y 距离阈值内）且以"图"开头的文本块
            caption = ""
            best_dist = _CAPTION_MAX_DIST
            for cand_rect, cand_text in caption_candidates:
                dist = cand_rect.y0 - img_rect.y1
                if 0 <= dist <= best_dist and cand_text.startswith("图"):
                    caption = cand_text
                    best_dist = dist
            # 图号：从 caption 提取；提取不到按页码与页内序号命名
            m = _DRAWING_NO_RE.search(caption)
            drawing_no = m.group(1) if m else f"p{page_no}-{kept}"
            if not caption:
                caption = drawing_no
            # 抽取嵌入原图存 PNG（CMYK 等多通道色彩空间先转 RGB）
            pix = pymupdf.Pixmap(doc, info["xref"])
            if pix.colorspace and pix.colorspace.n > 3:
                pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
            filename = f"{drawing_no}.png"
            pix.save(str(drawings_dir / filename))
            # 产物 Markdown 与原图同处 out_dir 下，路径按 out_dir 相对引用
            rel_path = (Path(drawings_dir.name) / filename).as_posix()
            drawing_items.append((img_rect.y0, DrawingRef(
                caption=caption, drawing_no=drawing_no, path=rel_path)))

        # 文本块、表格与插图指引按 y 坐标混排
        blocks = [item[1] for item in sorted(text_items + table_items + drawing_items,
                                             key=lambda it: it[0])]
        pages.append(PageContent(page_no=page_no, blocks=blocks))
    doc.close()
    return build_markdown(meta, pages)
