#!/usr/bin/env python3
"""
Wrapper script for winws_gui.cmd functionality
This script is built into run.exe using PyInstaller
"""

import sys
import os
import subprocess
from pathlib import Path

def get_script_dir():
    """Get the directory where the script is located (works with PyInstaller)"""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable (PyInstaller)
        return Path(sys.executable).parent
    else:
        # Running as script
        return Path(__file__).parent

def find_elevator():
    """Find elevator.exe in common locations"""
    script_dir = get_script_dir()
    # Determine project root: if gui/ directory exists in script_dir, we're in project root
    # Otherwise, we might be in gui/ directory, so try parent
    if (script_dir / "gui").is_dir():
        project_root = script_dir
    elif script_dir.parent and (script_dir.parent / "gui").is_dir():
        project_root = script_dir.parent
    else:
        # Fallback: assume script_dir is project root
        project_root = script_dir
    
    elevator_paths = [
        project_root / "tools" / "elevator.exe",
        project_root / "zapret-winws" / "elevator.exe",
        script_dir / "elevator.exe",
    ]
    
    for elevator_path in elevator_paths:
        if elevator_path.exists():
            return elevator_path
    
    return None

def find_launcher():
    """Find winws_gui_launcher.cmd"""
    script_dir = get_script_dir()
    # Try both locations: gui/ subdirectory or current directory
    launcher_paths = [
        script_dir / "gui" / "winws_gui_launcher.cmd",
        script_dir / "winws_gui_launcher.cmd",
    ]
    
    for launcher in launcher_paths:
        if launcher.exists():
            return launcher
    
    return None

def show_error(message):
    """Show error message - uses message box if no console available"""
    if sys.stdout and sys.stdout.isatty():
        # Console is available
        print(message, file=sys.stderr)
        input("Press Enter to exit...")
    else:
        # No console - try to show message box (Windows only)
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, message, "Error", 0x10)  # MB_ICONERROR
        except Exception:
            # Fallback: just exit silently
            pass

def main():
    """Main entry point - mimics winws_gui.cmd behavior"""
    elevator = find_elevator()
    if not elevator:
        show_error("Error: elevator.exe not found.\n\nPlease ensure elevator.exe is available in tools\\ or zapret-winws\\ directory.")
        sys.exit(1)
    
    launcher = find_launcher()
    if not launcher:
        show_error("Error: winws_gui_launcher.cmd not found.")
        sys.exit(1)
    
    # Run elevator.exe with launcher script
    try:
        subprocess.run([str(elevator), str(launcher)], check=False)
    except Exception as e:
        show_error(f"Error running elevator: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

