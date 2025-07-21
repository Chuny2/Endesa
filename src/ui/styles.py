#!/usr/bin/env python3
"""UI styling definitions for the Endesa batch processor interface."""

# Main application styles
MAIN_WINDOW_STYLE = """
    QMainWindow {
        background-color: #1e1e1e;
        color: #ffffff;
    }
    QWidget {
        background-color: #1e1e1e;
        color: #ffffff;
    }
"""

# Group box styles
GROUP_BOX_STYLE = """
    QGroupBox {
        font-weight: bold;
        border: 2px solid #404040;
        border-radius: 8px;
        margin-top: 1ex;
        padding-top: 10px;
        background-color: transparent;
        color: #ffffff;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 5px 0 5px;
        color: #00b4d8;
    }
"""

# Button styles
BUTTON_STYLE = """
    QPushButton {
        background-color: #00b4d8;
        color: white;
        border: none;
        padding: 8px 16px;
        border-radius: 6px;
        font-weight: bold;
        font-size: 12px;
    }
    QPushButton:hover {
        background-color: #0096c7;
    }
    QPushButton:pressed {
        background-color: #0077b6;
    }
    QPushButton:disabled {
        background-color: #404040;
        color: #666666;
    }
"""

# Spinbox styles
SPINBOX_STYLE = """
    QSpinBox {
        padding: 6px;
        border: 2px solid #404040;
        border-radius: 6px;
        background-color: #1e1e1e;
        color: #ffffff;
        font-size: 12px;
    }
    QSpinBox:focus {
        border: 2px solid #00b4d8;
    }
    QSpinBox::up-button, QSpinBox::down-button {
        background-color: #404040;
        border: none;
        border-radius: 3px;
    }
    QSpinBox::up-button:hover, QSpinBox::down-button:hover {
        background-color: #00b4d8;
    }
"""

# Text edit styles
TEXT_EDIT_STYLE = """
    QTextEdit {
        border: 2px solid #404040;
        border-radius: 6px;
        background-color: #1e1e1e;
        color: #ffffff;
        font-family: 'Consolas', 'Monaco', monospace;
        font-size: 10px;
        padding: 6px;
    }
    QTextEdit:focus {
        border: 2px solid #00b4d8;
    }
"""

# Progress bar styles
PROGRESS_BAR_STYLE = """
    QProgressBar {
        border: 2px solid #404040;
        border-radius: 6px;
        text-align: center;
        background-color: #1e1e1e;
        color: #ffffff;
        font-weight: bold;
        height: 25px;
    }
    QProgressBar::chunk {
        background-color: #00b4d8;
        border-radius: 4px;
    }
"""

# Line edit styles
LINE_EDIT_STYLE = """
    QLineEdit {
        padding: 6px;
        border: 2px solid #404040;
        border-radius: 6px;
        background-color: #1e1e1e;
        color: #ffffff;
        font-size: 12px;
    }
    QLineEdit:focus {
        border: 2px solid #00b4d8;
    }
    QLineEdit:read-only {
        background-color: #1e1e1e;
        color: #888888;
    }
"""

# Checkbox styles
CHECKBOX_STYLE = """
    QCheckBox {
        color: #ffffff;
        font-size: 11px;
    }
    QCheckBox::indicator {
        width: 18px;
        height: 18px;
        border: 2px solid #505050;
        border-radius: 4px;
        background-color: #1e1e1e;
    }
    QCheckBox::indicator:checked {
        background-color: #00b4d8;
        border: 2px solid #00b4d8;
    }
    QCheckBox::indicator:unchecked {
        background-color: #1e1e1e;
        border: 2px solid #505050;
    }
    QCheckBox::indicator:hover {
        background-color: #404040;
        border: 2px solid #00b4d8;
    }
    QCheckBox:checked {
        color: #00b4d8;
        font-weight: bold;
    }
"""

# Tab widget styles
TAB_WIDGET_STYLE = """
    QTabWidget::pane {
        border: 2px solid #404040;
        border-radius: 6px;
        background-color: #2d2d2d;
    }
    QTabBar::tab {
        background-color: #404040;
        color: #ffffff;
        padding: 10px 20px;
        margin-right: 2px;
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
        font-weight: bold;
    }
    QTabBar::tab:selected {
        background-color: #00b4d8;
        color: #ffffff;
    }
    QTabBar::tab:hover {
        background-color: #505050;
    }
"""

# Table widget styles
TABLE_WIDGET_STYLE = """
    QTableWidget {
        border: 2px solid #404040;
        border-radius: 6px;
        background-color: #1e1e1e;
        color: #ffffff;
        gridline-color: #404040;
        font-size: 11px;
    }
    QTableWidget::item {
        padding: 8px;
        border-bottom: 1px solid #404040;
    }
    QTableWidget::item:selected {
        background-color: #00b4d8;
        color: #ffffff;
    }
    QHeaderView::section {
        background-color: #2d2d2d;
        color: #ffffff;
        padding: 8px;
        border: none;
        border-bottom: 2px solid #404040;
        font-weight: bold;
    }
"""

# Specialized button styles
START_BUTTON_STYLE = """
    QPushButton {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
            stop:0 #28a745, stop:1 #20c997);
        color: white;
        border: none;
        padding: 12px 25px;
        border-radius: 8px;
        font-weight: bold;
        font-size: 14px;
    }
    QPushButton:hover {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
            stop:0 #20c997, stop:1 #17a2b8);
    }
    QPushButton:pressed {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
            stop:0 #17a2b8, stop:1 #138496);
    }
    QPushButton:disabled {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
            stop:0 #404040, stop:1 #2a2a2a);
        color: #666666;
    }
"""

STOP_BUTTON_STYLE = """
    QPushButton {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
            stop:0 #dc3545, stop:1 #c82333);
        color: white;
        border: none;
        padding: 12px 25px;
        border-radius: 8px;
        font-weight: bold;
        font-size: 14px;
    }
    QPushButton:hover {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
            stop:0 #c82333, stop:1 #bd2130);
    }
    QPushButton:pressed {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
            stop:0 #bd2130, stop:1 #a71e2a);
    }
    QPushButton:disabled {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
            stop:0 #404040, stop:1 #2a2a2a);
        color: #666666;
    }
"""

CLEAR_BUTTON_STYLE = """
    QPushButton {
        background-color: #6c757d;
        color: white;
        border: none;
        padding: 8px 16px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 12px;
    }
    QPushButton:hover {
        background-color: #5a6268;
    }
"""

# Status indicator styles
SUCCESS_LABEL_STYLE = """
    color: #00ff00; 
    font-size: 12px; 
    font-weight: bold; 
    padding: 6px; 
    border: 1px solid #00ff00; 
    border-radius: 4px; 
    background-color: transparent;
"""

FAILURE_LABEL_STYLE = """
    color: #ff4444; 
    font-size: 12px; 
    font-weight: bold; 
    padding: 6px; 
    border: 1px solid #ff4444; 
    border-radius: 4px; 
    background-color: transparent;
"""

BANNED_LABEL_STYLE = """
    color: #ff8800; 
    font-size: 12px; 
    font-weight: bold; 
    padding: 6px; 
    border: 1px solid #ff8800; 
    border-radius: 4px; 
    background-color: transparent;
"""

TOTAL_LABEL_STYLE = """
    color: #00b4d8; 
    font-size: 12px; 
    font-weight: bold; 
    padding: 6px; 
    border: 1px solid #00b4d8; 
    border-radius: 4px; 
    background-color: transparent;
"""

RATE_LABEL_STYLE = """
    color: #ffffff; 
    font-size: 11px; 
    font-weight: bold; 
    padding: 6px; 
    border: 1px solid #404040; 
    border-radius: 4px; 
    background-color: transparent;
"""

# VPN status indicator styles
VPN_ENABLED_STYLE = """
    color: #00ff00;
    font-size: 10px;
    font-weight: bold;
    padding: 4px 8px;
    border: 1px solid #00ff00;
    border-radius: 3px;
    background-color: rgba(0, 255, 0, 0.1);
"""

VPN_DISABLED_STYLE = """
    color: #ff6b6b;
    font-size: 10px;
    font-weight: bold;
    padding: 4px 8px;
    border: 1px solid #ff6b6b;
    border-radius: 3px;
    background-color: rgba(255, 107, 107, 0.1);
"""

# File path label styles
FILE_SELECTED_STYLE = """
    color: #00b4d8; 
    font-weight: bold; 
    padding: 8px 12px; 
    border: 2px solid #00b4d8; 
    border-radius: 6px; 
    background-color: transparent;
    font-size: 11px;
    min-height: 35px;
"""

FILE_NOT_SELECTED_STYLE = """
    color: #888888; 
    font-style: italic; 
    padding: 6px 8px; 
    border: 1px solid #505050; 
    border-radius: 4px; 
    background-color: transparent;
    font-size: 10px;
"""

def apply_main_styles(widget):
    """Apply the main application styles to a widget."""
    widget.setStyleSheet(MAIN_WINDOW_STYLE + GROUP_BOX_STYLE + BUTTON_STYLE + 
                        SPINBOX_STYLE + TEXT_EDIT_STYLE + PROGRESS_BAR_STYLE + 
                        LINE_EDIT_STYLE) 