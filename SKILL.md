---
name: table-slice-parse
description: 长表格截图切片解析为结构化表格。检测表格结构→横线切割→MinerU强制表格识别→智能拼接校验→输出CSV/Markdown。适用于超长电缆表、清单明细表、多行单元格表格，解决OCR识别不全/列错位/空行/被识别为纯文本等问题。
license: MIT
compatibility: opencode
metadata:
  engine: MinerU-pipeline
  output: merged/{image}/merged.csv + merged.md
---

## 何时使用

当用户提供**长表格截图**需要提取为结构化表格时：

- 表格超长（几百行），单次 OCR 识别不全
- 清单/明细类表格（单元格含多行描述文本，如 `1、名称...2、型号...`）
- MinerU 或其他 OCR 把表格识别为纯文本段落
- 识别结果存在空行、列错位、列数不齐

## 环境要求

- **MinerU venv**：`mineru-venv\Scripts\python.exe`（运行 `mineru_direct.py` 用）
- **系统 Python**：`python`（运行 `cut_only.py` / `smart_merge.py` 用）
- 依赖：见 `setup.ps1`（首次在新机器运行）
- 模型：PDF-Extract-Kit（首次运行自动下载，需联网）

## 使用流程

在 skill 目录下执行以下步骤（脚本在 `scripts/`）：

### 1. 横线切割

```bash
python scripts/cut_only.py --images <图片1> <图片2>... --out <切片输出目录>
# 例: python scripts/cut_only.py --images 2.png 53.png --out slices/
```

每张图生成 `<out>/<图片名>/slices/slice_001.png...` 切片。

### 2. MinerU 解析（强制表格识别）

```bash
<mineru-venv-python> scripts/mineru_direct.py \
    --input <切片输出目录>/<图片名>/slices \
    --output <mineru输出目录>/<图片名> \
    --force-table
# 例: mineru-venv\Scripts\python.exe scripts/mineru_direct.py \
#     --input slices/53/slices --output mineru_out/53 --force-table
```

每片生成 `<output>/<图片名>/slice_NNN_out/slice_NNN.md`（HTML table 格式）。
`--force-table` 强制布局阶段所有 text 区域按表格识别（解决清单表格被识别为文本的问题）。

### 3. 智能拼接校验

```bash
python scripts/smart_merge.py \
    --image <原图> \
    --slices <mineru输出目录>/<图片名> \
    --output <合并输出目录>/<图片名>
```

输出：
- `merged.csv` / `merged.md`：最终合并表格
- `structure.json`：结构检测 + 每片偏差
- `issues.json`：空行/列缺失/列错位明细
- `problem_slices.json`：偏差超阈值的问题片

## 输出结构

```
merged/{图片名}/
├── merged.csv / merged.md      ← 最终表格
├── structure.json              ← 全局+每片结构、偏差
├── issues.json                 ← 清洗记录（空行/列缺失）
└── problem_slices.json         ← 超偏差问题片
```

## 参数说明

| 脚本 | 关键参数 | 默认 |
|------|---------|------|
| cut_only.py | `--rows` 每片横线数 / `--max-slice-height` 单片最大高度 | 25 / 1400 |
| mineru_direct.py | `--force-table` 强制表格 / `--images` 指定切片 | 关 |
| smart_merge.py | `--threshold` 偏差阈值 | 0.2 |

## 新机器安装环境

```powershell
powershell -ExecutionPolicy Bypass -File setup.ps1
```

setup.ps1 会：创建 mineru-venv、装 `mineru[pipeline]` 依赖、装系统 Python 依赖、首次运行自动下载 PDF-Extract-Kit 模型。
