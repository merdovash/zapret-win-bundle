@echo off
REM Launcher script for winws_gui.py
REM This script is executed by elevator.exe with admin privileges
REM It then launches the Python GUI script

setlocal

REM Get the directory where this script is located
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

REM Set log file path
set "LOG_FILE=%SCRIPT_DIR%winws_gui_error.log"

REM Check if pythonw.exe is available (runs without console window)
where pythonw.exe >nul 2>&1
if errorlevel 1 (
    REM pythonw not found, write error to log and exit
    (
        echo.
        echo ========================================
        echo Error: pythonw.exe not found in PATH
        echo Timestamp: %DATE% %TIME%
        echo Please ensure Python is installed and added to PATH.
        echo ========================================
    ) >> "%LOG_FILE%"
    exit /b 1
) else (
    REM Use pythonw.exe which runs without console window
    set "PYTHON_EXE=pythonw"
)

REM Launch Python GUI script (already running with admin privileges)
REM Redirect stdout and stderr to log file
start "" "%PYTHON_EXE%" "%SCRIPT_DIR%winws_gui.py" > "%LOG_FILE%" 2>&1
set "EXIT_CODE=%ERRORLEVEL%"

REM If launch failed, write error info to log file
if not "%EXIT_CODE%"=="0" (
    (
        echo.
        echo ========================================
        echo GUI launch failed with exit code: %EXIT_CODE%
        echo Timestamp: %DATE% %TIME%
        echo ========================================
    ) >> "%LOG_FILE%"
    exit /b %EXIT_CODE%
)

endlocal
exit /b 0

