# -*- coding: utf-8 -*-
# 原始手册解析测试：覆盖 spec/parse-raw-manuals 与 pdf-image-ref 全部 Scenario
#   - 生成确定性：重跑生成函数，三类原始件哈希不变
#   - build_markdown 契约：声明头/页标记与 parser.py 正则精确匹配
#   - PDF 解析：声明头四字段、页标记数==PDF 页数、含 Markdown 表格与 18MPa，可被 parse_manual 切块
#   - PDF 插图：大图抽图存 PNG 并生成 [图] 指引行，装饰小图被面积阈值过滤，[图] 行切块页码正确
#   - DOCX 解析：页标记数==分页符数+1、表格完整、含 2000 小时，可被 parse_manual 切块
#   - OCR 解析：页标记数==PNG 数、每页关键词可检出（宽松断言），可被 parse_manual 切块
#   - CLI：三类输入各调一次，产物存在且声明头与参数一致
# OCR 较慢，OCR 相关断言共用一个 module 级 fixture，只识别一次
import hashlib
import re
import subprocess
import sys
from pathlib import Path

import pymupdf
import pytest

from scripts.gen_raw_data import RAW_DIR, gen_docx, gen_pdf, gen_scan_images
from src.parsing.parser import _HEADER_RE, _PAGE_RE, parse_manual
from src.parsing.raw.common import PageContent, RawDocMeta, build_markdown
from src.parsing.raw.docx_conv import convert_docx
from src.parsing.raw.ocr_conv import convert_images
from src.parsing.raw.pdf_conv import convert_pdf

ROOT = Path(__file__).resolve().parents[1]
PDF_PATH = RAW_DIR / "D-300操作手册.pdf"
DOCX_PATH = RAW_DIR / "E-450保养手册.docx"
SCAN_DIR = RAW_DIR / "维修记录单_scan"

PDF_META = RawDocMeta(doc="D-300操作手册", model="D-300", version="V1.0", status="active")
DOCX_META = RawDocMeta(doc="E-450保养手册", model="E-450", version="V1.0", status="active")
SCAN_META = RawDocMeta(doc="维修记录单", model="A-160", version="V1.0", status="active")


def _assert_header(md: str, meta: RawDocMeta) -> None:
    # 声明头四字段应位于文本开头，逐行精确匹配
    lines = md.splitlines()
    assert lines[0] == f"<!-- doc: {meta.doc} -->"
    assert lines[1] == f"<!-- model: {meta.model} -->"
    assert lines[2] == f"<!-- version: {meta.version} -->"
    assert lines[3] == f"<!-- status: {meta.status} -->"


def _page_markers(md: str) -> list[int]:
    # 抽取全部页标记页码（整行匹配，与 parser 口径一致）
    return [int(m.group(1)) for ln in md.splitlines()
            if (m := _PAGE_RE.match(ln.strip()))]


def _assert_chunkable(md: str, meta: RawDocMeta, tmp_path: Path,
                      expected_pages: set[int]) -> list[dict]:
    # 产物写出后经 parse_manual 切块：块数大于 0、页码集合正确、metadata 与声明一致
    out = tmp_path / f"{meta.doc}_{meta.version}.md"
    out.write_text(md, encoding="utf-8")
    chunks = parse_manual(out)
    assert len(chunks) > 0, "解析产物应可被 parse_manual 切出块"
    assert {c["metadata"]["page"] for c in chunks} == expected_pages
    for c in chunks:
        m = c["metadata"]
        assert (m["doc"], m["model"], m["version"], m["status"]) == \
               (meta.doc, meta.model, meta.version, meta.status)
    return chunks


# ---------- 生成确定性 ----------

def _hash_raw_products() -> dict[str, str]:
    files = [PDF_PATH, DOCX_PATH, *sorted(SCAN_DIR.glob("*.png"))]
    return {str(f.relative_to(RAW_DIR)): hashlib.sha256(f.read_bytes()).hexdigest()
            for f in files}


def test_gen_raw_data_deterministic():
    before = _hash_raw_products()
    assert len(before) == 5, "data/raw 下应已有三类原始件（PDF/DOCX/3 张 PNG）"
    # 重跑核心生成函数，产物字节级不变
    gen_pdf()
    gen_docx()
    gen_scan_images()
    assert _hash_raw_products() == before, "重复生成产物内容应一致"


# ---------- build_markdown 契约 ----------

def test_build_markdown_matches_parser_regex():
    meta = RawDocMeta(doc="测试手册", model="X-1", version="V9.9", status="archived")
    pages = [
        PageContent(page_no=1, blocks=["第一段文本", "| 表头 |", "| --- |"]),
        PageContent(page_no=2, blocks=["第二页文本"]),
    ]
    md = build_markdown(meta, pages)

    # 声明头四行、页标记均须被 parser.py 的正则整行匹配（即契约格式精确一致）
    lines = md.splitlines()
    for i, field in enumerate(("doc", "model", "version", "status")):
        m = _HEADER_RE.match(lines[i].strip())
        assert m and m.group(1) == field, f"声明头第 {i + 1} 行应被 parser 识别为 {field}"
    assert m.group(2) == "archived"
    assert _PAGE_RE.match("<!-- page: 1 -->"), "页标记格式应与 parser 正则精确匹配"
    assert _page_markers(md) == [1, 2]
    # 块内容按页序落到对应页标记之后
    assert lines.index("第一段文本") > lines.index("<!-- page: 1 -->")
    assert lines.index("第二页文本") > lines.index("<!-- page: 2 -->")


# ---------- PDF 解析 ----------

# D-300 PDF 中应被抽取的大图 caption 与指引行（精确格式，与 build_markdown 渲染一致）
DRAWING_REF_LINE = "[图] 图 1-1 液压系统动力单元示意图（图号 1-1，原图：drawings/1-1.png）"


@pytest.fixture(scope="module")
def pdf_drawings_dir(tmp_path_factory) -> Path:
    # module 级临时抽图目录：供 PDF 解析 fixture 与抽图断言共用
    return tmp_path_factory.mktemp("pdf_out") / "drawings"


@pytest.fixture(scope="module")
def pdf_markdown(pdf_drawings_dir) -> str:
    return convert_pdf(PDF_PATH, PDF_META, drawings_dir=pdf_drawings_dir)


def test_pdf_conversion_contract(pdf_markdown):
    _assert_header(pdf_markdown, PDF_META)
    # 页标记数 == PDF 实际页数
    with pymupdf.open(str(PDF_PATH)) as doc:
        assert _page_markers(pdf_markdown) == list(range(1, doc.page_count + 1))
    # 含 Markdown 表格：数据行与分隔行齐全
    assert "| 参数名称 | 数值 | 单位 | 备注 |" in pdf_markdown
    assert re.search(r"^\|( --- \|)+$", pdf_markdown, re.M), "应含 Markdown 表格分隔行"
    # 关键数值可检出：液压系统压力上限 18 MPa
    assert "| 液压系统压力上限 | 18 | MPa |" in pdf_markdown


def test_pdf_drawing_extraction(pdf_markdown, pdf_drawings_dir):
    # 大图被抽取：drawings 目录有且仅有 1-1.png（装饰小图 < 页面 4% 被过滤）
    assert [p.name for p in pdf_drawings_dir.glob("*.png")] == ["1-1.png"]
    # [图] 指引行格式精确，且位于 page 3 标记之下
    lines = pdf_markdown.splitlines()
    assert DRAWING_REF_LINE in lines
    assert lines.index(DRAWING_REF_LINE) > lines.index("<!-- page: 3 -->")
    # 装饰小图不产生任何指引行：全文 [图] 行仅一条
    assert sum(1 for ln in lines if ln.startswith("[图]")) == 1


def test_pdf_output_chunkable(pdf_markdown, tmp_path):
    chunks = _assert_chunkable(pdf_markdown, PDF_META, tmp_path, {1, 2, 3})
    # 参数表应整块成为一个 chunk，且页码为表格所在的第 2 页
    table_chunks = [c for c in chunks if c["text"].lstrip().startswith("|")]
    assert len(table_chunks) == 1
    assert table_chunks[0]["metadata"]["page"] == 2
    assert "| 液压系统压力上限 | 18 | MPa |" in table_chunks[0]["text"]
    # [图] 指引行被正常切为文本 chunk，且页码为图所在的第 3 页
    drawing_chunks = [c for c in chunks if DRAWING_REF_LINE in c["text"]]
    assert len(drawing_chunks) == 1
    assert drawing_chunks[0]["metadata"]["page"] == 3


# ---------- DOCX 解析 ----------

@pytest.fixture(scope="module")
def docx_markdown() -> str:
    return convert_docx(DOCX_PATH, DOCX_META)


def test_docx_conversion_contract(docx_markdown):
    from docx import Document
    from docx.oxml.ns import qn

    _assert_header(docx_markdown, DOCX_META)
    # 页标记数 == 文档内显式分页符数 + 1
    document = Document(str(DOCX_PATH))
    breaks = sum(1 for node in document.element.body.iter(qn("w:br"))
                 if node.get(qn("w:type")) == "page")
    assert _page_markers(docx_markdown) == list(range(1, breaks + 2))
    # 表格完整转为 Markdown 表格：表头、分隔行、数据行齐全
    assert "| 保养项目 | 周期 | 工时 | 备注 |" in docx_markdown
    assert re.search(r"^\|( --- \|)+$", docx_markdown, re.M)
    assert "| 液压油更换 | 2000 小时 | 2.0 h |" in docx_markdown
    # 声明的关键保养数值可检出
    assert "2000 小时" in docx_markdown


def test_docx_output_chunkable(docx_markdown, tmp_path):
    chunks = _assert_chunkable(docx_markdown, DOCX_META, tmp_path, {1, 2, 3})
    table_chunks = [c for c in chunks if c["text"].lstrip().startswith("|")]
    assert len(table_chunks) == 1
    assert table_chunks[0]["metadata"]["page"] == 2
    assert "2000 小时" in table_chunks[0]["text"]


# ---------- 扫描件 OCR 解析 ----------

@pytest.fixture(scope="module")
def ocr_markdown() -> str:
    # OCR 较慢：module 级 fixture 只识别一次，供本模块全部 OCR 断言共用
    return convert_images(sorted(SCAN_DIR.glob("*.png")), SCAN_META)


def test_ocr_conversion_contract(ocr_markdown):
    _assert_header(ocr_markdown, SCAN_META)
    # 页标记数 == PNG 张数，页码从 1 起连续
    pngs = sorted(SCAN_DIR.glob("*.png"))
    assert _page_markers(ocr_markdown) == list(range(1, len(pngs) + 1))
    # 每页关键内容词可检出（宽松断言：型号与日期年份，允许个别字符级 OCR 误差）
    sections = re.split(r"<!--\s*page\s*:\s*\d+\s*-->", ocr_markdown)[1:]
    assert len(sections) == len(pngs)
    for i, section in enumerate(sections, start=1):
        assert "A-160" in section, f"第 {i} 页应检出设备型号 A-160"
        assert "2026" in section, f"第 {i} 页应检出日期年份 2026"


def test_ocr_output_chunkable(ocr_markdown, tmp_path):
    _assert_chunkable(ocr_markdown, SCAN_META, tmp_path, {1, 2, 3})


# ---------- 解析 CLI ----------

def _run_cli(input_path: Path, out_dir: Path, meta: RawDocMeta) -> str:
    cmd = [sys.executable, str(ROOT / "scripts" / "parse_raw.py"), str(input_path),
           "--doc", meta.doc, "--model", meta.model,
           "--version", meta.version, "--status", meta.status,
           "--out-dir", str(out_dir)]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, f"CLI 执行失败: {result.stderr}"
    out = out_dir / f"{meta.doc}_{meta.version}.md"
    assert out.is_file(), f"CLI 未产出 {out}"
    return out.read_text(encoding="utf-8")


def test_cli_dispatch_pdf(tmp_path):
    md = _run_cli(PDF_PATH, tmp_path, PDF_META)
    _assert_header(md, PDF_META)
    # CLI 默认将抽图落盘到 out_dir/drawings，产物含 [图] 指引行
    assert (tmp_path / "drawings" / "1-1.png").is_file()
    assert DRAWING_REF_LINE in md


def test_cli_dispatch_docx(tmp_path):
    md = _run_cli(DOCX_PATH, tmp_path, DOCX_META)
    _assert_header(md, DOCX_META)


def test_cli_dispatch_scan_dir(tmp_path):
    # 目录输入分派 OCR：取一张扫描页放入临时目录，控制识别耗时
    scan_input = tmp_path / "scan"
    scan_input.mkdir()
    src_png = sorted(SCAN_DIR.glob("*.png"))[0]
    (scan_input / src_png.name).write_bytes(src_png.read_bytes())
    md = _run_cli(scan_input, tmp_path / "out", SCAN_META)
    _assert_header(md, SCAN_META)
    assert _page_markers(md) == [1], "单张 PNG 应产出 1 个页标记"
