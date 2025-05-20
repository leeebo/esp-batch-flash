#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Platform compatibility tests for ESP Batch Flash

This test module specifically checks that the code works correctly on 
different platforms including Windows.
"""

import os
import sys
import platform
import pytest
from unittest.mock import patch

# Determine the operating system - we'll use this for test assertions
IS_WINDOWS = platform.system() == "Windows"

# Import from the package
from esp_batch_flash.mock import get_mock_serial_ports
from esp_batch_flash.base import (
    IS_WINDOWS as PKG_IS_WINDOWS, 
    IS_LINUX as PKG_IS_LINUX,
    IS_MACOS as PKG_IS_MACOS,
    FlashProgress
)


def test_platform_detection():
    """Test that platform detection matches the actual platform"""
    actual_is_windows = platform.system() == "Windows"
    actual_is_linux = platform.system() == "Linux"
    actual_is_macos = platform.system() == "Darwin"
    
    assert PKG_IS_WINDOWS == actual_is_windows
    assert PKG_IS_LINUX == actual_is_linux
    assert PKG_IS_MACOS == actual_is_macos


def test_progress_bar_render():
    """Test that progress bars can be rendered without platform-specific errors"""
    # Import the ProgressBar class
    from esp_batch_flash.base import ProgressBar
    
    # Create a progress bar and try to render it
    pb = ProgressBar(width=30)
    result = pb.render(0.5, prefix="Test", suffix="Testing")
    
    # Verify basic formatting 
    assert "Test" in result
    assert "Testing" in result
    assert "50%" in result


@patch('sys.stdout')
def test_progress_bars_stdout(mock_stdout):
    """Test that progress bars can write to stdout without errors"""
    # Call the progress bars method - it should not raise any exceptions
    FlashProgress.print_progress_bars()
    # We don't need to assert anything specific - just that it runs without errors


def test_mock_serial_ports_platform():
    """Test that mock serial ports are generated with correct platform naming"""
    # Get 5 mock ports
    ports = get_mock_serial_ports(5)
    assert len(ports) == 5
    
    # Check platform-specific naming
    if IS_WINDOWS:
        assert all(port.startswith('COM') for port in ports)
        assert ports[0] == 'COM1'
    else:
        assert all(port.startswith('/dev/ttyUSB') for port in ports)
        assert ports[0] == '/dev/ttyUSB0'


if __name__ == "__main__":
    pytest.main(["-v", __file__]) 