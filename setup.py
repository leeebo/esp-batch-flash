#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="esp-batch-flash",
    version="0.1.0",
    author="leeebo",
    author_email="liboogo@gmail.com",
    description="A tool for parallel flashing multiple ESP32 devices",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/leeebo/esp-batch-flash",
    project_urls={
        "Bug Tracker": "https://github.com/leeebo/esp-batch-flash/issues",
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Embedded Systems",
    ],
    packages=find_packages(exclude=['examples', 'examples.*', 'tests', 'tests.*']),
    python_requires=">=3.8",
    install_requires=[
        "esptool>=4.0",
        "pyserial>=3.4",
    ],
    entry_points={
        "console_scripts": [
            "esp-batch-flash=esp_batch_flash.cli:main",
        ],
    },
) 