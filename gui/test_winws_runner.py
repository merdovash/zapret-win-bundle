#!/usr/bin/env python3
"""
Unit tests for WinWSRunner process tracking logic
"""

import unittest
import time
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from winws_runner import WinWSRunner


class TestWinWSRunnerTracking(unittest.TestCase):
    """Test process tracking logic"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create a mock project root
        self.test_root = Path(__file__).parent.parent
        self.runner = WinWSRunner(self.test_root)
        
        # Mock the process to avoid actually starting processes
        self.mock_process = MagicMock(spec=subprocess.Popen)
        self.runner.process = self.mock_process
    
    def test_initial_state_not_running(self):
        """Test that initially the process is not running"""
        self.assertFalse(self.runner.is_cmd_running)
        self.assertFalse(self.runner.is_running)
        self.assertIsNone(self.runner.start_time)
        self.assertIsNone(self.runner.termination_time)
        self.assertIsNone(self.runner.cmd_file_path)
    
    def test_start_sets_start_time(self):
        """Test that start() sets start_time and clears termination_time"""
        # Set up initial state as if process was previously terminated
        self.runner.start_time = time.time() - 10
        self.runner.termination_time = time.time() - 5
        
        # Mock the start method to avoid actual process execution
        with patch.object(self.runner, '_validate_winws_exists'), \
             patch.object(self.runner, '_find_elevator_path'), \
             patch.object(self.runner, '_parse_parameters'), \
             patch.object(self.runner, '_build_winws_command'), \
             patch.object(self.runner, '_create_cmd_file', return_value='test.cmd'), \
             patch.object(self.runner, '_log_cmd_file_content'), \
             patch.object(self.runner, '_execute_process', return_value=self.mock_process), \
             patch.object(self.runner, '_start_process_monitor'):
            
            self.runner.start()
            
            # Check that start_time is set and termination_time is cleared
            self.assertIsNotNone(self.runner.start_time)
            self.assertIsNone(self.runner.termination_time)
            self.assertEqual(self.runner.cmd_file_path, 'test.cmd')
    
    def test_is_running_after_start(self):
        """Test that is_running returns True after start() is called"""
        # Simulate process started
        self.runner.start_time = time.time()
        self.runner.termination_time = None
        
        self.assertTrue(self.runner.is_cmd_running)
        self.assertTrue(self.runner.is_running)
    
    def test_is_running_after_termination(self):
        """Test that is_running returns False after termination_time is set"""
        # Simulate process started and then terminated
        self.runner.start_time = time.time() - 10
        self.runner.termination_time = time.time() - 5
        
        self.assertFalse(self.runner.is_cmd_running)
        self.assertFalse(self.runner.is_running)
    
    def test_stop_sets_termination_time(self):
        """Test that stop() sets termination_time"""
        # Simulate running process
        self.runner.start_time = time.time()
        self.runner.termination_time = None
        self.runner.process = self.mock_process
        
        # Mock process termination
        self.mock_process.terminate = Mock()
        self.mock_process.wait = Mock(return_value=0)
        self.mock_process.poll = Mock(return_value=0)
        
        with patch('subprocess.run'):
            self.runner.stop()
        
        # Check that termination_time is set
        self.assertIsNotNone(self.runner.termination_time)
        self.assertFalse(self.runner.is_cmd_running)
        self.assertIsNone(self.runner.process)
        self.assertIsNone(self.runner.cmd_file_path)
    
    def test_process_handle_none_but_started(self):
        """Test that process is considered running even if handle is None but start_time exists"""
        # Simulate process started but handle lost
        self.runner.start_time = time.time()
        self.runner.termination_time = None
        self.runner.process = None
        
        # Should still be considered running until termination_time is set
        self.assertTrue(self.runner.is_cmd_running)
    
    def test_monitor_thread_detects_termination(self):
        """Test that monitor thread sets termination_time when process terminates"""
        # Simulate running process
        self.runner.start_time = time.time()
        self.runner.termination_time = None
        self.runner.process = self.mock_process
        
        # Mock process.wait() to simulate termination
        self.mock_process.wait = Mock(return_value=0)
        
        # Create monitor function
        def monitor_process():
            if self.runner.process is None:
                return
            try:
                self.runner.process.wait()
            except Exception:
                pass
            if self.runner.termination_time is None:
                self.runner.termination_time = time.time()
        
        # Run monitor
        monitor_process()
        
        # Check that termination_time was set
        self.assertIsNotNone(self.runner.termination_time)
        self.assertFalse(self.runner.is_cmd_running)
    
    def test_check_status_doesnt_falsely_detect_termination(self):
        """Test that check_status doesn't falsely detect termination when process handle exits"""
        # Simulate process started
        self.runner.start_time = time.time()
        self.runner.termination_time = None
        self.runner.process = self.mock_process
        
        # Mock process.poll() to return a value (simulating elevator.exe exit)
        # This should NOT set termination_time because the cmd file may still be running
        self.mock_process.poll = Mock(return_value=0)
        
        # Check status
        is_running = self.runner.check_status()
        
        # Should still be considered running (termination_time not set)
        self.assertTrue(is_running)
        self.assertIsNone(self.runner.termination_time)
    
    def test_start_clears_previous_termination(self):
        """Test that starting a new process clears previous termination"""
        # Simulate previously terminated process
        self.runner.start_time = time.time() - 20
        self.runner.termination_time = time.time() - 10
        self.runner.cmd_file_path = 'old.cmd'
        
        # Mock start to avoid actual execution
        with patch.object(self.runner, '_validate_winws_exists'), \
             patch.object(self.runner, '_find_elevator_path'), \
             patch.object(self.runner, '_parse_parameters'), \
             patch.object(self.runner, '_build_winws_command'), \
             patch.object(self.runner, '_create_cmd_file', return_value='new.cmd'), \
             patch.object(self.runner, '_log_cmd_file_content'), \
             patch.object(self.runner, '_execute_process', return_value=self.mock_process), \
             patch.object(self.runner, '_start_process_monitor'):
            
            self.runner.start()
            
            # Check that termination_time is cleared and new start_time is set
            self.assertIsNone(self.runner.termination_time)
            self.assertIsNotNone(self.runner.start_time)
            self.assertEqual(self.runner.cmd_file_path, 'new.cmd')
            self.assertTrue(self.runner.is_cmd_running)
    
    def test_get_cmd_file_path(self):
        """Test get_cmd_file_path() returns correct path"""
        # Initially None
        self.assertIsNone(self.runner.get_cmd_file_path())
        
        # After setting
        self.runner.cmd_file_path = 'test.cmd'
        self.assertEqual(self.runner.get_cmd_file_path(), 'test.cmd')
        
        # After clearing
        self.runner.cmd_file_path = None
        self.assertIsNone(self.runner.get_cmd_file_path())


class TestWinWSRunnerRealProcess(unittest.TestCase):
    """Test with real subprocess (if possible)"""
    
    @unittest.skipIf(sys.platform != 'win32', "Windows-specific test")
    def test_real_process_tracking(self):
        """Test tracking with a real short-lived process"""
        runner = WinWSRunner()
        
        # Use a simple command that runs briefly
        runner.process = subprocess.Popen(
            ['cmd', '/c', 'echo test'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        runner.start_time = time.time()
        runner.termination_time = None
        
        # Initially should be running
        self.assertTrue(runner.is_cmd_running)
        
        # Wait for process to complete
        runner.process.wait()
        
        # Even after process completes, if termination_time is not set,
        # it should still be considered running (this is the expected behavior
        # since we don't check poll() in is_cmd_running)
        # The monitor thread would set termination_time
        self.assertTrue(runner.is_cmd_running)
        
        # Manually set termination_time to simulate monitor thread
        runner.termination_time = time.time()
        self.assertFalse(runner.is_cmd_running)


if __name__ == '__main__':
    unittest.main()

