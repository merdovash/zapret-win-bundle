#!/usr/bin/env python3
"""
GUI application for winws.exe
Provides a simple interface to run winws.exe with parameters
"""

import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from tkinter import scrolledtext
import sys
import os
from datetime import datetime
from pathlib import Path
from winws_runner import WinWSRunner
from admin_utils import is_admin
from icon_manager import IconManager
from config_manager import ConfigManager
from blockcheck_parser import BlockcheckParser
from suggestions_window import SuggestionsWindow
from tray_manager import TrayManager

try:
    import pystray
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False
    print("Warning: pystray and PIL not installed. System tray functionality will be disabled.")
    print("Install with: pip install pystray pillow")


class WinWSGUI:
    """Main GUI application class for WinWS"""
    
    def __init__(self):
        """Initialize the GUI application"""
        self._check_admin_privileges()
        
        # Get script and project directories
        script_dir = Path(__file__).parent
        project_root = script_dir.parent
        
        # Initialize managers
        self.icon_manager = IconManager(script_dir)
        self.icon_manager.set_app_user_model_id()
        
        # Create root window
        self.root = tk.Tk()
        self.root.title("WinWS GUI (Administrator)")
        self.root.geometry("600x500")
        
        # Setup window icon
        self.icon_manager.setup_window_icon(self.root)
        
        # Initialize configuration manager
        config_file = script_dir / "winws_config.json"
        self.config_manager = ConfigManager(config_file)
        
        # Initialize blockcheck parser
        self.blockcheck_parser = BlockcheckParser(project_root)
        
        # Initialize winws runner
        self.runner = WinWSRunner(project_root)
        self.project_root = project_root
        
        # System tray
        self.tray_manager = TrayManager(
            self.icon_manager,
            self.show_from_tray,
            self.stop_winws,
            self.quit_application,
            lambda: self.is_running
        )
        self.hidden_to_tray = False
        
        # Setup GUI
        self.setup_gui()
        
        # Load saved parameters
        saved_params = self.config_manager.get_saved_params()
        if saved_params:
            self.params_entry.insert(0, saved_params)
        
        # Initialize logs
        self.log_info("GUI initialized")
        
        # Handle window close event
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Check process status periodically
        self.check_process_status()
    
    def _check_admin_privileges(self) -> None:
        """Check for admin privileges and show warning if needed"""
        if sys.platform == 'win32' and not is_admin():
            root = tk.Tk()
            root.withdraw()
            
            script_dir = Path(__file__).parent
            launcher_cmd = script_dir / "winws_gui_launcher.cmd"
            main_cmd = script_dir / "winws_gui.cmd"
            
            alt_method = ""
            if launcher_cmd.exists():
                alt_method = (
                    f"\n\nTo run with admin privileges:\n"
                    f"1. Right-click on '{main_cmd.name}' and select 'Run as administrator'\n"
                    f"2. Or right-click on '{launcher_cmd.name}' and select 'Run as administrator'"
                )
            else:
                alt_method = (
                    f"\n\nTo run with admin privileges:\n"
                    f"Right-click on '{main_cmd.name}' and select 'Run as administrator'"
                )
            
            result = messagebox.askyesno(
                "Administrator Privileges Required",
                f"This application requires administrator privileges to run winws.exe.\n\n"
                f"You are currently running without admin privileges.\n\n"
                f"{alt_method}\n\n"
                f"Continue anyway? (winws.exe may not work properly)"
            )
            
            if not result:
                root.destroy()
                sys.exit(0)
            
            root.destroy()
    
    def setup_gui(self) -> None:
        """Setup the GUI elements"""
        # Main container frame
        main_container = ttk.Frame(self.root, padding="10")
        main_container.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_container.columnconfigure(0, weight=1)
        main_container.rowconfigure(2, weight=1)
        
        # Control panel
        self._create_control_panel(main_container)
        
        # Logs section
        self._create_logs_section(main_container)
    
    def _create_control_panel(self, parent: ttk.Frame) -> None:
        """Create the control panel with parameters, buttons, and debug checkbox"""
        control_frame = ttk.Frame(parent)
        control_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        control_frame.columnconfigure(1, weight=1)
        
        # Parameters label
        ttk.Label(control_frame, text="Parameters:").grid(
            row=0, column=0, sticky=tk.W, padx=(0, 5), pady=5
        )
        
        # Parameters entry
        self.params_entry = ttk.Entry(control_frame, width=40)
        self.params_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        # Suggestions button
        self.suggestions_button = ttk.Button(
            control_frame, text="Suggestions", command=self.show_suggestions
        )
        self.suggestions_button.grid(row=0, column=2, padx=5, pady=5)
        
        # Debug checkbox
        self.debug_var = tk.BooleanVar(value=False)
        self.debug_checkbox = ttk.Checkbutton(
            control_frame, text="Debug", variable=self.debug_var
        )
        self.debug_checkbox.grid(row=0, column=3, padx=5, pady=5)
        
        # Run/Stop button
        self.run_button = ttk.Button(
            control_frame, text="Run", command=self.toggle_run
        )
        self.run_button.grid(row=0, column=4, padx=(5, 0), pady=5)
    
    def _create_logs_section(self, parent: ttk.Frame) -> None:
        """Create the logs text widget"""
        logs_label = ttk.Label(parent, text="Logs:")
        logs_label.grid(row=1, column=0, sticky=tk.W, pady=(0, 5))
        
        # Logs text widget (readonly, scrollable)
        self.logs_text = scrolledtext.ScrolledText(
            parent,
            wrap=tk.WORD,
            state='disabled',
            height=15,
            font=('Consolas', 9) if sys.platform == 'win32' else ('Courier', 9)
        )
        self.logs_text.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure text widget tags
        self.logs_text.tag_config('info', foreground='black')
        self.logs_text.tag_config('warning', foreground='orange')
        self.logs_text.tag_config('error', foreground='red')
        self.logs_text.tag_config('success', foreground='green')
    
    def log(self, message: str, level: str = 'info') -> None:
        """
        Write a log message to the logs text field
        
        Args:
            message: The log message to write
            level: Log level - 'info', 'warning', 'error', or 'success'
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{level.upper()}] {message}\n"
        
        self.logs_text.config(state='normal')
        self.logs_text.insert(tk.END, log_entry, level)
        self.logs_text.see(tk.END)
        self.logs_text.config(state='disabled')
    
    def log_info(self, message: str) -> None:
        """Log an info message"""
        self.log(message, 'info')
    
    def log_warning(self, message: str) -> None:
        """Log a warning message"""
        self.log(message, 'warning')
    
    def log_error(self, message: str) -> None:
        """Log an error message"""
        self.log(message, 'error')
    
    def log_success(self, message: str) -> None:
        """Log a success message"""
        self.log(message, 'success')
    
    def log_output(self, line: str) -> None:
        """Log output from winws.exe process"""
        self.log_info(line)
    
    def log_input(self, line: str) -> None:
        """Log input sent to winws.exe process"""
        self.log(line, 'info')
    
    @property
    def is_running(self) -> bool:
        """Check if winws.exe is currently running"""
        return self.runner.is_running
    
    def toggle_run(self) -> None:
        """Toggle between running and stopping winws.exe"""
        self.log_info("Run/Stop button clicked")
        if not self.is_running:
            self.start_winws()
        else:
            self.stop_winws()
    
    def start_winws(self) -> None:
        """Start winws.exe with parameters"""
        params_str = self.params_entry.get().strip()
        debug_mode = self.debug_var.get()
        
        # Save configuration
        self.config_manager.save_config(params_str)
        
        # Save user configuration if non-empty
        if params_str:
            self.config_manager.add_user_config(params_str)
            self.config_manager.save_config(params_str)
        
        self.log_info(f"Parameters: {params_str if params_str else '(none)'}")
        self.log_info(f"Debug mode: {'enabled' if debug_mode else 'disabled (hidden console)'}")
        
        try:
            self.runner.start(
                params_str,
                output_callback=self.log_output,
                input_callback=self.log_input,
                debug=debug_mode
            )
            self._update_ui_for_running()
            self.log_success("winws.exe started successfully")
        except FileNotFoundError as e:
            error_msg = f"winws.exe not found:\n{e}"
            self.log_error(error_msg)
            messagebox.showerror("Error", error_msg)
        except Exception as e:
            error_msg = str(e)
            self.log_error(f"Failed to start winws.exe: {error_msg}")
            messagebox.showerror("Error", f"Failed to start winws.exe:\n{error_msg}")
    
    def _update_ui_for_running(self) -> None:
        """Update UI elements when winws.exe is running"""
        self.run_button.config(text="Stop")
        self.params_entry.config(state='disabled')
        self.debug_checkbox.config(state='disabled')
    
    def _update_ui_for_stopped(self) -> None:
        """Update UI elements when winws.exe is stopped"""
        self.run_button.config(text="Run")
        self.params_entry.config(state='normal')
        self.debug_checkbox.config(state='normal')
    
    def stop_winws(self) -> None:
        """Stop winws.exe process"""
        self.log_info("Stopping winws.exe...")
        self.runner.stop()
        self._update_ui_for_stopped()
        self.log_info("winws.exe stopped")
    
    def check_process_status(self) -> None:
        """Check if process is still running"""
        was_running = self.runner.process is not None
        is_still_running = self.runner.check_status()
        
        if was_running and not is_still_running:
            self._update_ui_for_stopped()
            self.log_warning("winws.exe process terminated")
        
        # Schedule next check
        self.root.after(1000, self.check_process_status)
    
    def show_suggestions(self) -> None:
        """Show a new window with suggested configurations"""
        # Get configurations from blockcheck logs
        blockcheck_configs = self.blockcheck_parser.parse_logs()
        
        # Combine blockcheck and user configurations
        user_configs = self.config_manager.get_user_configs()
        all_configs = set(blockcheck_configs) | user_configs
        
        if not all_configs:
            messagebox.showinfo(
                "No Suggestions",
                "No configurations found.\n\n"
                "Configurations can come from:\n"
                "- blockcheck logs (run blockcheck/blockcheck.cmd or blockcheck/blockcheck2.cmd)\n"
                "- manually entered configurations (will be saved when you run them)"
            )
            return
        
        # Create suggestions window
        not_working_configs = self.config_manager.get_not_working_configs()
        SuggestionsWindow(
            self.root,
            all_configs,
            not_working_configs,
            self.apply_suggestion,
            self._mark_config_not_working,
            self._unmark_config_not_working
        )
    
    def apply_suggestion(self, configuration: str) -> None:
        """Apply a suggested configuration to the parameters field"""
        self.params_entry.delete(0, tk.END)
        self.params_entry.insert(0, configuration)
        config_preview = (
            configuration[:50] + "..." if len(configuration) > 50 else configuration
        )
        self.log_info(f"Applied suggestion: {config_preview}")
    
    def _mark_config_not_working(self, configuration: str) -> None:
        """Mark a configuration as 'not working'"""
        self.config_manager.mark_config_not_working(configuration)
        params_str = self.params_entry.get().strip()
        self.config_manager.save_config(params_str)
        # Refresh suggestions window if open
        self.show_suggestions()
    
    def _unmark_config_not_working(self, configuration: str) -> None:
        """Remove a configuration from 'not working' list"""
        self.config_manager.unmark_config_not_working(configuration)
        params_str = self.params_entry.get().strip()
        self.config_manager.save_config(params_str)
        # Refresh suggestions window if open
        self.show_suggestions()
    
    def on_closing(self) -> None:
        """Handle window close event"""
        if self.is_running:
            if TRAY_AVAILABLE and self.tray_manager.is_available():
                self.hide_to_tray()
            else:
                if messagebox.askokcancel("Quit", "winws.exe is still running. Stop it and quit?"):
                    self.stop_winws()
                    self._cleanup_and_destroy()
                # Otherwise do nothing (keep window open)
        else:
            self._cleanup_and_destroy()
    
    def _cleanup_and_destroy(self) -> None:
        """Clean up resources and destroy window"""
        self.icon_manager.cleanup()
        self.root.destroy()
    
    def hide_to_tray(self) -> None:
        """Hide window to system tray"""
        if not TRAY_AVAILABLE or not self.tray_manager.is_available():
            return
        
        self.hidden_to_tray = True
        self.root.withdraw()
        
        if self.tray_manager.tray_icon is None:
            self.tray_manager.create_tray_icon()
    
    def show_from_tray(self) -> None:
        """Show window from system tray"""
        self.tray_manager.stop_tray_icon()
        self.hidden_to_tray = False
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
    
    def quit_application(self, icon=None, item=None) -> None:
        """Quit application completely"""
        if self.is_running:
            self.stop_winws()
        self.tray_manager.stop_tray_icon()
        self._cleanup_and_destroy()
    
    def run(self) -> None:
        """Start the GUI application"""
        self.root.mainloop()


def main():
    """Main entry point"""
    app = WinWSGUI()
    app.run()


if __name__ == "__main__":
    main()
