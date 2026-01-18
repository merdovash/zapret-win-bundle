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
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from typing import Set, Tuple
from winws_runner import WinWSRunner
from admin_utils import is_admin
from icon_manager import IconManager
from config_manager import ConfigManager
from blockcheck_parser import BlockcheckParser
from suggestions_window import SuggestionsWindow
from tray_manager import TrayManager

# Windows API for dark title bar
if sys.platform == 'win32':
    try:
        import ctypes
        from ctypes import wintypes
        
        # Constants for DwmSetWindowAttribute
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        DWMWA_USE_IMMERSIVE_DARK_MODE_BEFORE_20H1 = 19
        
        def set_dark_title_bar(window):
            """Set Windows title bar to dark mode"""
            try:
                # Ensure window is created and mapped
                window.update()
                window.update_idletasks()
                
                # Get the window handle (HWND) from tkinter window
                # On Windows, winfo_id() returns the HWND directly for top-level windows
                window_id = window.winfo_id()
                
                # Try multiple methods to get the HWND
                hwnd = None
                
                # Method 1: Use the window ID directly (works for Tk root windows)
                if window_id:
                    hwnd = window_id
                
                # Method 2: Try GetParent (for Toplevel windows)
                if hwnd:
                    parent_hwnd = ctypes.windll.user32.GetParent(hwnd)
                    if parent_hwnd:
                        hwnd = parent_hwnd
                
                # Method 3: Try GetAncestor to get the root window
                if hwnd:
                    GA_ROOT = 2
                    root_hwnd = ctypes.windll.user32.GetAncestor(hwnd, GA_ROOT)
                    if root_hwnd:
                        hwnd = root_hwnd
                
                if hwnd:
                    value = ctypes.c_int(1)
                    # Try Windows 11/10 20H1+ method first
                    result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                        hwnd,
                        DWMWA_USE_IMMERSIVE_DARK_MODE,
                        ctypes.byref(value),
                        ctypes.sizeof(value)
                    )
                    # If that fails, try the older method
                    if result != 0:
                        ctypes.windll.dwmapi.DwmSetWindowAttribute(
                            hwnd,
                            DWMWA_USE_IMMERSIVE_DARK_MODE_BEFORE_20H1,
                            ctypes.byref(value),
                            ctypes.sizeof(value)
                        )
            except Exception:
                pass  # Silently fail if API is not available
    except Exception:
        def set_dark_title_bar(window):
            """Fallback: do nothing if Windows API is not available"""
            pass
else:
    def set_dark_title_bar(window):
        """Fallback: do nothing on non-Windows platforms"""
        pass

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
        
        # Initialize configuration manager (needed before loading geometry)
        config_file = script_dir / "winws_config.json"
        self.config_manager = ConfigManager(config_file)
        
        # Load saved geometry or use default
        saved_geometry = self.config_manager.get_window_geometry("main_window")
        if saved_geometry:
            self.root.geometry(saved_geometry)
        else:
            self.root.geometry("800x600")
        
        self.root.tk.call('tk', 'scaling', 4)
        
        # Setup dark theme
        self._setup_dark_theme()
        
        # Setup window icon
        self.icon_manager.setup_window_icon(self.root)
        
        # Set dark title bar (Windows only) - call after window is created and shown
        def apply_dark_title_bar():
            set_dark_title_bar(self.root)
            # Also try again after a short delay to ensure window is fully rendered
            self.root.after(100, lambda: set_dark_title_bar(self.root))
        self.root.after_idle(apply_dark_title_bar)
        
        # Initialize resize tracking variables
        self._resize_timer = None
        self._last_width = None
        self._last_height = None
        
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
            self.params_entry.insert('1.0', saved_params)
        
        # Initialize logs
        self.log_info("GUI initialized")
        
        # Initialize window size tracking
        def init_window_size():
            self.root.update_idletasks()
            self._last_width = self.root.winfo_width()
            self._last_height = self.root.winfo_height()
        self.root.after_idle(init_window_size)
        
        # Bind window resize events
        self.root.bind("<Configure>", self._on_resize)
        
        # Handle window close event
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Check process status periodically
        self.check_process_status()
    
    def _setup_dark_theme(self) -> None:
        """Setup dark theme for the application"""
        # Dark theme colors
        self.bg_color = "#1e1e1e"  # Dark gray background
        self.fg_color = "#d4d4d4"  # Light gray foreground
        self.entry_bg = "#2d2d2d"  # Slightly lighter for entries
        self.select_bg = "#3d3d3d"  # Selection background
        self.select_fg = "#ffffff"  # Selection foreground
        
        # Configure root window
        self.root.configure(bg=self.bg_color, highlightbackground='#3d3d3d', highlightthickness=1)
        
        # Configure ttk style
        style = ttk.Style()
        style.theme_use('clam')  # Use 'clam' as base theme for better customization
        
        # Configure styles for dark theme
        style.configure('TFrame', 
                       background=self.bg_color,
                       borderwidth=0,
                       relief='flat')
        style.configure('TLabel', background=self.bg_color, foreground=self.fg_color)
        style.configure('TButton', 
                       background="#3d3d3d", 
                       foreground=self.fg_color,
                       borderwidth=1,
                       relief='flat')
        style.map('TButton',
                  background=[('active', '#4d4d4d'), ('pressed', '#2d2d2d')],
                  bordercolor=[('active', '#5d5d5d'), ('pressed', '#2d2d2d')])
        
        # Run button style (green)
        style.configure('Run.TButton',
                       background='#2d5a2d',
                       foreground='#ffffff')
        style.map('Run.TButton',
                  background=[('active', '#3d7a3d'), ('pressed', '#1d4a1d')])
        
        # Stop button style (red)
        style.configure('Stop.TButton',
                       background='#5a2d2d',
                       foreground='#ffffff')
        style.map('Stop.TButton',
                  background=[('active', '#7a3d3d'), ('pressed', '#4a1d1d')])
        
        style.configure('TEntry', 
                       fieldbackground=self.entry_bg, 
                       foreground=self.fg_color,
                       borderwidth=1,
                       relief='flat',
                       bordercolor='#3d3d3d',
                       lightcolor='#3d3d3d',  # Top/left border color for 3D effect
                       darkcolor='#3d3d3d')   # Bottom/right border color for 3D effect
        style.map('TEntry',
                  fieldbackground=[('focus', self.entry_bg)],
                  bordercolor=[('focus', '#0078d4'), ('!focus', '#3d3d3d')],
                  lightcolor=[('focus', '#0078d4'), ('!focus', '#3d3d3d')],
                  darkcolor=[('focus', '#0078d4'), ('!focus', '#3d3d3d')])
        style.configure('TCombobox',
                       fieldbackground=self.entry_bg,
                       foreground=self.fg_color,
                       borderwidth=1,
                       relief='flat',
                       bordercolor='#3d3d3d',
                       lightcolor='#3d3d3d',
                       darkcolor='#3d3d3d')
        style.map('TCombobox',
                  fieldbackground=[('focus', self.entry_bg), ('readonly', self.entry_bg)],
                  bordercolor=[('focus', '#0078d4'), ('!focus', '#3d3d3d')],
                  lightcolor=[('focus', '#0078d4'), ('!focus', '#3d3d3d')],
                  darkcolor=[('focus', '#0078d4'), ('!focus', '#3d3d3d')])
        style.configure('TCheckbutton', 
                       background=self.bg_color, 
                       foreground=self.fg_color)
        style.map('TCheckbutton',
                  background=[('active', self.bg_color), ('selected', self.bg_color)])
        # Configure scrollbar with dark colors
        style.configure('TScrollbar', 
                       background='#3d3d3d',
                       troughcolor=self.bg_color,
                       borderwidth=0,
                       arrowcolor=self.fg_color,
                       darkcolor=self.bg_color,
                       lightcolor=self.bg_color)
        style.map('TScrollbar',
                  background=[('active', '#4d4d4d'), ('!active', '#3d3d3d')],
                  arrowcolor=[('active', self.fg_color), ('!active', self.fg_color)])
        
        # Configure Notebook (tabs) for dark theme
        style.configure('TNotebook',
                       background=self.bg_color,
                       borderwidth=0)
        style.configure('TNotebook.Tab',
                       background='#3d3d3d',
                       foreground=self.fg_color,
                       padding=[10, 5])
        style.map('TNotebook.Tab',
                  background=[('selected', self.bg_color), ('active', '#4d4d4d')],
                  expand=[('selected', [1, 1, 1, 0])])
        
        # Configure Treeview for dark theme
        style.configure('Treeview',
                       background=self.entry_bg,
                       foreground=self.fg_color,
                       fieldbackground=self.entry_bg,
                       borderwidth=1,
                       relief='flat',
                       rowheight=50)
        style.map('Treeview',
                  background=[('selected', '#0078d4')],
                  foreground=[('selected', '#ffffff')])
        style.configure('Treeview.Heading',
                       background="#3d3d3d",
                       foreground=self.fg_color,
                       borderwidth=1,
                       relief='flat')
        style.map('Treeview.Heading',
                  background=[('active', '#4d4d4d')])
    
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
        """Setup the GUI elements with tabbed interface"""
        # Main container frame
        main_container = ttk.Frame(self.root, padding="10")
        main_container.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_container.columnconfigure(0, weight=1)
        main_container.rowconfigure(0, weight=1)
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(main_container)
        self.notebook.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Create tabs
        self._create_parameters_tab()
        self._create_logs_tab()
        self._create_presets_tab()
        self._create_settings_tab()
        
        # Status bar at the bottom
        self._create_status_bar(main_container)
    
    def _create_parameters_tab(self) -> None:
        """Create Parameters tab with multi-line text editor"""
        params_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(params_frame, text="Parameters")
        params_frame.columnconfigure(0, weight=1)
        params_frame.rowconfigure(1, weight=1)
        
        # Control frame with buttons
        control_frame = ttk.Frame(params_frame)
        control_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        control_frame.columnconfigure(0, weight=1)
        
        # Run/Stop and Suggestions buttons
        buttons_frame = ttk.Frame(control_frame)
        buttons_frame.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        self.run_button = ttk.Button(
            buttons_frame, text="Run", command=self.toggle_run, style='Run.TButton'
        )
        self.run_button.pack(side=tk.LEFT, padx=(0, 5))
        
        
        # Parameters text editor (multi-line)
        text_frame = ttk.Frame(params_frame)
        text_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)
        
        # Use Text widget instead of Entry for multi-line editing
        self.params_entry = tk.Text(
            text_frame,
            wrap=tk.WORD,
            height=10,
            font=('Consolas', 9) if sys.platform == 'win32' else ('Courier', 9),
            bg=self.entry_bg,
            fg=self.fg_color,
            insertbackground=self.fg_color,
            selectbackground=self.select_bg,
            selectforeground=self.select_fg,
            highlightbackground='#3d3d3d',
            highlightcolor='#0078d4',
            highlightthickness=1,
            borderwidth=0,
            relief='flat'
        )
        self.params_entry.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Scrollbar for parameters text
        params_scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.params_entry.yview)
        self.params_entry.configure(yscrollcommand=params_scrollbar.set)
        params_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
    
    def _create_logs_tab(self) -> None:
        """Create Logs tab"""
        logs_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(logs_frame, text="Logs")
        logs_frame.columnconfigure(0, weight=1)
        logs_frame.rowconfigure(0, weight=1)
        
        # Create a frame to contain Text and Scrollbar
        text_frame = ttk.Frame(logs_frame)
        text_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)
        
        # Logs text widget
        self.logs_text = tk.Text(
            text_frame,
            wrap=tk.WORD,
            state='disabled',
            font=('Consolas', 9) if sys.platform == 'win32' else ('Courier', 9),
            bg=self.entry_bg,
            fg=self.fg_color,
            insertbackground=self.fg_color,
            selectbackground=self.select_bg,
            selectforeground=self.select_fg,
            highlightbackground='#3d3d3d',
            highlightcolor='#0078d4',
            highlightthickness=1,
            borderwidth=0,
            relief='flat'
        )
        self.logs_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Scrollbar
        logs_scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.logs_text.yview)
        self.logs_text.configure(yscrollcommand=logs_scrollbar.set)
        logs_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Configure text widget tags for dark theme with improved colors
        self.logs_text.tag_config('info', foreground='#4ec9b0')  # Green-cyan for INFO
        self.logs_text.tag_config('warning', foreground='#ffa500')
        self.logs_text.tag_config('error', foreground='#f48771')  # Red for ERROR
        self.logs_text.tag_config('success', foreground='#89d185')  # Green for SUCCESS
        self.logs_text.tag_config('debug', foreground='#808080')  # Gray for DEBUG
    
    def _create_presets_tab(self) -> None:
        """Create Presets tab with table containing presets, user configs, and blockcheck results"""
        presets_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(presets_frame, text="Presets")
        presets_frame.columnconfigure(0, weight=1)
        presets_frame.rowconfigure(1, weight=1)
        
        # Header label
        header_label = ttk.Label(
            presets_frame,
            text="Double-click a row to apply. Edit Name and Status by clicking on cells.",
            padding="5"
        )
        header_label.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        
        # Table frame
        table_frame = ttk.Frame(presets_frame)
        table_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
        
        # Create Treeview with columns: Name, Status, Config
        columns = ("Name", "Status", "Config")
        self.presets_tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=20)
        
        # Configure columns
        self.presets_tree.heading("Name", text="Name")
        self.presets_tree.heading("Status", text="Status")
        self.presets_tree.heading("Config", text="Config")
        self.presets_tree.column("Name", width=200, anchor=tk.W)
        self.presets_tree.column("Status", width=100, anchor=tk.CENTER)
        self.presets_tree.column("Config", width=600, anchor=tk.W)
        
        # Configure tags for status
        self.presets_tree.tag_configure("working", foreground="#d4d4d4")
        self.presets_tree.tag_configure("not_working", foreground="#808080")
        
        # Scrollbar
        scrollbar_preset = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.presets_tree.yview)
        self.presets_tree.configure(yscrollcommand=scrollbar_preset.set)
        
        # Grid
        self.presets_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar_preset.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Bind events
        self.presets_tree.bind('<Double-1>', lambda e: self._apply_preset_from_table())
        self.presets_tree.bind('<Button-1>', self._on_presets_table_click)
        self.presets_tree.bind('<KeyRelease>', self._on_presets_table_key)
        
        # Store editing state
        self.presets_editing_cell = None
        self.presets_edit_entry = None
        
        # Button frame
        button_frame = ttk.Frame(presets_frame)
        button_frame.grid(row=2, column=0, pady=(10, 0))
        
        # Apply button
        apply_preset_button = ttk.Button(
            button_frame, text="Apply Selected", command=self._apply_preset_from_table
        )
        apply_preset_button.pack(side=tk.LEFT, padx=5)
        
        # Refresh button
        refresh_button = ttk.Button(
            button_frame, text="Refresh", command=self._refresh_presets_table
        )
        refresh_button.pack(side=tk.LEFT, padx=5)
        
        # Run Blockcheck button
        self.run_blockcheck_button = ttk.Button(
            button_frame, text="Run Blockcheck", command=self._run_blockcheck
        )
        self.run_blockcheck_button.pack(side=tk.LEFT, padx=5)
        
        # Populate table
        self._populate_presets_table()
    
    def _create_settings_tab(self) -> None:
        """Create Settings tab"""
        settings_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(settings_frame, text="Settings")
        
        # Debug checkbox
        self.debug_var = tk.BooleanVar(value=False)
        self.debug_checkbox = ttk.Checkbutton(
            settings_frame, text="Debug mode (show console window)", variable=self.debug_var
        )
        self.debug_checkbox.grid(row=0, column=0, sticky=tk.W, pady=5)
    
    def _create_status_bar(self, parent: ttk.Frame) -> None:
        """Create status bar at the bottom"""
        status_frame = ttk.Frame(parent)
        status_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(5, 0))
        status_frame.columnconfigure(0, weight=1)
        
        # Status indicator and text
        self.status_label = ttk.Label(
            status_frame, text="Status: Stopped", foreground='#808080'
        )
        self.status_label.grid(row=0, column=0, sticky=tk.W)
        
        # Status indicator circle (canvas)
        self.status_canvas = tk.Canvas(
            status_frame, width=12, height=12, bg=self.bg_color,
            highlightthickness=0, borderwidth=0
        )
        self.status_canvas.grid(row=0, column=1, padx=(10, 0), sticky=tk.W)
        self.status_circle = self.status_canvas.create_oval(2, 2, 10, 10, fill='#808080', outline='')
    
    def _update_status_bar(self, running: bool) -> None:
        """Update status bar indicator"""
        if running:
            self.status_label.config(text="Status: Running", foreground='#89d185')
            self.status_canvas.itemconfig(self.status_circle, fill='#89d185')
        else:
            self.status_label.config(text="Status: Stopped", foreground='#808080')
            self.status_canvas.itemconfig(self.status_circle, fill='#808080')
    
    def _get_presets_config(self) -> dict:
        """Get presets configuration mapping"""
        return {
            "YouTube (winws)": "--wf-tcp=80,443 --filter-tcp=443 --hostlist=list-youtube.txt --dpi-desync=fake,multidisorder --dpi-desync-split-pos=1,midsld --dpi-desync-repeats=11 --dpi-desync-fooling=md5sig --new --filter-l7=quic --hostlist=list-youtube.txt --dpi-desync=fake --dpi-desync-repeats=11 --new --filter-l7=quic --dpi-desync=fake --dpi-desync-repeats=11",
            "YouTube (winws2)": "--wf-tcp-out=80,443 --filter-tcp=443 --filter-l7=tls --hostlist=list-youtube.txt --lua-desync=fake:repeats=11 --lua-desync=multidisorder:pos=1,midsld --new --filter-udp=443 --filter-l7=quic --hostlist=list-youtube.txt --lua-desync=fake:repeats=11",
            "Discord": "--wf-tcp=443 --filter-tcp=443 --dpi-desync=fake --new",
            "WireGuard": "--filter-l7=wireguard --dpi-desync=fake",
            "General HTTP/HTTPS": "--wf-tcp=80,443 --filter-tcp=80 --dpi-desync=fake,fakedsplit --new --filter-tcp=443 --dpi-desync=fake,multidisorder --new",
        }
    
    def _populate_presets_table(self) -> None:
        """Populate the presets table with presets, user configs, and blockcheck results"""
        # Clear existing items
        for item in self.presets_tree.get_children():
            self.presets_tree.delete(item)
        
        # Get all configurations
        presets_config = self._get_presets_config()
        user_configs = self.config_manager.get_user_configs()
        blockcheck_configs = self.blockcheck_parser.parse_logs()
        not_working_configs = self.config_manager.get_not_working_configs()
        
        # Combine all configs (presets, user, blockcheck)
        all_configs = set()
        all_configs.update(presets_config.values())
        all_configs.update(user_configs)
        all_configs.update(blockcheck_configs)
        
        # Sort: working first, then not working
        working_configs = [c for c in all_configs if c not in not_working_configs]
        not_working_list = [c for c in all_configs if c in not_working_configs]
        sorted_configs = working_configs + not_working_list
        
        # Insert into table
        for config in sorted_configs:
            # Get name (from config_names, or from presets, or empty string)
            name = self.config_manager.get_config_name(config)
            if not name:
                # Try to find preset name
                for preset_name, preset_config in presets_config.items():
                    if preset_config == config:
                        name = preset_name
                        break
                if not name:
                    # Set to empty string if not specified
                    name = ""
            
            # Get status
            is_not_working = config in not_working_configs
            status = "Not Working" if is_not_working else "Working"
            tag = "not_working" if is_not_working else "working"
            
            # Display config without "winws " prefix in the table
            display_config = config
            if display_config.startswith("winws "):
                display_config = display_config[6:]  # Remove "winws " prefix
            
            # Store original config in item tags for easy retrieval
            # Column order: Name, Status, Config
            self.presets_tree.insert("", tk.END, values=(name, status, display_config), tags=(config, tag))
    
    def _apply_preset_from_table(self) -> None:
        """Apply selected configuration from table to parameters"""
        selection = self.presets_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a configuration first.")
            return
        
        item = self.presets_tree.item(selection[0])
        config = item['tags'][0] if item['tags'] else item['values'][2]  # Config is in column 3 (index 2)
        
        if config:
            # Ensure config starts with "winws " prefix when applying
            if not config.startswith("winws "):
                config = "winws " + config
            
            # Switch to Parameters tab
            self.notebook.select(0)
            # Set parameters
            self.params_entry.delete('1.0', tk.END)
            self.params_entry.insert('1.0', config)
            name = item['values'][0]
            self.log_info(f"Applied configuration: {name}")
    
    def _refresh_presets_table(self) -> None:
        """Refresh the presets table"""
        self._populate_presets_table()
    
    def _run_blockcheck(self) -> None:
        """Run blockcheck.cmd and refresh the presets table when finished"""
        blockcheck_cmd = self.project_root / "blockcheck" / "blockcheck.cmd"
        if not blockcheck_cmd.exists():
            messagebox.showerror("Error", f"blockcheck.cmd not found at {blockcheck_cmd}")
            return
        
        # Disable button during execution
        if self.run_blockcheck_button:
            self.run_blockcheck_button.config(state='disabled', text="Running Blockcheck...")
        
        # Run in a separate thread to avoid blocking the UI
        def run_and_refresh():
            try:
                # Run blockcheck.cmd
                process = subprocess.Popen(
                    [str(blockcheck_cmd)],
                    cwd=str(blockcheck_cmd.parent),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    shell=True
                )
                # Wait for completion
                process.wait()
                
                # Refresh the table on the main thread
                self.root.after(0, self._refresh_presets_table)
                self.root.after(0, self._enable_blockcheck_button)
            except Exception as e:
                # Show error on main thread
                self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to run blockcheck: {e}"))
                self.root.after(0, self._enable_blockcheck_button)
        
        thread = threading.Thread(target=run_and_refresh, daemon=True)
        thread.start()
    
    def _enable_blockcheck_button(self) -> None:
        """Re-enable the blockcheck button"""
        if self.run_blockcheck_button:
            self.run_blockcheck_button.config(state='normal', text="Run Blockcheck")
    
    def _on_presets_table_click(self, event) -> None:
        """Handle click on presets table for cell editing"""
        region = self.presets_tree.identify_region(event.x, event.y)
        if region == "cell":
            column = self.presets_tree.identify_column(event.x)
            item = self.presets_tree.identify_row(event.y)
            
            if item and column and column.startswith('#'):
                try:
                    # Get column index (1-based)
                    col_index = int(column.replace('#', ''))
                    
                    # Only allow editing Name (column 1) and Status (column 2)
                    # Column 3 (Config) is not editable
                    if col_index == 1:  # Name column
                        self._start_editing_cell(item, col_index)
                    elif col_index == 2:  # Status column
                        self._start_editing_status(item, col_index)
                except (ValueError, AttributeError):
                    pass
    
    def _start_editing_cell(self, item, column) -> None:
        """Start editing a cell (Name column)"""
        if self.presets_edit_entry:
            self._finish_editing_cell()
        
        # Get cell bounds
        bbox = self.presets_tree.bbox(item, column)
        if not bbox:
            return
        
        x, y, width, height = bbox
        
        # Get current value
        values = list(self.presets_tree.item(item, 'values'))
        current_value = values[column - 1] if column - 1 < len(values) else ""
        
        # Create entry widget
        self.presets_editing_cell = (item, column)
        self.presets_edit_entry = tk.Entry(
            self.presets_tree,
            font=('Consolas', 9) if sys.platform == 'win32' else ('Courier', 9),
            bg=self.entry_bg,
            fg=self.fg_color,
            selectbackground=self.select_bg,
            selectforeground=self.select_fg,
            borderwidth=1,
            relief='flat',
            highlightthickness=1,
            highlightcolor='#0078d4',
            highlightbackground='#3d3d3d'
        )
        self.presets_edit_entry.insert(0, current_value)
        self.presets_edit_entry.place(x=x, y=y, width=width, height=height)
        self.presets_edit_entry.focus()
        self.presets_edit_entry.select_range(0, tk.END)
        
        # Bind events
        self.presets_edit_entry.bind('<Return>', lambda e: self._finish_editing_cell())
        self.presets_edit_entry.bind('<FocusOut>', lambda e: self._finish_editing_cell())
        self.presets_edit_entry.bind('<Escape>', lambda e: self._cancel_editing_cell())
    
    def _start_editing_status(self, item, column) -> None:
        """Start editing Status column with dropdown"""
        if self.presets_edit_entry:
            self._finish_editing_cell()
        
        # Get cell bounds
        bbox = self.presets_tree.bbox(item, column)
        if not bbox:
            return
        
        x, y, width, height = bbox
        
        # Get current value
        values = list(self.presets_tree.item(item, 'values'))
        current_value = values[column - 1] if column - 1 < len(values) else "Working"
        
        # Create combobox widget
        self.presets_editing_cell = (item, column)
        self.presets_edit_entry = ttk.Combobox(
            self.presets_tree,
            values=["Working", "Not Working"],
            state="readonly",
            font=('Consolas', 9) if sys.platform == 'win32' else ('Courier', 9)
        )
        self.presets_edit_entry.set(current_value)
        self.presets_edit_entry.place(x=x, y=y, width=width, height=height)
        self.presets_edit_entry.focus()
        
        # Bind events
        self.presets_edit_entry.bind('<<ComboboxSelected>>', lambda e: self._finish_editing_cell())
        self.presets_edit_entry.bind('<FocusOut>', lambda e: self._finish_editing_cell())
        self.presets_edit_entry.bind('<Escape>', lambda e: self._cancel_editing_cell())
    
    def _finish_editing_cell(self) -> None:
        """Finish editing a cell and save the value"""
        if not self.presets_editing_cell or not self.presets_edit_entry:
            return
        
        item, column = self.presets_editing_cell
        
        # Get new value
        if isinstance(self.presets_edit_entry, tk.Entry):
            new_value = self.presets_edit_entry.get()
        else:  # Combobox
            new_value = self.presets_edit_entry.get()
        
        # Get current values
        values = list(self.presets_tree.item(item, 'values'))
        
        # Get tags - the actual config is stored in tags[0]
        tags = list(self.presets_tree.item(item, 'tags'))
        config = tags[0] if tags else values[2]  # Use tag config if available, fallback to displayed value
        
        # Handle Config column editing (column 3)
        if column == 3:  # Config column
            # Ensure config starts with "winws " prefix when storing
            full_config = new_value
            if not full_config.startswith("winws "):
                full_config = "winws " + full_config
            
            # Store full config in tag
            if len(tags) == 0:
                tags.append(full_config)
            else:
                tags[0] = full_config
            
            # Display config without "winws " prefix
            display_config = full_config
            if display_config.startswith("winws "):
                display_config = display_config[6:]  # Remove "winws " prefix
            new_value = display_config
        
        # Update values
        if column - 1 < len(values):
            values[column - 1] = new_value
        
        old_tag = tags[1] if len(tags) > 1 else "working"
        
        # Update status if Status column was edited
        if column == 2:  # Status column (now column 2)
            is_not_working = new_value == "Not Working"
            new_tag = "not_working" if is_not_working else "working"
            tags[1] = new_tag
            
            # Update config manager using the actual config from tag
            actual_config = tags[0] if tags else values[2]
            if is_not_working:
                self.config_manager.mark_config_not_working(actual_config)
            else:
                self.config_manager.unmark_config_not_working(actual_config)
            self.config_manager.save_config(self.params_entry.get('1.0', tk.END).strip())
        
        # Update name if Name column was edited
        elif column == 1:  # Name column
            # Use actual config from tag
            actual_config = tags[0] if tags else values[2]
            self.config_manager.set_config_name(actual_config, new_value)
            self.config_manager.save_config(self.params_entry.get('1.0', tk.END).strip())
        
        # Update tree item
        self.presets_tree.item(item, values=values, tags=tags)
        
        # Cleanup
        self._cancel_editing_cell()
    
    def _cancel_editing_cell(self) -> None:
        """Cancel editing a cell"""
        if self.presets_edit_entry:
            self.presets_edit_entry.destroy()
            self.presets_edit_entry = None
        self.presets_editing_cell = None
    
    def _on_presets_table_key(self, event) -> None:
        """Handle key events in presets table"""
        if event.keysym == 'Return' and self.presets_editing_cell:
            self._finish_editing_cell()
    
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
        
        # Run/Stop button - will be styled based on running state
        self.run_button = ttk.Button(
            control_frame, text="Run", command=self.toggle_run, style='Run.TButton'
        )
        self.run_button.grid(row=0, column=4, padx=(5, 0), pady=5)
    
    def _create_logs_section(self, parent: ttk.Frame) -> None:
        """Create the logs text widget"""
        logs_label = ttk.Label(parent, text="Logs:")
        logs_label.grid(row=1, column=0, sticky=tk.W, pady=(0, 5))
        
        # Create a frame to contain Text and Scrollbar for better control
        text_frame = ttk.Frame(parent)
        text_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)
        
        # Logs text widget (readonly, scrollable)
        # Use tk.Text instead of ScrolledText for better scrollbar control
        self.logs_text = tk.Text(
            text_frame,
            wrap=tk.WORD,
            state='disabled',
            height=15,
            font=('Consolas', 9) if sys.platform == 'win32' else ('Courier', 9),
            bg=self.entry_bg,
            fg=self.fg_color,
            insertbackground=self.fg_color,
            selectbackground=self.select_bg,
            selectforeground=self.select_fg,
            highlightbackground='#3d3d3d',
            highlightcolor='#0078d4',
            highlightthickness=1,
            borderwidth=0,
            relief='flat'
        )
        self.logs_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Use ttk.Scrollbar instead of tk.Scrollbar for dark theme support
        logs_scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.logs_text.yview)
        self.logs_text.configure(yscrollcommand=logs_scrollbar.set)
        logs_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Configure text widget tags for dark theme with improved colors
        self.logs_text.tag_config('info', foreground='#4ec9b0')  # Green-cyan for INFO
        self.logs_text.tag_config('warning', foreground='#ffa500')
        self.logs_text.tag_config('error', foreground='#f48771')  # Red for ERROR
        self.logs_text.tag_config('success', foreground='#89d185')  # Green for SUCCESS
        self.logs_text.tag_config('debug', foreground='#808080')  # Gray for DEBUG
    
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
        # Get text from Text widget (remove trailing newline)
        params_str = self.params_entry.get('1.0', tk.END).strip()
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
        self.run_button.config(text="Stop", style='Stop.TButton')
        self.params_entry.config(state='disabled')
        if hasattr(self, 'debug_checkbox'):
            self.debug_checkbox.config(state='disabled')
        self._update_status_bar(running=True)

    def _update_ui_for_stopped(self) -> None:
        """Update UI elements when winws.exe is stopped"""
        self.run_button.config(text="Run", style='Run.TButton')
        self.params_entry.config(state='normal')
        if hasattr(self, 'debug_checkbox'):
            self.debug_checkbox.config(state='normal')
        self._update_status_bar(running=False)
    
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
            self._unmark_config_not_working,
            self._refresh_suggestions,
            self.project_root,
            self.config_manager
        )
    
    def _refresh_suggestions(self) -> Tuple[Set[str], Set[str]]:
        """Refresh suggestions by re-parsing logs and returning updated configs"""
        # Re-parse blockcheck logs
        blockcheck_configs = self.blockcheck_parser.parse_logs()
        
        # Combine blockcheck and user configurations
        user_configs = self.config_manager.get_user_configs()
        all_configs = set(blockcheck_configs) | user_configs
        
        # Get not working configs
        not_working_configs = self.config_manager.get_not_working_configs()
        
        return all_configs, not_working_configs
    
    def apply_suggestion(self, configuration: str) -> None:
        """Apply a suggested configuration to the parameters field"""
        self.params_entry.delete('1.0', tk.END)
        self.params_entry.insert('1.0', configuration)
        config_preview = (
            configuration[:50] + "..." if len(configuration) > 50 else configuration
        )
        self.log_info(f"Applied suggestion: {config_preview}")
    
    def _mark_config_not_working(self, configuration: str) -> None:
        """Mark a configuration as 'not working'"""
        self.config_manager.mark_config_not_working(configuration)
        params_str = self.params_entry.get('1.0', tk.END).strip()
        self.config_manager.save_config(params_str)
        # Refresh presets table
        self._refresh_presets_table()
    
    def _unmark_config_not_working(self, configuration: str) -> None:
        """Remove a configuration from 'not working' list"""
        self.config_manager.unmark_config_not_working(configuration)
        params_str = self.params_entry.get('1.0', tk.END).strip()
        self.config_manager.save_config(params_str)
        # Refresh presets table
        self._refresh_presets_table()
    
    def _on_resize(self, event: tk.Event) -> None:
        """Handle window resize event - save geometry with debouncing"""
        # Check if window size actually changed by comparing current size with last known size
        if not self.root or not self.root.winfo_exists():
            return
        
        try:
            # Get current window dimensions - use event width/height if available, otherwise winfo
            if hasattr(event, 'width') and hasattr(event, 'height') and event.width > 1 and event.height > 1:
                current_width = event.width
                current_height = event.height
            else:
                current_width = self.root.winfo_width()
                current_height = self.root.winfo_height()
            
            # Only proceed if size actually changed
            if (self._last_width is not None and self._last_height is not None and
                current_width == self._last_width and current_height == self._last_height):
                return
            
            self.log_info(f"Window resize detected: {self._last_width}x{self._last_height} -> {current_width}x{current_height}")
            
            # Update last known size
            self._last_width = current_width
            self._last_height = current_height
        except (tk.TclError, RuntimeError) as e:
            self.log_error(f"Error getting window dimensions: {e}")
            return
        
        # Cancel any pending save operation
        if self._resize_timer is not None:
            self.root.after_cancel(self._resize_timer)
        
        # Schedule save after 300ms of no resize events (debouncing)
        def save_geometry():
            if self.config_manager and self.root and self.root.winfo_exists():
                try:
                    geometry = self.root.geometry()
                    if geometry:  # Save if geometry exists
                        self.config_manager.save_window_geometry("main_window", geometry)
                        self.log_info(f"Window geometry saved: {geometry}")
                except Exception as e:
                    self.log_error(f"Error saving window geometry: {e}")
            self._resize_timer = None
        
        self._resize_timer = self.root.after(300, save_geometry)
    
    def on_closing(self) -> None:
        """Handle window close event"""
        # Cancel any pending resize save
        if self._resize_timer is not None:
            self.root.after_cancel(self._resize_timer)
            self._resize_timer = None
        
        # Save geometry one final time on close
        if self.config_manager and self.root:
            try:
                geometry = self.root.geometry()
                if geometry:
                    self.config_manager.save_window_geometry("main_window", geometry)
                    self.log_info(f"Window geometry saved on close: {geometry}")
            except Exception as e:
                self.log_error(f"Error saving window geometry on close: {e}")
        
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
    from ctypes import windll

    # Makes the app DPI aware on Windows 10/11
    try:
        windll.shcore.SetProcessDpiAwareness(1)
    except:
        pass
    """Main entry point"""
    app = WinWSGUI()
    app.run()


if __name__ == "__main__":
    main()
