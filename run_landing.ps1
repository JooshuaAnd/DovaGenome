# DovaGenome — Jalankan Landing Page Tamu
# Cara pakai: klik kanan file ini → "Run with PowerShell"
# Atau dari terminal: .\run_landing.ps1

Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }

Write-Host "Menjalankan Landing Page Tamu (streamlit run landing_page.py) ..." -ForegroundColor Green
Write-Host "Buka di browser: http://localhost:8501" -ForegroundColor DarkGray
& $python -m streamlit run (Join-Path $PSScriptRoot "landing_page.py")