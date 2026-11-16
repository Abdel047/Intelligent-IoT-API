# Kopiér dashboardpasswordet uden at udskrive det. Brug før skærmoptagelse.
$root = Split-Path -Parent $PSScriptRoot
$line = Get-Content -LiteralPath (Join-Path $root '.env') | Where-Object { $_.StartsWith('DASHBOARD_PASSWORD=') } | Select-Object -First 1
if (-not $line) { throw 'Kør scripts/prepare_env.py først.' }
$passwordValue = $line.Substring('DASHBOARD_PASSWORD='.Length).Trim()
if ($passwordValue.Length -lt 16) { throw 'Dashboard-adgangskoden mangler eller er for kort.' }
Set-Clipboard -Value $passwordValue
Write-Output 'Dashboard-adgangskode kopieret. Indsæt den kun i dashboardets loginfelt.'
