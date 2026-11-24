@echo off
rem Remove RouSanGPT (double-click me). Add -Purge to also delete your data.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0uninstall.ps1" %*
echo.
pause
