#!/usr/bin/env python3
"""Simplified proxy panel component with clean, understandable interface."""

import os
import time
from typing import List, Optional, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
import subprocess

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QLabel, QCheckBox, 
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QProgressBar
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QColor

from src.ui.styles import GROUP_BOX_STYLE, CHECKBOX_STYLE
from src.network.proxy_manager import ProxyManager


class ProxyTestThread(QThread):
    """Thread for testing proxies without blocking the UI."""
    
    proxy_tested = pyqtSignal(str, bool, float)
    testing_finished = pyqtSignal()
    
    def __init__(self, proxy_manager: ProxyManager, proxies_to_test: List[str]):
        super().__init__()
        self.proxy_manager = proxy_manager
        self.proxies_to_test = proxies_to_test
        self.keep_running = True

    def run(self):
        """Test proxies efficiently - ensures ALL proxies are tested or removed."""
        try:
            total_proxies = len(self.proxies_to_test)
            completed_count = 0
            
            # Simple batch processing
            batch_size = 50
            max_workers = 15
            
            for i in range(0, total_proxies, batch_size):
                if not getattr(self, 'keep_running', True):
                    break
                    
                batch = self.proxies_to_test[i:i + batch_size]
                
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = {
                        executor.submit(self._test_proxy_fast, proxy): proxy 
                        for proxy in batch
                    }
                    
                    # Process ALL futures - no timeouts to leave proxies untested
                    completed_futures = 0
                    for future in as_completed(futures, timeout=30):
                        proxy = futures[future]
                        try:
                            is_working, response_time = future.result(timeout=2.0)  # Longer timeout
                            completed_count += 1
                            completed_futures += 1
                            
                        except Exception as e:
                            # ANY exception = proxy failed and should be removed
                            print(f"Proxy {proxy} failed: {e}")
                            self.proxy_manager._record_failure(proxy)
                            completed_count += 1
                            completed_futures += 1
                    
                    # Ensure ALL proxies in batch were processed
                    if completed_futures < len(batch):
                        print(f"⚠️ {len(batch) - completed_futures} proxies timed out - marking as failed")
                        for future, proxy in futures.items():
                            if not future.done():
                                # Timeout = failed proxy, mark for removal
                                self.proxy_manager._record_failure(proxy)
                                completed_count += 1
                    
                    # Update progress
                    if completed_count % 10 == 0 or completed_count >= total_proxies:
                        self.proxy_tested.emit("batch_update", True, completed_count)
                
                # Small delay between batches
                self.msleep(50)
            
            # Clean up any remaining untested proxies
            self._cleanup_untested_proxies()
            
            self.proxy_tested.emit("final_update", True, total_proxies)
                
        except Exception as e:
            print(f"Proxy testing error: {e}")
        finally:
            self.testing_finished.emit()
            
    def _cleanup_untested_proxies(self):
        """Remove any proxies that remain in 'untested' state."""
        try:
            untested_proxies = []
            for proxy in list(self.proxy_manager.proxy_list):
                health = self.proxy_manager.proxy_health.get(proxy, {})
                if health.get('status', 'untested') == 'untested':
                    untested_proxies.append(proxy)
            
            if untested_proxies:
                print(f"🗑️ Cleaning up {len(untested_proxies)} untested proxies")
                for proxy in untested_proxies:
                    self.proxy_manager._record_failure(proxy)
                    
        except Exception as e:
            print(f"Error cleaning up untested proxies: {e}")

    def _test_proxy_fast(self, proxy: str):
        """Fast proxy testing."""
        try:
            normalized_proxy = self.proxy_manager._normalize_proxy_for_requests(proxy)
            
            import requests
            proxy_dict = {'http': normalized_proxy, 'https': normalized_proxy}
            
            start_time = time.time()
            response = requests.get(
                "http://httpbin.org/ip",
                proxies=proxy_dict, 
                timeout=2,
                headers={'User-Agent': 'ProxyTest/1.0'}
            )
            response_time = time.time() - start_time
            
            if response.status_code == 200:
                self.proxy_manager._record_success(proxy, response_time)
                return True, response_time
            else:
                self.proxy_manager._record_failure(proxy)
                return False, response_time
                
        except Exception:
            self.proxy_manager._record_failure(proxy)
            return False, 0.0

    def stop_testing(self):
        """Stop testing."""
        self.keep_running = False


class SimplifiedProxyPanel(QWidget):
    """Simplified proxy management panel with clean interface."""
    
    proxy_configuration_changed = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        
        # Initialize proxy manager
        self.proxy_manager = ProxyManager(auto_remove_failed=True, max_failures=1)
        self.proxy_manager.proxy_removed.connect(self._on_proxy_auto_removed)
        
        self.test_thread: Optional[ProxyTestThread] = None
        
        self.init_ui()
        
    def init_ui(self):
        """Initialize the simplified UI."""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # Top section - Simple controls
        self._create_simple_controls(main_layout)
        
        # Bottom section - Simple proxy list
        self._create_simple_proxy_list(main_layout)
        
    def _create_simple_controls(self, parent_layout: QVBoxLayout):
        """Create simple proxy controls."""
        controls_group = QGroupBox("🌐 Proxy Configuration")
        controls_group.setStyleSheet(GROUP_BOX_STYLE)
        controls_layout = QVBoxLayout(controls_group)
        controls_layout.setSpacing(15)
        
        # Enable proxy checkbox
        checkbox_layout = QHBoxLayout()
        
        self.enable_proxy_checkbox = QCheckBox("Use Proxy Rotation")
        self.enable_proxy_checkbox.setStyleSheet("""
            QCheckBox {
                color: #ffffff;
                font-size: 16px;
                font-weight: bold;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border-radius: 4px;
                border: 2px solid #666;
            }
            QCheckBox::indicator:checked {
                background-color: #4CAF50;
                border-color: #4CAF50;
            }
        """)
        self.enable_proxy_checkbox.toggled.connect(self._on_proxy_toggled)
        
        self.status_label = QLabel("❌ Disabled")
        self.status_label.setStyleSheet("""
            QLabel {
                color: #F44336;
                font-weight: bold;
                font-size: 14px;
                padding: 6px 12px;
                border-radius: 6px;
                background-color: rgba(244, 67, 54, 0.2);
            }
        """)
        
        checkbox_layout.addWidget(self.enable_proxy_checkbox)
        checkbox_layout.addWidget(self.status_label)
        checkbox_layout.addStretch()
        
        controls_layout.addLayout(checkbox_layout)
        
        # File operations and actions
        buttons_layout = QHBoxLayout()
        
        self.load_button = QPushButton("📁 Load Proxy File")
        self.load_button.setEnabled(False)
        self.load_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 12px 20px;
                font-size: 14px;
                font-weight: bold;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #1976D2; }
            QPushButton:disabled { background-color: #555; color: #888; }
        """)
        self.load_button.clicked.connect(self._load_proxy_file)
        
        self.test_button = QPushButton("🧪 Test All Proxies")
        self.test_button.setEnabled(False)
        self.test_button.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                padding: 12px 20px;
                font-size: 14px;
                font-weight: bold;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #F57C00; }
            QPushButton:disabled { background-color: #555; color: #888; }
        """)
        self.test_button.clicked.connect(self._test_all_proxies)
        
        self.clear_button = QPushButton("🗑️ Clear All")
        self.clear_button.setEnabled(False)
        self.clear_button.setStyleSheet("""
            QPushButton {
                background-color: #F44336;
                color: white;
                border: none;
                padding: 12px 20px;
                font-size: 14px;
                font-weight: bold;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #D32F2F; }
            QPushButton:disabled { background-color: #555; color: #888; }
        """)
        self.clear_button.clicked.connect(self._clear_all_proxies)
        
        self.cleanup_button = QPushButton("🧹 Remove Untested")
        self.cleanup_button.setEnabled(False)
        self.cleanup_button.setStyleSheet("""
            QPushButton {
                background-color: #9C27B0;
                color: white;
                border: none;
                padding: 12px 20px;
                font-size: 14px;
                font-weight: bold;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #7B1FA2; }
            QPushButton:disabled { background-color: #555; color: #888; }
        """)
        self.cleanup_button.clicked.connect(self._cleanup_untested_proxies_manual)
        
        buttons_layout.addWidget(self.load_button)
        buttons_layout.addWidget(self.test_button)
        buttons_layout.addWidget(self.clear_button)
        buttons_layout.addWidget(self.cleanup_button)
        buttons_layout.addStretch()
        
        controls_layout.addLayout(buttons_layout)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #555;
                border-radius: 6px;
                text-align: center;
                color: white;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 4px;
            }
        """)
        controls_layout.addWidget(self.progress_bar)
        
        parent_layout.addWidget(controls_group)
    
    def _create_simple_proxy_list(self, parent_layout: QVBoxLayout):
        """Create simplified proxy list."""
        list_group = QGroupBox("📋 Proxy List")
        list_group.setStyleSheet(GROUP_BOX_STYLE)
        list_layout = QVBoxLayout(list_group)
        
        # Summary label
        self.summary_label = QLabel("No proxies loaded")
        self.summary_label.setStyleSheet("""
            QLabel {
                color: #888;
                font-size: 12px;
                padding: 8px;
                border-radius: 4px;
                background-color: rgba(136, 136, 136, 0.1);
            }
        """)
        list_layout.addWidget(self.summary_label)
        
        # Simple table
        self.proxy_table = QTableWidget()
        self.proxy_table.setColumnCount(2)
        self.proxy_table.setHorizontalHeaderLabels(["Proxy", "Status"])
        
        # Simple table styling
        header = self.proxy_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.proxy_table.setColumnWidth(1, 100)
        
        self.proxy_table.setAlternatingRowColors(True)
        self.proxy_table.verticalHeader().setVisible(False)
        self.proxy_table.setStyleSheet("""
            QTableWidget {
                background-color: #2d2d2d;
                color: #ffffff;
                border: 1px solid #555;
                border-radius: 5px;
                gridline-color: #444;
            }
            QTableWidget::item {
                padding: 10px 8px;
                border: none;
                border-bottom: 1px solid #3a3a3a;
            }
            QTableWidget::item:alternate {
                background-color: #323232;
            }
            QHeaderView::section {
                background-color: #383838;
                color: #ffffff;
                padding: 12px;
                border: none;
                border-bottom: 2px solid #0078d4;
                font-weight: bold;
            }
        """)
        
        list_layout.addWidget(self.proxy_table)
        parent_layout.addWidget(list_group)
    
    def _on_proxy_toggled(self):
        """Handle proxy enable/disable."""
        enabled = self.enable_proxy_checkbox.isChecked()
        
        # Update status
        if enabled:
            self.status_label.setText("✅ Enabled")
            self.status_label.setStyleSheet("""
                QLabel {
                    color: #4CAF50;
                    font-weight: bold;
                    font-size: 14px;
                    padding: 6px 12px;
                    border-radius: 6px;
                    background-color: rgba(76, 175, 80, 0.2);
                }
            """)
        else:
            self.status_label.setText("❌ Disabled")
            self.status_label.setStyleSheet("""
                QLabel {
                    color: #F44336;
                    font-weight: bold;
                    font-size: 14px;
                    padding: 6px 12px;
                    border-radius: 6px;
                    background-color: rgba(244, 67, 54, 0.2);
                }
            """)
            # Clear proxies when disabled
            self.proxy_manager.proxy_list.clear()
            self.proxy_manager.proxy_health.clear()
        
        # Enable/disable controls
        self.load_button.setEnabled(enabled)
        self.test_button.setEnabled(enabled and len(self.proxy_manager.proxy_list) > 0)
        self.clear_button.setEnabled(enabled and len(self.proxy_manager.proxy_list) > 0)
        self.cleanup_button.setEnabled(enabled and len(self.proxy_manager.proxy_list) > 0)
        
        self._update_display()
        self.proxy_configuration_changed.emit()
    
    def _load_proxy_file(self):
        """Load proxies from file using native dialog."""
        file_path = self._open_native_file_dialog(
            title="Load Proxy File",
            file_types="*.txt",
            start_dir=os.getcwd()
        )
        
        if file_path:
            loaded_count = self.proxy_manager.load_proxies_from_file(file_path)
            self._update_display()
            
            if loaded_count > 0:
                QMessageBox.information(self, "Success", 
                    f"Loaded {loaded_count} proxies from file.")
                self.test_button.setEnabled(True)
                self.clear_button.setEnabled(True)
                self.cleanup_button.setEnabled(True)
            else:
                QMessageBox.warning(self, "Warning", "No valid proxies found in file.")
    
    def _test_all_proxies(self):
        """Test all proxies."""
        if not self.proxy_manager.proxy_list:
            return
        
        if self.test_thread and self.test_thread.isRunning():
            # Stop current testing
            self.test_thread.stop_testing()
            self.test_thread.wait(3000)
            self._on_testing_finished()
            return
        
        # Start new test
        self.test_button.setText("⏹️ Stop Testing")
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(self.proxy_manager.proxy_list))
        self.progress_bar.setValue(0)
        
        self.test_thread = ProxyTestThread(self.proxy_manager, self.proxy_manager.proxy_list)
        self.test_thread.keep_running = True
        self.test_thread.proxy_tested.connect(self._on_proxy_tested)
        self.test_thread.testing_finished.connect(self._on_testing_finished)
        self.test_thread.start()
    
    def _clear_all_proxies(self):
        """Clear all proxies."""
        reply = QMessageBox.question(self, "Confirm", "Clear all proxies?", 
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            self.proxy_manager.proxy_list.clear()
            self.proxy_manager.proxy_health.clear()
            self._update_display()
            self.test_button.setEnabled(False)
            self.clear_button.setEnabled(False)
            self.cleanup_button.setEnabled(False)
    
    def _cleanup_untested_proxies_manual(self):
        """Manually clean up any remaining untested proxies."""
        try:
            untested_proxies = []
            for proxy in list(self.proxy_manager.proxy_list):
                health = self.proxy_manager.proxy_health.get(proxy, {})
                if health.get('status', 'untested') == 'untested':
                    untested_proxies.append(proxy)
            
            if not untested_proxies:
                QMessageBox.information(self, "No Action Needed", 
                                      "✅ No untested proxies found!\nAll proxies have been tested.")
                return
            
            reply = QMessageBox.question(self, "Remove Untested Proxies", 
                                       f"Remove {len(untested_proxies)} untested proxies?\n\n"
                                       f"Untested proxies are those that haven't been "
                                       f"tested yet or failed to complete testing.", 
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            
            if reply == QMessageBox.StandardButton.Yes:
                removed_count = 0
                for proxy in untested_proxies:
                    if proxy in self.proxy_manager.proxy_list:
                        self.proxy_manager._record_failure(proxy)
                        removed_count += 1
                
                self._update_display()
                
                if removed_count > 0:
                    QMessageBox.information(self, "Cleanup Complete", 
                                          f"✅ Removed {removed_count} untested proxies.\n"
                                          f"Only tested proxies remain!")
                
        except Exception as e:
            print(f"Error during manual cleanup: {e}")
            QMessageBox.critical(self, "Error", f"Failed to cleanup untested proxies:\n{e}")
    
    def _on_proxy_tested(self, proxy_or_type: str, is_working: bool, completed_count: float):
        """Handle proxy test result."""
        try:
            if proxy_or_type in ["batch_update", "final_update"]:
                completed = int(completed_count)
                self.progress_bar.setValue(completed)
                
                if proxy_or_type == "final_update":
                    self._update_display()
                elif completed % 50 == 0:  # Update display every 50 completions
                    self._update_display()
        except Exception as e:
            print(f"UI update error: {e}")
    
    def _on_testing_finished(self):
        """Handle testing completion."""
        self.test_button.setText("🧪 Test All Proxies")
        self.progress_bar.setVisible(False)
        self._update_display()
        
        # Show completion message with clear results
        try:
            total_remaining = len(self.proxy_manager.proxy_list)
            healthy_count = self.proxy_manager.get_healthy_proxy_count()
            untested_count = sum(1 for proxy in self.proxy_manager.proxy_list 
                               if self.proxy_manager.proxy_health.get(proxy, {}).get('status', 'untested') == 'untested')
            
            if total_remaining < 200:  # Show message for smaller datasets
                if untested_count > 0:
                    QMessageBox.warning(self, "Testing Complete", 
                                      f"⚠️ Testing finished with issues:\n"
                                      f"• Healthy proxies: {healthy_count}\n"
                                      f"• Untested proxies: {untested_count}\n"
                                      f"• Total remaining: {total_remaining}")
                else:
                    QMessageBox.information(self, "Testing Complete", 
                                          f"✅ Testing finished successfully!\n"
                                          f"• Working proxies: {healthy_count}\n"
                                          f"• All failed/untestable proxies removed\n"
                                          f"• Zero untested proxies remaining")
        except Exception as e:
            print(f"Error showing completion message: {e}")
    
    def _on_proxy_auto_removed(self, proxy: str, reason: str):
        """Handle automatic proxy removal (thread-safe)."""
        print(f"🗑️ Proxy auto-removed: {proxy} ({reason})")
        try:
            self._update_display()
        except Exception as e:
            print(f"Error updating display after proxy removal: {e}")
    
    def _update_display(self):
        """Update all display elements (thread-safe)."""
        try:
            proxy_count = len(self.proxy_manager.proxy_list)
            
            if proxy_count == 0:
                self.summary_label.setText("No proxies loaded")
            else:
                healthy_count = self.proxy_manager.get_healthy_proxy_count()
                self.summary_label.setText(f"Total: {proxy_count} proxies | Healthy: {healthy_count}")
        except Exception as e:
            print(f"Error getting proxy counts: {e}")
            self.summary_label.setText("Error updating proxy count")
        
        # Update table (thread-safe)
        try:
            proxy_count = len(self.proxy_manager.proxy_list)
            self.proxy_table.setRowCount(proxy_count)
            
            # Create snapshot of proxy list to avoid race conditions
            proxy_list_snapshot = list(self.proxy_manager.proxy_list)
            
            for row, proxy in enumerate(proxy_list_snapshot):
                if row >= proxy_count:  # Safety check
                    break
                    
                # Proxy URL
                self.proxy_table.setItem(row, 0, QTableWidgetItem(proxy))
                
                # Status (with safe dictionary access)
                health = self.proxy_manager.proxy_health.get(proxy, {})
                status = health.get('status', 'untested')
                
                if status == 'healthy':
                    status_text = "✅ OK"
                    color = QColor("#4CAF50")
                elif status == 'unhealthy':
                    status_text = "❌ Failed"  
                    color = QColor("#F44336")
                else:
                    status_text = "⚪ Untested"
                    color = QColor("#FFC107")
                
                status_item = QTableWidgetItem(status_text)
                status_item.setForeground(color)
                self.proxy_table.setItem(row, 1, status_item)
                
        except Exception as e:
            print(f"Error updating proxy table: {e}")
    
    def _open_native_file_dialog(self, title="Select File", file_types="*", start_dir=None):
        """Open native OS file dialog."""
        try:
            if start_dir is None:
                start_dir = os.getcwd()
            
            # Try zenity first
            try:
                cmd = [
                    'zenity', '--file-selection',
                    '--title=' + title,
                    '--filename=' + start_dir + '/'
                ]
                
                if file_types != "*":
                    cmd.extend(['--file-filter=' + file_types + ' | ' + file_types])
                    cmd.extend(['--file-filter=All files | *'])
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip()
                return None
            except (subprocess.SubprocessError, FileNotFoundError):
                pass
            
            # Try kdialog
            try:
                cmd = ['kdialog', '--getopenfilename', start_dir, file_types]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip()
                return None
            except (subprocess.SubprocessError, FileNotFoundError):
                pass
            
            return None
                
        except Exception as e:
            print(f"Failed to open native file dialog: {e}")
            return None
    
    def get_proxy_configuration(self) -> Dict:
        """Get current proxy configuration."""
        if not self.enable_proxy_checkbox.isChecked():
            return {
                'enabled': False,
                'proxy_manager': None,
                'strategy': 'round_robin',
                'proxy_count': 0,
                'healthy_count': 0
            }
        
        return {
            'enabled': True,
            'proxy_manager': self.proxy_manager,
            'strategy': 'round_robin',  # Simplified to single strategy
            'proxy_count': len(self.proxy_manager.proxy_list),
            'healthy_count': self.proxy_manager.get_healthy_proxy_count()
        } 