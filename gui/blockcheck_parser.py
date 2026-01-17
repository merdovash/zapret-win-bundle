#!/usr/bin/env python3
"""
Blockcheck log parser for WinWS GUI
Parses blockcheck log files to extract working configurations
"""

import re
from pathlib import Path
from typing import List


class BlockcheckParser:
    """Parses blockcheck log files to extract working configurations"""
    
    def __init__(self, project_root: Path):
        """
        Initialize BlockcheckParser
        
        Args:
            project_root: Root directory of the project (contains blockcheck directory)
        """
        self.project_root = project_root
        self.blockcheck_dir = project_root / "blockcheck"
    
    def parse_logs(self) -> List[str]:
        """
        Parse blockcheck log files to extract working configurations.
        
        Returns:
            List of configuration strings found in the logs.
        
        Expected log format:
        !!!!! <test>: working strategy found for ipv<version> <domain> : <daemon> <strategy> !!!!!
        Example:
        !!!!! curl_test_https_tls12: working strategy found for ipv4 youtube.com : winws --dpi-desync=fake,fakeddisorder --dpi-desync-fooling=ts --dpi-desync-split-pos=midsld !!!!!
        """
        configurations = []
        log_files = [
            self.blockcheck_dir / "blockcheck.log",
            self.blockcheck_dir / "blockcheck2.log"
        ]
        
        for log_file in log_files:
            if not log_file.exists():
                continue
            
            try:
                configs = self._parse_log_file(log_file)
                configurations.extend(configs)
            except Exception as e:
                print(f"Error parsing log file {log_file}: {e}")
                continue
        
        # Remove duplicates while preserving order
        seen = set()
        unique_configs = []
        for config in configurations:
            if config not in seen:
                seen.add(config)
                unique_configs.append(config)
        
        return unique_configs
    
    def _parse_log_file(self, log_file: Path) -> List[str]:
        """Parse a single log file and extract configurations"""
        configurations = []
        
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not self._is_working_strategy_line(line):
                    continue
                
                strategy = self._extract_strategy(line)
                if strategy:
                    configurations.append(strategy)
        
        return configurations
    
    def _is_working_strategy_line(self, line: str) -> bool:
        """Check if a line contains a working strategy"""
        return "working strategy found" in line.lower() and "!!!!!" in line
    
    def _extract_strategy(self, line: str) -> str:
        """
        Extract strategy from a log line
        
        Args:
            line: Log line containing strategy information
            
        Returns:
            Strategy string or empty string if not found
        """
        # Pattern: " : winws " or " : winws2 " followed by strategy until "!!!!!"
        match = re.search(r'\s:\s(winws2?|nfqws2?|dvtws2?)\s+(.+?)(?:\s+!!!!!)?$', line)
        if match:
            strategy = match.group(2).strip().rstrip("!").strip()
            return strategy
        
        # Fallback: find last " : " in the line and extract everything after it
        if " : " in line:
            last_colon_idx = line.rfind(" : ")
            if last_colon_idx >= 0:
                after_colon = line[last_colon_idx + 3:]
                after_colon = after_colon.rstrip("!").strip()
                parts = after_colon.split(None, 1)
                if len(parts) >= 2:
                    return parts[1].strip()
        
        return ""

