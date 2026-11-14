param([switch]$InitializeOnly)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$pythonPath = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
$configPath = Join-Path $PSScriptRoot 'private/local-config.json'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Create .venv and install requirements.txt first.' }
if (-not (Test-Path -LiteralPath $configPath)) { throw 'Run .\run-local.ps1 first to initialize backend demo keys.' }
$config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
if (-not $config.intake_key) {
    $bytes = New-Object byte[] 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    $config | Add-Member -NotePropertyName intake_key -NotePropertyValue ([BitConverter]::ToString($bytes).Replace('-', '').ToLowerInvariant())
    $config | ConvertTo-Json | Set-Content -LiteralPath $configPath -Encoding utf8
}
if ($config.intake_key -eq $config.bridge_key -or $config.intake_key -eq $config.admin_key) {
    throw 'Intake, bridge and admin keys must be distinct. Correct private config locally.'
}
if ($InitializeOnly) {
    Write-Host 'Distinct intake key initialized; existing backend keys preserved. No listener or Zalo connection started.'
    return
}
$channelPath = Join-Path $PSScriptRoot 'private/zalo-channel.json'
if (-not (Test-Path -LiteralPath $channelPath)) { throw 'Generate validated private/zalo-channel.json with tools/build_deplao_workflows.py first.' }
$channel = Get-Content -LiteralPath $channelPath -Raw | ConvertFrom-Json
if ($channel.account_id -notmatch '^[0-9]{1,100}$' -or -not $channel.sender_ids -or
    ($channel.policy_validated -isnot [bool]) -or -not $channel.policy_validated -or
    ($channel.strict_account_binding_verified -isnot [bool]) -or -not $channel.strict_account_binding_verified) {
    throw 'Invalid/unvalidated trusted channel configuration.'
}
$env:BACKEND_URL = 'http://127.0.0.1:8000'
$env:BRIDGE_API_KEY = $config.bridge_key
$env:INTAKE_API_KEY = $config.intake_key
$env:COMMUNITY_ID = $channel.community_id
$env:ZALO_ACCOUNT_ID = $channel.account_id
$env:ZALO_TEST_SENDER_IDS = $channel.sender_ids -join ','
$env:ZALO_IMAGES_ENABLED = if ($channel.images_enabled -eq $true) { 'true' } else { 'false' }
Write-Host 'Trusted intake: http://127.0.0.1:8001; Zalo connection remains unverified.'
& $pythonPath -m uvicorn backend.intake_bridge:from_environment --factory --host 127.0.0.1 --port 8001
