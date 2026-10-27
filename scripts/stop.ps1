$ErrorActionPreference = "Stop"

$containerName = "pm-mvp"

$running = docker ps --filter "name=$containerName" --format "{{.Names}}"
if ($running -match "^$containerName$") {
  Write-Host "Stopping container $containerName ..."
  docker stop $containerName | Out-Null
  Write-Host "Container stopped."
} else {
  Write-Host "Container $containerName is not running."
}
