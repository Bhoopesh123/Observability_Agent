[CmdletBinding(SupportsShouldProcess = $true)]
param(
  [int[]]$Ports = @(3005, 8000)
)

function Stop-ProcessOnPort {
  param(
    [Parameter(Mandatory = $true)]
    [int]$Port
  )

  $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
  if (-not $connections) {
    Write-Host "No listening process found on port $Port."
    return
  }

  $processIds = $connections |
    Select-Object -ExpandProperty OwningProcess -Unique |
    Where-Object { $_ -and $_ -gt 0 }

  foreach ($processId in $processIds) {
    $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if (-not $process) {
      Write-Host "Process $processId on port $Port already exited."
      continue
    }

    $target = "$($process.ProcessName) [$processId] on port $Port"
    if ($PSCmdlet.ShouldProcess($target, "Stop")) {
      try {
        Stop-Process -Id $processId -Force -ErrorAction Stop
        Write-Host "Stopped $target."
      }
      catch {
        Write-Host "Stop-Process could not stop $target. Trying WMI terminate..."
        try {
          $wmiResult = Invoke-CimMethod -ClassName Win32_Process -MethodName Terminate -Arguments @{ ProcessId = $processId } -ErrorAction Stop
          if ($wmiResult.ReturnValue -eq 0) {
            Write-Host "Stopped $target with WMI."
          }
          else {
            Write-Host "Could not stop $target. WMI return value: $($wmiResult.ReturnValue)."
          }
        }
        catch {
          Write-Host "Could not stop $target. $($_.Exception.Message)"
        }
      }
    }
  }
}

foreach ($port in $Ports) {
  Stop-ProcessOnPort -Port $port
}
