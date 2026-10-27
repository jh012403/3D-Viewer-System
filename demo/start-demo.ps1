$ErrorActionPreference='Stop'
if ($env:DEMO_MODE -ne '1') { throw 'Set $env:DEMO_MODE="1" explicitly before starting the prepared demo.' }
$repo=Split-Path $PSScriptRoot -Parent
$logDir=Join-Path $repo 'storage/obs-demo/demo-server'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
try {
  $running=Invoke-RestMethod 'http://127.0.0.1:8020/scene-api/health' -TimeoutSec 2
  if ($running.demo_mode) { Write-Output 'Prepared API is already running. Open http://127.0.0.1:5174/scene.html'; exit 0 }
} catch {}
$python=Join-Path $repo '.runtime/scene312-env/Scripts/python.exe'
$env:PYTHONUTF8='1'
$api=Start-Process -FilePath $python -ArgumentList '-u','demo/demo_server.py' -WorkingDirectory $repo -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logDir 'api.stdout.log') -RedirectStandardError (Join-Path $logDir 'api.stderr.log') -PassThru
$node='C:/Program Files/nodejs/node.exe'
$front=Start-Process -FilePath $node -ArgumentList 'frontend/node_modules/vite/bin/vite.js','--config','demo/vite.demo.mjs' -WorkingDirectory $repo -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logDir 'vite.stdout.log') -RedirectStandardError (Join-Path $logDir 'vite.stderr.log') -PassThru
Start-Sleep -Seconds 2
$children=@(Get-CimInstance Win32_Process -Filter "ParentProcessId = $($api.Id)" | Select-Object -ExpandProperty ProcessId)
@{api_pid=$api.Id;api_children=$children;frontend_pid=$front.Id;url='http://127.0.0.1:5174/scene.html'} | ConvertTo-Json | Tee-Object -FilePath (Join-Path $logDir 'processes.json')
