# -*- coding: utf-8 -*-
# 手册解析切块模块：将 Markdown 手册解析为带 metadata 的 chunk 列表
# 切块规则：页标记为硬边界；页内按「文本区 / Markdown 表格」切块，表格整块序列化保留；
# metadata 六字段（chunk_id / doc / model / page / version / status）取自文件头声明与页标记
import re
from pathlib import Path

# 文件头声明：<!-- doc: ... --> <!-- model: ... --> <!-- version: ... --> <!-- status: ... -->
_HEADER_RE = re.compile(r"<!--\s*(doc|model|version|status)\s*:\s*(.+?)\s*-->")
# 页标记：<!-- page: 87 -->
_PAGE_RE = re.compile(r"<!--\s*page\s*:\s*(\d+)\s*-->")


def _id_part(raw: str) -> str:
    # chunk_id 组成部分只保留字母数字，如 A-160 -> A160、V3.0 -> V30
    return re.sub(r"[^0-9A-Za-z]", "", raw)


def _make_chunk(text: str, id_prefix: str, page: int, seq: int,
                doc: str, model: str, version: str, status: str) -> dict:
    return {
        "text": text,
        "metadata": {
            # 版本纳入 chunk_id：同型号新旧版本页码重叠时仍保证全局唯一
            "chunk_id": f"{id_prefix}_p{page}_c{seq}",
            "doc": doc,
            "model": model,
            "page": page,
            "version": version,
            "status": status,
        },
    }


def parse_manual(path: Path) -> list[dict]:
    # 解析单个手册文件，返回 [{"text": str, "metadata": {...}}] 列表
    lines = Path(path).read_text(encoding="utf-8").splitlines()

    # 解析文件头四个声明字段（位于首个页标记之前）
    header = {}
    for line in lines:
        m = _HEADER_RE.match(line.strip())
        if m:
            header[m.group(1)] = m.group(2).strip()
    doc = header["doc"]
    model = header["model"]
    version = header["version"]
    status = header["status"]
    id_prefix = f"{_id_part(model)}_{_id_part(version)}"

    chunks: list[dict] = []
    page: int | None = None     # 当前页码
    seq = 0                     # 当前页内 chunk 序号
    text_buf: list[str] = []    # 文本区缓冲
    table_buf: list[str] = []   # 表格缓冲（非空表示正处于表格中）

    def flush_text() -> None:
        nonlocal seq
        content = "\n".join(text_buf).strip()
        text_buf.clear()
        if content:
            seq += 1
            chunks.append(_make_chunk(content, id_prefix, page, seq,
                                      doc, model, version, status))

    def flush_table() -> None:
        nonlocal seq
        if table_buf:
            seq += 1
            chunks.append(_make_chunk("\n".join(table_buf), id_prefix, page, seq,
                                      doc, model, version, status))
            table_buf.clear()

    for line in lines:
        m = _PAGE_RE.match(line.strip())
        if m:
            # 页标记为硬边界：先收尾上一页未落盘的块
            flush_table()
            flush_text()
            page = int(m.group(1))
            seq = 0
            continue
        if page is None:
            continue  # 跳过文件头与首个页标记之间的内容
        if line.strip().startswith("|"):
            if not table_buf:
                flush_text()  # 表格开始前先落盘前面的文本块
            table_buf.append(line.rstrip())
        else:
            flush_table()     # 非表格行：表格结束（不在表格中时为空操作）
            text_buf.append(line)
    flush_table()
    flush_text()
    return chunks


def parse_all(manuals_dir: Path) -> list[dict]:
    # 解析目录下全部 Markdown 手册，按文件名排序保证全局结果稳定
    chunks: list[dict] = []
    for path in sorted(Path(manuals_dir).glob("*.md")):
        chunks.extend(parse_manual(path))
    return chunks
