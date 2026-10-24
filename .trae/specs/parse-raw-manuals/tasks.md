# Tasks

- [x] Task 1: 环境与依赖——安装新增依赖（reportlab / pymupdf / python-docx / rapidocr-onnxruntime / pillow），确认可 import（rapidocr 模型随包分发，首次运行加载即可）
- [x] Task 2: 原始件生成脚本 `scripts/gen_raw_data.py`——确定性生成三类原始件至 `data/raw/`（D-300 PDF 含表格、E-450 DOCX 含表格与分页符、维修记录单扫描 PNG 序列含噪声/微倾斜）
- [x] Task 3: 解析层 `src/parsing/raw/`——common（RawDocMeta + build_markdown 契约出口）、pdf_conv（PyMuPDF 文本 + find_tables）、docx_conv（段落/表格/分页符）、ocr_conv（RapidOCR 逐图逐行）
- [x] Task 4: CLI `scripts/parse_raw.py`——按后缀分派、metadata 参数化、--out-dir 可配；三类输入各跑一次，产物写 `data/parsed/` 验证
- [x] Task 5: 测试 `tests/test_raw_parsing.py`——生成→解析→契约断言（页标记数、表格完整性、关键数值、关键词包含）+ parse_manual 可切块断言；全量回归 `python -m pytest tests/ -q` 全绿（54 passed）

# Task Dependencies

- [Task 2] depends on [Task 1]
- [Task 3] depends on [Task 1]；与 [Task 2] 可并行（生成产物格式以本 spec 约定为准）
- [Task 4] depends on [Task 2, Task 3]
- [Task 5] depends on [Task 4]

# 接口约定（实现与测试以此为准）

```python
# src/parsing/raw/common.py
@dataclass
class RawDocMeta:
    doc: str; model: str; version: str; status: str

@dataclass
class PageContent:
    page_no: int            # 1 起
    blocks: list[str]       # 文本段落 或 完整 Markdown 表格（含表头/分隔行/数据行）

def build_markdown(meta: RawDocMeta, pages: list[PageContent]) -> str:
    """输出契约 Markdown：声明头 + 每页 '<!-- page: N -->' + 块内容"""

# src/parsing/raw/pdf_conv.py
def convert_pdf(pdf_path: Path, meta: RawDocMeta) -> str

# src/parsing/raw/docx_conv.py
def convert_docx(docx_path: Path, meta: RawDocMeta) -> str

# src/parsing/raw/ocr_conv.py
def convert_images(image_paths: list[Path], meta: RawDocMeta) -> str

# scripts/parse_raw.py
# python scripts/parse_raw.py <输入路径> --doc D-300操作手册 --model D-300 --version V1.0 --status active [--out-dir data/manuals]
# 分派：.pdf → convert_pdf；.docx → convert_docx；目录 → convert_images（按文件名排序）
```
