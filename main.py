#!/usr/bin/env python3
"""
Main entry point for Endesa Batch Processor.
"""

import os
import sys

# Fix for Windows Qt platform plugin issue
if os.name == 'nt':  # Windows
    os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = ''
    os.environ['QT_QPA_PLATFORM'] = 'windows'

from interface import main

if __name__ == "__main__":
    main() 