@echo off
rem Install or update RouSanGPT (double-click me). Options: -ImportData "folder"  -Yes  -DesktopShortcut
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
echo.
pause
