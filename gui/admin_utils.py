#!/usr/bin/env python3
"""
Utility functions for checking and requesting administrator privileges on Windows
"""

import sys
import os
import ctypes
import subprocess
from pathlib import Path


def is_admin() -> bool:
    """
    Check if the current process is running with administrator privileges
    
    Returns:
        True if running as administrator, False otherwise
    """
    try:
        # On Windows, check if we have admin privileges
        if sys.platform == 'win32':
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        else:
            # On Unix-like systems, check if we're root
            return os.geteuid() == 0
    except Exception:
        return False


def request_elevation() -> None:
    """
    Request elevation and restart the application with admin privileges.
    This will exit the current process and start a new elevated instance.
    
    Tries multiple methods:
    1. Uses existing elevator.exe if available (most reliable)
    2. Falls back to ShellExecuteW with "runas" verb
    
    Raises:
        SystemExit: Always raises SystemExit to terminate the current process
    """
    if sys.platform != 'win32':
        raise RuntimeError("Elevation is only supported on Windows")
    
    if is_admin():
        # Already running as admin, no need to elevate
        return
    
    # Get the current script path - try multiple methods
    script_path = None
    
    # Method 1: Try to get from __main__ module if available
    try:
        if hasattr(sys.modules.get('__main__'), '__file__'):
            script_path = Path(sys.modules['__main__'].__file__).resolve()
    except Exception:
        pass
    
    # Method 2: Try sys.argv[0]
    if script_path is None or not script_path.exists():
        try:
            script_path = Path(sys.argv[0]).resolve()
        except Exception:
            pass
    
    # Method 3: Try relative to admin_utils.py location
    if script_path is None or not script_path.exists():
        script_path = Path(__file__).parent / "winws_gui.py"
    
    # Final fallback
    if not script_path.exists():
        raise RuntimeError("Could not determine script path for elevation")
    
    script_path = script_path.resolve()
    script_dir = script_path.parent
    project_root = script_dir.parent
    
    # Try method 1: Use elevator.exe if available (most reliable)
    elevator_paths = [
        project_root / "tools" / "elevator.exe",
        project_root / "zapret-winws" / "elevator.exe",
        project_root / "zapret-winws" / "elevator",
    ]
    
    # Create a launcher script that elevator.exe can execute
    launcher_script = script_dir / "winws_gui_launcher.cmd"
    
    for elevator_path in elevator_paths:
        if elevator_path.exists():
            try:
                # Use elevator.exe to launch the launcher script
                # elevator.exe takes the script path as argument
                # The launcher script will then run Python with admin privileges
                cmd = [str(elevator_path), str(launcher_script)]
                subprocess.Popen(cmd, cwd=str(script_dir), shell=False)
                # Exit the current process since we're starting an elevated instance
                sys.exit(0)
            except Exception as e:
                # If elevator fails, try the next method or fall through to ShellExecuteW
                # Don't print here as we might not have a console
                pass
    
    # Method 2: Use ShellExecuteW with "runas" verb
    try:
        # Convert paths to strings for ctypes
        python_exe = str(sys.executable)
        script_str = str(script_path)
        work_dir = str(script_dir)
        
        # ShellExecuteW parameters:
        # hwnd, lpOperation, lpFile, lpParameters, lpDirectory, nShowCmd
        # Note: lpParameters should be a single string, not a list
        result = ctypes.windll.shell32.ShellExecuteW(
            None,  # hwnd
            "runas",  # lpOperation - Request elevation
            python_exe,  # lpFile - Python executable
            f'"{script_str}"',  # lpParameters - Script path (quoted)
            work_dir,  # lpDirectory - Working directory
            1  # nShowCmd - SW_SHOWNORMAL
        )
        
        # If ShellExecuteW returns a value <= 32, it indicates an error
        # Common error codes:
        # 2 = ERROR_FILE_NOT_FOUND
        # 3 = ERROR_PATH_NOT_FOUND
        # 5 = ERROR_ACCESS_DENIED
        # 1223 = ERROR_CANCELLED (user cancelled UAC prompt)
        if result <= 32:
            error_codes = {
                2: "File not found",
                3: "Path not found",
                5: "Access denied",
                1223: "User cancelled elevation prompt",
            }
            error_msg = error_codes.get(result, f"Unknown error")
            raise RuntimeError(f"Failed to request elevation. Error code {result}: {error_msg}")
        
        # Exit the current process since we're starting an elevated instance
        sys.exit(0)
    except SystemExit:
        # Re-raise SystemExit
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to request elevation: {e}")

