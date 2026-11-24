# Remove the RouSanGPT Windows app for this user.
#
#   uninstall.cmd            remove the app, keep your data (chats, course files, settings)
#   uninstall.cmd -Purge     also delete your data (asks first)
#
# Also used by Settings > Apps > RouSanGPT > Uninstall.
param([switch]$Purge)
$ErrorActionPreference = "Continue"

$Root = Join-Path $env:LOCALAPPDATA "RouSanGPT"
$Data = Join-Path $Root "data"

# Close the app if it is running
$info = Join-Path $Data "server.json"
if (Test-Path $info) {
    try {
        $port = (Get-Content $info -Raw | ConvertFrom-Json).port
        $status = Invoke-RestMethod -Uri "http://127.0.0.1:$port/api/status" -TimeoutSec 2
        if ($status.app -eq "RouSanGPT") {
            Write-Host "Closing RouSanGPT..."
            Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:$port/api/quit" -TimeoutSec 5 | Out-Null
            Start-Sleep -Seconds 3
        }
    } catch { }
}

Remove-Item -Force -ErrorAction SilentlyContinue (Join-Path ([Environment]::GetFolderPath("Programs")) "RouSanGPT.lnk")
Remove-Item -Force -ErrorAction SilentlyContinue (Join-Path ([Environment]::GetFolderPath("Desktop")) "RouSanGPT.lnk")
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\RouSanGPT"
foreach ($dir in @("app", "app.new", "venv")) {
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue (Join-Path $Root $dir)
}
Remove-Item -Force -ErrorAction SilentlyContinue (Join-Path $Root "rousangpt-console.cmd")
Write-Host "RouSanGPT was removed from this computer."

if (Test-Path $Data) {
    $delete = $false
    if ($Purge) {
        $answer = Read-Host "Also DELETE your data in $Data (chats, course files, settings, API key)? [y/N]"
        $delete = $answer -match "^[Yy]"
    }
    if ($delete) {
        Remove-Item -Recurse -Force $Root
        Write-Host "Your data was deleted."
    } else {
        Write-Host "Your data was kept in $Data"
        if (-not $Purge) { Write-Host "(run uninstall.cmd -Purge to delete it)" }
    }
} else {
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $Root
}
