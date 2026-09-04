#!/usr/bin/env bash
# 一次全流程 pilot：cut → mineru_direct → smart_merge（在仓库目录内执行）
set -e
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
V="$(pwd)/mineru-venv/bin"
export PYTHONIOENCODING=utf-8

echo "=== [采样] 启动前 VRAM ==="
nvidia-smi --query-gpu=memory.used,memory.free --format=csv,noheader

echo "=== cut_only.py 切片 ==="
$V/python scripts/cut_only.py --images "$1" --out slices/

echo "=== mineru_direct.py --force-table ==="
timeout 1500 $V/python scripts/mineru_direct.py \
  --input "slices/$(basename "$1")/slices" \
  --output mineru_out/"$(basename "$1")" \
  --force-table > mineru_pilot.log 2>&1 || true
tail -15 mineru_pilot.log

echo "=== smart_merge.py ==="
$V/python scripts/smart_merge.py \
  --image "$1" \
  --slices mineru_out/"$(basename "$1")" \
  --output merged/"$(basename "$1")" 2>&1 | tail -10