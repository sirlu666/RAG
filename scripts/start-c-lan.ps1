param(
    [Parameter(Mandatory = $true)]
    [string]$Address
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$parsedAddress = $null
if (-not [System.Net.IPAddress]::TryParse($Address, [ref]$parsedAddress) -or
    $parsedAddress.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork) {
    throw 'Address must be a local physical adapter IPv4 address.'
}
$adapterIndexes = @(Get-NetAdapter -Physical | Where-Object Status -eq 'Up' | Select-Object -ExpandProperty ifIndex)
$localAddress = Get-NetIPAddress -AddressFamily IPv4 | Where-Object {
    $_.IPAddress -eq $Address -and $_.InterfaceIndex -in $adapterIndexes
}
if (-not $localAddress) {
    throw 'Address must belong to an active physical adapter; VPN and wildcard addresses are not supported.'
}
if (Get-NetTCPConnection -LocalAddress $Address -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue) {
    throw 'The LAN frontend is already listening on this address. Reuse it rather than starting another instance.'
}
$previousHost = $env:MATHRAG_LAN_HOST
try {
    $env:MATHRAG_LAN_HOST = $Address
    Push-Location (Join-Path $projectRoot 'frontend')
    try {
        Write-Host "LAN browser URL: http://${Address}:5173/ ; stop with Ctrl+C."
        Write-Host 'Use a trusted local network only. Backend remains on 127.0.0.1:8000.'
        & npm.cmd run dev
        if ($LASTEXITCODE -ne 0) { throw "LAN frontend exited with code $LASTEXITCODE." }
    } finally {
        Pop-Location
    }
} finally {
    $env:MATHRAG_LAN_HOST = $previousHost
}
