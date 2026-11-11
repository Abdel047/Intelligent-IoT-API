# Kør som administrator. Åbner kun HTTPS-porten fra det lokale subnet.
param([switch]$Remove)
try {
$ErrorActionPreference = 'Stop'
$ruleName = 'Intelligent-IoT-HTTPS-LAN'
$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) { throw 'Kør dette script i PowerShell som administrator.' }
if ($Remove) {
    Get-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue | Remove-NetFirewallRule
    Write-Output 'LAN-firewallreglen er fjernet.'
    exit
}
$values = @{}
Get-Content -LiteralPath (Join-Path (Split-Path -Parent $PSScriptRoot) '.env') | ForEach-Object {
    if ($_ -match '^([A-Z_]+)=(.*)$') { $values[$matches[1]] = $matches[2].Trim() }
}
$address = $values['LAN_HOST']
$port = [int]$values['LAN_HTTPS_PORT']
if ($port -lt 1024 -or $port -gt 65535) { throw 'LAN-port skal være mellem 1024 og 65535.' }
if (-not (Get-NetIPAddress -IPAddress $address -ErrorAction SilentlyContinue)) { throw 'LAN_HOST er ikke en lokal IP-adresse.' }
$existing = Get-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue
if ($existing) {
    $existing | Set-NetFirewallRule -Enabled True -Direction Inbound -Action Allow -Profile Any
    $existing | Get-NetFirewallPortFilter | Set-NetFirewallPortFilter -Protocol TCP -LocalPort $port
    $existing | Get-NetFirewallAddressFilter | Set-NetFirewallAddressFilter -LocalAddress $address -RemoteAddress LocalSubnet
} else {
    New-NetFirewallRule -Name $ruleName -DisplayName 'Intelligent IoT: HTTPS fra lokalnet' -Direction Inbound -Action Allow -Protocol TCP -LocalAddress $address -LocalPort $port -RemoteAddress LocalSubnet -Profile Any | Out-Null
}
Write-Output "Firewall klar: kun TCP $port på $address fra LocalSubnet. Databaseporten er ikke åbnet."

    @{ status = 'ok' } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'firewall-status.local.json')
} catch {
    @{ status = 'error'; message = $_.Exception.Message } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'firewall-status.local.json')
    exit 1
}
