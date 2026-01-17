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
echo [1/1] Preparing GUI icons...
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
    echo WARNING: Pillow (PIL) is not installed.
    echo Icon preparation requires Pillow. Install with: pip install Pillow
    echo.
)

REM Final status
:build_complete
echo ========================================
if %ERROR_COUNT%==0 (
    echo Build completed successfully!
    echo ========================================
    exit /b 0
) else (
    echo Build completed with %ERROR_COUNT% error(s).
    echo ========================================
    exit /b 1
)

:build_error
echo ========================================
echo Build failed!
echo ========================================
pause
exit /b 1

