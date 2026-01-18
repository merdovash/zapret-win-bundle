#!/usr/bin/env python3
"""
Configuration management for WinWS GUI
Handles loading and saving configuration data
"""

import json
from pathlib import Path
from typing import Set, Dict, Any, Optional


class ConfigManager:
    """Manages configuration data for the GUI application"""
    
    def __init__(self, config_file: Path):
        """
        Initialize ConfigManager
        
        Args:
            config_file: Path to the configuration JSON file
        """
        self.config_file = config_file
        self._load_config()
    
    def _load_config(self) -> None:
        """Load configuration from file"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    self.saved_params = config.get('params', '')
                    self.not_working_configs = set(config.get('not_working_configs', []))
                    self.user_configs = set(config.get('user_configs', []))
                    # Config names: maps config string to name
                    self.config_names = config.get('config_names', {})
                    # Window geometry: saves window size and position
                    self.window_geometry = config.get('window_geometry', {})
            else:
                self.saved_params = ''
                self.not_working_configs = set()
                self.user_configs = set()
                self.config_names = {}
                self.window_geometry = {}
        except Exception as e:
            print(f"Error loading config: {e}")
            self.saved_params = ''
            self.not_working_configs = set()
            self.user_configs = set()
            self.config_names = {}
            self.window_geometry = {}
    
    def save_config(self, params: str) -> None:
        """
        Save configuration to file
        
        Args:
            params: Current parameters string
        """
        self.saved_params = params
        self._save_config_file()
    
    def get_saved_params(self) -> str:
        """Get saved parameters"""
        return self.saved_params
    
    def get_user_configs(self) -> Set[str]:
        """Get user configurations set"""
        return self.user_configs
    
    def get_not_working_configs(self) -> Set[str]:
        """Get not working configurations set"""
        return self.not_working_configs
    
    def add_user_config(self, configuration: str) -> None:
        """
        Add a user-entered configuration to the list
        
        Args:
            configuration: Configuration string to add
        """
        if configuration and configuration.strip():
            self.user_configs.add(configuration.strip())
    
    def mark_config_not_working(self, configuration: str) -> None:
        """
        Mark a configuration as 'not working'
        
        Args:
            configuration: Configuration string to mark
        """
        self.not_working_configs.add(configuration)
    
    def unmark_config_not_working(self, configuration: str) -> None:
        """
        Remove a configuration from 'not working' list
        
        Args:
            configuration: Configuration string to unmark
        """
        self.not_working_configs.discard(configuration)
    
    def get_config_name(self, configuration: str) -> str:
        """
        Get the name for a configuration, or return empty string if not set
        
        Args:
            configuration: Configuration string
            
        Returns:
            Name for the configuration, or empty string
        """
        return self.config_names.get(configuration, '')
    
    def set_config_name(self, configuration: str, name: str) -> None:
        """
        Set the name for a configuration
        
        Args:
            configuration: Configuration string
            name: Name to set for the configuration
        """
        if name and name.strip():
            self.config_names[configuration] = name.strip()
        elif configuration in self.config_names:
            del self.config_names[configuration]
    
    def get_window_geometry(self, window_name: str) -> Optional[str]:
        """
        Get saved geometry for a window
        
        Args:
            window_name: Name identifier for the window
            
        Returns:
            Geometry string (widthxheight+x+y) or None if not saved
        """
        return self.window_geometry.get(window_name)
    
    def save_window_geometry(self, window_name: str, geometry: str) -> None:
        """
        Save geometry for a window and persist to file
        
        Args:
            window_name: Name identifier for the window
            geometry: Geometry string (widthxheight+x+y)
        """
        if geometry:
            self.window_geometry[window_name] = geometry
            # Save to file immediately
            self._save_config_file()
    
    def _save_config_file(self) -> None:
        """Internal method to save config to file with current state"""
        try:
            config = {
                'params': self.saved_params,
                'user_configs': list(self.user_configs),
                'not_working_configs': list(self.not_working_configs),
                'config_names': self.config_names,
                'window_geometry': self.window_geometry
            }
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")

