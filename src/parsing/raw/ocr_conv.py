# -*- coding: utf-8 -*-
# 扫描件 OCR 解析：RapidOCR 逐图识别，一张图对应一页（页码按传入顺序）
# 识别结果按 y 坐标聚行、行内按 x 排序拼接，输出按行文本块
from pathlib import Path

from rapidocr_onnxruntime import RapidOCR

from .common import RawDocMeta, PageContent, build_markdown


def _cluster_lines(result: list) -> list[str]:
    # OCR 结果聚行：每项为 [box, text, score]，box 为四点坐标
    items = []
    for box, text, _score in result:
        xs = [pt[0] for pt in box]
        ys = [pt[1] for pt in box]
        items.append({
            "x0": min(xs),
            "y_center": (min(ys) + max(ys)) / 2,
            "height": max(ys) - min(ys),
            "text": text.strip(),
        })
    items.sort(key=lambda it: it["y_center"])

    # y 中心距小于行高阈值（平均行高的一半）则视为同一行
    if not items:
        return []
    avg_h = sum(it["height"] for it in items) / len(items)
    threshold = avg_h / 2

    lines: list[list[dict]] = []
    for item in items:
        if lines and abs(item["y_center"] - lines[-1][0]["y_center"]) <= threshold:
            lines[-1].append(item)
        else:
            lines.append([item])

    # 行内按 x 排序拼接为一句文本
    out = []
    for line in lines:
        line.sort(key=lambda it: it["x0"])
        out.append(" ".join(it["text"] for it in line if it["text"]))
    return [t for t in out if t]


def convert_images(image_paths: list[Path], meta: RawDocMeta) -> str:
    engine = RapidOCR()
    pages: list[PageContent] = []
    for page_no, path in enumerate(image_paths, start=1):
        result, _elapsed = engine(str(path))
        lines = _cluster_lines(result or [])
        pages.append(PageContent(page_no=page_no, blocks=lines))
    return build_markdown(meta, pages)
