[CmdletBinding()]
param(
    [string]$LangflowExe = "C:\Users\LENOVO\langflow\.venv\Scripts\langflow.exe",
    [int]$Port = 7860,
    [string]$BackendUrl = "",
    [string]$InternalToken = "",
    [string]$TimeoutSeconds = ""
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$envPath = Join-Path $repoRoot ".env"

function Read-DotEnvValue {
    param([Parameter(Mandatory = $true)][string]$Name)

    if (-not (Test-Path -LiteralPath $envPath)) {
        return ""
    }
    $line = Get-Content -LiteralPath $envPath | Where-Object {
        $_ -match ("^" + [regex]::Escape($Name) + "=")
    } | Select-Object -Last 1
    if ($null -eq $line) {
        return ""
    }
    $value = ($line -split "=", 2)[1].Trim()
    if ($value.Length -ge 2 -and $value.StartsWith('"') -and $value.EndsWith('"')) {
        $value = $value.Substring(1, $value.Length - 2)
    }
    return $value.Trim()
}

if ([string]::IsNullOrWhiteSpace($BackendUrl)) {
    $BackendUrl = Read-DotEnvValue "DOVAGENOME_BACKEND_URL"
}
if ([string]::IsNullOrWhiteSpace($BackendUrl)) {
    # Local development default; pass -BackendUrl to reach a container or remote API.
    $BackendUrl = "http://127.0.0.1:8000"
}
if ([string]::IsNullOrWhiteSpace($InternalToken)) {
    $InternalToken = Read-DotEnvValue "DOVAGENOME_INTERNAL_TOKEN"
}
if ([string]::IsNullOrWhiteSpace($InternalToken)) {
    # The project documents LANGFLOW_INTERNAL_TOKEN as the same shared secret.
    $InternalToken = Read-DotEnvValue "LANGFLOW_INTERNAL_TOKEN"
}
if ([string]::IsNullOrWhiteSpace($TimeoutSeconds)) {
    $TimeoutSeconds = Read-DotEnvValue "DOVAGENOME_LIVE_TIMEOUT_SECONDS"
}
if ([string]::IsNullOrWhiteSpace($TimeoutSeconds)) {
    $TimeoutSeconds = Read-DotEnvValue "LANGFLOW_TIMEOUT_SECONDS"
}

if ([string]::IsNullOrWhiteSpace($BackendUrl)) {
    throw "DOVAGENOME_BACKEND_URL wajib diisi lewat .env atau -BackendUrl."
}
if ([string]::IsNullOrWhiteSpace($InternalToken)) {
    throw "DOVAGENOME_INTERNAL_TOKEN/LANGFLOW_INTERNAL_TOKEN wajib diisi lewat .env atau -InternalToken."
}
if ([string]::IsNullOrWhiteSpace($TimeoutSeconds)) {
    throw "DOVAGENOME_LIVE_TIMEOUT_SECONDS atau LANGFLOW_TIMEOUT_SECONDS wajib diisi lewat .env atau -TimeoutSeconds."
}
$timeout = 0.0
if (-not [double]::TryParse($TimeoutSeconds, [System.Globalization.NumberStyles]::Float, [System.Globalization.CultureInfo]::InvariantCulture, [ref]$timeout) -or $timeout -le 0) {
    throw "Timeout Langflow harus berupa angka positif."
}
if (-not (Test-Path -LiteralPath $LangflowExe)) {
    throw "Executable Langflow tidak ditemukan: $LangflowExe"
}
if ($Port -lt 1 -or $Port -gt 65535) {
    throw "Port Langflow tidak valid."
}

$env:DOVAGENOME_BACKEND_URL = $BackendUrl.Trim().TrimEnd('/')
$env:DOVAGENOME_INTERNAL_TOKEN = $InternalToken
$env:LANGFLOW_INTERNAL_TOKEN = $InternalToken
$env:DOVAGENOME_LIVE_TIMEOUT_SECONDS = $TimeoutSeconds
$env:LANGFLOW_TIMEOUT_SECONDS = $TimeoutSeconds

Write-Host "Starting Langflow LIVE on port $Port (backend URL configured; token withheld; timeout $TimeoutSeconds s)."
& $LangflowExe run --port $Port
exit $LASTEXITCODE
