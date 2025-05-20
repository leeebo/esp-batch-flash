#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Core functionality module for ESP Batch Flash
"""

import os
import sys
import glob
import time
import subprocess
import threading
import re
import platform

# Determine the operating system
IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux" 
IS_MACOS = platform.system() == "Darwin"

# Import platform-specific modules
if not IS_WINDOWS:
    import fcntl
    import select
import signal
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict

# Determine the operating system
IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"
IS_MACOS = platform.system() == "Darwin"

# Lock for thread-safe file writing
file_lock = threading.Lock()

# Progress tracking
progress_lock = threading.Lock()
device_progress = defaultdict(dict)  # Dictionary to track progress for each device
progress_output_lock = threading.Lock()  # Lock for console output

class ProgressBar:
    """Simple console progress bar"""
    def __init__(self, width=50):
        self.width = width
        
    def render(self, percent, prefix="", suffix=""):
        """Render a progress bar based on percentage"""
        filled_width = int(self.width * percent)
        bar = '█' * filled_width + '░' * (self.width - filled_width)
        percent_str = f"{int(percent * 100):3d}%"
        return f"{prefix} |{bar}| {percent_str} {suffix}"
        
class FlashProgress:
    """Monitor flash progress for ESP devices"""
    
    # Known patterns in esptool output
    WRITE_START_PATTERN = "Writing at"
    HASH_PATTERN = "Hash of data verified"
    HARD_RESET_PATTERN = "Hard resetting"
    PERCENTAGES = {
        "Chip is ESP32": 0.05,            # 5% when chip is detected
        "Compressed": 0.1,                # 10% when preparing to write
        "Writing at": 0.0,                # Progress will be calculated during writing
        "Hash of data verified": 0.95,    # 95% when hash verified 
        "Hard resetting": 1.0             # 100% when resetting
    }
    
    # Flag to track if a terminal resize has occurred
    window_resized = False
    
    @staticmethod
    def handle_window_resize(signum, frame):
        """Signal handler for window resize events"""
        FlashProgress.window_resized = True
    
    @staticmethod
    def update_progress(device, line, binary_size=None):
        """Update progress based on parsed output line"""
        progress = 0.0
        status = ""
        
        # Initialize device progress entry if needed
        with progress_lock:
            if "total_size" not in device_progress[device]:
                device_progress[device]["total_size"] = binary_size or 1
                device_progress[device]["written"] = 0
                device_progress[device]["progress"] = 0.0
                device_progress[device]["status"] = "Starting"
        
        # Match for "Chip is ESP32" and similar
        if "Chip is ESP" in line:
            chip_type = line.split("Chip is ")[1].split()[0]
            status = f"Detected {chip_type}"
            progress = FlashProgress.PERCENTAGES["Chip is ESP32"]
            
        # Match for compressed data information
        elif "Compressed" in line and "bytes" in line:
            try:
                # Try to extract binary size
                size_parts = line.split("bytes")[0].strip().split()
                if size_parts:
                    binary_size = int(size_parts[-1])
                    with progress_lock:
                        device_progress[device]["total_size"] = binary_size
                status = f"Preparing to write {binary_size} bytes"
                progress = FlashProgress.PERCENTAGES["Compressed"]
            except (ValueError, IndexError):
                pass
                
        # Match for writing progress
        elif FlashProgress.WRITE_START_PATTERN in line and "..." in line:
            try:
                addr_part = line.split("...")[0].strip().split()[-1]
                addr = int(addr_part, 16)  # Convert hex address to int
                with progress_lock:
                    device_progress[device]["written"] = addr
                    total_size = device_progress[device]["total_size"]
                    # Calculate progress between 10% and 90%
                    write_progress = min(addr / total_size, 1.0) if total_size > 0 else 0
                    progress = 0.1 + (write_progress * 0.8)  # Scale to 10%-90% range
                    status = f"Writing {addr}/{total_size} bytes"
            except (ValueError, IndexError):
                pass
                
        # Match for hash verification
        elif FlashProgress.HASH_PATTERN in line:
            status = "Verifying data"
            progress = FlashProgress.PERCENTAGES["Hash of data verified"]
            
        # Match for reset
        elif FlashProgress.HARD_RESET_PATTERN in line:
            status = "Resetting device"
            progress = FlashProgress.PERCENTAGES["Hard resetting"]
        
        # Update progress if we have a valid value
        if progress > 0:
            with progress_lock:
                device_progress[device]["progress"] = progress
                device_progress[device]["status"] = status
                
        return progress, status
        
    @staticmethod
    def get_progress(device):
        """Get current progress for a device"""
        with progress_lock:
            if device in device_progress:
                return device_progress[device]["progress"], device_progress[device]["status"]
            return 0.0, "Waiting"
            
    @staticmethod
    def print_progress_bars():
        """Print progress bars for all devices"""
        with progress_lock:
            devices = sorted(device_progress.keys())
        
        if not devices:
            return
            
        # Create progress bar renderer - adjust width based on terminal size
        try:
            # Get terminal width (if available)
            terminal_width = os.get_terminal_size().columns
            # Limit progress bar width to a reasonable size
            bar_width = min(max(20, terminal_width - 50), 60)  # Between 20 and 60 chars
        except (OSError, AttributeError):
            # If terminal size can't be determined, use a default width
            bar_width = 40
            
        renderer = ProgressBar(width=bar_width)
        
        # Check if we need to redraw everything due to resize
        full_redraw = FlashProgress.window_resized
        if full_redraw:
            FlashProgress.window_resized = False
            # For a full redraw, clear the screen first
            sys.stdout.write("\033[2J")  # Clear entire screen
            sys.stdout.write("\033[H")   # Move cursor to home position
        
        # Clear previous lines (one line per device)
        with progress_output_lock:
            try:
                # Check if the terminal supports ANSI escape codes
                ansi_supported = not IS_WINDOWS or os.environ.get('TERM') is not None
                
                if not full_redraw and ansi_supported:
                    # Standard update - move cursor and clear lines
                    num_devices = len(devices)
                    if num_devices > 1:
                        # Move cursor up n lines
                        sys.stdout.write(f"\033[{num_devices}A")
                    # Clear all lines
                    for _ in range(num_devices):
                        sys.stdout.write("\033[K\n")  # Clear line and move down
                    # Reset cursor position
                    sys.stdout.write(f"\033[{num_devices}A")
                elif not ansi_supported:
                    # For Windows terminals without ANSI support, use a simpler approach
                    if not hasattr(FlashProgress, 'last_output_length'):
                        FlashProgress.last_output_length = 0
                    
                    # Clear the console in a Windows-friendly way
                    if FlashProgress.last_output_length > 0:
                        try:
                            # Use os.system to clear the screen on Windows if needed
                            if full_redraw:
                                os.system('cls')
                        except:
                            # If that fails, just print newlines
                            print("\n" * len(devices))
                
                # Print updated progress bars
                for device in devices:
                    progress, status = FlashProgress.get_progress(device)
                    
                    # Get consistent display name
                    device_name = get_display_name(device)
                    
                    # Ensure device name fits in allocated space
                    if len(device_name) > 15:
                        device_name = device_name[:12] + "..."
                    device_name = device_name.ljust(15)
                    
                    # Limit status length based on terminal width
                    max_status_len = max(10, terminal_width - bar_width - 30) if 'terminal_width' in locals() else 30
                    if len(status) > max_status_len:
                        status = status[:max_status_len-3] + "..."
                    
                    progress_bar = renderer.render(progress, prefix=f"{device_name}", suffix=status)
                    print(progress_bar)
                
                # Flush stdout to ensure immediate display
                sys.stdout.flush()
                
                # Update last output length for Windows terminals
                if not IS_WINDOWS or not os.environ.get('TERM'):
                    FlashProgress.last_output_length = len(devices)
                
            except Exception as e:
                # If anything goes wrong with progress display, just silently continue
                # This makes the script more robust on terminals that don't support ANSI escape codes
                pass


def check_dependencies():
    """Check if required dependencies are installed"""
    try:
        # First try to run esptool directly to check if it's available
        try:
            result = subprocess.run([sys.executable, "-m", "esptool", "--version"], 
                                  capture_output=True, text=True, check=False)
            if result.returncode == 0:
                version = result.stdout.strip()
                print(f"✓ Found {version}")
                return
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            # On some Windows systems, subprocess might fail
            pass
            
        # If direct run failed, check if the module is importable
        import esptool
        print(f"✓ Found esptool version {esptool.__version__}")
        
    except ImportError:
        print("❌ esptool package is not installed or not in PATH.")
        print("Installing esptool...")
        try:
            # Different install approach for different platforms
            if IS_WINDOWS:
                # On Windows, sometimes pip install directly works better
                try:
                    subprocess.check_call([sys.executable, "-m", "pip", "install", "esptool"])
                except:
                    # Try with a more explicit command on Windows if the standard approach fails
                    python_path = sys.executable
                    pip_cmd = f'"{python_path}" -m pip install esptool'
                    subprocess.check_call(pip_cmd, shell=True)
            else:
                # Standard approach for Unix systems
                subprocess.check_call([sys.executable, "-m", "pip", "install", "esptool"])
                
            print("✅ esptool successfully installed!")
            
            # Verify installation
            try:
                import esptool
                print(f"✓ Using esptool version {esptool.__version__}")
            except ImportError:
                print("⚠️ esptool installed but import failed. You may need to restart the script.")
        except Exception as e:
            print(f"❌ Failed to install esptool: {e}")
            print("Please manually install esptool using: pip install esptool")
            sys.exit(1)


def find_flash_args_file(dir_path):
    """Find flash_args file in the given directory and its subdirectories"""
    # First check if flash_args exists in the specified directory
    flash_args_path = os.path.join(dir_path, 'flash_args')
    if os.path.exists(flash_args_path):
        print(f"✓ Found flash_args in the current directory")
        # Infer build path as the same directory
        build_path = dir_path
        return flash_args_path, build_path
    
    # Check for build directory in the specified directory
    build_path = os.path.join(dir_path, 'build')
    build_flash_args = os.path.join(build_path, 'flash_args')
    if os.path.exists(build_flash_args):
        print(f"✓ Found flash_args in the build directory")
        return build_flash_args, build_path
    
    # If not found in common locations, search subdirectories (up to depth 4)
    print("Searching for flash_args file in subdirectories...")
    for root, dirs, files in os.walk(dir_path):
        # Limit depth to avoid excessive searching
        if root.count(os.sep) - dir_path.count(os.sep) > 4:
            continue
            
        if 'flash_args' in files:
            flash_args_path = os.path.join(root, 'flash_args')
            rel_path = os.path.relpath(root, dir_path)
            path_str = rel_path if rel_path != '.' else 'current directory'
            print(f"✓ Found flash_args in {path_str}")
            return flash_args_path, root
        
        # Specially check for build directories
        build_dir = os.path.join(root, 'build')
        if os.path.isdir(build_dir) and 'flash_args' in os.listdir(build_dir):
            flash_args_path = os.path.join(build_dir, 'flash_args')
            rel_path = os.path.relpath(root, dir_path)
            path_str = rel_path if rel_path != '.' else 'current directory'
            print(f"✓ Found flash_args in {path_str}/build directory")
            return flash_args_path, build_dir
    
    # If we get here, we couldn't find the file
    print("❌ Could not find flash_args file in the current directory or its subdirectories")
    print("Please ensure you're running this tool in an ESP-IDF project directory, or specify the path using --flash-args option")
    raise SystemExit(1)


def find_local_bin_files(script_dir):
    """Find .bin files in the script directory"""
    local_bin_files = glob.glob(os.path.join(script_dir, "*.bin"))
    result = []
    
    if not local_bin_files:
        return result
        
    print(f"Found {len(local_bin_files)} bin files in script directory:")
    for bin_file in local_bin_files:
        print(f"  - {os.path.basename(bin_file)}")
    
    return local_bin_files


def parse_flash_args(flash_args_file, build_path, script_dir):
    """Parse the flash_args file to get flash options and binary files info"""
    if not os.path.exists(flash_args_file):
        print(f"❌ Flash args file not found: {flash_args_file}")
        sys.exit(1)
    
    flash_args_dir = os.path.dirname(flash_args_file)
    
    with open(flash_args_file, 'r') as f:
        lines = f.readlines()
    
    # Extract flash options from the first line
    # Format will be like: "--flash_mode dio --flash_freq 80m --flash_size 2MB"
    flash_options = []
    if lines and lines[0].strip():
        # Convert flash_mode, flash_freq, flash_size to the format expected by esptool
        options_line = lines[0].strip()
        options_line = options_line.replace("--flash_mode", "--flash_mode")
        options_line = options_line.replace("--flash_freq", "--flash_freq")
        options_line = options_line.replace("--flash_size", "--flash_size")
        flash_options = options_line.split()
    
    binary_files = []
    
    for line in lines[1:]:
        line = line.strip()
        if line:
            addr, binary = line.split(' ', 1)
            
            # Normalize paths for cross-platform compatibility
            if IS_WINDOWS:
                # Convert forward slashes to backslashes for Windows
                binary = binary.replace('/', '\\')
            else:
                # Convert backslashes to forward slashes for Unix
                binary = binary.replace('\\', '/')
            
            # Search order for binary files:
            # 1. First check in the same directory as flash_args file
            binary_path = os.path.join(flash_args_dir, binary)
            if os.path.exists(binary_path):
                binary_files.append((addr, binary_path))
                continue
                
            # 2. Then check in build_path (which might be different from flash_args_dir)
            if build_path:
                build_binary_path = os.path.join(build_path, binary)
                if os.path.exists(build_binary_path):
                    binary_files.append((addr, build_binary_path))
                    continue
            
            # 3. Check in the subdirectories of flash_args_dir
            # Split the binary path into components (handle both slash types)
            binary_components = re.split(r'[/\\]', binary)
            if len(binary_components) > 1:
                # Try to find the file in the build directory
                binary_name = binary_components[-1]
                try:
                    possible_paths = glob.glob(os.path.join(flash_args_dir, "**", binary_name), recursive=True)
                    if possible_paths:
                        binary_files.append((addr, possible_paths[0]))
                        print(f"🔍 Found binary file in subdirectory: {os.path.relpath(possible_paths[0], script_dir)}")
                        continue
                except Exception as e:
                    print(f"Warning: Error searching for {binary_name}: {e}")
            
            # 4. Check in script directory for files with the same name
            bin_name = os.path.basename(binary)
            local_bin_path = os.path.join(script_dir, bin_name)
            if os.path.exists(local_bin_path):
                print(f"🔍 Found binary file in script directory: {bin_name}")
                binary_files.append((addr, local_bin_path))
                continue
                
            # If we get here, we couldn't find the binary file
            print(f"⚠️ Warning: Binary file not found: {binary}")
    
    return flash_options, binary_files


def get_display_name(device):
    """Create a user-friendly display name for a device."""
    if '/dev/serial/by-id/' in device:
        # For by-id devices, use a shortened version that's more meaningful
        # Extract just the model and last part of the serial number
        parts = device.split('/')[-1].split('_')
        if len(parts) >= 4 and parts[0] == 'usb':
            # Format: Model + last few chars of serial
            model = parts[2][:3]  # First few chars of model name
            serial = parts[-2][-4:] if len(parts) > 4 else ""
            return f"{model}_{serial}"
        else:
            return device.split('/')[-1]
    else:
        # For regular devices, just use the base name
        return os.path.basename(device)


def flash_device(device, flash_options, binary_files, log_dir, chip_type='auto', baud_rate=1152000):
    """Flash a single device using esptool"""
    device_display_name = get_display_name(device)
    log_file = os.path.join(log_dir, f"flash_{device_display_name}.log")
    
    # Calculate total binary size for progress tracking
    total_binary_size = 0
    for _, binary_path in binary_files:
        try:
            total_binary_size += os.path.getsize(binary_path)
        except (OSError, IOError):
            pass
    
    # Initialize progress for this device
    with progress_lock:
        device_progress[device] = {
            "progress": 0.0,
            "status": "Starting",
            "total_size": total_binary_size,
            "written": 0
        }
    
    # Use a file lock when printing to avoid mixing output in parallel mode
    with progress_output_lock:
        print(f"=========================================")
        print(f"Flashing to {device}... (Log: {log_file})")
        print(f"=========================================")
    
    # Construct the esptool command
    cmd = [sys.executable, "-m", "esptool", "--chip", chip_type, "--port", device, "--baud", str(baud_rate), "write_flash"]
    
    # Add flash options after write_flash command
    cmd.extend(flash_options)
    
    # Add each binary file and its address
    for addr, binary_path in binary_files:
        cmd.extend([addr, binary_path])
    
    # Print the command for debugging (to the log file only)
    cmd_str = " ".join(cmd)
    
    # Execute the flash command
    try:
        with open(log_file, 'w', encoding='utf-8', errors='replace') as log_file_handle:
            # Log the command to the log file
            log_file_handle.write(f"Executing: {cmd_str}\n\n")
            log_file_handle.flush()
            
            # Create the subprocess with pipes
            if IS_WINDOWS:
                # Windows approach - can't use real-time progress monitoring
                # Just update progress periodically based on log file
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    bufsize=1,
                    universal_newlines=True,
                    creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
                )
                
                # Process output line by line for Windows
                for line in process.stdout:
                    log_file_handle.write(line)
                    log_file_handle.flush()
                    # Update progress based on line content
                    FlashProgress.update_progress(device, line, total_binary_size)
                
                process.wait()  # Wait for process to complete
                result = process.returncode
                
            else:
                # Unix approach - use non-blocking reads for real-time progress
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    bufsize=0
                )
                
                # Platform-specific non-blocking IO handling
                if IS_WINDOWS:
                    # Windows doesn't support fcntl, so we'll use a simpler approach
                    # Process output line by line
                    output_buffer = b""
                    
                    while process.poll() is None:
                        # Read from stdout without blocking
                        try:
                            # Use readline with a small timeout
                            line = process.stdout.readline().decode('utf-8', errors='replace')
                            if line:
                                log_file_handle.write(line)
                                log_file_handle.flush()
                                FlashProgress.update_progress(device, line, total_binary_size)
                        except Exception:
                            # If reading fails, just wait a bit
                            time.sleep(0.1)
                    
                    # Process any remaining output after process ends
                    for line in process.stdout:
                        line_str = line.decode('utf-8', errors='replace')
                        log_file_handle.write(line_str)
                        log_file_handle.flush()
                        FlashProgress.update_progress(device, line_str, total_binary_size)
                
                else:
                    # Unix systems - use fcntl and select for non-blocking IO
                    fd = process.stdout.fileno()
                    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
                    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
                    
                    # Process output in real-time for Unix
                    poll_obj = select.poll()
                    poll_obj.register(process.stdout, select.POLLIN)
                    
                    output_buffer = b""
                    timeout_ms = 100  # 100ms polling timeout
                    
                    while True:
                        # Check for output
                        events = poll_obj.poll(timeout_ms)
                        
                        if events:
                            # Data is available to read
                            try:
                                chunk = process.stdout.read()
                                if chunk:
                                    output_buffer += chunk
                                    
                                    # Look for complete lines
                                    while b'\n' in output_buffer:
                                        line_end = output_buffer.find(b'\n')
                                        line = output_buffer[:line_end].decode('utf-8', errors='replace')
                                        output_buffer = output_buffer[line_end + 1:]
                                        
                                        # Process the line
                                        log_file_handle.write(line + '\n')
                                        log_file_handle.flush()
                                        FlashProgress.update_progress(device, line, total_binary_size)
                                        
                            except (BlockingIOError, OSError):
                                # No data available at the moment, wait for next poll
                                pass
                                
                        # Check if the process is still running
                        if process.poll() is not None:
                            # Process remaining output buffer
                            if output_buffer:
                                line = output_buffer.decode('utf-8', errors='replace')
                                log_file_handle.write(line)
                                log_file_handle.flush()
                                FlashProgress.update_progress(device, line, total_binary_size)
                            break
                
                # Get the process exit code
                result = process.returncode
                
        # Handle flash success or failure
        results_dir = os.path.dirname(log_file)
        results_file = os.path.join(results_dir, 'flash_results.txt')
        
        with file_lock:
            with open(results_file, 'a') as f:
                if result == 0:
                    # Update to success status
                    with progress_lock:
                        device_progress[device]["progress"] = 1.0
                        device_progress[device]["status"] = "✅ Done"
                    f.write(f"success {device}\n")
                    return True, f"Successfully flashed to {device}"
                else:
                    # Update to failure status
                    with progress_lock:
                        device_progress[device]["status"] = "❌ Failed"
                    f.write(f"failed {device}\n")
                    return False, f"Failed to flash to {device} (exit code {result})"
                    
    except Exception as e:
        # Catch any other exceptions
        error_message = f"Error flashing to {device}: {str(e)}"
        print(f"❌ {error_message}")
        
        # Update to error status
        with progress_lock:
            device_progress[device]["status"] = "❌ Error"
            
        # Log to results file
        results_dir = os.path.dirname(log_file)
        results_file = os.path.join(results_dir, 'flash_results.txt')
        
        with file_lock:
            with open(results_file, 'a') as f:
                f.write(f"failed {device}\n")
                
        return False, error_message


def find_serial_ports():
    """Find all possible serial ports/ESP devices"""
    ports = []
    
    if IS_WINDOWS:
        # Windows method - check for valid COM ports using regex
        try:
            from serial.tools import list_ports
            ports_info = list(list_ports.comports())
            for port in ports_info:
                if port.device:
                    # On Windows, we want to include all COM ports
                    ports.append(port.device)
        except ImportError:
            # If pyserial is not available, use alternate methods
            try:
                # Use esptool to directly list available COM ports
                result = subprocess.run([sys.executable, '-m', 'esptool', '--port', 'COM', 'chip_id'], 
                                      capture_output=True, text=True, check=False)
                
                # Try to parse COM port list from error output
                error_text = result.stderr
                com_ports = re.findall(r'(COM\d+)', error_text)
                if com_ports:
                    ports.extend(com_ports)
            except:
                # If esptool method fails, try comprehensive scan of COM ports
                print("Could not automatically detect COM ports. Attempting manual scan...")
                for i in range(1, 33):  # Scan COM1 through COM32
                    port_name = f"COM{i}"
                    ports.append(port_name)
                
    elif IS_LINUX:
        # Linux method: Directly search for device files
        # Try two common ESP serial device patterns: /dev/ttyUSB* and /dev/ttyACM*
        usb_devices = glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*')
        
        # Instead of adding the by-id devices directly, create a mapping to avoid duplicates
        by_id_devices = glob.glob('/dev/serial/by-id/*')
        
        # Get the real paths of all devices to check for duplicates
        usb_real_paths = {os.path.realpath(device): device for device in usb_devices}
        
        # Only add by-id devices that don't point to the same physical device as a ttyUSB device
        for by_id_device in by_id_devices:
            real_path = os.path.realpath(by_id_device)
            if real_path not in usb_real_paths:
                usb_devices.append(by_id_device)
        
        ports.extend(usb_devices)
        
    elif IS_MACOS:
        # macOS method: Look for common serial device names
        terminal_devices = glob.glob('/dev/cu.usbserial*') + glob.glob('/dev/cu.SLAB_USBtoUART*') + glob.glob('/dev/cu.wchusbserial*')
        ports.extend(terminal_devices)
        
    if not ports:
        print("⚠️ No serial ports detected. Please check your connections and drivers.")
        
    return sorted(ports) 