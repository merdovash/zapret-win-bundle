#!/usr/bin/env python3
"""
Library for running winws.exe with terminal/console management
Handles process execution, elevation, and console window management
"""

import subprocess
import sys
import os
import threading
import time
from pathlib import Path
from typing import Optional, List, Callable



class WinWSRunner:
    """Manages execution of winws.exe with console terminal"""
    
    def __init__(self, project_root: Optional[Path] = None):
        """
        Initialize WinWSRunner
        
        Args:
            project_root: Root directory of the project. If None, will try to auto-detect
        """
        if project_root is None:
            # Try to auto-detect project root (assume this file is in gui/ directory)
            script_dir = Path(__file__).parent
            project_root = script_dir.parent
        
        self.project_root = Path(project_root)
        self.winws_exe = self.project_root / "zapret-winws" / "winws.exe"
        
        # Process state
        self.process: Optional[subprocess.Popen] = None  # winws.exe process
        self.cmd_file_path: Optional[str] = None  # Deprecated: kept for compatibility
        self.start_time: Optional[float] = None  # Timestamp when cmd file process started
        self.termination_time: Optional[float] = None  # Timestamp when cmd file process terminated
        self.monitor_thread: Optional[threading.Thread] = None  # Thread to monitor process termination
        self.output_threads: List[threading.Thread] = []
        self.output_callback: Optional[Callable[[str], None]] = None
        self.input_callback: Optional[Callable[[str], None]] = None
    
    @property
    def is_cmd_running(self) -> bool:
        """
        Check if winws.exe process is currently running based on start/termination times and process status.
        """
        # If we have a termination time, process is not running
        if self.termination_time is not None:
            return False
        
        # If we have a process, check if it's still running
        if self.process is not None:
            # Check if process has terminated
            if self.process.poll() is not None:
                # Process has terminated
                if self.termination_time is None:
                    self.termination_time = time.time()
                return False
            # Process is still running
            return True
        
        # If we have a start time and no termination time, consider it running
        if self.start_time is not None:
            return True
        
        # No start time means process was never started
        return False
    
    @property
    def is_running(self) -> bool:
        """Check if winws.exe is currently running (alias for is_cmd_running)"""
        return self.is_cmd_running
    
    def get_winws_path(self) -> Path:
        """Get the path to winws.exe"""
        return self.winws_exe
    
    def _validate_winws_exists(self) -> None:
        """Validate that winws.exe exists, raise FileNotFoundError if not"""
        if not self.winws_exe.exists():
            raise FileNotFoundError(f"winws.exe not found at: {self.winws_exe}")
    
    def _parse_parameters(self, parameters: str) -> List[str]:
        """
        Parse parameters string into a list
        
        Args:
            parameters: Command-line parameters as a string
            
        Returns:
            List of parameter strings
        """
        return parameters.strip().split() if parameters and parameters.strip() else []
    
    def _build_winws_command(self, params_list: List[str]) -> List[str]:
        """
        Build the winws command as a list
        
        Args:
            params_list: List of command-line parameters
            
        Returns:
            List of command parts ready for subprocess
        """
        return [str(self.winws_exe)] + params_list
    
    def _execute_process(self, winws_cmd: List[str], winws_dir: Path, debug: bool = False) -> subprocess.Popen:
        """
        Execute winws.exe directly (GUI is already running with admin privileges)
        
        Args:
            winws_cmd: List of command parts (executable + parameters)
            winws_dir: Directory where winws.exe is located
            debug: If True, show console window. If False, run in hidden console.
            
        Returns:
            subprocess.Popen object for the started process
        """
        startupinfo = None
        creation_flags = 0
        
        if sys.platform == 'win32':
            if debug:
                # Show console window
                creation_flags = subprocess.CREATE_NEW_CONSOLE
            else:
                # Run in hidden console using STARTUPINFO
                try:
                    startupinfo = subprocess.STARTUPINFO()
                    # STARTF_USESHOWWINDOW = 0x00000001
                    # SW_HIDE = 0
                    startupinfo.dwFlags |= 0x00000001  # STARTF_USESHOWWINDOW
                    startupinfo.wShowWindow = 0  # SW_HIDE
                    # Use CREATE_NO_WINDOW as additional flag
                    creation_flags = subprocess.CREATE_NO_WINDOW
                except (AttributeError, TypeError):
                    # Fallback if STARTUPINFO is not available
                    creation_flags = subprocess.CREATE_NO_WINDOW
        
        return subprocess.Popen(
            winws_cmd,
            stdout=None,
            stderr=None,
            stdin=None,
            cwd=str(winws_dir),
            startupinfo=startupinfo,
            creationflags=creation_flags,
            shell=False
        )
    
    
    def start(self, parameters: str = "", output_callback: Optional[Callable[[str], None]] = None, input_callback: Optional[Callable[[str], None]] = None, debug: bool = False) -> subprocess.Popen:
        """
        Start winws.exe with the given parameters
        
        Args:
            parameters: Command-line parameters as a string
            output_callback: Optional callback function to receive stdout/stderr output.
                           Called with each line of output as a string.
            input_callback: Optional callback function to log input sent to the process.
                          Called with each input line as a string.
            debug: If True, show console window. If False, run in hidden console.
            
        Returns:
            subprocess.Popen object for the started process
            
        Raises:
            FileNotFoundError: If winws.exe is not found
            subprocess.SubprocessError: If process fails to start
            Exception: Other errors (including elevation errors)
        """
        # Validate prerequisites
        self._validate_winws_exists()
        
        # Stop any existing process
        if self.is_running:
            self.stop()
        
        # Store callbacks
        self.output_callback = output_callback
        self.input_callback = input_callback
        
        # Get the directory where winws.exe is located
        winws_dir = self.winws_exe.parent
        
        # Parse and build command
        params_list = self._parse_parameters(parameters)
        winws_cmd = self._build_winws_command(params_list)
        
        # Log command execution
        log_message = f"> {' '.join(winws_cmd)}"
        callback = self.output_callback or self.input_callback
        if callback:
            callback(log_message)
        
        # Execute process directly (GUI is already running with admin privileges)
        self.process = self._execute_process(winws_cmd, winws_dir, debug=debug)
        
        # Clear cmd file path (no longer used)
        self.cmd_file_path = None
        
        # Record start time
        self.start_time = time.time()
        self.termination_time = None
        
        # Start monitoring thread to detect unexpected termination
        self._start_process_monitor()
        
        return self.process
    
    def _start_process_monitor(self):
        """Start a background thread to monitor winws.exe process termination"""
        if self.process is None:
            return
            
        self.start_time = time.time()
        # Monitor thread will check process.poll() periodically
        if self.process.poll() is None:
            self.termination_time = None
        else:
            # Process already terminated
            self.termination_time = time.time()
        
    def _read_output(self, pipe):
        """Read output from a pipe and call the callback for each line"""
        try:
            for line in iter(pipe.readline, ''):
                if not line:
                    break
                if self.output_callback:
                    self.output_callback(line.rstrip('\n\r'))
        except Exception:
            pass  # Ignore errors when reading output
        finally:
            pipe.close()
    
    def send_input(self, data: str):
        """
        Send input to the process and log it
        
        Args:
            data: Input string to send to the process
        """
        if self.process and self.process.stdin:
            # Log the input if we have input callback
            if self.input_callback:
                self.input_callback(f"< {data}")
            
            try:
                self.process.stdin.write(data + '\n')
                self.process.stdin.flush()
            except Exception as e:
                if self.output_callback:
                    self.output_callback(f"Error sending input: {e}")
    
    def stop(self) -> None:
        """
        Stop the running winws.exe process
        
        This will terminate the winws.exe process and clean up output threads
        """
        # Record termination time
        if self.start_time is not None and self.termination_time is None:
            self.termination_time = time.time()
        
        # Clean up the process handle if it exists
        if self.process is not None:
            try:
                self.process.terminate()
                try:
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()
            except Exception:
                pass  # Ignore errors
            finally:
                self.process = None
        
        # Try to kill winws.exe by name (fallback method)
        try:
            subprocess.run(
                ['taskkill', '/F', '/IM', 'winws.exe'],
                capture_output=True,
                timeout=5
            )
        except Exception:
            pass  # Ignore errors
        
        # Clear state
        self.cmd_file_path = None
        self.output_threads = []
        self.output_callback = None
        self.input_callback = None
    
    def check_status(self) -> bool:
        """
        Check if winws.exe process is still running and update internal state
        
        Returns:
            True if winws.exe process is still running, False otherwise
        """
        # Check process status and update termination_time if needed
        if self.process is not None:
            if self.process.poll() is not None:
                # Process has terminated
                if self.termination_time is None:
                    self.termination_time = time.time()
                return False
        
        # Use the is_cmd_running property which checks start/termination times and process status
        return self.is_cmd_running
    
    def get_cmd_file_path(self) -> Optional[str]:
        """
        Get the path to the currently running cmd file
        
        Returns:
            Path to the cmd file if one is running, None otherwise
        """
        return self.cmd_file_path


def create_runner(project_root: Optional[Path] = None) -> WinWSRunner:
    """
    Factory function to create a WinWSRunner instance
    
    Args:
        project_root: Root directory of the project. If None, will try to auto-detect
        
    Returns:
        WinWSRunner instance
    """
    return WinWSRunner(project_root)

