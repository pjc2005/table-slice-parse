# -*- coding: utf-8 -*-
"""
横线切割（自包含版）
====================
用 OpenCV 检测表格横线，按横线切割长图；切片过高时自动收缩线数。

用法:
    python cut_only.py --images pic/2.png pic/53.png --out slices/
"""

import argparse
import os
import shutil
import sys

import numpy as np
from PIL import Image


def cv2_imread(path):
    import cv2
    data = np.fromfile(path, dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


# ==================== 横线检测 ====================

def detect_horizontal_lines_adaptive(image_path):
    import cv2
    img = cv2_imread(image_path)
    if img is None:
        return []
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    height, width = gray.shape

    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 15, 3
    )
    kernel_sizes = [width // 12, width // 8, width // 6]
    all_lines = np.zeros_like(binary)
    for ksize in kernel_sizes:
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(ksize, 20), 1))
        lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
        all_lines = cv2.bitwise_or(all_lines, lines)
    projection = np.sum(all_lines, axis=1) / width
    mean_proj = np.mean(projection)
    std_proj = np.std(projection)
    threshold = max(0.02, mean_proj + 0.3 * std_proj)
    line_positions = [y for y in range(height) if projection[y] > threshold]
    if not line_positions:
        threshold = max(0.01, mean_proj + 0.1 * std_proj)
        line_positions = [y for y in range(height) if projection[y] > threshold]
    if not line_positions:
        return []

    merged = []
    current = line_positions[0]
    for y in line_positions[1:]:
        if y - current <= 5:
            continue
        merged.append(current)
        current = y
    merged.append(current)
    margin = 20
    merged = [y for y in merged if margin < y < height - margin]
    if len(merged) > 2:
        filtered = [merged[0]]
        for y in merged[1:]:
            if y - filtered[-1] > 15:
                filtered.append(y)
        merged = filtered
    return merged


def detect_horizontal_lines_otsu(image_path):
    import cv2
    img = cv2_imread(image_path)
    if img is None:
        return []
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    height, width = gray.shape
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    kernel_width = max(30, width // 8)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_width, 1))
    horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
    projection = np.sum(horizontal, axis=1) / width
    threshold = 0.05
    line_positions = [y for y in range(height) if projection[y] > threshold]
    if not line_positions:
        return []
    merged = []
    current = line_positions[0]
    for y in line_positions[1:]:
        if y - current <= 5:
            continue
        merged.append(current)
        current = y
    merged.append(current)
    margin = 20
    merged = [y for y in merged if margin < y < height - margin]
    return merged


def detect_horizontal_lines_hybrid(image_path):
    lines1 = detect_horizontal_lines_adaptive(image_path)
    lines2 = detect_horizontal_lines_otsu(image_path)
    all_lines = sorted(set(lines1 + lines2))
    if not all_lines:
        return []
    merged = [all_lines[0]]
    for y in all_lines[1:]:
        if y - merged[-1] > 5:
            merged.append(y)
    return merged


# ==================== 切割 ====================

def split_by_lines(image_path, output_folder, rows_per_piece=25,
                   max_slice_height=1400, min_lines_per_piece=8):
    """用横线切割，每片固定 rows_per_piece 条横线；切片过高时自动收缩线数。"""
    lines = detect_horizontal_lines_hybrid(image_path)
    if len(lines) < 3:
        print(f"  [warn] 检测到横线不足({len(lines)}条)，改用像素切割")
        return split_by_pixel(image_path, output_folder, rows_per_piece)

    print(f"  [det] 检测到 {len(lines)} 条横线")
    img = Image.open(image_path)
    width, height = img.size

    base_name = os.path.splitext(os.path.basename(image_path))[0]
    sub_folder = os.path.join(output_folder, base_name, "slices")
    os.makedirs(sub_folder, exist_ok=True)

    slice_paths = []
    start_idx = 0
    part_num = 1

    while start_idx < len(lines):
        end_idx = min(start_idx + rows_per_piece, len(lines))
        y_top = lines[start_idx]
        y_bottom = lines[end_idx] if end_idx < len(lines) else height

        slice_h = y_bottom - y_top
        while slice_h > max_slice_height and (end_idx - start_idx) > min_lines_per_piece:
            end_idx = max(start_idx + min_lines_per_piece, end_idx - 5)
            y_bottom = lines[end_idx] if end_idx < len(lines) else height
            slice_h = y_bottom - y_top

        remaining = len(lines) - end_idx
        if part_num > 1 and remaining > 0 and remaining < rows_per_piece // 3:
            prev_start_idx = max(0, start_idx - rows_per_piece)
            merge_top = lines[prev_start_idx] if prev_start_idx < len(lines) else 0
            merge_h = height - merge_top
            if merge_h <= max_slice_height:
                prev_path = slice_paths[-1]
                if os.path.exists(prev_path):
                    os.remove(prev_path)
                slice_paths.pop()
                slice_path = os.path.join(sub_folder, f"slice_{len(slice_paths) + 1:03d}.png")
                part = img.crop((0, merge_top, width, height))
                part.save(slice_path)
                slice_paths.append(slice_path)
                print(f"  [cut] 第{len(slice_paths)}张(合并): Y轴 {merge_top}~{height}")
                break

        slice_path = os.path.join(sub_folder, f"slice_{part_num:03d}.png")
        part = img.crop((0, y_top, width, y_bottom))
        part.save(slice_path)
        slice_paths.append(slice_path)
        print(f"  [cut] 第{part_num}张: Y轴 {y_top}~{y_bottom}")

        start_idx = end_idx
        part_num += 1

    return slice_paths


def split_by_pixel(image_path, output_folder, rows_per_piece=40):
    """像素切割兜底"""
    img = Image.open(image_path)
    width, height = img.size
    if width < 800:
        row_h = 32
    elif width < 1200:
        row_h = 35
    else:
        row_h = 38
    piece_h = rows_per_piece * row_h + 60
    overlap = 80
    step = piece_h - overlap

    slice_paths = []
    current_top = 0
    part_num = 1
    base_name = os.path.splitext(os.path.basename(image_path))[0]
    sub_folder = os.path.join(output_folder, base_name, "slices")
    os.makedirs(sub_folder, exist_ok=True)

    while current_top < height:
        top = 0 if part_num == 1 else max(0, current_top - overlap // 2)
        bottom = min(top + piece_h, height)
        if bottom - top < 100:
            break
        if bottom - top < piece_h // 2 and part_num > 1:
            prev_path = slice_paths[-1]
            if os.path.exists(prev_path):
                os.remove(prev_path)
            slice_paths.pop()
            top = max(0, current_top - piece_h - overlap // 2)
            bottom = height
            slice_path = os.path.join(sub_folder, f"slice_{len(slice_paths) + 1:03d}.png")
            part = img.crop((0, top, width, bottom))
            part.save(slice_path)
            slice_paths.append(slice_path)
            break
        slice_path = os.path.join(sub_folder, f"slice_{part_num:03d}.png")
        part = img.crop((0, top, width, bottom))
        part.save(slice_path)
        slice_paths.append(slice_path)
        current_top += step
        part_num += 1
    return slice_paths


# ==================== 入口 ====================

def main():
    parser = argparse.ArgumentParser(description="横线切割")
    parser.add_argument("--images", nargs="+", required=True, help="图片路径")
    parser.add_argument("--out", required=True, help="输出根目录，每图一个子目录")
    parser.add_argument("--rows", type=int, default=25, help="每片横线数")
    parser.add_argument("--max-slice-height", type=int, default=1400)
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    for img in args.images:
        base = os.path.splitext(os.path.basename(img))[0]
        tmp = os.path.join(args.out, base, "_cut")
        os.makedirs(tmp, exist_ok=True)
        slices = split_by_lines(img, tmp, args.rows, max_slice_height=args.max_slice_height)
        if not slices:
            print(f"[fail] {base}: 切割失败")
            shutil.rmtree(tmp, ignore_errors=True)
            continue
        dst = os.path.join(args.out, base, "slices")
        os.makedirs(dst, exist_ok=True)
        for s in slices:
            shutil.copy2(s, os.path.join(dst, os.path.basename(s)))
        shutil.rmtree(tmp, ignore_errors=True)
        print(f"[ok] {base}: {len(slices)} 片 -> {dst}")


if __name__ == "__main__":
    main()
