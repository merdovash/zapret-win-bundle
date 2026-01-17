#!/usr/bin/env python3
"""
Configuration management for WinWS GUI
Handles loading and saving configuration data
"""

import json
from pathlib import Path
from typing import Set, Dict, Any


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
            else:
                self.saved_params = ''
                self.not_working_configs = set()
                self.user_configs = set()
        except Exception as e:
            print(f"Error loading config: {e}")
            self.saved_params = ''
            self.not_working_configs = set()
            self.user_configs = set()
    
    def save_config(self, params: str) -> None:
        """
        Save configuration to file
        
        Args:
            params: Current parameters string
        """
        try:
            config = {
                'params': params,
                'user_configs': list(self.user_configs),
                'not_working_configs': list(self.not_working_configs)
            }
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")
    
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

