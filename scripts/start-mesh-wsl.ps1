param([switch]$ProbeOnly)
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$python=Join-Path $root '.runtime/scene312-env/Scripts/python.exe'
$env:PATH='C:\Program Files\Git\cmd;C:\Program Files\nodejs;'+$env:PATH
$env:AI3D_MOCK_MODE='false'
$env:AI3D_TRELLIS_DIRECT_INPUT='true'
$env:AI3D_SKIP_MULTIVIEW_FOR_DIRECT_RECON='true'
$env:IMAGE_RECON_HEAD='trellis'
$env:SAM3_CMD='"'+$python.Replace('\','/')+'"'
$env:SAM3_REPO_DIR=Join-Path $root '.runtime/sam3'
$env:SAM3_MODEL_ID=Join-Path $root '.runtime/weights/sam3/sam3.pt'
$env:FASTVLM_CMD=$env:SAM3_CMD
$env:FASTVLM_MODEL_ID=Join-Path $root '.runtime/weights/FastVLM-0.5B'
$env:FASTVLM_MAX_NEW_TOKENS='512'
$env:TRELLIS_REPO_DIR=Join-Path $root '.runtime/TRELLIS.2'
$env:TRELLIS_CMD=$env:SAM3_CMD+' "'+(Join-Path $root 'scripts/trellis_wsl_bridge.py').Replace('\','/')+'"'
$env:TRELLIS_MODEL_PATH='microsoft/TRELLIS.2-4B'
$env:TRELLIS_RESOLUTION='1024'
$env:TRELLIS_SEED='363987120'
$env:TRELLIS_RANDOMIZE_SEED='false'
$env:TRELLIS_DECIMATION_TARGET='500000'
$env:TRELLIS_TEXTURE_SIZE='2048'
$env:TRELLIS_LOW_VRAM_MODE='true'
$env:TRELLIS_STRICT_OFFICIAL_MODE='true'
$env:TRELLIS_REQUIRE_CLEAN_REPO='true'
$env:BACKEND_HOST='127.0.0.1'
$env:BACKEND_PORT='8000'
$env:PYTHONUTF8='1'
if($ProbeOnly){& $python -m pipelines.image_to_3d.trellis_wrapper; exit $LASTEXITCODE}
if(Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue){throw 'Port 8000 already in use'}
$logs=Join-Path $root 'storage/mesh_logs';New-Item -ItemType Directory -Force $logs | Out-Null
$backend=Start-Process -FilePath $python -ArgumentList '-m','uvicorn','backend.app.main:app','--host','127.0.0.1','--port','8000' -WorkingDirectory $root -WindowStyle Hidden -PassThru -RedirectStandardOutput "$logs/backend.log" -RedirectStandardError "$logs/backend-error.log"
$worker=Start-Process -FilePath $python -ArgumentList '-m','workers.image_worker' -WorkingDirectory $root -WindowStyle Hidden -PassThru -RedirectStandardOutput "$logs/worker.log" -RedirectStandardError "$logs/worker-error.log"
Write-Output "Mesh service http://127.0.0.1:5173/prismscan-v2.html ; launcher PIDs $($backend.Id),$($worker.Id)"
