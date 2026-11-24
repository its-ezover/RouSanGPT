@echo off
rem Install or update RouSanGPT (double-click me). Options: -ImportData "folder"  -Yes  -DesktopShortcut
if not exist "%~dp0install.ps1" (
    echo install.ps1 was not found next to install.cmd.
    echo Extract the whole ZIP file first ^(right-click it, Extract All^), then run
    echo install.cmd from the extracted folder.
    pause
    exit /b 1
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
set RESULT=%ERRORLEVEL%
echo.
pause
exit /b %RESULT%
