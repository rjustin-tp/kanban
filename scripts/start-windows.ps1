$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Resolve-Path (Join-Path $ScriptDir "..")
$ImageName = "pm-mvp"
$ContainerName = "pm-mvp-app"
$EnvFile = Join-Path $RootDir ".env"

Write-Host "Building Docker image..."
docker build -t $ImageName $RootDir | Out-Null

$existing = docker ps -a --format "{{.Names}}" | Where-Object { $_ -eq $ContainerName }
if ($existing) {
  Write-Host "Removing existing container..."
  docker rm -f $ContainerName | Out-Null
}

Write-Host "Starting container..."
docker run -d --name $ContainerName -p 8000:8000 --env-file $EnvFile $ImageName | Out-Null

Write-Host "App is running at http://127.0.0.1:8000"
