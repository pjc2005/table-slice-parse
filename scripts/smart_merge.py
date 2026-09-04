# -*- coding: utf-8 -*-
"""
smart_merge.py - MinerU 切片结果智能拼接 + 结构校验 + 列对齐
=============================================================
输入: MinerU 批量解析后的每片 md 目录 + 原图
流程: 解析每片表格 → 结构检测(全局+每片) → 方案X列对齐 → 空行删除
      → 偏差>20%标记问题片 → 智能拼接 → 全局校验 → 输出

用法:
    python smart_merge.py \
        --image "图片切割 (1)\pic\2.png" \
        --slices "C:\train\mineru_slice_out\2" \
        --output "C:\train\mineru_merge结果\2" \
        --threshold 0.2
"""

import argparse
import csv
import glob
import html.parser
import json
import os
import re
import sys

import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)


# ==================== HTML 表格解析 ====================

class _TableParser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.current_row = None
        self.current_cell = None
        self.in_cell = False
        self.in_table = False
        self.attrs = {}

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.in_table = True
        elif tag == "tr" and self.in_table:
            self.current_row = []
        elif tag in ("td", "th") and self.current_row is not None:
            self.in_cell = True
            self.current_cell = ""
            self.attrs = dict(attrs)

    def handle_data(self, data):
        if self.in_cell:
            self.current_cell += data

    def handle_endtag(self, tag):
        if tag in ("td", "th"):
            if self.in_cell and self.current_row is not None:
                colspan = int(self.attrs.get("colspan", 1))
                cell = (self.current_cell or "").strip()
                self.current_row.append(cell)
                for _ in range(colspan - 1):
                    self.current_row.append("")
            self.in_cell = False
            self.current_cell = None
        elif tag == "tr":
            if self.current_row is not None:
                self.rows.append(self.current_row)
                self.current_row = None
        elif tag == "table":
            self.in_table = False

    def parse(self, html_text):
        self.rows = []
        self.feed(html_text)
        return self.rows


# ==================== 工具 ====================

def parse_md_file(md_path):
    """解析 MinerU md 文件，返回所有 HTML table 行。"""
    with open(md_path, encoding="utf-8") as f:
        content = f.read()
    tables = re.findall(r"<table.*?</table>", content, re.DOTALL)
    parser = _TableParser()
    all_rows = []
    for t in tables:
        all_rows.extend(parser.parse(t))
    return all_rows


def normalize_cols(rows, col_base):
    """列对齐：不足 col_base 补空列（右对齐）；超过截断并记录。"""
    normalized = []
    issues = []
    for i, r in enumerate(rows):
        n = len(r)
        if n < col_base:
            r = r + [""] * (col_base - n)
            issues.append({"row": i, "type": "col_missing", "detail": f"{n}列->补{col_base}列"})
        elif n > col_base:
            issues.append({"row": i, "type": "col_overflow", "detail": f"{n}列->截断到{col_base}列"})
            r = r[:col_base]
        normalized.append(r)
    return normalized, issues


def detect_slice_dir_sorted(slices_dir):
    """收集所有切片输出目录（slice_001, slice_002...）按序号排序。"""
    dirs = glob.glob(os.path.join(slices_dir, "slice_*"))
    dirs.sort(key=lambda d: int(re.search(r"\d+", os.path.basename(d)).group()))
    return dirs


def find_md_in_slice(slice_dir):
    """在切片目录内找到 .md 文件（可能嵌套在 hybrid_auto/ 下）。"""
    mds = glob.glob(os.path.join(slice_dir, "**", "*.md"), recursive=True)
    return mds[0] if mds else None


def export_csv(rows, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerows(rows)


def export_md(rows, path):
    if not rows:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    ncols = max(len(r) for r in rows)
    lines = ["| " + " | ".join(rows[0]) + " |"]
    lines.append("| " + " | ".join(["---"] * ncols) + " |")
    for r in rows[1:]:
        lines.append("| " + " | ".join(r) + " |")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ==================== 主流程 ====================

def process(image_path, slices_dir, output_dir, threshold=0.2, col_base_override=None):
    """智能拼接主函数。"""
    os.makedirs(output_dir, exist_ok=True)

    # ① 原图结构检测
    import detect_structure as ds
    g = ds.analyze(image_path)
    global_rows, global_cols = g["rows"], g["cols"]
    print(f"[struct] 原图: 行={global_rows} 列={global_cols}")

    # 收集每片切片目录
    slice_dirs = detect_slice_dir_sorted(slices_dir)
    if not slice_dirs:
        print(f"[fail] 未找到切片目录: {slices_dir}")
        return None

    # ② 逐片解析 + 每片结构检测
    per_slice = []
    for sd in slice_dirs:
        name = os.path.basename(sd)
        md = find_md_in_slice(sd)
        rows = parse_md_file(md) if md else []
        # 每片结构检测
        img_files = glob.glob(os.path.join(sd, "**", "*.png"), recursive=True) + \
                    glob.glob(os.path.join(sd, "*.png"))
        if img_files:
            try:
                sl = ds.analyze(img_files[0])
                expected_rows, expected_cols = sl["rows"], sl["cols"]
            except Exception as e:
                expected_rows, expected_cols = len(rows), None
                print(f"  [warn] {name} 结构检测失败: {e}")
        else:
            expected_rows, expected_cols = len(rows), None

        per_slice.append({
            "name": name,
            "md": md,
            "rows": rows,
            "expected_rows": expected_rows,
            "expected_cols": expected_cols,
        })

    # ③ 列基准（方案X：众数列数）
    all_rows_flat = []
    for s in per_slice:
        all_rows_flat.extend(s["rows"])
    col_counts = [len(r) for r in all_rows_flat if r]
    from collections import Counter
    col_base = col_base_override or (Counter(col_counts).most_common(1)[0][0] if col_counts else global_cols)
    print(f"[align] 列基准 col_base = {col_base} (检测全局={global_cols})")

    # ④ 逐片清洗 + 偏差检测
    merged_rows = []
    issues_all = []
    problem_slices = []

    for s in per_slice:
        name = s["name"]
        rows = s["rows"]
        exp_rows = s["expected_rows"]

        # 列对齐
        aligned, col_issues = normalize_cols(rows, col_base)
        for iss in col_issues:
            iss["slice"] = name
            issues_all.append(iss)

        # 空行删除
        cleaned = []
        for i, r in enumerate(aligned):
            if all(not (c or "").strip() for c in r):
                issues_all.append({"slice": name, "row": i, "type": "empty_row", "detail": "全空行删除"})
            else:
                cleaned.append(r)

        # 行数偏差检测
        actual = len(cleaned)
        if exp_rows and exp_rows > 0:
            dev = abs(actual - exp_rows) / exp_rows
            print(f"  [chk] {name}: 识别{actual} vs 检测{exp_rows} (偏差{dev:.0%})")
            if dev > threshold:
                problem_slices.append({
                    "slice": name,
                    "actual_rows": actual,
                    "expected_rows": exp_rows,
                    "deviation": round(dev, 3),
                    "strategy": "二次切割或整片重提交",
                })
                print(f"    [warn] 偏差超阈值! 标记问题片")

        merged_rows.extend(cleaned)
        s["cleaned_rows"] = len(cleaned)

    # ⑤ 全局校验
    total = len(merged_rows)
    if global_rows and global_rows > 0:
        gdev = abs(total - global_rows) / global_rows
        print(f"[merge] 拼接总行数 {total} vs 检测 {global_rows} (偏差{gdev:.0%})")
        if gdev > threshold:
            print(f"  [warn] 全局偏差超阈值!")
    else:
        gdev = 0

    # ⑥ 输出
    export_csv(merged_rows, os.path.join(output_dir, "merged.csv"))
    export_md(merged_rows, os.path.join(output_dir, "merged.md"))

    structure = {
        "global_rows": global_rows,
        "global_cols": global_cols,
        "col_base": col_base,
        "total_merged": total,
        "global_deviation": round(gdev, 3),
        "per_slice": [
            {"name": s["name"], "rows": len(s["rows"]), "cleaned": s["cleaned_rows"],
             "expected_rows": s["expected_rows"], "expected_cols": s["expected_cols"]}
            for s in per_slice
        ],
    }
    with open(os.path.join(output_dir, "structure.json"), "w", encoding="utf-8") as f:
        json.dump(structure, f, ensure_ascii=False, indent=2)

    with open(os.path.join(output_dir, "issues.json"), "w", encoding="utf-8") as f:
        json.dump(issues_all, f, ensure_ascii=False, indent=2)

    with open(os.path.join(output_dir, "problem_slices.json"), "w", encoding="utf-8") as f:
        json.dump(problem_slices, f, ensure_ascii=False, indent=2)

    print(f"\n[ok] 输出: {output_dir}")
    print(f"  [stat] 合并 {total} 行, {col_base} 列")
    print(f"  [stat] 问题片 {len(problem_slices)} 个, issues {len(issues_all)} 条")

    return structure


# ============ 运行 ============
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MinerU 切片智能拼接")
    parser.add_argument("--image", required=True, help="原图路径")
    parser.add_argument("--slices", required=True, help="MinerU 切片输出目录")
    parser.add_argument("--output", required=True, help="输出目录")
    parser.add_argument("--threshold", type=float, default=0.2, help="偏差阈值(默认0.2)")
    parser.add_argument("--col-base", type=int, default=None, help="强制列数基准(默认众数)")
    args = parser.parse_args()

    process(args.image, args.slices, args.output, args.threshold, args.col_base)
