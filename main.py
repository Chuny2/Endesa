#!/usr/bin/env python3
"""Main entry point for Endesa Batch Processor."""

import os
import sys

# Force native file dialogs and avoid Qt browser issues
os.environ['QT_QPA_PLATFORM'] = 'xcb'
os.environ['QT_STYLE_OVERRIDE'] = ''
os.environ['QT_QPA_PLATFORMTHEME'] = 'gtk3'

from interface import main

if __name__ == "__main__":
    main() 