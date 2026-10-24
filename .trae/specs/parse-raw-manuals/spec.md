# 原始手册解析（PDF / DOCX / 扫描件 → Markdown 契约）Spec

## Why

现有 demo（build-rag-demo）只支持 Markdown 手册入库，但生产场景中原始资料是 PDF / Word / 扫描件。本 change 补上"解析环节"：程序化生成三类原始件作为演示数据，并实现解析层将其统一转换为既有 Markdown 契约（声明头 + 页标记 + Markdown 表格），下游切块/索引/检索链路零改动复用。

## What Changes

- 新增原始件生成脚本 `scripts/gen_raw_data.py`：程序化生成三类演示原始件（可控、可复现、可断言，不依赖网络下载）
  - `data/raw/D-300操作手册.pdf`：电子版 PDF（reportlab，多页、含参数表格）
  - `data/raw/E-450保养手册.docx`：Word（python-docx，含表格、显式分页符）
  - `data/raw/维修记录单_scan/`：扫描件模拟（PIL 渲染中文文本成 PNG 多页，加轻微噪声/倾斜；内容为纯文本维修记录，不含表格）
- 新增解析层 `src/parsing/raw/`：
  - `common.py`：`RawDocMeta`（doc/model/version/status）+ `build_markdown(meta, pages)` 统一出口，输出符合既有契约的 Markdown 文本
  - `pdf_conv.py`：PyMuPDF 按页抽文本 + find_tables 表格识别 → Markdown 表格
  - `docx_conv.py`：python-docx 段落/表格解析，分页符映射页码
  - `ocr_conv.py`：RapidOCR 逐图识别为按行文本，一图一页
- 新增 CLI `scripts/parse_raw.py <输入> --doc --model --version --status [--out-dir]`：按后缀分派（.pdf→电子版解析、.docx→Word 解析、目录→OCR 解析），写出契约 Markdown（默认 `data/manuals/`，可指定 `--out-dir`）
- 修复 `requirements.txt`：删除第 12 行乱入的中文句号（"。"），补充新增依赖（reportlab / pymupdf / python-docx / rapidocr-onnxruntime / pillow）
- 新增 `tests/test_raw_parsing.py`，全量回归通过

非目标（本 change 明确不做）：

- 扫描件表格结构重建（OCR 仅覆盖纯文本页；表格还原属生产形态，叙事讲解）
- 任意真实 PDF 的鲁棒版面分析（解析器针对结构正常的文档，不处理极端排版）
- 从原始件内容自动推断 metadata（doc/model/version/status 一律由 CLI 参数声明，与"metadata 取自声明不靠猜"一致）
- 解析产物自动入库（解析与入库是两个动作；验证用产物写到 `data/parsed/`，不污染演示知识库）
- 不做 fallback 与旧兼容（按用户规则）

## Impact

- Affected specs: 无冲突（build-rag-demo 已验收归档；本 change 为其"解析环节"补全）
- Affected code:
  - 新增 `scripts/gen_raw_data.py`、`scripts/parse_raw.py`
  - 新增 `src/parsing/raw/`（common / pdf_conv / docx_conv / ocr_conv）
  - 新增 `tests/test_raw_parsing.py`
  - 修改 `requirements.txt`（删乱入字符 + 5 个新依赖）
  - 新增 `data/raw/`（生成的原始件，入库留档）、`data/parsed/`（验证产物，不入演示库）
  - 不改 `src/parsing/parser.py` 及任何下游模块（契约复用）

## ADDED Requirements

### Requirement: 原始件生成

系统 SHALL 提供 `scripts/gen_raw_data.py`，一键生成三类演示原始件：电子版 PDF（多页、含至少一个带框线参数表格）、DOCX（含表格与显式分页符、至少 2 页）、扫描件 PNG 序列（中文文本渲染、含轻微噪声或倾斜、至少 2 页）。生成内容 SHALL 包含可断言的关键数值（如 D-300 液压上限 18MPa），供解析正确性验证。

#### Scenario: 一键生成

- **WHEN** 运行 `python scripts/gen_raw_data.py`
- **THEN** `data/raw/` 下存在 PDF、DOCX、扫描件 PNG 序列三类原始件，且重复运行产物内容一致（确定性生成）

### Requirement: PDF 解析

系统 SHALL 将电子版 PDF 按页解析：每页生成对应 `<!-- page: N -->` 页标记（N 为 PDF 页码，1 起）；正文段落转为文本块；带框线表格识别为 Markdown 表格（表头、分隔行、数据行完整）。

#### Scenario: PDF 解析产出契约 Markdown

- **WHEN** 对生成的 D-300 PDF 执行解析
- **THEN** 输出文本含声明头（doc/model/version/status）、页标记数等于 PDF 页数、含至少一个 Markdown 表格、含关键数值 18MPa，且可被 `src.parsing.parser.parse_manual` 直接切块（块数大于 0、页码正确）

### Requirement: DOCX 解析

系统 SHALL 将 DOCX 解析：段落转为文本块，表格转为 Markdown 表格，显式分页符映射为页标记递增。

#### Scenario: DOCX 解析产出契约 Markdown

- **WHEN** 对生成的 E-450 DOCX 执行解析
- **THEN** 输出文本含声明头、页标记数等于分页符数+1、表格完整转为 Markdown 表格、含声明的关键保养数值

### Requirement: 扫描件 OCR 解析

系统 SHALL 将扫描件 PNG 序列经 RapidOCR 识别为按行文本，一张图对应一页（页码按文件名序），输出契约 Markdown。

#### Scenario: OCR 解析产出契约 Markdown

- **WHEN** 对生成的扫描件 PNG 序列执行解析
- **THEN** 输出文本含声明头与正确数量的页标记，且每页关键内容词（生成时写入的句子关键词）可被检出（允许个别字符级 OCR 误差，按关键词包含断言）

### Requirement: 解析 CLI

系统 SHALL 提供 `scripts/parse_raw.py`，按输入后缀分派解析器，metadata 由参数声明（--doc/--model/--version/--status），输出契约 Markdown 至 `--out-dir`（默认 `data/manuals/`）。

#### Scenario: 三类输入分派

- **WHEN** 分别以 .pdf 文件、.docx 文件、PNG 目录为输入运行 CLI
- **THEN** 各自产出对应契约 Markdown 文件，声明头与参数一致
