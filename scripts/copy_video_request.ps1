# Fallback hvis Postman ikke kan importere collection-filen.
param([ValidateSet('Normal','Alarm','Events','Alarms','Readings','Health')][string]$Request = 'Normal')
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$collection = Get-Content -Raw -LiteralPath (Join-Path $root 'VIDEO.local.postman_collection.json') | ConvertFrom-Json
$map = @{ Normal=0; Alarm=1; Events=2; Alarms=3; Readings=4; Health=5 }
$item = $collection.item[$map[$Request]]
$key = ($collection.variable | Where-Object key -eq 'api_key').value
$base = ($collection.variable | Where-Object key -eq 'base_url').value
$url = $item.request.url.Replace('{{base_url}}', $base)
$curl = 'curl --request ' + $item.request.method + ' "' + $url + '" --header "X-API-Key: ' + $key + '"'
if ($item.request.body) {
    $body = ($item.request.body.raw | ConvertFrom-Json | ConvertTo-Json -Compress)
    $curl += ' --header "Content-Type: application/json" --data-raw ' + "'" + $body + "'"
}
Set-Clipboard -Value $curl
Write-Output "Video-request $Request er kopieret. I Postman: Import > cURL > Ctrl+V > Enter. Indholdet indeholder en privat nøgle; vis det ikke på video."
