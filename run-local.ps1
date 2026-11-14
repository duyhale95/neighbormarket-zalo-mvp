param([string]$GeminiKeyFile, [string]$GeminiModel)
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
$settingsPath = Join-Path $PSScriptRoot 'private/gemini-settings.json'
if (Test-Path -LiteralPath $settingsPath) {
    $settings = Get-Content -LiteralPath $settingsPath -Raw | ConvertFrom-Json
    if (-not $GeminiModel) { $GeminiModel = $settings.model }
    if (-not $GeminiKeyFile) { $GeminiKeyFile = Join-Path $PSScriptRoot 'private/gemini-key.xml' }
}
if ($GeminiModel) { $env:GEMINI_MODEL = $GeminiModel }
if ($GeminiKeyFile) {
    $secureKey = Import-Clixml -LiteralPath $GeminiKeyFile
    $keyPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
    try { $env:GEMINI_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($keyPointer) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($keyPointer) }
}
Write-Host ('Natural text AI configured: ' + [bool]($env:GEMINI_API_KEY -and $env:GEMINI_MODEL))
Write-Host 'API: http://127.0.0.1:8000/docs'
Write-Host 'Dashboard: http://127.0.0.1:8000/admin'
Write-Host 'Local demo keys are in private/local-config.json. Do not upload this file.'
$pythonPath = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Create .venv and install requirements first; see README.'
}
try { & $pythonPath -m uvicorn backend.app:from_environment --factory --host 127.0.0.1 --port 8000 }
finally { if ($GeminiKeyFile) { Remove-Item Env:GEMINI_API_KEY -ErrorAction SilentlyContinue } }
