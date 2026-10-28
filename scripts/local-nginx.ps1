param([ValidateSet('Check','Start','Reload','Stop')][string]$Action = 'Check')
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$runtimeRoot = Join-Path $env:LOCALAPPDATA 'MathRAG\runtime'
$nginxExe = Join-Path $runtimeRoot 'nginx-1.31.8\nginx.exe'
$instanceRoot = Join-Path $runtimeRoot 'mathrag-local'
$instancePrefix = $instanceRoot.Replace('\','/') + '/'
if (-not (Test-Path -LiteralPath $nginxExe)) { throw 'Official nginx/Windows 1.31.8 runtime not found.' }
if ($Action -in @('Check','Start','Reload')) {
    if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'frontend\dist\index.html'))) { throw 'Build frontend first.' }
    foreach ($name in @('logs','conf','html','temp')) { New-Item -ItemType Directory -Path (Join-Path $instanceRoot $name) -Force | Out-Null }
    # Nginx Windows cannot consume this workspace Unicode prefix. Copy only generated static assets.
    Get-ChildItem -LiteralPath (Join-Path $repoRoot 'frontend\dist') | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $instanceRoot 'html') -Recurse -Force
    }
    $config = [IO.File]::ReadAllText((Join-Path $repoRoot 'deploy\nginx-local.conf'))
    $config = $config.Replace('root frontend/dist;', 'root html;')
    [IO.File]::WriteAllText((Join-Path $instanceRoot 'conf\mathrag.conf'), $config, [Text.UTF8Encoding]::new($false))
    & $nginxExe -p $instancePrefix -c conf/mathrag.conf -t
    if ($LASTEXITCODE -ne 0) { throw 'nginx configuration check failed; nothing started.' }
}
if ($Action -eq 'Start') {
    if (Get-NetTCPConnection -State Listen -LocalPort 8086 -ErrorAction SilentlyContinue) { throw 'Port 8086 occupied; nothing stopped.' }
    Start-Process -FilePath $nginxExe -ArgumentList @('-p', $instancePrefix, '-c', 'conf/mathrag.conf') -WorkingDirectory $instanceRoot -WindowStyle Hidden
} elseif ($Action -in @('Reload','Stop')) {
    $masterId = [int]([IO.File]::ReadAllText((Join-Path $instanceRoot 'logs\mathrag-nginx.pid')).Trim())
    $master = Get-CimInstance Win32_Process -Filter "ProcessId=$masterId"
    if (-not $master -or $master.ExecutablePath -ne $nginxExe -or $master.CommandLine -notlike '*conf/mathrag.conf*') { throw 'Nginx master identity mismatch.' }
    $signal = if ($Action -eq 'Stop') { 'quit' } else { 'reload' }
    & $nginxExe -p $instancePrefix -c conf/mathrag.conf -s $signal
    if ($LASTEXITCODE -ne 0) { throw 'Nginx control command failed.' }
}
Write-Output "Nginx $Action completed. Runtime: $instanceRoot"
