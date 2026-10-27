@echo off
setlocal

set REPO_ROOT=%~dp0..

echo Building Docker image pm-mvp...
docker build -t pm-mvp "%REPO_ROOT%"
if errorlevel 1 (
  echo Docker build failed.
  exit /b 1
)

echo Starting container pm-mvp on http://localhost:8000 ...
docker run --rm -d --name pm-mvp -p 8000:8000 pm-mvp
if errorlevel 1 (
  echo Docker run failed.
  exit /b 1
)

echo Container started.
