# table-slice-parse

长表格截图切片解析为结构化表格的开源技能/管线：检测表格结构 → 横线切割 →
MinerU 强制表格识别 → 智能拼接校验 → 输出 CSV / Markdown。

适用于超长清单表、多行单元格表格（如电缆表、明细表），解决 OCR 识别不全、
列错位、空行、被识别为纯文本等问题。

## 组件

- `SKILL.md` — 技能入口（frontmatter + 使用流程）
- `scripts/cut_only.py` — 横线切割（自动检测结构）
- `scripts/mineru_direct.py` — MinerU 管线直连解析，`--force-table` 强制表格识别
  （monkey-patch 布局阶段 text→table）
- `scripts/smart_merge.py` — 切片智能拼接 + 偏差校验
- `scripts/detect_structure.py` — 表格结构检测（列基准确认等）
- `setup.ps1` — Windows 一键建 MinerU 环境
- `setup_server.sh` — Linux 服务器部署（torch-CPU，可与其它 GPU 服务共存）

## 用法

```bash
# 1. 横线切割
python scripts/cut_only.py --images 2.png 53.png --out slices/

# 2. MinerU 解析（强制表格识别）
<mineru-venv>/bin/python scripts/mineru_direct.py \
    --input slices/53/slices --output mineru_out/53 --force-table

# 3. 智能拼接校验 → merged/53/{merged.md, merged.csv, structure.json}
python scripts/smart_merge.py --image 53.png --slices mineru_out/53 --output merged/53
```

## 说明

- MinerU 模型（PDF-Extract-Kit，约 2.6GB）首次运行自动从 ModelScope 下载。
- Linux 服务器部署走 CPU（现代 torch 的 CUDA wheel 不支持 P100/Pascal），
  实测约 8s/片，显存 0 占用。
- License: MIT（详见 `SKILL.md` 头部）。