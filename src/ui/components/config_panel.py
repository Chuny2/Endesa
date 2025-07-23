#!/usr/bin/env python3
"""Configuration panel component for the Endesa batch processor."""

import os
from typing import Optional, List, Tuple

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QGridLayout,
    QPushButton, QLabel, QSpinBox, QCheckBox, QLineEdit
)
import subprocess
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from src.ui.styles import (
    GROUP_BOX_STYLE, CHECKBOX_STYLE, FILE_SELECTED_STYLE, 
    FILE_NOT_SELECTED_STYLE, VPN_ENABLED_STYLE, VPN_DISABLED_STYLE
)


class ConfigPanel(QWidget):
    """Configuration panel for batch processor settings."""
    

    
    def __init__(self):
        super().__init__()
        self.credentials_file = None
        self.init_ui()
        
    def init_ui(self):
        """Initialize the configuration panel UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Configuration group
        config_group = QGroupBox("⚙️ Configuration")
        config_group.setStyleSheet(GROUP_BOX_STYLE)
        config_layout = QGridLayout(config_group)
        config_layout.setSpacing(12)
        config_layout.setContentsMargins(15, 15, 15, 15)
        
        self._create_credentials_section(config_layout)
        self._create_threads_section(config_layout)
        self._create_retry_section(config_layout)
        self._create_vpn_section(config_layout)
        
        layout.addWidget(config_group)
        
    def _create_credentials_section(self, layout: QGridLayout):
        """Create the credentials file selection section."""
        # Credentials file selection - Row 0
        self.credentials_label = QLabel("📁 Credentials File:")
        self.credentials_label.setStyleSheet("color: #ffffff; font-size: 12px; font-weight: bold; padding: 8px 0px;")
        
        self.credentials_path_label = QLabel("No file selected")
        self.credentials_path_label.setStyleSheet(FILE_NOT_SELECTED_STYLE)
        
        self.browse_button = QPushButton("Browse")
        self.browse_button.setMinimumWidth(70)
        self.browse_button.setMinimumHeight(30)
        self.browse_button.clicked.connect(self.browse_credentials_file)
        
        layout.addWidget(self.credentials_label, 0, 0)
        layout.addWidget(self.credentials_path_label, 0, 1)
        layout.addWidget(self.browse_button, 0, 2)
        
        # Set default credentials file if it exists
        if os.path.exists("credentials.txt"):
            self._set_credentials_file("credentials.txt")
    
    def _create_threads_section(self, layout: QGridLayout):
        """Create the thread count selection section."""
        # Thread count selection - Row 1
        self.threads_label = QLabel("⚡ Thread Count:")
        self.threads_label.setStyleSheet("color: #ffffff; font-size: 12px; font-weight: bold; padding: 8px 0px;")
        
        self.threads_spinbox = QSpinBox()
        self.threads_spinbox.setRange(1, 200)
        self.threads_spinbox.setValue(50)
        self.threads_spinbox.setMinimumWidth(100)
        self.threads_spinbox.setMinimumHeight(30)
        
        layout.addWidget(self.threads_label, 1, 0)
        layout.addWidget(self.threads_spinbox, 1, 1)
    
    def _create_retry_section(self, layout: QGridLayout):
        """Create the retry configuration section."""
        # Retry configuration - Row 2
        self.retry_label = QLabel("🔄 Retry Settings:")
        self.retry_label.setStyleSheet("color: #ffffff; font-size: 12px; font-weight: bold; padding: 8px 0px;")
        
        retry_container = QWidget()
        retry_layout = QHBoxLayout(retry_container)
        retry_layout.setSpacing(10)
        retry_layout.setContentsMargins(0, 0, 0, 0)
        
        # Max retries
        retry_attempts_label = QLabel("Max Retries:")
        retry_attempts_label.setStyleSheet("color: #888888; font-size: 11px; padding: 8px 0px;")
        
        self.retry_attempts_spinbox = QSpinBox()
        self.retry_attempts_spinbox.setRange(1, 10)
        self.retry_attempts_spinbox.setValue(3)
        self.retry_attempts_spinbox.setMinimumWidth(60)
        self.retry_attempts_spinbox.setMinimumHeight(30)
        
        # Base delay
        retry_delay_label = QLabel("Base Delay (s):")
        retry_delay_label.setStyleSheet("color: #888888; font-size: 11px; padding: 8px 0px;")
        
        self.retry_delay_spinbox = QSpinBox()
        self.retry_delay_spinbox.setRange(1, 30)
        self.retry_delay_spinbox.setValue(2)
        self.retry_delay_spinbox.setMinimumWidth(60)
        self.retry_delay_spinbox.setMinimumHeight(30)
        
        retry_layout.addWidget(retry_attempts_label)
        retry_layout.addWidget(self.retry_attempts_spinbox)
        retry_layout.addWidget(retry_delay_label)
        retry_layout.addWidget(self.retry_delay_spinbox)
        retry_layout.addStretch()
        
        layout.addWidget(self.retry_label, 2, 0)
        layout.addWidget(retry_container, 2, 1, 1, 2)
    
    def _create_vpn_section(self, layout: QGridLayout):
        """Create the VPN configuration section."""
        # VPN checkbox - Row 3
        self.vpn_label = QLabel("🌐 VPN:")
        self.vpn_label.setStyleSheet("color: #ffffff; font-size: 12px; font-weight: bold; padding: 8px 0px;")
        
        vpn_container = QWidget()
        vpn_layout = QHBoxLayout(vpn_container)
        vpn_layout.setSpacing(10)
        vpn_layout.setContentsMargins(0, 0, 0, 0)
        
        self.vpn_checkbox = QCheckBox("Enable IP rotation")
        self.vpn_checkbox.setChecked(False)
        self.vpn_checkbox.setStyleSheet(CHECKBOX_STYLE)
        
        self.vpn_status_indicator = QLabel("❌ Disabled")
        self.vpn_status_indicator.setStyleSheet(VPN_DISABLED_STYLE)
        
        self.vpn_checkbox.toggled.connect(self._update_vpn_status_indicator)
        
        vpn_layout.addWidget(self.vpn_checkbox)
        vpn_layout.addWidget(self.vpn_status_indicator)
        vpn_layout.addStretch()
        
        layout.addWidget(self.vpn_label, 3, 0)
        layout.addWidget(vpn_container, 3, 1, 1, 2)
    

    
    def browse_credentials_file(self):
        """Open native OS file dialog to select credentials file."""
        file_path = self._open_native_file_dialog(
            title="Select Credentials File",
            file_types="*.txt",
            start_dir=os.getcwd()
        )
        
        if file_path:
            self._set_credentials_file(file_path)
    
    def _open_native_file_dialog(self, title="Select File", file_types="*", start_dir=None):
        """Open native OS file dialog - CROSS-PLATFORM with Windows support!"""
        try:
            import platform
            if start_dir is None:
                start_dir = os.getcwd()
            
            # WINDOWS - Use PowerShell native dialog
            if platform.system() == "Windows":
                try:
                    # Convert file_types for Windows filter
                    if file_types == "*":
                        filter_str = "All files (*.*)|*.*"
                    else:
                        # Convert "*.txt" to "Text files (*.txt)|*.txt|All files (*.*)|*.*"
                        ext_display = file_types.replace("*.", "").upper() + " files"
                        filter_str = f"{ext_display} ({file_types})|{file_types}|All files (*.*)|*.*"
                    
                    # PowerShell script for native Windows file dialog
                    ps_script = f'''
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Title = "{title}"
$dialog.InitialDirectory = "{start_dir.replace('/', '\\')}"
$dialog.Filter = "{filter_str}"
$result = $dialog.ShowDialog()
if ($result -eq "OK") {{
    $dialog.FileName
}}
'''
                    result = subprocess.run(
                        ['powershell', '-Command', ps_script], 
                        capture_output=True, text=True, timeout=30
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        return result.stdout.strip()
                    return None
                except (subprocess.SubprocessError, FileNotFoundError):
                    # Fallback to zenity if available
                    try:
                        if file_types == "*":
                            filter_arg = ""
                        else:
                            filter_arg = f"--file-filter={file_types}"
                        
                        cmd = ["zenity", "--file-selection", "--title", title]
                        if filter_arg:
                            cmd.append(filter_arg)
                        
                        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                        if result.returncode == 0:
                            return result.stdout.strip()
                        return None
                    except (subprocess.SubprocessError, FileNotFoundError):
                        # Final fallback to kdialog
                        try:
                            cmd = ["kdialog", "--getopenfilename", start_dir, file_types]
                            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                            if result.returncode == 0:
                                return result.stdout.strip()
                            return None
                        except (subprocess.SubprocessError, FileNotFoundError):
                            pass
            
            # LINUX - Try zenity first (most common on Linux)
            else:
                try:
                    cmd = [
                        'zenity', '--file-selection',
                        '--title=' + title,
                        '--filename=' + start_dir + '/'
                    ]
                    
                    if file_types != "*":
                        # Add file filter for zenity
                        cmd.extend(['--file-filter=' + file_types + ' | ' + file_types])
                        cmd.extend(['--file-filter=All files | *'])
                    
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                    if result.returncode == 0 and result.stdout.strip():
                        return result.stdout.strip()
                    return None
                except (subprocess.SubprocessError, FileNotFoundError):
                    pass
                
                # Try kdialog (KDE)
                try:
                    cmd = ['kdialog', '--getopenfilename', start_dir, file_types]
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                    if result.returncode == 0 and result.stdout.strip():
                        return result.stdout.strip()
                    return None
                except (subprocess.SubprocessError, FileNotFoundError):
                    pass
            
            # No native dialogs found - fail silently
            return None
                
        except Exception as e:
            print(f"Failed to open native file dialog: {e}")
            return None
        
        return None
    

    
    def _set_credentials_file(self, file_path: str):
        """Set the credentials file and update UI."""
        self.credentials_file = file_path
        self.credentials_path_label.setText(file_path)
        self.credentials_path_label.setStyleSheet(FILE_SELECTED_STYLE)
    
    def _update_vpn_status_indicator(self, checked: bool):
        """Update the VPN status indicator based on checkbox state."""
        if checked:
            self.vpn_status_indicator.setText("✅ Enabled")
            self.vpn_status_indicator.setStyleSheet(VPN_ENABLED_STYLE)
        else:
            self.vpn_status_indicator.setText("❌ Disabled")
            self.vpn_status_indicator.setStyleSheet(VPN_DISABLED_STYLE)
    

    
    def get_configuration(self) -> dict:
        """Get current configuration settings."""
        return {
            'credentials_file': self.credentials_file,
            'max_workers': self.threads_spinbox.value(),
            'max_retries': self.retry_attempts_spinbox.value(),
            'retry_delay': self.retry_delay_spinbox.value(),
            'use_vpn': self.vpn_checkbox.isChecked()
        }
    
    def validate_configuration(self) -> Tuple[bool, str]:
        """Validate current configuration."""
        config = self.get_configuration()
        
        if not config['credentials_file'] or not os.path.exists(config['credentials_file']):
            return False, "Please select a valid credentials file."
        
        if not config['credentials_file'].endswith('.txt'):
            return False, "Please select a .txt file."
        
        return True, "" 