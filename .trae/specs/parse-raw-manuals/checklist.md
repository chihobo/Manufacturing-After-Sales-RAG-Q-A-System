# Checklist

- [x] `python scripts/gen_raw_data.py` 一键生成三类原始件，重复运行内容一致（测试以 SHA256 断言）
- [x] PDF 解析产物含声明头、页标记数 == PDF 页数、含 Markdown 表格、含关键数值 18MPa
- [x] DOCX 解析产物含声明头、页标记数 == 分页符数+1、表格完整、含声明的保养数值（2000 小时）
- [x] 扫描件 OCR 产物含声明头与正确页标记数，每页关键词（A-160、日期年份）可检出
- [x] 三类解析产物均可被 `src.parsing.parser.parse_manual` 直接切块（块数 > 0、页码正确）
- [x] CLI 三类输入分派正确，--out-dir 生效，默认写 `data/manuals/`
- [x] requirements.txt 无乱入字符，新增依赖可安装可 import
- [x] 全量回归 `python -m pytest tests/ -q` 全绿（54 passed）
- [x] 解析层未改动 `src/parsing/parser.py` 及任何下游模块
