param(
    [ValidateRange(1024, 65535)]
    [int]$Port = 8000
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Project virtual environment is missing. Follow docs/C-BASELINE.md first.'
}

# Process-only overrides: never write .env or use production data/keys.
$demoRoot = Join-Path $projectRoot '.tmp\c-demo'
$overrides = @{
    APP_ENV = 'dev'
    DATABASE_URL = 'sqlite:///' + ((Join-Path $demoRoot 'app.db') -replace '\\', '/')
    UPLOAD_DIR = Join-Path $demoRoot 'uploads'
    CHROMA_DIR = Join-Path $demoRoot 'vectors'
    EMBED_PROVIDER = 'dev'
    EMBED_DIM = '256'
    VECTOR_BACKEND = 'local'
    MOCK_LLM = 'true'
    RERANK_PROVIDER = 'none'
    RELEVANCE_THRESHOLD = '0.05'
    OCR_FORMULA = 'rapid_latex'
}
$previous = @{}
foreach ($key in $overrides.Keys) {
    $previous[$key] = [Environment]::GetEnvironmentVariable($key, 'Process')
    [Environment]::SetEnvironmentVariable($key, $overrides[$key], 'Process')
}

Write-Host 'DEMO ONLY: hash embeddings + mock answers. Not real mathematical QA.'
Write-Host "API docs: http://127.0.0.1:$Port/docs ; stop with Ctrl+C."
Write-Host "Demo data: $demoRoot"
Push-Location (Join-Path $projectRoot 'backend')
try {
    & $pythonPath -X utf8 -m uvicorn app.main:app --host 127.0.0.1 --port $Port
    if ($LASTEXITCODE -ne 0) {
        throw "Backend exited with code $LASTEXITCODE. Check the log above."
    }
} finally {
    Pop-Location
    foreach ($key in $overrides.Keys) {
        [Environment]::SetEnvironmentVariable($key, $previous[$key], 'Process')
    }
}
