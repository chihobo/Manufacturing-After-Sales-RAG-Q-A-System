# Tasks

- [x] Task 1: 修改 `scripts/gen_raw_data.py`——D-300 PDF 第 1 页加装饰小图（< 页面 4%）、第 3 页加带 caption"图 1-1 液压系统动力单元示意图"的大图；保持确定性生成
- [x] Task 2: 修改 `src/parsing/raw/common.py`——新增 DrawingRef 类型，build_markdown 渲染 `[图]` 行
- [x] Task 3: 修改 `src/parsing/raw/pdf_conv.py`——convert_pdf 增加 drawings_dir 参数，图像枚举/面积过滤/抽图存盘/caption 关联/DrawingRef 按 y 插入
- [x] Task 4: 修改 `scripts/parse_raw.py`——PDF 分派传 drawings_dir=out_dir/"drawings"
- [x] Task 5: 更新 `tests/test_raw_parsing.py` 并全量回归——抽图存在、[图] 行格式、装饰图过滤、切块页码正确、既有测试全绿（55 passed）

# Task Dependencies

- [Task 1] 与 [Task 2] 可并行；[Task 3] depends on [Task 1, Task 2]；[Task 4] depends on [Task 3]；[Task 5] depends on [Task 4]
