# -*- coding: utf-8 -*-
# 建库入口脚本：解析全部内置手册 -> embedding -> 构建索引并持久化到 kb/
# 用法：python scripts/build_index.py
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import KB_DIR, MANUALS_DIR
from src.indexing.builder import build_index
from src.indexing.embedder import embed_texts
from src.parsing.parser import parse_all


def main() -> None:
    chunks = parse_all(MANUALS_DIR)
    build_index(chunks, embed_texts, KB_DIR)
    print(f"建库完成：{len(chunks)} 条 chunk，产物位于 {KB_DIR}")


if __name__ == "__main__":
    main()
