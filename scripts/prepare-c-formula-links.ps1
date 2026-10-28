# Reuse existing original-repository models in this integration worktree.
# No downloads, dependency installs, source copies, or existing-path replacement.
$ErrorActionPreference = 'Stop'
$workspaceRoot = Split-Path -Parent $PSScriptRoot
$originalRoot = (Resolve-Path (Join-Path $workspaceRoot '../..')).Path
foreach ($relative in @('.venv-formula','data/models/formula-onnx')) {
    $sourcePath = Join-Path $originalRoot $relative
    $targetPath = Join-Path $workspaceRoot $relative
    if (-not (Test-Path -LiteralPath $sourcePath)) { throw "Existing formula resource missing: $sourcePath" }
    if (Test-Path -LiteralPath $targetPath) { Write-Output "Preserved existing path: $targetPath"; continue }
    New-Item -ItemType Directory -Path (Split-Path -Parent $targetPath) -Force | Out-Null
    New-Item -ItemType Junction -Path $targetPath -Target $sourcePath | Out-Null
    Write-Output "Linked existing resource: $targetPath"
}
