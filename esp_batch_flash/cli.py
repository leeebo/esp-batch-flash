#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ESP Batch Flash command line interface
"""

import os
import sys
import time
import argparse
import signal
import threading
from concurrent.futures import ThreadPoolExecutor

from . import __version__
from .base import (
    IS_WINDOWS, IS_LINUX, IS_MACOS,
    check_dependencies, find_flash_args_file, find_local_bin_files,
    parse_flash_args, flash_device, find_serial_ports,
    FlashProgress, device_progress, progress_output_lock, progress_lock
)

# Default configuration
MAX_PARALLEL = 20

# Import mock functionality from internal module
from .mock import get_mock_serial_ports, mock_flash_device

def main():
    # Check script directory
    if getattr(sys, 'frozen', False):
        # If it's a compiled binary
        script_dir = os.path.dirname(os.path.abspath(sys.executable))
    else:
        # If it's a Python script
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Use current working directory as preferred directory
    work_dir = os.getcwd()
    
    # Create log directory
    log_dir = os.path.join(script_dir, 'log')
    os.makedirs(log_dir, exist_ok=True)
    
    # Results file path
    results_file = os.path.join(log_dir, 'flash_results.txt')

    # Set up window resize handler (for Unix-like systems only)
    if not IS_WINDOWS:
        try:
            # Register signal handler for window resize events
            if hasattr(signal, 'SIGWINCH'):  # Make sure SIGWINCH is available
                signal.signal(signal.SIGWINCH, FlashProgress.handle_window_resize)
        except (AttributeError, ValueError):
            # Signal might not be available on all platforms
            pass
    
    print(f"ESP-IDF Flash All Devices Tool v{__version__}")
    print("----------------------------------------------")
    if IS_WINDOWS:
        print("Note: On Windows only physically connected COM ports will be detected\n")
    elif IS_LINUX:
        print("Note: On Linux only ttyUSB and ttyACM devices will be detected as ESP programming ports\n")
    elif IS_MACOS:
        print("Note: On macOS only common ESP device ports will be detected\n")
    
    parser = argparse.ArgumentParser(description='Flash firmware to all ttyUSB/COM devices using parallel processing')
    parser.add_argument('--max-parallel', type=int, default=MAX_PARALLEL, help='Maximum number of parallel flash operations')
    parser.add_argument('--flash-args', type=str, help='Path to flash_args file (auto-detected if not specified)')
    parser.add_argument('--chip', type=str, default='auto', help='Target chip type (auto, esp32, esp32c3, esp32c6, etc.)')
    parser.add_argument('--bin', type=str, help='Specify a specific bin file to flash (format: addr:file.bin)')
    parser.add_argument('--scan-bins', action='store_true', help='Scan for bin files in the script directory and prompt for flash addresses')
    parser.add_argument('--ports', type=str, help='Comma-separated list of specific ports to use (e.g. "COM3,COM5" on Windows or "/dev/ttyUSB0,/dev/ttyUSB1" on Linux)')
    parser.add_argument('--interactive', action='store_true', help='Show an interactive menu to select which detected ports to use')
    parser.add_argument('--no-progress', action='store_true', help='Disable progress bars (useful for terminals that do not support ANSI escape codes)')
    parser.add_argument('--baud', type=int, default=1152000, help='Baud rate for flashing (default: 1152000)')
    parser.add_argument('--mock', action='store_true', help='Run in mock mode without real ESP devices')
    parser.add_argument('--mock-ports', type=int, default=3, help='Number of mock ports to simulate in mock mode')
    parser.add_argument('--skip-deps-check', action='store_true', help='Skip dependencies check (useful in mock mode)')
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    args = parser.parse_args()
    
    # Check dependencies (skip if in mock mode and skip-deps-check is set)
    if args.mock and args.skip_deps_check:
        print("Skipping dependency check in mock mode")
    else:
        check_dependencies()
    
    # Find flash_args file and build path
    if args.flash_args:
        # User-specified flash_args file path
        flash_args_file = args.flash_args
        if not os.path.exists(flash_args_file):
            print(f"❌ Specified flash_args file not found: {flash_args_file}")
            sys.exit(1)
        # Infer build path from flash_args path
        build_path = os.path.dirname(flash_args_file)
        print(f"Using user-specified flash_args file: {flash_args_file}")
    else:
        # Only search in current working directory and its subdirectories for flash_args
        try:
            flash_args_file, build_path = find_flash_args_file(work_dir)
            print(f"Using flash_args from current directory: {os.path.relpath(flash_args_file, work_dir)}")
        except SystemExit:
            print(f"❌ Could not find flash_args file in current directory or its subdirectories.")
            print(f"Please run this tool in an ESP-IDF project directory, or use --flash-args option to specify the path.")
            sys.exit(1)
    
    # Parse flash arguments
    flash_options, binary_files = parse_flash_args(flash_args_file, build_path, script_dir)
    
    # If requested, check for bin files in the script directory
    if args.scan_bins:
        # Only search in current working directory for bin files
        local_bins = find_local_bin_files(work_dir)
            
        if local_bins:
            print("\nWould you like to include these local bin files for flashing?")
            for i, bin_file in enumerate(local_bins):
                bin_name = os.path.basename(bin_file)
                print(f"{i+1}. {bin_name}")
            
            selections = input("\nEnter bin numbers to include (comma separated) or 'all': ")
            if selections.lower().strip() == 'all':
                selected_bins = list(range(len(local_bins)))
            else:
                selected_bins = [int(x.strip())-1 for x in selections.split(',') if x.strip().isdigit()]
            
            for idx in selected_bins:
                if 0 <= idx < len(local_bins):
                    address = input(f"Enter flash address for {os.path.basename(local_bins[idx])} (e.g. 0x10000): ")
                    if address.strip():
                        binary_files.append((address.strip(), local_bins[idx]))
    
    # If the user specified a bin file via command line
    if args.bin:
        try:
            addr, bin_file = args.bin.split(':', 1)
            
            # Check if absolute path
            if os.path.isabs(bin_file):
                bin_path = bin_file
            else:
                # Look in current working directory
                bin_path = os.path.join(work_dir, bin_file)
            
            if os.path.exists(bin_path):
                print(f"Adding user-specified binary: {bin_path} at address {addr}")
                binary_files.append((addr, bin_path))
            else:
                print(f"❌ Specified bin file not found: {bin_path}")
        except ValueError:
            print("❌ Invalid bin file format. Use addr:file.bin (e.g. 0x10000:firmware.bin)")
    
    # Show what will be flashed
    print(f"\nFlash options: {' '.join(flash_options)}")
    print(f"Binary files to flash:")
    for addr, path in binary_files:
        print(f"  - {addr}: {path}")
    print()
    
    # Find all serial ports (or use mock ports if in mock mode)
    if args.mock:
        all_usb_devices = get_mock_serial_ports(args.mock_ports)
        print(f"Running in MOCK MODE with {len(all_usb_devices)} simulated devices")
    else:
        all_usb_devices = find_serial_ports()
    
    if not all_usb_devices:
        print("No USB devices found. Please connect your ESP32 devices or use --mock mode.")
        sys.exit(1)
    
    # Determine which devices to use based on command-line arguments
    usb_devices = []
    
    # If specific ports are specified via command line
    if args.ports:
        specified_ports = [p.strip() for p in args.ports.split(',') if p.strip()]
        if IS_WINDOWS:
            # Add 'COM' prefix if not already present for Windows
            specified_ports = [p if p.upper().startswith('COM') else f"COM{p}" for p in specified_ports]
        
        # Filter to only include ports that actually exist
        usb_devices = [device for device in all_usb_devices if any(
            device.endswith(port) or device == port for port in specified_ports)]
            
        if not usb_devices:
            print(f"⚠️  None of the specified ports {specified_ports} were found.")
            print(f"Available ports: {all_usb_devices}")
            sys.exit(1)
    
    # If interactive mode is enabled
    elif args.interactive:
        print("\nAvailable USB devices:")
        for i, device in enumerate(all_usb_devices):
            print(f"  [{i+1}] {device}")
        
        print("\nSelect devices to flash (comma-separated numbers, 'all' for all devices):")
        selection = input("> ").strip().lower()
        
        if selection == 'all':
            usb_devices = all_usb_devices
        else:
            try:
                # Parse the selection indices (1-based)
                indices = [int(idx.strip())-1 for idx in selection.split(',') if idx.strip()]
                # Get the corresponding devices
                usb_devices = [all_usb_devices[i] for i in indices if 0 <= i < len(all_usb_devices)]
            except ValueError:
                print("Invalid selection. Please enter numbers separated by commas.")
                sys.exit(1)
        
        if not usb_devices:
            print("No devices selected. Exiting.")
            sys.exit(0)
    
    # If no specific selection method, use all detected devices
    else:
        usb_devices = all_usb_devices
    
    print("\nSelected devices for flashing:")
    for device in usb_devices:
        print(f"  - {device}")
    print()
    
    # Clean up any previous results file and create a new one
    if os.path.exists(results_file):
        os.remove(results_file)
    
    # Process devices in parallel
    print(f"Starting parallel flashing process (max {args.max_parallel} concurrent tasks)...")
    
    # Clear any previous progress information, ensure no duplicate progress bars
    with progress_lock:
        device_progress.clear()  # Add this line to ensure clearing progress data before each run

    # Determine whether to show progress bars or not
    show_progress = not args.no_progress

    # Create blank lines for progress bars (one per device) if showing progress
    if show_progress:
        with progress_output_lock:
            for _ in range(len(usb_devices)):
                print()  # Print empty lines to reserve space for progress bars
                
    # Start the flashing tasks in parallel
    with ThreadPoolExecutor(max_workers=args.max_parallel) as executor:
        # Submit all tasks - use mock function if in mock mode
        flash_func = mock_flash_device if args.mock else flash_device
        futures = [executor.submit(flash_func, device, flash_options, binary_files, log_dir, args.chip, args.baud) for device in usb_devices]
        
        # Monitor and update progress while tasks are running
        all_done = False
        try:
            while not all_done:
                # Print progress bars for all devices if enabled
                if show_progress:
                    FlashProgress.print_progress_bars()
                
                # Check if all tasks are done
                all_done = all(future.done() for future in futures)
                
                # Sleep briefly to avoid excessive CPU usage
                time.sleep(0.2)
                
            # Print final progress state if showing progress
            if show_progress:
                FlashProgress.print_progress_bars()
                # Move cursor past the progress bars
                print("\n")
            
            # Wait for all results and collect them
            results = [future.result() for future in futures]
            
            # Now that progress bars are done, print the success/failure messages
            success_count = 0
            failed_count = 0
            
            with progress_output_lock:
                print("\nFlash results:")
                for device in usb_devices:
                    if device in device_progress:
                        if "status" in device_progress[device]:
                            status = device_progress[device]["status"]
                            if "✅" in status or "completed" in status.lower() or "resetting" in status.lower():
                                print(f"✅ Successfully flashed to {device}")
                                success_count += 1
                            elif "❌" in status or "error" in status.lower() or "fail" in status.lower():
                                print(f"❌ Failed to flash to {device} (check {log_dir}/flash_{os.path.basename(device)}.log for details)")
                                failed_count += 1
                print()
            
        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user! Cancelling tasks...")
            for future in futures:
                future.cancel()
            executor.shutdown(wait=False)
            sys.exit(1)
    
    # Count total devices
    total_devices = len(usb_devices)
    
    # Print summary report
    print()
    print("========================================")
    print("📊 Flash Task Summary Report")
    print("========================================")
    print(f"🔍 Total devices: {total_devices}")
    print(f"✅ Success count: {success_count}")
    print(f"❌ Failed count: {failed_count}")
    print(f"⚠️ Unprocessed count: {total_devices - success_count - failed_count}")
    print("========================================")
    print()
    
    # Return exit code 1 if any failures, otherwise 0
    sys.exit(1 if failed_count > 0 else 0)


if __name__ == "__main__":
    main() 