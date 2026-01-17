#!/usr/bin/env python3
"""
GUI application for winws.exe
Provides a simple interface to run winws.exe with parameters
"""

import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from tkinter import scrolledtext
import json
import re
import sys
import os
import tempfile
from datetime import datetime
from pathlib import Path
from winws_runner import WinWSRunner
from admin_utils import is_admin, request_elevation

# Windows-specific imports for AppUserModelID
if sys.platform == 'win32':
    try:
        from ctypes import windll
        WINDOWS_AVAILABLE = True
    except ImportError:
        WINDOWS_AVAILABLE = False
else:
    WINDOWS_AVAILABLE = False

try:
    import pystray
    from PIL import Image, ImageDraw, ImageTk
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False
    print("Warning: pystray and PIL not installed. System tray functionality will be disabled.")
    print("Install with: pip install pystray pillow")


class WinWSGUI:
    def __init__(self):
        # Check for admin privileges
        # Note: Elevation should be handled by winws_gui.cmd using elevator.exe
        # If we're here without admin privileges, show a warning but continue
        # (The user might have launched Python directly)
        if sys.platform == 'win32' and not is_admin():
            # Create a minimal root window just to show the warning
            root = tk.Tk()
            root.withdraw()  # Hide the window
            
            script_dir = Path(__file__).parent
            launcher_cmd = script_dir / "winws_gui_launcher.cmd"
            main_cmd = script_dir / "winws_gui.cmd"
            
            alt_method = ""
            if launcher_cmd.exists():
                alt_method = f"\n\nTo run with admin privileges:\n1. Right-click on '{main_cmd.name}' and select 'Run as administrator'\n2. Or right-click on '{launcher_cmd.name}' and select 'Run as administrator'"
            else:
                alt_method = f"\n\nTo run with admin privileges:\nRight-click on '{main_cmd.name}' and select 'Run as administrator'"
            
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
        
        # Set AppUserModelID for Windows taskbar icon (must be done before creating window)
        if WINDOWS_AVAILABLE:
            try:
                # Set a unique AppUserModelID for this application
                windll.shell32.SetCurrentProcessExplicitAppUserModelID("com.winws.gui")
            except Exception as e:
                print(f"Warning: Could not set AppUserModelID: {e}")
        
        self.root = tk.Tk()
        self.root.title("WinWS GUI (Administrator)")
        self.root.geometry("600x500")
        
        # Get the directory where this script is located
        script_dir = Path(__file__).parent
        project_root = script_dir.parent
        
        # Set window icon for both title bar and taskbar
        # First try to use pre-generated icon.ico (best quality)
        icon_dir = script_dir / "icon"
        ico_path = icon_dir / "icon.ico"
        icon_64_path = icon_dir / "icon_64x64.png"
        icon_jpg_path = icon_dir / "icon.jpg"
        
        # Use pre-generated ICO file if available (best for taskbar)
        if ico_path.exists():
            try:
                if sys.platform == 'win32':
                    # Use pre-generated ICO for taskbar (best quality, multi-size)
                    self.root.iconbitmap(str(ico_path))
                    self.temp_ico_path = None  # No cleanup needed for pre-generated file
                
                # Set window icon - prefer pre-generated 64x64 PNG
                if TRAY_AVAILABLE:
                    if icon_64_path.exists():
                        try:
                            window_icon = Image.open(icon_64_path)
                            if window_icon.mode != 'RGBA':
                                window_icon = window_icon.convert('RGBA')
                            icon_photo = ImageTk.PhotoImage(window_icon)
                            self.root.iconphoto(False, icon_photo)
                            self.root.icon_image = icon_photo
                        except Exception as e:
                            print(f"Warning: Could not load 64x64 icon: {e}")
                            # Fallback to ICO
                            try:
                                ico_image = Image.open(ico_path)
                                window_icon = ico_image.resize((64, 64), Image.Resampling.LANCZOS)
                                icon_photo = ImageTk.PhotoImage(window_icon)
                                self.root.iconphoto(False, icon_photo)
                                self.root.icon_image = icon_photo
                            except Exception:
                                pass
                    else:
                        # Use ICO for window icon
                        try:
                            ico_image = Image.open(ico_path)
                            window_icon = ico_image.resize((64, 64), Image.Resampling.LANCZOS)
                            icon_photo = ImageTk.PhotoImage(window_icon)
                            self.root.iconphoto(False, icon_photo)
                            self.root.icon_image = icon_photo
                        except Exception as e:
                            print(f"Warning: Could not load ICO for window icon: {e}")
            except Exception as e:
                print(f"Warning: Could not use pre-generated ICO: {e}")
                ico_path = None  # Fall back to creating from JPG
        
        # Fallback: create ICO from icon.jpg if pre-generated ICO doesn't exist
        if not ico_path or not ico_path.exists():
            if icon_jpg_path.exists():
                try:
                    if TRAY_AVAILABLE:
                        # Load original image
                        original_icon = Image.open(icon_jpg_path)
                        if original_icon.mode != 'RGBA':
                            original_icon = original_icon.convert('RGBA')
                        
                        # Create window icon (resized for title bar)
                        window_icon = original_icon.copy()
                        if window_icon.size[0] > 64 or window_icon.size[1] > 64:
                            window_icon = window_icon.resize((64, 64), Image.Resampling.LANCZOS)
                        
                        # Create PhotoImage for iconphoto (title bar)
                        icon_photo = ImageTk.PhotoImage(window_icon)
                        self.root.iconphoto(False, icon_photo)
                        self.root.icon_image = icon_photo
                        
                        # For Windows taskbar, create temporary ICO
                        if sys.platform == 'win32':
                            try:
                                temp_ico = tempfile.NamedTemporaryFile(delete=False, suffix='.ico')
                                temp_ico_path = temp_ico.name
                                temp_ico.close()
                                
                                # Create ICO from original
                                ico_image = original_icon.resize((256, 256), Image.Resampling.LANCZOS)
                                ico_image.save(temp_ico_path, format='ICO')
                                
                                self.root.iconbitmap(temp_ico_path)
                                self.temp_ico_path = temp_ico_path
                            except Exception as e:
                                print(f"Warning: Could not create ICO for taskbar: {e}")
                                if hasattr(self, 'temp_ico_path') and os.path.exists(self.temp_ico_path):
                                    try:
                                        os.unlink(self.temp_ico_path)
                                    except:
                                        pass
                    else:
                        print("Warning: PIL not available, cannot set custom icon")
                except (NameError, Exception) as e:
                    print(f"Warning: Could not load icon: {e}")
        
        # Config file path - stores all configuration data
        self.config_file = script_dir / "winws_config.json"
        
        # Load all configuration data from the consolidated config file
        config_data = self.load_config()
        self.saved_params = config_data.get('params', '')
        self.not_working_configs = set(config_data.get('not_working_configs', []))
        self.user_configs = set(config_data.get('user_configs', []))
        
        # Create winws runner instance for process management
        self.runner = WinWSRunner(project_root)
        
        # Store project root for blockcheck log paths
        self.project_root = project_root
        
        # System tray
        self.tray_icon = None
        self.hidden_to_tray = False
        self.temp_ico_path = None  # For temporary ICO file cleanup
        
        # Setup GUI
        self.setup_gui()
        
        # Load saved parameters into text field
        if self.saved_params:
            self.params_entry.insert(0, self.saved_params)
        
        # Initialize logs
        self.log_info("GUI initialized")
        
        # Handle window close event
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Check process status periodically
        self.check_process_status()
    
    def load_config(self):
        """Load all configuration data from config file"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    # Return dict with all config data, ensuring all keys exist
                    return {
                        'params': config.get('params', ''),
                        'user_configs': config.get('user_configs', []),
                        'not_working_configs': config.get('not_working_configs', [])
                    }
        except Exception as e:
            print(f"Error loading config: {e}")
        return {'params': '', 'user_configs': [], 'not_working_configs': []}
    
    def parse_blockcheck_logs(self):
        """
        Parse blockcheck log files to extract working configurations.
        Returns a list of configuration strings found in the logs.
        
        Expected log format:
        !!!!! <test>: working strategy found for ipv<version> <domain> : <daemon> <strategy> !!!!!
        Example:
        !!!!! curl_test_https_tls12: working strategy found for ipv4 youtube.com : winws --dpi-desync=fake,fakeddisorder --dpi-desync-fooling=ts --dpi-desync-split-pos=midsld !!!!!
        """
        configurations = []
        blockcheck_dir = self.project_root / "blockcheck"
        
        # Try both log files: blockcheck.log and blockcheck2.log
        log_files = [
            blockcheck_dir / "blockcheck.log",
            blockcheck_dir / "blockcheck2.log"
        ]
        
        for log_file in log_files:
            if not log_file.exists():
                continue
            
            try:
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        line = line.strip()
                        # Look for lines with "working strategy found" and "!!!!!"
                        if "working strategy found" in line.lower() and "!!!!!" in line:
                            # Pattern: !!!!! <test>: working strategy found for ipv<version> <domain> : <daemon> <strategy> !!!!!
                            # Example: !!!!! curl_test_https_tls12: working strategy found for ipv4 youtube.com : winws --dpi-desync=fake,fakeddisorder --dpi-desync-fooling=ts --dpi-desync-split-pos=midsld !!!!!
                            
                            # Extract strategy part after ": <daemon> " and before trailing "!!!!!"
                            # Match pattern: " : winws " or " : winws2 " followed by strategy until "!!!!!"
                            match = re.search(r'\s:\s(winws2?|nfqws2?|dvtws2?)\s+(.+?)(?:\s+!!!!!)?$', line)
                            if match:
                                daemon_name = match.group(1)
                                strategy = match.group(2).strip().rstrip("!").strip()
                                
                                if strategy and strategy not in configurations:
                                    configurations.append(strategy)
                            else:
                                # Fallback: find last " : " in the line and extract everything after it until "!!!!!"
                                if " : " in line:
                                    # Find the last occurrence of " : "
                                    last_colon_idx = line.rfind(" : ")
                                    if last_colon_idx >= 0:
                                        # Extract everything after " : "
                                        after_colon = line[last_colon_idx + 3:]
                                        # Remove trailing "!!!!!" and clean up
                                        after_colon = after_colon.rstrip("!").strip()
                                        # Split by space: first part is daemon, rest is strategy
                                        parts = after_colon.split(None, 1)
                                        if len(parts) >= 2:
                                            strategy = parts[1].strip()
                                            if strategy and strategy not in configurations:
                                                configurations.append(strategy)
            
            except Exception as e:
                print(f"Error parsing log file {log_file}: {e}")
                continue
        
        return configurations
    
    def show_suggestions(self):
        """Show a new window with a table of suggested configurations from blockcheck logs and user configs"""
        # Get configurations from blockcheck logs
        blockcheck_configs = self.parse_blockcheck_logs()
        
        # Combine blockcheck and user configurations (user configs may include ones not in blockcheck)
        all_configs = set(blockcheck_configs) | self.user_configs
        
        if not all_configs:
            messagebox.showinfo(
                "No Suggestions",
                "No configurations found.\n\n"
                "Configurations can come from:\n"
                "- blockcheck logs (run blockcheck/blockcheck.cmd or blockcheck/blockcheck2.cmd)\n"
                "- manually entered configurations (will be saved when you run them)"
            )
            return
        
        # Sort configurations: working ones first, then not working ones
        working_configs = [c for c in all_configs if c not in self.not_working_configs]
        not_working_configs = [c for c in all_configs if c in self.not_working_configs]
        sorted_configs = working_configs + not_working_configs
        
        # Create new window
        suggestions_window = tk.Toplevel(self.root)
        suggestions_window.title("Configuration Suggestions")
        suggestions_window.geometry("950x500")
        
        # Configure grid
        suggestions_window.columnconfigure(0, weight=1)
        suggestions_window.rowconfigure(1, weight=1)
        
        # Header label
        header_label = ttk.Label(
            suggestions_window,
            text=f"Found {len(sorted_configs)} configuration(s). Select a row and use the buttons below. Double-click to apply.",
            padding="10"
        )
        header_label.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(10, 5))
        
        # Frame for table and scrollbar
        table_frame = ttk.Frame(suggestions_window)
        table_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=10, pady=5)
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
        
        # Create Treeview as table
        columns = ("#", "Status", "Configuration")
        tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=20)
        
        # Configure columns
        tree.heading("#", text="#")
        tree.heading("Status", text="Status")
        tree.heading("Configuration", text="Configuration")
        tree.column("#", width=50, anchor=tk.CENTER)
        tree.column("Status", width=100, anchor=tk.CENTER)
        tree.column("Configuration", width=750, anchor=tk.W)
        
        # Configure tags for styling
        tree.tag_configure("working", foreground="black")
        tree.tag_configure("not_working", foreground="gray")
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        # Grid table and scrollbar
        tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Populate table with configurations
        for i, config in enumerate(sorted_configs, start=1):
            is_not_working = config in self.not_working_configs
            status = "Not Working" if is_not_working else "Working"
            tag = "not_working" if is_not_working else "working"
            tree.insert("", tk.END, values=(i, status, config), tags=(config, tag))
        
        # Bind double-click to apply configuration
        def on_double_click(event):
            selection = tree.selection()
            if selection:
                item = tree.item(selection[0])
                config = item['tags'][0] if item['tags'] else item['values'][2]
                if config:
                    self.apply_suggestion(config)
                    suggestions_window.destroy()
        
        tree.bind("<Double-1>", on_double_click)
        
        # Context menu for marking configs as not working
        context_menu = tk.Menu(suggestions_window, tearoff=0)
        
        def mark_not_working():
            selection = tree.selection()
            if selection:
                item = tree.item(selection[0])
                config = item['tags'][0] if item['tags'] else item['values'][2]
                if config:
                    self.mark_config_not_working(config)
                    # Refresh the window to reflect changes
                    suggestions_window.destroy()
                    self.show_suggestions()
        
        def mark_working():
            selection = tree.selection()
            if selection:
                item = tree.item(selection[0])
                config = item['tags'][0] if item['tags'] else item['values'][2]
                if config:
                    self.unmark_config_not_working(config)
                    # Refresh the window to reflect changes
                    suggestions_window.destroy()
                    self.show_suggestions()
        
        def on_right_click(event):
            selection = tree.selection()
            if selection:
                item = tree.item(selection[0])
                config = item['tags'][0] if item['tags'] else item['values'][2]
                is_not_working = config in self.not_working_configs
                
                # Clear menu and add appropriate options
                context_menu.delete(0, tk.END)
                if is_not_working:
                    context_menu.add_command(label="Mark as Working", command=mark_working)
                else:
                    context_menu.add_command(label="Mark as Not Working", command=mark_not_working)
                
                try:
                    context_menu.tk_popup(event.x_root, event.y_root)
                finally:
                    context_menu.grab_release()
        
        tree.bind("<Button-3>", on_right_click)  # Right-click on Windows/Linux
        tree.bind("<Button-2>", on_right_click)  # Right-click on Mac (middle button)
        
        # Button frame
        button_frame = ttk.Frame(suggestions_window)
        button_frame.grid(row=2, column=0, pady=10)
        
        # Apply button
        def apply_selected():
            selection = tree.selection()
            if selection:
                item = tree.item(selection[0])
                config = item['tags'][0] if item['tags'] else item['values'][2]
                if config:
                    self.apply_suggestion(config)
                    suggestions_window.destroy()
            else:
                messagebox.showwarning("No Selection", "Please select a configuration from the table.")
        
        apply_button = ttk.Button(button_frame, text="Apply Selected", command=apply_selected)
        apply_button.pack(side=tk.LEFT, padx=5)
        
        # Mark as Not Working / Working button
        def toggle_not_working():
            selection = tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a configuration from the table first.")
                return
            
            item = tree.item(selection[0])
            config = item['tags'][0] if item['tags'] else item['values'][2]
            if config:
                is_not_working = config in self.not_working_configs
                if is_not_working:
                    self.unmark_config_not_working(config)
                else:
                    self.mark_config_not_working(config)
                # Refresh the window to reflect changes
                suggestions_window.destroy()
                self.show_suggestions()
        
        # Create the button with dynamic text based on selection
        def update_mark_button_state():
            selection = tree.selection()
            if selection:
                item = tree.item(selection[0])
                config = item['tags'][0] if item['tags'] else item['values'][2]
                is_not_working = config in self.not_working_configs if config else False
                if is_not_working:
                    mark_button.config(text="Mark as Working")
                else:
                    mark_button.config(text="Mark as Not Working")
                mark_button.config(state='normal')
            else:
                mark_button.config(state='disabled')
        
        mark_button = ttk.Button(button_frame, text="Mark as Not Working", command=toggle_not_working, state='disabled')
        mark_button.pack(side=tk.LEFT, padx=5)
        
        # Update button state when selection changes
        tree.bind("<<TreeviewSelect>>", lambda e: update_mark_button_state())
        
        # Close button
        close_button = ttk.Button(button_frame, text="Close", command=suggestions_window.destroy)
        close_button.pack(side=tk.LEFT, padx=5)
    
    def apply_suggestion(self, configuration):
        """Apply a suggested configuration to the parameters field"""
        # Clear existing parameters and set the new one
        self.params_entry.delete(0, tk.END)
        self.params_entry.insert(0, configuration)
        self.log_info(f"Applied suggestion: {configuration[:50]}..." if len(configuration) > 50 else f"Applied suggestion: {configuration}")
    
    def save_config(self):
        """Save all configuration data to config file"""
        try:
            params = self.params_entry.get()
            config = {
                'params': params,
                'user_configs': list(self.user_configs),
                'not_working_configs': list(self.not_working_configs)
            }
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def mark_config_not_working(self, configuration):
        """Mark a configuration as 'not working'"""
        self.not_working_configs.add(configuration)
        self.save_config()
    
    def unmark_config_not_working(self, configuration):
        """Remove a configuration from 'not working' list"""
        self.not_working_configs.discard(configuration)
        self.save_config()
    
    def add_user_config(self, configuration):
        """Add a user-entered configuration to the list"""
        if configuration and configuration.strip():  # Only add non-empty configs
            self.user_configs.add(configuration.strip())
            self.save_config()
    
    def setup_gui(self):
        """Setup the GUI elements"""
        # Main container frame
        main_container = ttk.Frame(self.root, padding="10")
        main_container.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_container.columnconfigure(0, weight=1)
        main_container.rowconfigure(2, weight=1)
        
        # Control panel frame
        control_frame = ttk.Frame(main_container)
        control_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        control_frame.columnconfigure(1, weight=1)
        
        # Parameters label
        ttk.Label(control_frame, text="Parameters:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5), pady=5)
        
        # Parameters entry
        self.params_entry = ttk.Entry(control_frame, width=40)
        self.params_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        # Suggestions button
        self.suggestions_button = ttk.Button(control_frame, text="Suggestions", command=self.show_suggestions)
        self.suggestions_button.grid(row=0, column=2, padx=5, pady=5)
        
        # Debug checkbox
        self.debug_var = tk.BooleanVar(value=False)
        self.debug_checkbox = ttk.Checkbutton(control_frame, text="Debug", variable=self.debug_var)
        self.debug_checkbox.grid(row=0, column=3, padx=5, pady=5)
        
        # Run/Stop button
        self.run_button = ttk.Button(control_frame, text="Run", command=self.toggle_run)
        self.run_button.grid(row=0, column=4, padx=(5, 0), pady=5)
        
        # Logs section
        logs_label = ttk.Label(main_container, text="Logs:")
        logs_label.grid(row=1, column=0, sticky=tk.W, pady=(0, 5))
        
        # Logs text widget (readonly, scrollable)
        self.logs_text = scrolledtext.ScrolledText(
            main_container,
            wrap=tk.WORD,
            state='disabled',
            height=15,
            font=('Consolas', 9) if sys.platform == 'win32' else ('Courier', 9)
        )
        self.logs_text.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure text widget to be readonly but allow programmatic insertion
        self.logs_text.tag_config('info', foreground='black')
        self.logs_text.tag_config('warning', foreground='orange')
        self.logs_text.tag_config('error', foreground='red')
        self.logs_text.tag_config('success', foreground='green')
    
    def log(self, message: str, level: str = 'info'):
        """
        Write a log message to the logs text field
        
        Args:
            message: The log message to write
            level: Log level - 'info', 'warning', 'error', or 'success'
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{level.upper()}] {message}\n"
        
        # Enable text widget for writing
        self.logs_text.config(state='normal')
        
        # Insert log entry with appropriate tag
        self.logs_text.insert(tk.END, log_entry, level)
        
        # Auto-scroll to bottom
        self.logs_text.see(tk.END)
        
        # Disable text widget to make it readonly
        self.logs_text.config(state='disabled')
    
    def log_info(self, message: str):
        """Log an info message"""
        self.log(message, 'info')
    
    def log_warning(self, message: str):
        """Log a warning message"""
        self.log(message, 'warning')
    
    def log_error(self, message: str):
        """Log an error message"""
        self.log(message, 'error')
    
    def log_success(self, message: str):
        """Log a success message"""
        self.log(message, 'success')
    
    def log_output(self, line: str):
        """Log output from winws.exe process"""
        # Log as info, but you can parse the line to determine log level if needed
        self.log_info(line)
    
    def log_input(self, line: str):
        """Log input sent to winws.exe process"""
        # Log input with a different style - you could use a different tag if desired
        self.log(line, 'info')
    
    def clear_logs(self):
        """Clear all logs from the log text field"""
        self.logs_text.config(state='normal')
        self.logs_text.delete(1.0, tk.END)
        self.logs_text.config(state='disabled')
    
    @property
    def is_running(self) -> bool:
        """Check if winws.exe is currently running"""
        return self.runner.is_running
    
    def toggle_run(self):
        """Toggle between running and stopping winws.exe"""
        self.log_info("Run/Stop button clicked")
        if not self.is_running:
            self.start_winws()
        else:
            self.stop_winws()
    
    def start_winws(self):
        """Start winws.exe with parameters"""
        params_str = self.params_entry.get().strip()
        debug_mode = self.debug_var.get()
        
        # Save parameters
        self.save_config()
        
        # Save user configuration if non-empty
        if params_str:
            self.add_user_config(params_str)
        
        self.log_info(f"Parameters: {params_str if params_str else '(none)'}")
        self.log_info(f"Debug mode: {'enabled' if debug_mode else 'disabled (hidden console)'}")
        
        try:
            # Use runner to start winws.exe with output and input callbacks to log to UI
            self.runner.start(
                params_str, 
                output_callback=self.log_output,
                input_callback=self.log_input,
                debug=debug_mode
            )
            self.run_button.config(text="Stop")
            self.params_entry.config(state='disabled')
            self.debug_checkbox.config(state='disabled')
            self.log_success("winws.exe started successfully")
        except FileNotFoundError as e:
            error_msg = f"winws.exe not found:\n{e}"
            self.log_error(error_msg)
            messagebox.showerror("Error", error_msg)
        except Exception as e:
            error_msg = str(e)
            self.log_error(f"Failed to start winws.exe: {error_msg}")
            messagebox.showerror("Error", f"Failed to start winws.exe:\n{error_msg}")
    
    def stop_winws(self):
        """Stop winws.exe process"""
        self.log_info("Stopping winws.exe...")
        self.runner.stop()
        self.run_button.config(text="Run")
        self.params_entry.config(state='normal')
        self.debug_checkbox.config(state='normal')
        self.log_info("winws.exe stopped")
    
    def check_process_status(self):
        """Check if process is still running"""
        # Check status and update UI if process has terminated
        was_running = self.runner.process is not None
        is_still_running = self.runner.check_status()
        
        if was_running and not is_still_running:
            # Process has terminated
            self.run_button.config(text="Run")
            self.params_entry.config(state='normal')
            self.debug_checkbox.config(state='normal')
            self.log_warning("winws.exe process terminated")
        
        # Schedule next check
        self.root.after(1000, self.check_process_status)
    
    def on_closing(self):
        """Handle window close event"""
        if self.is_running:
            # Move to system tray instead of closing
            if TRAY_AVAILABLE:
                self.hide_to_tray()
            else:
                # If tray not available, ask user
                if messagebox.askokcancel("Quit", "winws.exe is still running. Stop it and quit?"):
                    self.stop_winws()
                    # Clean up temporary ICO file
                    if hasattr(self, 'temp_ico_path') and self.temp_ico_path and os.path.exists(self.temp_ico_path):
                        try:
                            os.unlink(self.temp_ico_path)
                        except Exception:
                            pass
                    self.root.destroy()
                # Otherwise do nothing (keep window open)
        else:
            # Fully close if not running
            # Clean up temporary ICO file
            if hasattr(self, 'temp_ico_path') and self.temp_ico_path and os.path.exists(self.temp_ico_path):
                try:
                    os.unlink(self.temp_ico_path)
                except Exception:
                    pass
            self.root.destroy()
    
    def hide_to_tray(self):
        """Hide window to system tray"""
        if not TRAY_AVAILABLE:
            return
        
        self.hidden_to_tray = True
        self.root.withdraw()
        
        # Create tray icon
        if self.tray_icon is None:
            self.create_tray_icon()
            self.tray_icon.run_detached()
    
    def show_from_tray(self):
        """Show window from system tray"""
        if self.tray_icon:
            self.tray_icon.stop()
            self.tray_icon = None
        
        self.hidden_to_tray = False
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
    
    def create_tray_icon(self):
        """Create system tray icon"""
        # Load icon from file - prefer pre-generated 32x32 PNG, fallback to ICO or JPG
        script_dir = Path(__file__).parent
        icon_dir = script_dir / "icon"
        icon_32_path = icon_dir / "icon_32x32.png"
        icon_ico_path = icon_dir / "icon.ico"
        icon_jpg_path = icon_dir / "icon.jpg"
        
        image = None
        
        # Try pre-generated 32x32 PNG first (best quality)
        if icon_32_path.exists():
            try:
                image = Image.open(icon_32_path)
                if image.mode != 'RGBA':
                    image = image.convert('RGBA')
            except Exception as e:
                print(f"Warning: Could not load pre-generated 32x32 icon: {e}")
        
        # Fallback to ICO file
        if image is None and icon_ico_path.exists():
            try:
                image = Image.open(icon_ico_path)
                # Extract 32x32 size from ICO if available
                if hasattr(image, 'sizes') and (32, 32) in image.sizes:
                    # ICO has 32x32 size, use it
                    image.load()
                    # Resize to 32x32 if needed
                    if image.size != (32, 32):
                        image = image.resize((32, 32), Image.Resampling.LANCZOS)
                else:
                    # Resize to 32x32
                    image = image.resize((32, 32), Image.Resampling.LANCZOS)
                if image.mode != 'RGBA':
                    image = image.convert('RGBA')
            except Exception as e:
                print(f"Warning: Could not load ICO for tray: {e}")
        
        # Fallback to JPG
        if image is None and icon_jpg_path.exists():
            try:
                image = Image.open(icon_jpg_path)
                if image.mode != 'RGBA':
                    image = image.convert('RGBA')
                # Resize to 32x32
                image = image.resize((32, 32), Image.Resampling.LANCZOS)
            except Exception as e:
                print(f"Warning: Could not load JPG for tray: {e}")
        
        # Final fallback to simple icon
        if image is None:
            print(f"Warning: No icon file found, using fallback icon")
            image = Image.new('RGBA', (32, 32), color=(255, 255, 255, 255))
            draw = ImageDraw.Draw(image)
            draw.rectangle([8, 8, 24, 24], fill=(0, 0, 0, 255))
        
        menu = pystray.Menu(
            pystray.MenuItem("Show Window", self.show_from_tray, default=True),
            pystray.MenuItem("Stop winws.exe", self.stop_winws, enabled=lambda item: self.runner.is_running),
            pystray.MenuItem("Quit", self.quit_application)
        )
        
        self.tray_icon = pystray.Icon("winws_gui", image, "WinWS GUI", menu)
    
    def quit_application(self, icon=None, item=None):
        """Quit application completely"""
        if self.is_running:
            self.stop_winws()
        if self.tray_icon:
            self.tray_icon.stop()
        
        # Clean up temporary ICO file
        if hasattr(self, 'temp_ico_path') and self.temp_ico_path and os.path.exists(self.temp_ico_path):
            try:
                os.unlink(self.temp_ico_path)
            except Exception:
                pass
        
        self.root.quit()
        self.root.destroy()
    
    def run(self):
        """Start the GUI application"""
        self.root.mainloop()


def main():
    app = WinWSGUI()
    app.run()


if __name__ == "__main__":
    main()

