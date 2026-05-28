# Shared Memory Skill Installer (Windows)
# Usage: powershell -ExecutionPolicy Bypass -File install.ps1

param(
    [switch]$SkipInit = $false
)

$ErrorActionPreference = "Stop"
Write-Host ""
Write-Host "=== Shared Memory System Installer ===" -ForegroundColor Cyan
Write-Host "Cross-tool memory for Codex, Claude, Hermes"
Write-Host ""

# 1. Find Python
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    $python = Get-Command python3 -ErrorAction SilentlyContinue
}
if (-not $python) {
    @"
Python not found in PATH!
Install Python 3.11+ from https://python.org and try again.
"@ | Write-Host -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Python: $($python.Source)" -ForegroundColor Green

# 2. Install package
$repoDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Write-Host "[..] Installing shared-memory package..." -ForegroundColor Yellow
pip install -e "$repoDir" --quiet 2>&1 | Out-Null
Write-Host "[OK] Package installed" -ForegroundColor Green

# 3. Verify
$smPath = Get-Command sm -ErrorAction SilentlyContinue
if ($smPath) {
    Write-Host "[OK] CLI: $($smPath.Source)" -ForegroundColor Green
} else {
    Write-Host "[WARN] sm CLI not found in PATH (pip scripts may not be on PATH)" -ForegroundColor Yellow
    Write-Host "       Try: python -m shared_memory.cli.main"
}

# 4. Run init unless skipped
if (-not $SkipInit) {
    Write-Host "[..] Running sm init..." -ForegroundColor Yellow
    python -m shared_memory.cli.main init 2>&1
}

Write-Host ""
Write-Host "[DONE] Shared memory system installed!" -ForegroundColor Green
Write-Host ""
Write-Host "Quick test:" -ForegroundColor Cyan
Write-Host "  sm remember 'hello world' --layer profile"
Write-Host "  sm recall hello"
Write-Host "  sm status"
