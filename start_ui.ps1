$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $RootDir "backend"
$FrontendDir = Join-Path $RootDir "frontend"
$BackendPython = Join-Path $BackendDir ".venv\Scripts\python.exe"
$NpmCmd = "C:\Program Files\nodejs\npm.cmd"

Start-Process `
  -FilePath $BackendPython `
  -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000") `
  -WorkingDirectory $BackendDir `
  -WindowStyle Hidden

Start-Process `
  -FilePath $NpmCmd `
  -ArgumentList @("run", "dev", "--", "--host", "127.0.0.1", "--port", "3005") `
  -WorkingDirectory $FrontendDir `
  -WindowStyle Hidden

Write-Host "Observability Agent backend:  http://127.0.0.1:8000"
Write-Host "Observability Agent frontend: http://127.0.0.1:3005"
