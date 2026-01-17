#!/usr/bin/env python3
"""
System tray management for WinWS GUI
Handles system tray icon and menu
"""

import sys
from typing import Optional, Callable, Any

try:
    import pystray
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False

from icon_manager import IconManager


class TrayManager:
    """Manages system tray icon and functionality"""
    
    def __init__(
        self,
        icon_manager: IconManager,
        on_show_window: Callable[[], None],
        on_stop_winws: Callable[[], None],
        on_quit: Callable[[], None],
        is_running_getter: Callable[[], bool]
    ):
        """
        Initialize TrayManager
        
        Args:
            icon_manager: IconManager instance for loading tray icon
            on_show_window: Callback to show the main window
            on_stop_winws: Callback to stop winws.exe
            on_quit: Callback to quit the application
            is_running_getter: Function that returns whether winws.exe is running
        """
        self.icon_manager = icon_manager
        self.on_show_window = on_show_window
        self.on_stop_winws = on_stop_winws
        self.on_quit = on_quit
        self.is_running_getter = is_running_getter
        self.tray_icon: Optional[Any] = None  # pystray.Icon when available
    
    def is_available(self) -> bool:
        """Check if system tray is available"""
        return TRAY_AVAILABLE
    
    def create_tray_icon(self) -> None:
        """Create and start the system tray icon"""
        if not TRAY_AVAILABLE:
            return
        
        image = self.icon_manager.create_tray_icon()
        if image is None:
            return
        
        menu = pystray.Menu(
            pystray.MenuItem("Show Window", self.on_show_window, default=True),
            pystray.MenuItem(
                "Stop winws.exe",
                self.on_stop_winws,
                enabled=lambda item: self.is_running_getter()
            ),
            pystray.MenuItem("Quit", self.on_quit)
        )
        
        self.tray_icon = pystray.Icon("winws_gui", image, "WinWS GUI", menu)
        self.tray_icon.run_detached()
    
    def stop_tray_icon(self) -> None:
        """Stop the system tray icon"""
        if self.tray_icon:
            self.tray_icon.stop()
            self.tray_icon = None

