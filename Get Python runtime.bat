@echo off
rem Get Python runtime.bat - starts get_python_runtime.ps1, which is plain text: open it in Notepad to read what it does.
rem Only needed on a PC that has no Python installed.
rem "-ExecutionPolicy Bypass" is for this one run only: it lets PowerShell run a script file that has no signature.
setlocal
cd /d "%~dp0"
echo This downloads the official Python for Windows from python.org into the folder
echo   "%CD%\python"
echo checks its SHA-256 and its digital signature (Python Software Foundation), and tries it.
echo Nothing is installed: no registry entry, no PATH change, no administrator rights.
echo To undo it later, delete the folder "python".
echo.
echo Press a key to start, or close this window to cancel.
pause >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0get_python_runtime.ps1"
echo.
pause
