# DovaGenome — Jalankan Admin Portal (analytics & katalog)
# Cara pakai: klik kanan file ini → "Run with PowerShell"
# Atau dari terminal: .\run_admin.ps1

Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }

Write-Host "Menjalankan Admin Portal (streamlit run admin_kitchen_dashboard.py) ..." -ForegroundColor Green
Write-Host "Buka di browser: http://localhost:8501" -ForegroundColor DarkGray
& $python -m streamlit run (Join-Path $PSScriptRoot "admin_kitchen_dashboard.py")