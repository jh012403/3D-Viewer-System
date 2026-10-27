$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
foreach ($service in @(@(8001,'start-scene.ps1'),@(8000,'start-mesh-wsl.ps1'))) {
    if (!(Get-NetTCPConnection -LocalPort $service[0] -State Listen -ErrorAction SilentlyContinue)) {
        & powershell -ExecutionPolicy Bypass -File (Join-Path $root ('scripts/'+$service[1]))
        if ($LASTEXITCODE -ne 0) { throw "Service launcher failed: $($service[1])" }
    }
}
Write-Output 'Check scene http://127.0.0.1:8001/scene-api/health and frontend http://127.0.0.1:5173/scene.html'
