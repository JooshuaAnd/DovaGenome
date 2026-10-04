# DovaGenome — Jalankan Papan Kerja Dapur
# Cara pakai: klik kanan file ini → "Run with PowerShell"
# Untuk Admin Portal: .\run_admin.ps1
# Untuk Landing Page : .\run_landing.ps1

Set-Location $PSScriptRoot

$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$sysPython  = Get-Command python -ErrorAction SilentlyContinue

if (Test-Path $venvPython) {
    Write-Host "Menjalankan Papan Kerja Dapur via .venv ..." -ForegroundColor Green
    & $venvPython -m streamlit run (Join-Path $PSScriptRoot "kitchen_dashboard.py")
} elseif ($sysPython) {
    Write-Host "Menjalankan Papan Kerja Dapur via python sistem ..." -ForegroundColor Green
    python -m streamlit run (Join-Path $PSScriptRoot "kitchen_dashboard.py")
} else {
    Write-Host "Python tidak ditemukan. Pasang Streamlit dulu:" -ForegroundColor Yellow
    Write-Host "  pip install -r requirements.txt" -ForegroundColor Yellow
    Read-Host "Tekan Enter untuk keluar"
}