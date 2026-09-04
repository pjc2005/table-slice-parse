#!/usr/bin/env bash
# Linux 服务器部署脚本（torch-CPU，可与其它 GPU 服务共存）
# 用法: bash setup_server.sh   (在仓库目录内执行)
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"
export HTTPS_PROXY=${HTTPS_PROXY:-http://127.0.0.1:7890}
export HTTP_PROXY=${HTTP_PROXY:-http://127.0.0.1:7890}
export ALL_PROXY=${ALL_PROXY:-socks5://127.0.0.1:7890}
export NO_PROXY=127.0.0.1,localhost
export PIP_NO_CACHE_DIR=1

echo "[1/4] venv"
python3 -m venv "$DIR/mineru-venv"
V="$DIR/mineru-venv/bin"

echo "[2/4] torch+torchvision (CPU 源) + safetensors (PyPI)"
$V/pip install -q torch torchvision --index-url https://download.pytorch.org/whl/cpu --default-timeout=180
$V/pip install -q safetensors --default-timeout=180

echo "[3/4] mineru[pipeline]"
$V/pip install -q "mineru[pipeline]" --default-timeout=180

echo "[4/4] 系统依赖 numpy/pillow/opencv"
$V/pip install -q numpy pillow opencv-python --default-timeout=180

echo "=== 版本 ==="
$V/python -V
$V/python -c "import torch;print('torch',torch.__version__,'cuda_avail=',torch.cuda.is_available())"
$V/python -c "import mineru;print('mineru ok')" 2>&1 | tail -1
echo "SETUP DONE"