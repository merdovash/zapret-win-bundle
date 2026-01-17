@echo off
REM GUI launcher for winws.exe
REM Uses elevator.exe to run with administrator privileges

REM Try to find elevator.exe in common locations
if exist "%~dp0..\tools\elevator.exe" (
    "%~dp0..\tools\elevator" "%~dp0winws_gui_launcher.cmd"
) else if exist "%~dp0..\zapret-winws\elevator.exe" (
    "%~dp0..\zapret-winws\elevator" "%~dp0winws_gui_launcher.cmd"
) else if exist "%~dp0elevator.exe" (
    "%~dp0elevator" "%~dp0winws_ggui_launcher.cmd"
) else (
    echo Error: elevator.exe not found.
    echo Please ensure elevator.exe is available in tools\ or zapret-winws\ directory.
    pause
    exit /b 1
)

