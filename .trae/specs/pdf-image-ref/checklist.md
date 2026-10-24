# Checklist

- [x] D-300 PDF 重新生成后含大图（带 caption）与装饰小图，生成仍确定性可复现
- [x] 解析产物含 `[图] 图 1-1 液压系统动力单元示意图（图号 1-1，原图：drawings/1-1.png）` 行，位于 page 3 标记下
- [x] drawings 目录下存在大图 PNG（1-1.png），装饰小图未被抽取
- [x] [图] 行所在 chunk 页码 == 3
- [x] convert_pdf 签名带 drawings_dir，parse_raw.py 默认指向 out_dir/drawings
- [x] parser.py 及下游模块零改动
- [x] 全量回归 `python -m pytest tests/ -q` 全绿（55 passed）
