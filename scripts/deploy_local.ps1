# Kontrolleret lokal deployment af de kildefiler, der allerede er i projektmappen.
param([switch]$Lan)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path -LiteralPath '.env')) { throw 'Kør scripts/prepare_env.py først.' }
$composeArgs = @('compose', '-f', 'compose.yaml')
if ($Lan) { $composeArgs += @('-f', 'compose.lan.yaml') }
& docker @composeArgs config --quiet
if ($LASTEXITCODE -ne 0) { throw 'Compose-konfiguration fejlede; deployment afbrudt.' }
& docker @composeArgs up --build -d --wait --wait-timeout 180
if ($LASTEXITCODE -ne 0) { throw 'Deployment fejlede; kontrollér containerstatus. Volumes er ikke slettet.' }
$apiPort = '8000'
Get-Content -LiteralPath '.env' | ForEach-Object {
    if ($_ -match '^API_PORT=(.+)$') { $apiPort = $matches[1].Trim() }
}
$health = Invoke-RestMethod -Uri "http://127.0.0.1:$apiPort/health"
if ($health.status -ne 'ok') { throw 'Database-healthcheck bestod ikke.' }
Write-Output 'Lokal deployment gennemført. API og database er klar, og volume er bevaret.'
