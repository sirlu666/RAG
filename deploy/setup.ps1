param([switch]$Demo)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot '.venv-deploy/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    py -3.12 -m venv (Join-Path $repoRoot '.venv-deploy')
    if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.12 first.' }
    & $python -X utf8 -m pip install torch --index-url https://download.pytorch.org/whl/cpu
    if ($LASTEXITCODE -ne 0) { throw 'CPU torch installation failed.' }
    & $python -X utf8 -m pip install -r (Join-Path $repoRoot 'backend/requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed; see output.' }
}
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'frontend/dist/index.html'))) {
    Push-Location (Join-Path $repoRoot 'frontend')
    try {
        npm.cmd ci
        if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
        npm.cmd run build
        if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
    } finally { Pop-Location }
}
$settings = Join-Path $repoRoot 'deploy/deploy.env'
if (-not (Test-Path -LiteralPath $settings)) {
    Copy-Item -LiteralPath (Join-Path $repoRoot 'deploy/deploy.env.example') -Destination $settings
}
if ($Demo) { & $python -X utf8 (Join-Path $repoRoot 'deploy/run.py') --demo }
else { & $python -X utf8 (Join-Path $repoRoot 'deploy/run.py') --download-models }
if ($LASTEXITCODE -ne 0) { throw 'Deployment did not start; see output above.' }
