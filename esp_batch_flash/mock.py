#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ESP Batch Flash - Mock functionality for testing without real hardware
"""

import os
import time
from .base import (
    IS_WINDOWS, 
    progress_lock, 
    device_progress
)

def get_mock_serial_ports(num_ports=3):
    """
    Generate mock serial ports for demonstration without actual hardware.
    
    Args:
        num_ports: Number of mock ports to generate
        
    Returns:
        List of mock port names
    """
    if IS_WINDOWS:
        return [f'COM{i+1}' for i in range(num_ports)]
    else:
        return [f'/dev/ttyUSB{i}' for i in range(num_ports)]
            
def mock_flash_device(port, flash_options, binary_files, log_dir, chip='auto', baud_rate=1152000):
    """
    Mock implementation that simulates flashing without actual hardware.
    
    This function simulates the flashing process with progress updates.
    
    Args:
        port: Serial port to simulate flashing
        flash_options: Flash options from flash_args file
        binary_files: List of binary files to flash
        log_dir: Directory for log files
        chip: Target chip type
        baud_rate: Baud rate for flashing
        
    Returns:
        (bool, str): Success status and message
    """
    # Initialize progress for this device
    with progress_lock:
        device_progress[port] = {
            "progress": 0.0,
            "status": "Starting (mock)",
            "total_size": 1024 * 1024,  # Mock 1MB size
            "written": 0
        }
    
    # Create a log file
    log_file = os.path.join(log_dir, f"flash_{os.path.basename(port)}.log")
    with open(log_file, 'w') as f:
        f.write(f"Mock flashing on {port}\n")
        f.write(f"Flash options: {' '.join(flash_options)}\n")
        f.write(f"Binary files:\n")
        for addr, path in binary_files:
            f.write(f"  {addr}: {path}\n")
    
    # Simulate the flashing process
    total_steps = 10
    
    # Simulate detection
    with progress_lock:
        device_progress[port]["status"] = f"Detected ESP32 (mock)"
        device_progress[port]["progress"] = 0.05
    time.sleep(0.5)
    
    # Simulate preparing
    with progress_lock:
        device_progress[port]["status"] = f"Preparing to write files"
        device_progress[port]["progress"] = 0.1
    time.sleep(0.5)
    
    # Simulate writing
    total_size = 1024 * 1024  # 1MB mock size
    for step in range(1, total_steps):
        # Update progress to simulate writing (between 10% and 90%)
        progress = 0.1 + (step / total_steps * 0.8)
        written = int(total_size * (step / total_steps))
        
        with progress_lock:
            device_progress[port]["progress"] = progress
            device_progress[port]["written"] = written
            device_progress[port]["status"] = f"Writing {written}/{total_size} bytes"
        
        # Simulate work
        time.sleep(0.5)
    
    # Simulate verification
    with progress_lock:
        device_progress[port]["status"] = "Verifying data"
        device_progress[port]["progress"] = 0.95
    time.sleep(0.5)
    
    # Simulate reset
    with progress_lock:
        device_progress[port]["status"] = "Resetting device"
        device_progress[port]["progress"] = 1.0
    time.sleep(0.5)
    
    return True, f"Successfully flashed {port} (mock)" 