param([string]$Address)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
if (-not $Address) {
    $network = Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway -and $_.NetAdapter.Status -eq 'Up' } | Select-Object -First 1
    $Address = $network.IPv4Address.IPAddress
}
$parsed = $null
if (-not [System.Net.IPAddress]::TryParse($Address, [ref]$parsed) -or $parsed.AddressFamily -ne 'InterNetwork') {
    throw 'Kunne ikke finde en IPv4-adresse. Brug -Address med computerens lokale IP.'
}
$bytes = $parsed.GetAddressBytes()
$isPrivate = $bytes[0] -eq 10 -or ($bytes[0] -eq 172 -and $bytes[1] -ge 16 -and $bytes[1] -le 31) -or ($bytes[0] -eq 192 -and $bytes[1] -eq 168)
if (-not $isPrivate) { throw 'LAN-demoen kræver en privat lokal IPv4-adresse.' }
if (-not (Get-NetIPAddress -IPAddress $Address -ErrorAction SilentlyContinue)) { throw 'Adressen tilhører ikke denne computer.' }
$envFile = Join-Path $projectRoot '.env'
$content = [System.IO.File]::ReadAllText($envFile)
if ($content -match '(?m)^LAN_HOST=') { $content = [regex]::Replace($content, '(?m)^LAN_HOST=.*', "LAN_HOST=$Address") }
else { $content = $content.TrimEnd() + "`nLAN_HOST=$Address`n" }
if ($content -notmatch '(?m)^LAN_HTTPS_PORT=') { $content = $content.TrimEnd() + "`nLAN_HTTPS_PORT=8443`n" }
[System.IO.File]::WriteAllText($envFile, $content, [System.Text.UTF8Encoding]::new($false))
$env:LAN_HOST = $Address
& docker compose -f compose.yaml -f compose.lan.yaml config --quiet
if ($LASTEXITCODE -ne 0) { throw 'LAN-konfiguration kunne ikke valideres.' }
& docker compose -f compose.yaml -f compose.lan.yaml up -d --wait --wait-timeout 180
if ($LASTEXITCODE -ne 0) { throw 'LAN-services kunne ikke startes.' }
New-Item -ItemType Directory -Path (Join-Path $projectRoot 'certs') -Force | Out-Null
$copied = $false
for ($attempt = 0; $attempt -lt 15; $attempt++) {
    & docker compose -f compose.yaml -f compose.lan.yaml cp gateway:/data/caddy/pki/authorities/local/root.crt certs/iot-local-root.crt 2>$null
    if ($LASTEXITCODE -eq 0) { $copied = $true; break }
    Start-Sleep -Seconds 2
}
if (-not $copied) { throw 'Kunne ikke hente det offentlige rodcertifikat.' }
$portLine = ($content -split "`n" | Where-Object { $_.StartsWith('LAN_HTTPS_PORT=') })
$port = ($portLine -split '=', 2)[1].Trim()
Write-Output "HTTPS klar på https://${Address}:$port/docs"
Write-Output 'Rodcertifikat: certs/iot-local-root.crt. Del kun denne offentlige certifikatfil, aldrig private nøgler.'
Write-Output 'Åbn firewall med scripts/enable_lan_firewall.ps1 som administrator før test fra en anden computer.'
