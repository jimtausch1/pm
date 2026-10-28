@echo off
setlocal

set REPO_ROOT=%~dp0..
set DATA_DIR=%REPO_ROOT%\backend\data

if not exist "%DATA_DIR%" (
  mkdir "%DATA_DIR%"
)

echo Building Docker image pm-mvp...
docker build -t pm-mvp "%REPO_ROOT%"
if errorlevel 1 (
  echo Docker build failed.
  exit /b 1
)

echo Starting container pm-mvp on http://localhost:8000 ...
docker run --rm -d --name pm-mvp -p 127.0.0.1:8000:8000 -v "%DATA_DIR%:/app/backend/data" --env-file "%REPO_ROOT%\.env" pm-mvp
if errorlevel 1 (
  echo Docker run failed.
  exit /b 1
)

echo Container started.
