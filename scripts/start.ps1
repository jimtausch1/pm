$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot

Write-Host "Building Docker image pm-mvp..."
docker build -t pm-mvp $repoRoot

if ($LASTEXITCODE -ne 0) {
  throw "Docker build failed."
}

Write-Host "Starting container pm-mvp on http://localhost:8000 ..."
docker run --rm -d --name pm-mvp -p 8000:8000 pm-mvp

if ($LASTEXITCODE -ne 0) {
  throw "Docker run failed."
}

Write-Host "Container started."
