#!/usr/bin/env python3
"""
Suggestions window for WinWS GUI
Displays a table of suggested configurations from blockcheck logs and user configs
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Set, Callable, Optional


class SuggestionsWindow:
    """Window displaying configuration suggestions"""
    
    def __init__(
        self,
        parent: tk.Tk,
        all_configs: Set[str],
        not_working_configs: Set[str],
        on_apply: Callable[[str], None],
        on_mark_not_working: Callable[[str], None],
        on_unmark_not_working: Callable[[str], None]
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
        """
        self.parent = parent
        self.all_configs = all_configs
        self.not_working_configs = not_working_configs
        self.on_apply = on_apply
        self.on_mark_not_working = on_mark_not_working
        self.on_unmark_not_working = on_unmark_not_working
        
        self.window = None
        self.tree = None
        self.mark_button = None
        
        self._create_window()
    
    def _create_window(self) -> None:
        """Create and populate the suggestions window"""
        self.window = tk.Toplevel(self.parent)
        self.window.title("Configuration Suggestions")
        self.window.geometry("950x500")
        
        # Configure grid
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(1, weight=1)
        
        # Header label
        sorted_configs = self._get_sorted_configs()
        header_label = ttk.Label(
            self.window,
            text=f"Found {len(sorted_configs)} configuration(s). Select a row and use the buttons below. Double-click to apply.",
            padding="10"
        )
        header_label.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(10, 5))
        
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
        
        # Configure tags
        tree.tag_configure("working", foreground="black")
        tree.tag_configure("not_working", foreground="gray")
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        # Grid
        tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
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
        
        # Close button
        close_button = ttk.Button(button_frame, text="Close", command=self.window.destroy)
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
            self.window.destroy()
    
    def _apply_selected(self) -> None:
        """Apply the selected configuration"""
        config = self._get_selected_config()
        if config:
            self.on_apply(config)
            self.window.destroy()
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
        self.window.destroy()
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
        
        context_menu = tk.Menu(self.window, tearoff=0)
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
        self.window.destroy()
    
    def _mark_working(self, config: str) -> None:
        """Mark configuration as working"""
        self.on_unmark_not_working(config)
        self.window.destroy()

