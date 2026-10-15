param([switch]$LegacyEnvironment)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$environment = if ($LegacyEnvironment) { 'scene-env' } else { 'scene312-env' }
$pythonPath = Join-Path $projectRoot ".runtime/$environment/Scripts/python.exe"
$nodePath = 'C:\Program Files\nodejs\node.exe'
if (!(Test-Path -LiteralPath $pythonPath)) { throw "Missing environment: $pythonPath" }
foreach ($port in @(8001, 5173)) {
  if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) { throw "Port $port already in use. Stop the existing scene server first." }
}
$logRoot = Join-Path $projectRoot 'storage/scene_logs'
New-Item -ItemType Directory -Force -Path $logRoot | Out-Null
$backend = Start-Process -FilePath $pythonPath -ArgumentList '-m','uvicorn','pipelines.scene.server:app','--host','127.0.0.1','--port','8001' -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput "$logRoot/backend.log" -RedirectStandardError "$logRoot/backend-error.log"
$frontend = Start-Process -FilePath $nodePath -ArgumentList 'node_modules/vite/bin/vite.js','--host','127.0.0.1','--port','5173','--strictPort' -WorkingDirectory "$projectRoot/frontend" -WindowStyle Hidden -PassThru -RedirectStandardOutput "$logRoot/frontend.log" -RedirectStandardError "$logRoot/frontend-error.log"
Write-Output "Scene: http://127.0.0.1:5173/scene.html?scene=sunroom"
Write-Output "Stop only these processes when finished: Stop-Process -Id $($backend.Id),$($frontend.Id)"
