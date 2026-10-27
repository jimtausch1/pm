$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$dataDir = Join-Path $repoRoot "backend\\data"
if (-not (Test-Path $dataDir)) {
  New-Item -ItemType Directory -Path $dataDir | Out-Null
}

Write-Host "Building Docker image pm-mvp..."
docker build -t pm-mvp $repoRoot

if ($LASTEXITCODE -ne 0) {
  throw "Docker build failed."
}

Write-Host "Starting container pm-mvp on http://localhost:8000 ..."
docker run --rm -d --name pm-mvp -p 8000:8000 -v "${dataDir}:/app/backend/data" --env-file "$repoRoot\.env" pm-mvp

if ($LASTEXITCODE -ne 0) {
  throw "Docker run failed."
}

Write-Host "Container started."
