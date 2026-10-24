# PDF 插图抽取与指引 chunk Spec

## Why

parse-raw-manuals 已覆盖 PDF 文本与表格，但电子版 PDF 中的嵌入插图被跳过。本 change 补上图的处理：有价值插图抽图存文件并生成指引 chunk，装饰小图丢弃。指针放 chunk 文本内（图号 + 原图路径），既有 Markdown 契约与 parser.py 零改动，下游链路无感。

## What Changes

- 修改 `scripts/gen_raw_data.py`：D-300 PDF 增加两幅图——一幅有 caption 的示意图（大，应被抽取）、一幅装饰小图（应被过滤）；DOCX / 扫描件不变
- 修改 `src/parsing/raw/common.py`：`PageContent.blocks` 元素类型扩展为 `str | DrawingRef`；`DrawingRef`（caption / drawing_no / path）；build_markdown 将 DrawingRef 渲染为定格式文本行 `[图] {caption}（图号 {drawing_no}，原图：{path}）`
- 修改 `src/parsing/raw/pdf_conv.py`：`convert_pdf` 增加 `drawings_dir` 参数；逐页 `page.get_image_info()` 枚举图像，按面积阈值（< 页面面积 4% 视为装饰图）过滤；合格图抽取存 PNG 至 drawings_dir；caption 取图下方最近且以"图"开头的文本块，缺失时用 drawing_no 兜底命名；DrawingRef 按图像 y 坐标插入 blocks 保持阅读顺序
- 修改 `scripts/parse_raw.py`：PDF 分派时传 `drawings_dir = out_dir / "drawings"`
- 新增/更新 `tests/test_raw_parsing.py`：抽图断言、[图] 行格式、装饰图过滤、切块验证；全量回归

非目标（本 change 明确不做）：

- 整页扫描图识别路由（页面无文本层时转 OCR）——属后续 change
- chunk metadata 增加 drawing_path 字段（需改 parser.py 契约，本 change 以文本携带指针替代）
- 前端按指针渲染原图
- OCR 图中文字（插图内容不识别，只做指引）

## Impact

- Affected specs: parse-raw-manuals（追加图处理能力，不改其已验收行为）
- Affected code:
  - 修改 `scripts/gen_raw_data.py`、`src/parsing/raw/common.py`、`src/parsing/raw/pdf_conv.py`、`scripts/parse_raw.py`
  - 修改 `tests/test_raw_parsing.py`
  - 不改 `src/parsing/parser.py` 及下游模块；`data/raw/` 产物重新生成（内容变化，哈希随之更新）

## ADDED Requirements

### Requirement: 插图抽取

PDF 解析时，嵌入图像面积 >= 页面面积 4% 的 SHALL 抽取为 PNG 存至 drawings_dir；< 4% 的 SHALL 丢弃。每幅被抽取的图 SHALL 生成一条 DrawingRef（caption、drawing_no、path），并按图像 y 坐标插入该页 blocks 保持阅读顺序。caption SHALL 取图下方最近且以"图"开头的文本块；drawing_no 从 caption 中的"图 x-x"提取，提取不到则以 `p{页码}-{序号}` 命名。

#### Scenario: 示意图被抽取并生成指引

- **WHEN** 解析含示意图（带 caption"图 1-1 …"）的 D-300 PDF
- **THEN** drawings_dir 下存在对应 PNG；产物 Markdown 含 `[图] 图 1-1 …（图号 1-1，原图：…）` 行，且位于正确页标记之下；该行所在 chunk 页码正确

#### Scenario: 装饰小图被过滤

- **WHEN** PDF 含面积小于页面 4% 的装饰图
- **THEN** 该图不出现在 drawings_dir，产物 Markdown 无对应 [图] 行

### Requirement: 指引 chunk 契约兼容

DrawingRef 渲染行 SHALL 为普通文本段落，parse_manual 无需修改即可切块。

#### Scenario: 下游零改动

- **WHEN** 产物 Markdown 经 parse_manual 切块
- **THEN** [图] 行被正常切为文本块，既有全部测试保持绿色
