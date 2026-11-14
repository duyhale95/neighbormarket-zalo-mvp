$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$configPath = Join-Path $PSScriptRoot 'private/local-config.json'
if (-not (Test-Path -LiteralPath $configPath)) {
    New-Item -ItemType Directory -Path (Join-Path $PSScriptRoot 'private') -Force | Out-Null
    $config = @{
        bridge_key = [Convert]::ToHexString([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
        admin_key = [Convert]::ToHexString([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
    }
    $config | ConvertTo-Json | Set-Content -LiteralPath $configPath -Encoding utf8
}
$config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
$env:BRIDGE_API_KEY = $config.bridge_key
$env:ADMIN_API_KEY = $config.admin_key
$env:DATABASE_PATH = Join-Path $PSScriptRoot 'private/market.db'
Write-Host 'API: http://127.0.0.1:8000/docs'
Write-Host 'Local demo keys are in private/local-config.json. Do not upload this file.'
python -m uvicorn backend.app:from_environment --factory --host 127.0.0.1 --port 8000
