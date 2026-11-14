$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
function New-DemoKey {
    # Instance RNG and BitConverter work on Windows PowerShell 5.1 and PowerShell 7.
    $bytes = New-Object byte[] 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($bytes)
    }
    finally {
        $rng.Dispose()
    }
    return [BitConverter]::ToString($bytes).Replace('-', '').ToLowerInvariant()
}
$pythonPath = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Python virtual environment not found. Run: python -m venv .venv; .\.venv\Scripts\python.exe -m pip install -r requirements.txt'
}
$configPath = Join-Path $PSScriptRoot 'private/local-config.json'
if (-not (Test-Path -LiteralPath $configPath)) {
    New-Item -ItemType Directory -Path (Join-Path $PSScriptRoot 'private') -Force | Out-Null
    $config = @{
        bridge_key = New-DemoKey
        admin_key = New-DemoKey
    }
    $config | ConvertTo-Json | Set-Content -LiteralPath $configPath -Encoding utf8
}
$config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
$env:BRIDGE_API_KEY = $config.bridge_key
$env:ADMIN_API_KEY = $config.admin_key
$env:DATABASE_PATH = Join-Path $PSScriptRoot 'private/market.db'
# Group, community and optional AI settings are inherited from the caller.
if ([string]::IsNullOrWhiteSpace($env:ZALO_LEGIT_GROUP_ID)) {
    Write-Warning 'No group configured: approved listings will not create delivery jobs. Set ZALO_LEGIT_GROUP_ID before starting.'
}
Write-Host 'API: http://127.0.0.1:8000/docs'
Write-Host 'Local demo keys are in private/local-config.json. Do not upload this file.'
& $pythonPath -m uvicorn backend.app:from_environment --factory --host 127.0.0.1 --port 8000
