$ErrorActionPreference='Stop'
$repo=Split-Path $PSScriptRoot -Parent
$file=Join-Path $repo 'storage/obs-demo/demo-server/processes.json'
if (Test-Path -LiteralPath $file) {
  $record=Get-Content -LiteralPath $file -Raw | ConvertFrom-Json
  $ids=@($record.api_children)+@($record.api_pid,$record.frontend_pid)
  foreach ($processId in $ids) {
    if (-not $processId) {continue}
    $process=Get-CimInstance Win32_Process -Filter "ProcessId = $processId"
    if ($process -and $process.CommandLine -match 'demo[/\\](demo_server\.py|vite\.demo\.mjs)') {
      Stop-Process -Id $processId
    }
  }
}
Remove-Item Env:DEMO_MODE -ErrorAction SilentlyContinue
Write-Output 'Prepared servers stopped. Normal UI: http://127.0.0.1:5173/scene.html'
