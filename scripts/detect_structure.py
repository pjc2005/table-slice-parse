# -*- coding: utf-8 -*-
"""表格结构检测:输出每张图片的行列数

用法:
    python detect_structure.py 53.png                  # 单张
    python detect_structure.py .\\pic                   # 批量
    python detect_structure.py .\\pic --json struct.json  # 可选,导出汇总
"""

import argparse
import glob
import json
import os

import cv2
import numpy as np


def cv2_imread(path):
    """兼容中文路径的图片读取"""
    data = np.fromfile(path, dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def _merge_close(positions, min_gap):
    if not positions:
        return []
    positions = sorted(positions)
    merged = [positions[0]]
    for p in positions[1:]:
        if p - merged[-1] > min_gap:
            merged.append(p)
    return merged


def detect_table_structure(image_path):
    """
    检测表格网格结构
    返回: 行边界Y坐标列表, 列边界X坐标列表
    """
    img = cv2_imread(image_path)
    if img is None:
        raise ValueError(f"无法读取图片: {image_path}")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    height, width = gray.shape

    # 1. 自适应二值化(对灰色线敏感)
    binary = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        15, 2
    )

    # 2. 去除小噪点
    kernel = np.ones((2, 2), np.uint8)
    cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

    # 3. 多尺度提取水平线
    horizontal = np.zeros_like(binary)
    for k in (width // 12, width // 8, width // 6):
        hk = cv2.getStructuringElement(cv2.MORPH_RECT, (max(k, 20), 1))
        horizontal = cv2.bitwise_or(horizontal, cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, hk))

    # 4. 多尺度提取竖直线
    vertical = np.zeros_like(binary)
    for k in (height // 12, height // 8, height // 6):
        vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(k, 20)))
        vertical = cv2.bitwise_or(vertical, cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, vk))

    # 5. 水平/垂直投影定位线位置
    h_proj = np.sum(horizontal, axis=1) / width
    v_proj = np.sum(vertical, axis=0) / height
    row_positions = [y for y in range(height) if h_proj[y] > 0.3]
    col_positions = [x for x in range(width) if v_proj[x] > 0.3]

    # 6. 合并相邻线
    row_positions = _merge_close(row_positions, 15)
    col_positions = _merge_close(col_positions, 15)

    # 7. 兜底:线不足时改用投影法
    if len(row_positions) < 2:
        row_positions = _detect_rows_by_projection(binary, height, width)
    if len(col_positions) < 2:
        col_positions = _detect_cols_by_projection(binary, height, width)

    return row_positions, col_positions


def _detect_rows_by_projection(binary, height, width):
    """备用:通过水平投影检测行位置(无表格线时使用)"""
    h_proj = np.sum(binary, axis=1) / width
    text_rows = [y for y, val in enumerate(h_proj) if val > 0.05]
    if not text_rows:
        return []

    merged = []
    start = text_rows[0]
    end = text_rows[0]
    for y in text_rows[1:]:
        if y - end <= 5:
            end = y
        else:
            merged.append((start + end) // 2)
            start = y
            end = y
    merged.append((start + end) // 2)

    margin = 20
    return [y for y in merged if margin < y < height - margin]


def _detect_cols_by_projection(binary, height, width):
    """备用:通过垂直投影检测列位置"""
    v_proj = np.sum(binary, axis=0) / height
    text_cols = [x for x, val in enumerate(v_proj) if val > 0.05]
    if not text_cols:
        return []

    merged = []
    start = text_cols[0]
    end = text_cols[0]
    for x in text_cols[1:]:
        if x - end <= 5:
            end = x
        else:
            merged.append((start + end) // 2)
            start = x
            end = x
    merged.append((start + end) // 2)

    margin = 20
    return [x for x in merged if margin < x < width - margin]


def _count_cells(lines, size, margin=10):
    """
    由线位置推算数据单元格数。
    若首线/末线不在图片边缘,则推断表格延伸至图片边缘(边框线漏检)。
    """
    if len(lines) < 2:
        return max(0, len(lines) - 1)
    n = len(lines) - 1
    if lines[0] > margin:
        n += 1  # 左边缘有表格但无线
    if lines[-1] < size - 1 - margin:
        n += 1  # 右/下边缘有表格但无线
    return max(0, n)


def analyze(image_path):
    """分析单张图片,返回结构信息"""
    row_positions, col_positions = detect_table_structure(image_path)
    img = cv2_imread(image_path)
    height, width = img.shape[:2]

    return {
        "filename": os.path.basename(image_path),
        "width": width,
        "height": height,
        "rows": _count_cells(row_positions, height),
        "cols": _count_cells(col_positions, width),
        "rows_raw": len(row_positions),
        "cols_raw": len(col_positions),
        "row_y": row_positions,
        "col_x": col_positions,
    }


def _image_files(folder):
    files = []
    for ext in ('*.png', '*.jpg', '*.jpeg', '*.bmp', '*.tiff'):
        files.extend(glob.glob(os.path.join(folder, ext)))
        files.extend(glob.glob(os.path.join(folder, ext.upper())))
    return sorted(set(files))


def main():
    parser = argparse.ArgumentParser(description="检测表格结构:输出行列数")
    parser.add_argument("input", help="图片路径或文件夹")
    parser.add_argument("--json", default=None, help="可选:导出汇总JSON到指定文件")
    parser.add_argument("--raw", action="store_true", help="打印原始线数")
    args = parser.parse_args()

    if os.path.isdir(args.input):
        files = _image_files(args.input)
        if not files:
            print(f"未找到图片: {args.input}")
            return
        print(f"找到 {len(files)} 张图片")
        results = []
        ok = fail = 0
        for f in files:
            try:
                r = analyze(f)
                results.append(r)
                ok += 1
                extra = f" (线:行{r['rows_raw']} 列{r['cols_raw']})" if args.raw else ""
                print(f"#{r['filename']:<12} 行={r['rows']} 列={r['cols']}{extra}")
            except Exception as e:
                fail += 1
                print(f"#{os.path.basename(f):<12} 检测失败: {e}")
        print("-" * 40)
        print(f"完成: 成功 {ok} 张, 失败 {fail} 张")
        if args.json:
            with open(args.json, 'w', encoding='utf-8') as fh:
                json.dump(results, fh, ensure_ascii=False, indent=2)
            print(f"已导出: {args.json}")
    else:
        r = analyze(args.input)
        extra = f" (线:行{r['rows_raw']} 列{r['cols_raw']})" if args.raw else ""
        print(f"#{r['filename']}: 行={r['rows']} 列={r['cols']}{extra}")
        if args.json:
            with open(args.json, 'w', encoding='utf-8') as fh:
                json.dump([r], fh, ensure_ascii=False, indent=2)
            print(f"已导出: {args.json}")


if __name__ == "__main__":
    main()
