$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
New-Item -ItemType Directory -Path (Join-Path $PSScriptRoot 'private') -Force | Out-Null
Write-Host 'Use a NEW OpenAI API key. Do not paste the key into chat.'
$moderationKey = Read-Host 'New OpenAI API key (hidden)' -AsSecureString
if ($moderationKey.Length -lt 10) { throw 'No valid key entered.' }
$moderationKey | Export-Clixml -LiteralPath (Join-Path $PSScriptRoot 'private/moderation-key.xml')
Write-Host 'Saved with Windows DPAPI for this user. Restart run-local.ps1 to load it. Key not printed.'
