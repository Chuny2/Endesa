#!/usr/bin/env python3
"""Control panel component for the Endesa batch processor."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QGridLayout,
    QPushButton, QLabel, QProgressBar
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from src.ui.styles import (
    GROUP_BOX_STYLE, START_BUTTON_STYLE, STOP_BUTTON_STYLE,
    SUCCESS_LABEL_STYLE, FAILURE_LABEL_STYLE, BANNED_LABEL_STYLE,
    TOTAL_LABEL_STYLE, RATE_LABEL_STYLE, PROGRESS_BAR_STYLE
)


class ControlPanel(QWidget):
    """Control panel for batch processor operations and statistics."""
    
    # Signals for control actions
    start_processing = pyqtSignal()
    stop_processing = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.init_ui()
        
    def init_ui(self):
        """Initialize the control panel UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Control group
        control_group = QGroupBox("🎮 Controls")
        control_group.setStyleSheet(GROUP_BOX_STYLE)
        control_layout = QHBoxLayout(control_group)
        control_layout.setSpacing(10)
        control_layout.setContentsMargins(15, 15, 15, 15)
        
        # Control buttons container
        control_buttons = QWidget()
        control_buttons_layout = QHBoxLayout(control_buttons)
        control_buttons_layout.setSpacing(10)
        control_buttons_layout.setContentsMargins(10, 10, 10, 10)
        
        self.start_button = QPushButton("▶ Start Processing")
        self.start_button.clicked.connect(self.start_processing.emit)
        self.start_button.setMinimumHeight(35)
        self.start_button.setStyleSheet(START_BUTTON_STYLE)
        
        self.stop_button = QPushButton("⏹ Stop Processing")
        self.stop_button.clicked.connect(self.stop_processing.emit)
        self.stop_button.setEnabled(False)
        self.stop_button.setMinimumHeight(35)
        self.stop_button.setStyleSheet(STOP_BUTTON_STYLE)
        
        control_buttons_layout.addWidget(self.start_button)
        control_buttons_layout.addWidget(self.stop_button)
        
        control_layout.addWidget(control_buttons)
        layout.addWidget(control_group)
        
        # Progress group
        progress_group = QGroupBox("📊 Progress & Statistics")
        progress_group.setStyleSheet(GROUP_BOX_STYLE)
        progress_layout = QVBoxLayout(progress_group)
        progress_layout.setSpacing(12)
        progress_layout.setContentsMargins(15, 15, 15, 15)
        
        # Status and progress
        self.status_label = QLabel("Ready to start")
        self.status_label.setStyleSheet("color: #888888; font-size: 12px; padding: 8px; font-weight: bold;")
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet(PROGRESS_BAR_STYLE)
        
        # Statistics panel
        stats_layout = QGridLayout()
        stats_layout.setSpacing(6)
        
        # Success counter
        self.success_label = QLabel("Success: 0")
        self.success_label.setStyleSheet(SUCCESS_LABEL_STYLE)
        
        # Failure counter
        self.failure_label = QLabel("Failed: 0")
        self.failure_label.setStyleSheet(FAILURE_LABEL_STYLE)
        
        # Banned counter
        self.banned_label = QLabel("Banned: 0")
        self.banned_label.setStyleSheet(BANNED_LABEL_STYLE)
        
        # Total counter
        self.total_label = QLabel("Total: 0")
        self.total_label.setStyleSheet(TOTAL_LABEL_STYLE)
        
        # Rate counter
        self.rate_label = QLabel("Rate: 0 req/s")
        self.rate_label.setStyleSheet(RATE_LABEL_STYLE)
        
        # Arrange statistics in a 2x3 grid
        stats_layout.addWidget(self.success_label, 0, 0)
        stats_layout.addWidget(self.failure_label, 0, 1)
        stats_layout.addWidget(self.banned_label, 0, 2)
        stats_layout.addWidget(self.total_label, 1, 0)
        stats_layout.addWidget(self.rate_label, 1, 1)
        
        progress_layout.addWidget(self.status_label)
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addLayout(stats_layout)
        
        layout.addWidget(progress_group)
    
    def set_processing_state(self, is_processing: bool):
        """Update UI state based on processing status."""
        self.start_button.setEnabled(not is_processing)
        self.stop_button.setEnabled(is_processing)
        self.progress_bar.setVisible(is_processing)
        
        if is_processing:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
        else:
            self.progress_bar.setVisible(False)
    
    def update_status(self, message: str):
        """Update the status label."""
        self.status_label.setText(message)
    
    def update_stats(self, successful: int, failed: int, banned: int, total: int, rate: float):
        """Update the statistics labels."""
        self.success_label.setText(f"Success: {successful}")
        self.failure_label.setText(f"Failed: {failed}")
        self.banned_label.setText(f"Banned: {banned}")
        self.total_label.setText(f"Total: {total}")
        self.rate_label.setText(f"Rate: {rate:.1f} req/s")
    
    def update_progress_percentage(self, percentage: int):
        """Update the progress bar with percentage."""
        self.progress_bar.setValue(percentage)
    
    def reset_stats(self):
        """Reset all statistics to zero."""
        self.success_label.setText("Success: 0")
        self.failure_label.setText("Failed: 0")
        self.banned_label.setText("Banned: 0")
        self.total_label.setText("Total: 0")
        self.rate_label.setText("Rate: 0 req/s") 