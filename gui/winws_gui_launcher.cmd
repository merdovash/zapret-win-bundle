@echo off
REM Launcher script for winws_gui.py
REM This script is executed by elevator.exe with admin privileges
REM It then launches the Python GUI script

setlocal

REM Get the directory where this script is located
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

REM Check if pythonw.exe is available (runs without console window)
where pythonw.exe >nul 2>&1
if errorlevel 1 (
    REM pythonw not found, use python
    set "PYTHON_EXE=python"
) else (
    REM Use pythonw.exe which runs without console window
    set "PYTHON_EXE=pythonw"
)

REM Launch Python GUI script (already running with admin privileges)
start "" "%PYTHON_EXE%" "%SCRIPT_DIR%winws_gui.py"

endlocal
exit /b 0

