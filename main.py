#!/usr/bin/env python3
"""
Main entry point for Endesa Batch Processor.
"""

import os
import sys
import platform


# Set environment variables for native file dialogs
if platform.system() == "Windows":
    # Windows: Use native Windows file dialog
    os.environ['QT_QPA_PLATFORM'] = 'windows'
    os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = ''
    os.environ['QT_QPA_PLATFORMTHEME'] = ''
elif platform.system() == "Linux":
    # Linux: Force native file dialog (tunar, etc.)
    os.environ['QT_QPA_PLATFORM'] = 'xcb'
    os.environ['QT_QPA_PLATFORMTHEME'] = ''
    os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = ''

from src.ui.interface import main

if __name__ == "__main__":
    main() 