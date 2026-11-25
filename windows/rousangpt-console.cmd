@echo off
chcp 65001 >nul
rem RouSanGPT with its messages shown in this window (for troubleshooting)
"%~dp0python\python.exe" -X utf8 "%~dp0app\launcher.py" --data-dir "%LOCALAPPDATA%\RouSanGPT\data" --console %*
pause
