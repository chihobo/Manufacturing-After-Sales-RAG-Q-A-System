# -*- coding: utf-8 -*-
# 原始件解析 CLI：按输入后缀分派解析器，metadata 由参数声明，输出契约 Markdown
# 用法：
#   python scripts/parse_raw.py <输入路径> --doc D-300操作手册 --model D-300 \
#       --version V1.0 --status active [--out-dir data/manuals]
# 分派：.pdf -> convert_pdf；.docx -> convert_docx；目录 -> convert_images（按文件名排序）
import argparse
import sys
from pathlib import Path

# 脚本直接运行时把项目根目录加入 sys.path，保证可 import src.*
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.parsing.raw.common import RawDocMeta
from src.parsing.raw.pdf_conv import convert_pdf
from src.parsing.raw.docx_conv import convert_docx
from src.parsing.raw.ocr_conv import convert_images


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="原始件解析：PDF/DOCX/扫描件 -> 契约 Markdown")
    parser.add_argument("input", type=Path, help="输入路径：.pdf 文件 / .docx 文件 / PNG 目录")
    parser.add_argument("--doc", required=True, help="文档名声明，如 D-300操作手册")
    parser.add_argument("--model", required=True, help="型号声明，如 D-300")
    parser.add_argument("--version", required=True, help="版本声明，如 V1.0")
    parser.add_argument("--status", required=True, help="状态声明，如 active / archived")
    parser.add_argument("--out-dir", type=Path, default=Path("data/manuals"),
                        help="输出目录（默认 data/manuals）")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    meta = RawDocMeta(doc=args.doc, model=args.model,
                      version=args.version, status=args.status)
    src: Path = args.input

    if src.is_dir():
        # 目录视为扫描件：按文件名排序取 PNG 序列
        image_paths = sorted(src.glob("*.png"))
        if not image_paths:
            raise SystemExit(f"目录内无 PNG 文件: {src}")
        markdown = convert_images(image_paths, meta)
    elif src.suffix.lower() == ".pdf":
        # PDF 抽图落盘到 out_dir/drawings，产物 Markdown 以相对路径引用原图
        markdown = convert_pdf(src, meta, drawings_dir=args.out_dir / "drawings")
    elif src.suffix.lower() == ".docx":
        markdown = convert_docx(src, meta)
    else:
        raise SystemExit(f"不支持的输入类型: {src}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out = args.out_dir / f"{meta.doc}_{meta.version}.md"
    out.write_text(markdown, encoding="utf-8")
    print(f"[解析完成] {src} -> {out}")


if __name__ == "__main__":
    main()
