# -*- coding: utf-8 -*-
"""
MinerU 底层直连解析（无需 server）
==================================
用 doc_analyze_streaming 直接解析切片，支持 --force-table（强制 text→table）。

用法:
    python mineru_direct.py --input pipe_slices/53/slices --output pipe_mineru_ft/53 --force-table
"""

import argparse
import io
import os
import sys
from pathlib import Path

os.environ.setdefault("MINERU_MODEL_SOURCE", "modelscope")
os.environ.setdefault("CUDA_PATH", r"C:\cuda128")

from PIL import Image
from mineru.backend.pipeline.pipeline_analyze import doc_analyze_streaming
from mineru.backend.pipeline.pipeline_middle_json_mkcontent import make_blocks_to_markdown
from mineru.utils.enum_class import MakeMode

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tiff", ".gif"}


def enable_force_table():
    """Monkey-patch：布局阶段所有 text 区域按表格识别。"""
    import mineru.backend.pipeline.batch_analyze as ba
    _orig = ba.run_layout_inference

    def _patched(cb, *a, **kw):
        res = _orig(cb, *a, **kw)
        for lr in res:
            for it in lr:
                if it.get("label") == "text":
                    it["label"] = "table"
        return res

    ba.run_layout_inference = _patched
    print("[mineru] force-table 已启用: text -> table")


class _Writer:
    """MinerU image_writer：把裁剪出的图片写到输出目录。"""
    def __init__(self, folder: Path):
        self.folder = folder
        self.folder.mkdir(parents=True, exist_ok=True)

    def write(self, name, data):
        p = self.folder / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return str(p)


def image_to_pdf_bytes(image_path: Path, dpi: int = 300) -> bytes:
    img = Image.open(image_path).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PDF", resolution=dpi)
    return buf.getvalue()


def parse_single(image_path: Path, output_md: Path, force_table: bool) -> int:
    """解析单张图片，输出 markdown 到 output_md，返回 HTML table 行数。"""
    pdf_bytes = image_to_pdf_bytes(image_path)
    writer = _Writer(output_md.parent / "images")
    mds: list[str] = []

    def on_doc_ready(doc_index, model_list, middle_json, ocr_enable):
        for page in middle_json["pdf_info"]:
            blocks = page.get("para_blocks", [])
            md = make_blocks_to_markdown(blocks, MakeMode.MM_MD)
            mds.append("\n\n".join(md))

    doc_analyze_streaming(
        pdf_bytes_list=[pdf_bytes],
        image_writer_list=[writer],
        lang_list=["ch"],
        on_doc_ready=on_doc_ready,
        parse_method="auto",
        formula_enable=False,
        table_enable=True,
        client_side_output_generation=False,
    )

    output_md.parent.mkdir(parents=True, exist_ok=True)
    md_text = "\n\n".join(mds)
    with open(output_md, "w", encoding="utf-8") as f:
        f.write(md_text)

    # 统计 HTML table 行数
    import re
    tables = re.findall(r"<table.*?</table>", md_text, re.DOTALL)
    rows = sum(t.count("<tr>") for t in tables)
    return rows


def main():
    parser = argparse.ArgumentParser(description="MinerU 底层直连解析切片")
    parser.add_argument("--input", type=Path, required=True, help="切片目录")
    parser.add_argument("--output", type=Path, required=True, help="输出目录(每片一个子目录)")
    parser.add_argument("--images", nargs="*", default=None, help="指定切片名(默认全部)")
    parser.add_argument("--force-table", action="store_true", help="强制 text->table")
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    if args.force_table:
        enable_force_table()

    # 收集输入
    if args.images:
        paths = [args.input / n for n in args.images if (args.input / n).is_file()]
    else:
        paths = sorted(
            (p for p in args.input.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES),
            key=lambda p: p.name.lower(),
        )
    if not paths:
        print(f"[fail] 未找到图片: {args.input}")
        return

    print(f"[mineru] 解析 {len(paths)} 张切片...")
    total_rows = 0
    for i, p in enumerate(paths, 1):
        out_md = args.output / f"{p.stem}_out" / f"{p.stem}.md"
        rows = parse_single(p, out_md, args.force_table)
        total_rows += rows
        print(f"  [{i}/{len(paths)}] {p.name}: {rows} table行 -> {out_md}")

    print(f"[mineru] 完成: 共 {total_rows} table行")


if __name__ == "__main__":
    main()
