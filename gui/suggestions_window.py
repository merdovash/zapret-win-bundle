#!/usr/bin/env python3
"""
Suggestions window for WinWS GUI
Displays a table of suggested configurations from blockcheck logs and user configs
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Set, Callable, Optional, Tuple
from config_manager import ConfigManager
import subprocess
import threading
import sys
from pathlib import Path

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


class SuggestionsWindow:
    """Window displaying configuration suggestions"""
    
    def __init__(
        self,
        parent: tk.Tk,
        all_configs: Set[str],
        not_working_configs: Set[str],
        on_apply: Callable[[str], None],
        on_mark_not_working: Callable[[str], None],
        on_unmark_not_working: Callable[[str], None],
        on_refresh: Optional[Callable[[], Tuple[Set[str], Set[str]]]] = None,
        project_root: Optional[Path] = None,
        config_manager: Optional[ConfigManager] = None
    ):
        """
        Initialize SuggestionsWindow
        
        Args:
            parent: Parent window
            all_configs: Set of all available configurations
            not_working_configs: Set of configurations marked as not working
            on_apply: Callback function when a configuration is applied
            on_mark_not_working: Callback function when a configuration is marked as not working
            on_unmark_not_working: Callback function when a configuration is unmarked
            on_refresh: Optional callback function to refresh configurations (returns (all_configs, not_working_configs))
            project_root: Optional project root path for running blockcheck.cmd
        """
        self.parent = parent
        self.all_configs = all_configs
        self.not_working_configs = not_working_configs
        self.on_apply = on_apply
        self.on_mark_not_working = on_mark_not_working
        self.on_unmark_not_working = on_unmark_not_working
        self.on_refresh = on_refresh
        self.project_root = project_root
        self.config_manager = config_manager
        
        self.window = None
        self.tree = None
        self.mark_button = None
        self.run_blockcheck_button = None
        self.header_label = None
        self._resize_timer = None  # Timer for debouncing resize events
        self._last_geometry = None  # Track last saved geometry to avoid unnecessary saves
        self._last_width = None
        self._last_height = None
        
        self._create_window()
    
    def _create_window(self) -> None:
        """Create and populate the suggestions window"""
        self.window = tk.Toplevel(self.parent)
        self.window.title("Configuration Suggestions")
        
        # Setup dark theme
        self._setup_dark_theme()
        
        # Configure grid
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(1, weight=1)
        
        # Set dark title bar (Windows only) - call after window is created and shown
        def apply_dark_title_bar():
            set_dark_title_bar(self.window)
            # Also try again after a short delay to ensure window is fully rendered
            self.window.after(100, lambda: set_dark_title_bar(self.window))
        self.window.after_idle(apply_dark_title_bar)
        
        # Header label
        sorted_configs = self._get_sorted_configs()
        self.header_label = ttk.Label(
            self.window,
            text=f"Found {len(sorted_configs)} configuration(s). Select a row and use the buttons below. Double-click to apply.",
            padding="10"
        )
        self.header_label.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(10, 5))
        
        # Table frame
        table_frame = ttk.Frame(self.window)
        table_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=10, pady=5)
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
        
        # Create Treeview
        self.tree = self._create_treeview(table_frame)
        
        # Populate table
        self._populate_table()
        
        # Button frame
        self._create_button_frame()
        
        # Load saved geometry or use default - do this after widgets are created
        window_name = "suggestions_window"
        saved_geometry = None
        if self.config_manager:
            saved_geometry = self.config_manager.get_window_geometry(window_name)
        
        # Set geometry after window is fully created
        def apply_geometry():
            if saved_geometry:
                self.window.geometry(saved_geometry)
            else:
                self.window.geometry("950x500")
            # Initialize last known size
            self.window.update_idletasks()
            self._last_width = self.window.winfo_width()
            self._last_height = self.window.winfo_height()
        self.window.after_idle(apply_geometry)
        
        # Bind window resize events to save geometry
        # Bind to all Configure events and filter by actual size change
        self.window.bind("<Configure>", self._on_resize)
        
        # Bind window close event to save geometry
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _setup_dark_theme(self) -> None:
        """Setup dark theme for the suggestions window"""
        # Dark theme colors
        self.bg_color = "#1e1e1e"  # Dark gray background
        self.fg_color = "#d4d4d4"  # Light gray foreground
        self.entry_bg = "#2d2d2d"  # Slightly lighter for entries
        self.select_bg = "#3d3d3d"  # Selection background
        self.select_fg = "#ffffff"  # Selection foreground
        
        # Configure window
        self.window.configure(bg=self.bg_color, highlightbackground='#3d3d3d', highlightthickness=1)
        
        # Configure ttk style
        style = ttk.Style()
        style.theme_use('clam')
        
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
        style.configure('Treeview',
                       background=self.entry_bg,
                       foreground=self.fg_color,
                       fieldbackground=self.entry_bg,
                       borderwidth=1,
                       relief='flat')
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
    
    def _get_sorted_configs(self) -> list:
        """Get configurations sorted with working ones first"""
        working_configs = [c for c in self.all_configs if c not in self.not_working_configs]
        not_working_configs = [c for c in self.all_configs if c in self.not_working_configs]
        return working_configs + not_working_configs
    
    def _create_treeview(self, parent: ttk.Frame) -> ttk.Treeview:
        """Create and configure the treeview table"""
        columns = ("#", "Status", "Configuration")
        tree = ttk.Treeview(parent, columns=columns, show="headings", height=20)
        
        # Configure columns
        tree.heading("#", text="#")
        tree.heading("Status", text="Status")
        tree.heading("Configuration", text="Configuration")
        tree.column("#", width=50, anchor=tk.CENTER)
        tree.column("Status", width=100, anchor=tk.CENTER)
        tree.column("Configuration", width=750, anchor=tk.W)
        
        # Configure tags for dark theme
        tree.tag_configure("working", foreground="#d4d4d4")
        tree.tag_configure("not_working", foreground="#808080")
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        # Grid
        tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Ensure scrollbar is dark (ttk.Scrollbar should use the style, but let's make sure)
        try:
            # Also configure any tk.Scrollbar if it exists
            for widget in parent.winfo_children():
                if isinstance(widget, tk.Scrollbar):
                    widget.configure(
                        bg='#3d3d3d',
                        troughcolor=self.bg_color,
                        activebackground='#4d4d4d',
                        borderwidth=0,
                        highlightthickness=0,
                        relief='flat'
                    )
        except Exception:
            pass
        
        # Bind events
        tree.bind("<Double-1>", self._on_double_click)
        tree.bind("<<TreeviewSelect>>", lambda e: self._update_mark_button_state())
        tree.bind("<Button-3>", self._on_right_click)
        tree.bind("<Button-2>", self._on_right_click)
        
        return tree
    
    def _populate_table(self) -> None:
        """Populate the table with configurations"""
        sorted_configs = self._get_sorted_configs()
        
        for i, config in enumerate(sorted_configs, start=1):
            is_not_working = config in self.not_working_configs
            status = "Not Working" if is_not_working else "Working"
            tag = "not_working" if is_not_working else "working"
            self.tree.insert("", tk.END, values=(i, status, config), tags=(config, tag))
    
    def _create_button_frame(self) -> None:
        """Create button frame with action buttons"""
        button_frame = ttk.Frame(self.window)
        button_frame.grid(row=2, column=0, pady=10)
        
        # Apply button
        apply_button = ttk.Button(button_frame, text="Apply Selected", command=self._apply_selected)
        apply_button.pack(side=tk.LEFT, padx=5)
        
        # Mark button
        self.mark_button = ttk.Button(
            button_frame,
            text="Mark as Not Working",
            command=self._toggle_not_working,
            state='disabled'
        )
        self.mark_button.pack(side=tk.LEFT, padx=5)
        
        # Run Blockcheck button
        if self.project_root is not None:
            self.run_blockcheck_button = ttk.Button(
                button_frame,
                text="Run Blockcheck",
                command=self._run_blockcheck
            )
            self.run_blockcheck_button.pack(side=tk.LEFT, padx=5)
        
        # Close button
        close_button = ttk.Button(button_frame, text="Close", command=self._on_close)
        close_button.pack(side=tk.LEFT, padx=5)
    
    def _get_selected_config(self) -> Optional[str]:
        """Get the configuration string from selected item"""
        selection = self.tree.selection()
        if not selection:
            return None
        
        item = self.tree.item(selection[0])
        config = item['tags'][0] if item['tags'] else item['values'][2]
        return config
    
    def _on_double_click(self, event) -> None:
        """Handle double-click on table row"""
        config = self._get_selected_config()
        if config:
            self.on_apply(config)
            self._on_close()
    
    def _apply_selected(self) -> None:
        """Apply the selected configuration"""
        config = self._get_selected_config()
        if config:
            self.on_apply(config)
            self._on_close()
        else:
            messagebox.showwarning("No Selection", "Please select a configuration from the table.")
    
    def _toggle_not_working(self) -> None:
        """Toggle not working status of selected configuration"""
        config = self._get_selected_config()
        if not config:
            messagebox.showwarning("No Selection", "Please select a configuration from the table first.")
            return
        
        is_not_working = config in self.not_working_configs
        if is_not_working:
            self.on_unmark_not_working(config)
        else:
            self.on_mark_not_working(config)
        
        # Refresh window
        self._on_close()
        # Note: The parent should recreate this window if needed
    
    def _update_mark_button_state(self) -> None:
        """Update the mark button text and state based on selection"""
        config = self._get_selected_config()
        if config:
            is_not_working = config in self.not_working_configs
            self.mark_button.config(
                text="Mark as Working" if is_not_working else "Mark as Not Working",
                state='normal'
            )
        else:
            self.mark_button.config(state='disabled')
    
    def _on_right_click(self, event) -> None:
        """Handle right-click context menu"""
        config = self._get_selected_config()
        if not config:
            return
        
        context_menu = tk.Menu(
            self.window, 
            tearoff=0,
            bg=self.entry_bg,
            fg=self.fg_color,
            selectcolor=self.select_bg,
            activebackground=self.select_bg,
            activeforeground=self.select_fg
        )
        is_not_working = config in self.not_working_configs
        
        if is_not_working:
            context_menu.add_command(label="Mark as Working", command=lambda: self._mark_working(config))
        else:
            context_menu.add_command(label="Mark as Not Working", command=lambda: self._mark_not_working(config))
        
        try:
            context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            context_menu.grab_release()
    
    def _mark_not_working(self, config: str) -> None:
        """Mark configuration as not working"""
        self.on_mark_not_working(config)
        self._on_close()
    
    def _mark_working(self, config: str) -> None:
        """Mark configuration as working"""
        self.on_unmark_not_working(config)
        self._on_close()
    
    def _run_blockcheck(self) -> None:
        """Run blockcheck.cmd and refresh the table when finished"""
        if self.project_root is None:
            messagebox.showerror("Error", "Project root not specified")
            return
        
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
                self.window.after(0, self._refresh_table)
            except Exception as e:
                # Show error on main thread
                self.window.after(0, lambda: messagebox.showerror("Error", f"Failed to run blockcheck: {e}"))
                self.window.after(0, self._enable_blockcheck_button)
        
        thread = threading.Thread(target=run_and_refresh, daemon=True)
        thread.start()
    
    def _enable_blockcheck_button(self) -> None:
        """Re-enable the blockcheck button"""
        if self.run_blockcheck_button:
            self.run_blockcheck_button.config(state='normal', text="Run Blockcheck")
    
    def _refresh_table(self) -> None:
        """Refresh the table with updated configurations"""
        # Re-enable button
        self._enable_blockcheck_button()
        
        # Get fresh configurations
        if self.on_refresh:
            all_configs, not_working_configs = self.on_refresh()
            self.all_configs = all_configs
            self.not_working_configs = not_working_configs
        else:
            # Fallback: just clear and repopulate with existing data
            pass
        
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Update header
        sorted_configs = self._get_sorted_configs()
        if self.header_label:
            self.header_label.config(
                text=f"Found {len(sorted_configs)} configuration(s). Select a row and use the buttons below. Double-click to apply."
            )
        
        # Repopulate table
        self._populate_table()
    
    def _on_resize(self, event: tk.Event) -> None:
        """Handle window resize event - save geometry with debouncing"""
        # Check if window size actually changed by comparing current size with last known size
        if not self.window or not self.window.winfo_exists():
            print(f"[RESIZE] Window not available")
            return
        
        try:
            # Get current window dimensions - use event width/height if available, otherwise winfo
            if hasattr(event, 'width') and hasattr(event, 'height') and event.width > 1 and event.height > 1:
                current_width = event.width
                current_height = event.height
                print(f"[RESIZE] Event dimensions: {current_width}x{current_height}, widget: {event.widget}")
            else:
                current_width = self.window.winfo_width()
                current_height = self.window.winfo_height()
                print(f"[RESIZE] Winfo dimensions: {current_width}x{current_height}")
            
            # Only proceed if size actually changed
            if (self._last_width is not None and self._last_height is not None and
                current_width == self._last_width and current_height == self._last_height):
                print(f"[RESIZE] Size unchanged ({current_width}x{current_height}), skipping")
                return
            
            print(f"[RESIZE] Size changed from {self._last_width}x{self._last_height} to {current_width}x{current_height}")
            
            # Update last known size
            self._last_width = current_width
            self._last_height = current_height
        except (tk.TclError, RuntimeError) as e:
            print(f"[RESIZE] Error getting dimensions: {e}")
            return
        
        # Cancel any pending save operation
        if self._resize_timer is not None:
            self.window.after_cancel(self._resize_timer)
        
        # Schedule save after 300ms of no resize events (debouncing)
        def save_geometry():
            print(f"[RESIZE] save_geometry() called")
            if not self.config_manager:
                print(f"[RESIZE] ERROR: config_manager is None")
                return
            if not self.window or not self.window.winfo_exists():
                print(f"[RESIZE] ERROR: window is None or doesn't exist")
                return
            try:
                geometry = self.window.geometry()
                print(f"[RESIZE] Current geometry string: {geometry}")
                if geometry:  # Save if geometry exists
                    print(f"[RESIZE] Calling save_window_geometry('suggestions_window', '{geometry}')")
                    self.config_manager.save_window_geometry("suggestions_window", geometry)
                    print(f"[RESIZE] SUCCESS: Geometry saved to config_manager")
                    self._last_geometry = geometry
                else:
                    print(f"[RESIZE] ERROR: geometry string is empty")
            except Exception as e:
                import traceback
                print(f"[RESIZE] EXCEPTION saving geometry: {e}")
                traceback.print_exc()
            self._resize_timer = None
        
        print(f"[RESIZE] Scheduling save in 300ms")
        self._resize_timer = self.window.after(300, save_geometry)
    
    def _on_close(self) -> None:
        """Handle window close event - save geometry before destroying"""
        # Cancel any pending resize save
        if self._resize_timer is not None:
            self.window.after_cancel(self._resize_timer)
            self._resize_timer = None
        
        # Save geometry one final time on close
        if self.config_manager and self.window:
            geometry = self.window.geometry()
            self.config_manager.save_window_geometry("suggestions_window", geometry)
        self.window.destroy()

