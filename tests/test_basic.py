#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Basic tests for ESP Batch Flash.
These tests verify core functionality without requiring actual hardware.
"""

import os
import sys
import pytest
from unittest import mock
from esp_batch_flash import __version__


def test_version():
    """Test that version is a valid string."""
    assert isinstance(__version__, str)
    assert __version__ != ""
    # Version should follow semantic versioning format
    parts = __version__.split('.')
    assert len(parts) == 3, "Version should follow semantic versioning (x.y.z)"
    for part in parts:
        assert part.isdigit(), "Each version part should be numeric"


def test_imports():
    """Test that all necessary modules can be imported."""
    from esp_batch_flash import base, cli
    
    # Ensure main classes and functions exist
    assert hasattr(base, 'FlashProgress')
    assert hasattr(base, 'find_serial_ports')
    assert hasattr(base, 'flash_device')
    assert hasattr(base, 'parse_flash_args')
    assert hasattr(cli, 'main')


def test_progress_bar():
    """Test the ProgressBar class functionality."""
    from esp_batch_flash.base import ProgressBar
    
    # Create a progress bar with default width
    bar = ProgressBar()
    
    # Test rendering at different percentages
    empty_bar = bar.render(0.0, prefix="Test", suffix="Empty")
    assert "0%" in empty_bar
    assert "Test" in empty_bar
    assert "Empty" in empty_bar
    
    half_bar = bar.render(0.5, prefix="Test", suffix="Half")
    assert "50%" in half_bar
    assert "Test" in half_bar
    assert "Half" in half_bar
    
    full_bar = bar.render(1.0, prefix="Test", suffix="Full")
    assert "100%" in full_bar
    assert "Test" in full_bar
    assert "Full" in full_bar


@pytest.mark.skipif(sys.platform != "linux", reason="Port detection test only runs on Linux")
def test_find_serial_ports_linux():
    """Test serial port detection on Linux with mocked devices."""
    from esp_batch_flash.base import find_serial_ports
    
    # Mock glob to return fake devices
    with mock.patch('glob.glob') as mock_glob:
        # Simulate USB devices
        mock_glob.side_effect = lambda pattern: {
            '/dev/ttyUSB*': ['/dev/ttyUSB0', '/dev/ttyUSB1'],
            '/dev/ttyACM*': ['/dev/ttyACM0'],
            '/dev/serial/by-id/*': []
        }.get(pattern, [])
        
        ports = find_serial_ports()
        assert len(ports) == 3
        assert '/dev/ttyUSB0' in ports
        assert '/dev/ttyUSB1' in ports
        assert '/dev/ttyACM0' in ports


def test_flash_args_parsing():
    """Test parsing of flash_args file."""
    from esp_batch_flash.base import parse_flash_args
    import tempfile
    
    # Create a temporary flash_args file
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        f.write("--flash_mode dio --flash_freq 80m --flash_size 4MB\n")
        f.write("0x1000 bootloader.bin\n")
        f.write("0x8000 partition-table.bin\n")
        f.write("0x10000 firmware.bin\n")
        flash_args_path = f.name
    
    try:
        # Create temporary binary files
        bin_dir = os.path.dirname(flash_args_path)
        with open(os.path.join(bin_dir, "bootloader.bin"), 'wb') as f:
            f.write(b'dummy bootloader data')
        with open(os.path.join(bin_dir, "partition-table.bin"), 'wb') as f:
            f.write(b'dummy partition data')
        with open(os.path.join(bin_dir, "firmware.bin"), 'wb') as f:
            f.write(b'dummy firmware data')
            
        # Parse the flash_args file
        flash_options, binary_files = parse_flash_args(flash_args_path, bin_dir, bin_dir)
        
        # Verify flash options
        assert "--flash_mode" in flash_options
        assert "dio" in flash_options
        assert "--flash_freq" in flash_options
        assert "80m" in flash_options
        assert "--flash_size" in flash_options
        assert "4MB" in flash_options
        
        # Verify binary files
        assert len(binary_files) == 3
        addresses = [addr for addr, _ in binary_files]
        assert "0x1000" in addresses
        assert "0x8000" in addresses
        assert "0x10000" in addresses
        
    finally:
        # Clean up temporary files
        try:
            os.unlink(flash_args_path)
            os.unlink(os.path.join(bin_dir, "bootloader.bin"))
            os.unlink(os.path.join(bin_dir, "partition-table.bin"))
            os.unlink(os.path.join(bin_dir, "firmware.bin"))
        except Exception:
            pass  # Ignore cleanup errors 