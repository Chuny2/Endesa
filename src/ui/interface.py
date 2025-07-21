#!/usr/bin/env python3
"""Entry point for the Endesa batch processor interface."""

import sys
from PyQt6.QtWidgets import QApplication
from src.ui.main_window import MainWindow


def main():
    """Main function to run the interface."""
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("Endesa Batch Processor")
    app.setApplicationVersion("1.0")
    
    # Create and show the main window
    window = MainWindow()
    window.show()
    
    # Run the application
    sys.exit(app.exec())


if __name__ == "__main__":
    main()