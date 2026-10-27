@echo off
setlocal

for /f %%i in ('docker ps --filter "name=pm-mvp" --format "{{.Names}}"') do (
  if "%%i"=="pm-mvp" (
    echo Stopping container pm-mvp ...
    docker stop pm-mvp >nul
    echo Container stopped.
    exit /b 0
  )
)

echo Container pm-mvp is not running.
