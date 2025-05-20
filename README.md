# ESP Batch Flash

[![PyPI](https://img.shields.io/pypi/v/esp-batch-flash.svg)](https://pypi.org/project/esp-batch-flash/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

[English](#english) | [中文摘要](#chinese-summary)

<a name="english"></a>
## Overview

ESP Batch Flash is a tool for parallel flashing multiple ESP32 devices simultaneously. It significantly improves efficiency when you need to flash firmware to multiple ESP32/ESP8266 devices at once.

### Key Features

- **Parallel Flashing**: Flash multiple devices simultaneously, significantly improving flashing efficiency
- **Cross-Platform Support**: Compatible with Linux, Windows, and macOS
- **Real-time Progress**: Beautiful real-time progress bars
- **Auto-detection**: Automatically detect connected ESP devices
- **Flexible Configuration**: Support for various configuration options, including port specification, chip type, etc.
- **Interactive Menu**: Select which devices to flash through an interactive menu
- **Configurable Baud Rate**: Set the flashing baud rate to optimize for stability or speed
- **Mock Mode**: Test and demonstrate functionality without physical devices

### Installation

```bash
pip install esp-batch-flash
```

### Quick Start

ESP Batch Flash can be run directly from the command line:

```bash
# Flash all devices using auto-detected flash_args file
esp-batch-flash

# Specify a specific flash_args file
esp-batch-flash --flash-args path/to/flash_args

# Specify specific ports
esp-batch-flash --ports COM3,COM4  # Windows
esp-batch-flash --ports /dev/ttyUSB0,/dev/ttyUSB1  # Linux

# Interactive device selection
esp-batch-flash --interactive

# Specify chip type
esp-batch-flash --chip esp32s3

# Set custom baud rate
esp-batch-flash --baud 460800
```

### Finding the flash_args File

ESP Batch Flash automatically searches for the flash_args file in the following locations:

1. Script directory
2. Build directory within the script directory
3. Subdirectories of the script directory (searching down to a maximum of 2 levels)

The flash_args file is generated during the ESP-IDF build process and contains flashing parameters and binary file paths.

### Usage Examples

#### Basic Usage

```bash
# Auto-detect all ESP devices and flash them
esp-batch-flash
```

#### Specify Devices

```bash
# On Windows
esp-batch-flash --ports COM3,COM4,COM5

# On Linux
esp-batch-flash --ports /dev/ttyUSB0,/dev/ttyUSB1,/dev/ttyACM0
```

#### Specify Binary Files

```bash
# Specify a specific binary file to flash at a specific address
esp-batch-flash --bin 0x10000:firmware.bin
```

#### Interactive Selection

```bash
# Interactively select which devices to flash
esp-batch-flash --interactive
```

#### Limit Parallel Tasks

```bash
# Limit to flashing maximum 5 devices simultaneously
esp-batch-flash --max-parallel 5
```

#### Adjust Baud Rate

```bash
# Lower baud rate for more stable flashing
esp-batch-flash --baud 460800

# Higher baud rate for faster flashing (if devices support it)
esp-batch-flash --baud 2000000
```

#### Mock Mode for Testing/Demonstration

```bash
# Run in mock mode to simulate flashing without real devices
esp-batch-flash --mock

# Specify number of mock devices to simulate
esp-batch-flash --mock --mock-ports 5
```

### Command-Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--max-parallel` | Maximum number of parallel flash operations | 20 |
| `--flash-args` | Path to flash_args file | Auto-detected |
| `--chip` | Target chip type (esp32, esp32c3, etc.) | auto |
| `--bin` | Specify binary file to flash (addr:file.bin) | None |
| `--scan-bins` | Scan for bin files in script directory | False |
| `--ports` | Comma-separated list of specific ports | All detected |
| `--interactive` | Show menu to select ports | False |
| `--no-progress` | Disable progress bars | False |
| `--baud` | Baud rate for flashing | 1152000 |
| `--mock` | Run in mock mode without real ESP devices | False |
| `--mock-ports` | Number of mock ports to simulate in mock mode | 3 |

### Log Files

Flash logs for each device are stored in the `log` folder within the script directory.

### License

Apache 2.0

### Contributing

Contributions via Pull Requests or Issues are welcome!

---

<a name="chinese-summary"></a>
## 中文摘要

ESP Batch Flash 是一个支持批量并行烧录多个 ESP32 设备的工具。主要特点包括：

- **并行烧录**：同时烧录多个设备，显著提高效率
- **多平台支持**：兼容 Linux、Windows 和 macOS
- **实时进度显示**：美观的实时进度条
- **自动检测**：自动检测已连接的 ESP 设备
- **灵活配置**：支持多种配置选项（端口、芯片类型等）
- **交互式菜单**：选择要烧录的设备
- **可配置波特率**：优化稳定性或速度
- **模拟模式**：无需实际设备即可测试功能

### 安装

```bash
pip install esp-batch-flash
```

### 基本用法

```bash
# 自动检测并烧录所有设备
esp-batch-flash

# 指定端口
esp-batch-flash --ports COM3,COM4  # Windows
esp-batch-flash --ports /dev/ttyUSB0,/dev/ttyUSB1  # Linux

# 交互式选择设备
esp-batch-flash --interactive

# 模拟模式（无需实际设备）
esp-batch-flash --mock
```

更多详细用法请参考上面的英文文档。 