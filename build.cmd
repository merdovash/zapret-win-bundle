@echo off
REM Build script for zapret-win-bundle project
REM Builds all required components for the project

setlocal enabledelayedexpansion

cd /d "%~dp0"
set "BUILD_ROOT=%~dp0"
set "ERROR_COUNT=0"

echo ========================================
echo zapret-win-bundle Build Script
echo ========================================
echo.

REM Check if Python is available
where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not found in PATH!
    echo Please install Python 3 and ensure it's in your PATH.
    set /a ERROR_COUNT+=1
    goto :build_error
)

REM Get Python version
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYTHON_VERSION=%%v
echo Python version: %PYTHON_VERSION%
echo.

REM Step 1: Prepare GUI icons
echo [1/2] Preparing GUI icons...
echo ----------------------------------------
if exist "%BUILD_ROOT%gui\icon\prepare_icons.py" (
    cd /d "%BUILD_ROOT%gui\icon"
    python prepare_icons.py
    if errorlevel 1 (
        echo ERROR: Icon preparation failed!
        set /a ERROR_COUNT+=1
    ) else (
        echo Icon preparation completed successfully.
    )
    cd /d "%BUILD_ROOT%"
) else (
    echo ERROR: prepare_icons.py not found at gui\icon\prepare_icons.py
    set /a ERROR_COUNT+=1
)
echo.

REM Check if Pillow is installed (required for icon preparation)
python -c "import PIL" >nul 2>&1
if errorlevel 1 (
    echo WARNING: Pillow ^(PIL^) is not installed.
    echo Icon preparation requires Pillow. Install with: pip install Pillow
    echo.
)

REM Step 2: Build run.exe from winws_gui.cmd
echo [2/2] Building run.exe from winws_gui.cmd...
echo ----------------------------------------
if not exist "%BUILD_ROOT%gui\run.py" (
    echo ERROR: gui\run.py not found!
    set /a ERROR_COUNT+=1
    goto :build_complete
)

REM Check if PyInstaller is installed
python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo PyInstaller not found. Installing...
    python -m pip install pyinstaller --quiet
    if errorlevel 1 (
        echo ERROR: Failed to install PyInstaller!
        echo Please install manually with: pip install pyinstaller
        set /a ERROR_COUNT+=1
        goto :build_complete
    )
)

REM Build run.exe using PyInstaller
cd /d "%BUILD_ROOT%gui"
echo Building run.exe with PyInstaller...
set "PYINST_CMD=python -m PyInstaller --onefile --noconsole --name run --distpath %BUILD_ROOT% --workpath %BUILD_ROOT%build_temp --specpath %BUILD_ROOT%build_temp"
if exist "%BUILD_ROOT%gui\icon\icon.ico" (
    set "PYINST_CMD=%PYINST_CMD% --icon %BUILD_ROOT%gui\icon\icon.ico"
)
set "PYINST_CMD=%PYINST_CMD% run.py"
%PYINST_CMD%

if errorlevel 1 (
    echo ERROR: Failed to build run.exe!
    set /a ERROR_COUNT+=1
) else (
    if exist "%BUILD_ROOT%run.exe" (
        echo run.exe created successfully.
    ) else (
        echo ERROR: run.exe was not created!
        set /a ERROR_COUNT+=1
    )
)

cd /d "%BUILD_ROOT%" 2>nul
echo.

REM Final status
:build_complete
echo ========================================
if "!ERROR_COUNT!"=="0" (
    echo Build completed successfully!
    echo ========================================
    exit /b 0
)
if not "!ERROR_COUNT!"=="0" (
    echo Build completed with !ERROR_COUNT! error(s).
    echo ========================================
    exit /b 1
)
exit /b 0

:build_error
echo ========================================
echo Build failed!
echo ========================================
pause
exit /b 1

