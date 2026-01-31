#!/usr/bin/env python3
"""
Icon management for WinWS GUI
Handles loading and setting window icons, taskbar icons, and tray icons
"""

import sys
import os
import tempfile
from pathlib import Path
from typing import Optional

try:
    import pystray
    from PIL import Image, ImageDraw, ImageTk
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False

# Windows-specific imports
if sys.platform == 'win32':
    try:
        from ctypes import windll
        WINDOWS_AVAILABLE = True
    except ImportError:
        WINDOWS_AVAILABLE = False
else:
    WINDOWS_AVAILABLE = False


class IconManager:
    """Manages icon loading and setting for the GUI application"""
    
    def __init__(self, script_dir: Path):
        """
        Initialize IconManager
        
        Args:
            script_dir: Directory where the script is located (for finding icon files)
        """
        self.script_dir = script_dir
        self.icon_dir = script_dir / "icon"
        self.temp_ico_path: Optional[str] = None
    
    def set_app_user_model_id(self, app_id: str = "com.winws.gui") -> None:
        """Set AppUserModelID for Windows taskbar icon"""
        if WINDOWS_AVAILABLE:
            try:
                windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
            except Exception as e:
                print(f"Warning: Could not set AppUserModelID: {e}")
    
    def setup_window_icon(self, root_window) -> None:
        """
        Setup window icon for both title bar and taskbar
        
        Args:
            root_window: Tkinter root window
        """
        ico_path = self.icon_dir / "icon.ico"
        icon_64_path = self.icon_dir / "icon_64x64.png"
        icon_jpg_path = self.icon_dir / "icon.jpg"
        
        # Try pre-generated ICO file first
        if ico_path.exists():
            try:
                if sys.platform == 'win32':
                    root_window.iconbitmap(str(ico_path))
                    self.temp_ico_path = None
                
                # Set window icon - prefer pre-generated 64x64 PNG
                if TRAY_AVAILABLE:
                    if icon_64_path.exists():
                        self._set_window_icon_from_png(root_window, icon_64_path)
                    else:
                        self._set_window_icon_from_ico(root_window, ico_path)
            except Exception as e:
                print(f"Warning: Could not use pre-generated ICO: {e}")
                ico_path = None
        
        # Fallback: create ICO from icon.jpg
        if not ico_path or not ico_path.exists():
            if icon_jpg_path.exists():
                self._setup_icon_from_jpg(root_window, icon_jpg_path)
    
    def _set_window_icon_from_png(self, root_window, png_path: Path) -> None:
        """Set window icon from PNG file"""
        try:
            window_icon = Image.open(png_path)
            if window_icon.mode != 'RGBA':
                window_icon = window_icon.convert('RGBA')
            icon_photo = ImageTk.PhotoImage(window_icon)
            root_window.iconphoto(False, icon_photo)
            root_window.icon_image = icon_photo
        except Exception as e:
            print(f"Warning: Could not load PNG icon: {e}")
    
    def _set_window_icon_from_ico(self, root_window, ico_path: Path) -> None:
        """Set window icon from ICO file"""
        try:
            ico_image = Image.open(ico_path)
            window_icon = ico_image.resize((64, 64), Image.Resampling.LANCZOS)
            icon_photo = ImageTk.PhotoImage(window_icon)
            root_window.iconphoto(False, icon_photo)
            root_window.icon_image = icon_photo
        except Exception as e:
            print(f"Warning: Could not load ICO for window icon: {e}")
    
    def _setup_icon_from_jpg(self, root_window, jpg_path: Path) -> None:
        """Setup icon from JPG file (fallback method)"""
        if not TRAY_AVAILABLE:
            print("Warning: PIL not available, cannot set custom icon")
            return
        
        try:
            original_icon = Image.open(jpg_path)
            if original_icon.mode != 'RGBA':
                original_icon = original_icon.convert('RGBA')
            
            # Create window icon
            window_icon = original_icon.copy()
            if window_icon.size[0] > 64 or window_icon.size[1] > 64:
                window_icon = window_icon.resize((64, 64), Image.Resampling.LANCZOS)
            
            icon_photo = ImageTk.PhotoImage(window_icon)
            root_window.iconphoto(False, icon_photo)
            root_window.icon_image = icon_photo
            
            # For Windows taskbar, create temporary ICO
            if sys.platform == 'win32':
                self._create_temp_ico(root_window, original_icon)
        except Exception as e:
            print(f"Warning: Could not load icon: {e}")
    
    def _create_temp_ico(self, root_window, original_icon: Image.Image) -> None:
        """Create temporary ICO file for Windows taskbar"""
        try:
            temp_ico = tempfile.NamedTemporaryFile(delete=False, suffix='.ico')
            temp_ico_path = temp_ico.name
            temp_ico.close()
            
            ico_image = original_icon.resize((256, 256), Image.Resampling.LANCZOS)
            ico_image.save(temp_ico_path, format='ICO')
            
            root_window.iconbitmap(temp_ico_path)
            self.temp_ico_path = temp_ico_path
        except Exception as e:
            print(f"Warning: Could not create ICO for taskbar: {e}")
            self._cleanup_temp_ico()
    
    def create_tray_icon(self) -> Optional[Image.Image]:
        """
        Create system tray icon image
        
        Returns:
            PIL Image object for tray icon or None if tray is not available
        """
        if not TRAY_AVAILABLE:
            return None
        
        image = self._load_tray_image()
        if image is None:
            image = self._create_fallback_icon()
        
        return image
    
    def _load_tray_image(self) -> Optional[Image.Image]:
        """Load image for system tray icon"""
        icon_32_path = self.icon_dir / "icon_32x32.png"
        icon_ico_path = self.icon_dir / "icon.ico"
        icon_jpg_path = self.icon_dir / "icon.jpg"
        
        # Try pre-generated 32x32 PNG first
        if icon_32_path.exists():
            try:
                image = Image.open(icon_32_path)
                if image.mode != 'RGBA':
                    image = image.convert('RGBA')
                return image
            except Exception as e:
                print(f"Warning: Could not load pre-generated 32x32 icon: {e}")
        
        # Fallback to ICO file
        if icon_ico_path.exists():
            try:
                image = Image.open(icon_ico_path)
                if hasattr(image, 'sizes') and (32, 32) in image.sizes:
                    image.load()
                if image.size != (32, 32):
                    image = image.resize((32, 32), Image.Resampling.LANCZOS)
                if image.mode != 'RGBA':
                    image = image.convert('RGBA')
                return image
            except Exception as e:
                print(f"Warning: Could not load ICO for tray: {e}")
        
        # Fallback to JPG
        if icon_jpg_path.exists():
            try:
                image = Image.open(icon_jpg_path)
                if image.mode != 'RGBA':
                    image = image.convert('RGBA')
                image = image.resize((32, 32), Image.Resampling.LANCZOS)
                return image
            except Exception as e:
                print(f"Warning: Could not load JPG for tray: {e}")
        
        return None
    
    def _create_fallback_icon(self) -> Image.Image:
        """Create a simple fallback icon"""
        print("Warning: No icon file found, using fallback icon")
        image = Image.new('RGBA', (32, 32), color=(255, 255, 255, 255))
        draw = ImageDraw.Draw(image)
        draw.rectangle([8, 8, 24, 24], fill=(0, 0, 0, 255))
        return image
    
    def cleanup(self) -> None:
        """Clean up temporary files"""
        self._cleanup_temp_ico()
    
    def _cleanup_temp_ico(self) -> None:
        """Clean up temporary ICO file if it exists"""
        if self.temp_ico_path and os.path.exists(self.temp_ico_path):
            try:
                os.unlink(self.temp_ico_path)
            except Exception:
                pass
            self.temp_ico_path = None

