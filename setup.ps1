# MinerU Skill setup script (run on new machine)
# Creates mineru-venv + installs deps. MinerU downloads PDF-Extract-Kit models on first run.
# Usage (in skill dir table-slice-parse/):
#   powershell -ExecutionPolicy Bypass -File setup.ps1
param(
    [string]$Python = "python",
    [string]$CudaIndex = "https://download.pytorch.org/whl/cu128",
    [switch]$NoCuda
)

$ErrorActionPreference = "Stop"
$SkillDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvDir = Join-Path $SkillDir "mineru-venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

Write-Host "=== MinerU Skill Setup ===" -ForegroundColor Cyan

if (Test-Path $VenvPython) {
    Write-Host "[skip] mineru-venv exists" -ForegroundColor Yellow
} else {
    Write-Host "[1/4] Creating venv: $VenvDir"
    & $Python -m venv $VenvDir
    if (-not $?) { throw "Failed to create venv" }
}

Write-Host "[2/4] Installing torch + torchvision + safetensors..."
$pip = Join-Path $VenvDir "Scripts\pip.exe"
if ($NoCuda) {
    & $pip install torch torchvision safetensors --default-timeout=120
} else {
    & $pip install torch torchvision safetensors --index-url $CudaIndex --default-timeout=120
}
if (-not $?) { throw "torch install failed" }

Write-Host "[3/4] Installing mineru[pipeline]..."
& $pip install "mineru[pipeline]" --default-timeout=120
if (-not $?) { throw "mineru install failed" }

Write-Host "[4/4] Installing system Python deps (pillow/numpy/opencv)..."
& $Python -m pip install -r (Join-Path $SkillDir "requirements.txt") --default-timeout=120
if (-not $?) { throw "system deps install failed" }

Write-Host ""
Write-Host "=== Ready ===" -ForegroundColor Green
Write-Host "MinerU venv: $VenvDir"
Write-Host "PDF-Extract-Kit models (~2.6GB) auto-download on first mineru_direct.py run."
Write-Host ""
Write-Host "Usage:"
Write-Host "  python scripts/cut_only.py --images <img> --out slices/"
Write-Host "  $VenvPython scripts/mineru_direct.py --input slices/<name>/slices --output mineru_out/<name> --force-table"
Write-Host "  python scripts/smart_merge.py --image <img> --slices mineru_out/<name> --output merged/<name>"
