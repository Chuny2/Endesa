#!/usr/bin/env python3
"""Main window for the Endesa batch processor interface."""

import os
from typing import Optional

from PyQt6.QtWidgets import (
    QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QMessageBox, QApplication,
    QTabWidget
)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QFont

from src.core.processing_thread import BatchProcessorThread
from src.ui.styles import MAIN_WINDOW_STYLE, apply_main_styles
from src.ui.components import ConfigPanel, ControlPanel, ResultsPanel
from src.ui.components.proxy_panel_simple import SimplifiedProxyPanel


class MainWindow(QMainWindow):
    """Main interface window for Endesa batch processor."""
    
    def __init__(self):
        super().__init__()
        self.processor_thread: Optional[BatchProcessorThread] = None
        self.stop_timer: Optional[QTimer] = None
        self.init_ui()
        
    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("Endesa Batch Processor")
        
        # More responsive window sizing
        screen = QApplication.primaryScreen().geometry()
        window_width = min(1200, screen.width() - 100)
        window_height = min(900, screen.height() - 100)
        self.setGeometry(100, 100, window_width, window_height)
        self.setMinimumSize(800, 600)
        
        # Apply main styling
        self.setStyleSheet(MAIN_WINDOW_STYLE)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Title
        title_label = QLabel("Endesa Batch Processor")
        font_size = min(18, max(14, int(window_width / 70)))
        title_label.setFont(QFont("Arial", font_size, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet(f"color: #00b4d8; margin-bottom: 10px; font-size: {font_size}px; padding: 10px;")
        main_layout.addWidget(title_label)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #555;
                background-color: #2d2d2d;
                border-radius: 5px;
            }
            QTabWidget::tab-bar {
                alignment: center;
            }
            QTabBar::tab {
                background-color: #383838;
                color: #ffffff;
                padding: 8px 20px;
                margin: 2px;
                border: 1px solid #555;
                border-bottom: none;
                border-radius: 5px 5px 0px 0px;
                min-width: 100px;
            }
            QTabBar::tab:selected {
                background-color: #0078d4;
                border-color: #0078d4;
            }
            QTabBar::tab:hover {
                background-color: #454545;
            }
        """)
        
        # Create UI components
        self.config_panel = ConfigPanel()
        self.proxy_panel = SimplifiedProxyPanel()
        self.control_panel = ControlPanel()
        self.results_panel = ResultsPanel()
        
        # Create tab pages
        config_tab = QWidget()
        config_tab_layout = QVBoxLayout(config_tab)
        config_tab_layout.addWidget(self.config_panel)
        config_tab_layout.addWidget(self.control_panel)
        config_tab_layout.addStretch()
        
        # Add tabs to tab widget
        self.tab_widget.addTab(config_tab, "⚙️ Configuration")
        self.tab_widget.addTab(self.proxy_panel, "🔗 Proxy Management")
        self.tab_widget.addTab(self.results_panel, "📊 Results")
        
        # Connect signals
        self._connect_signals()
        
        # Add tab widget to main layout
        main_layout.addWidget(self.tab_widget)
    
    def _connect_signals(self):
        """Connect signals between components."""
        # Control panel signals
        self.control_panel.start_processing.connect(self.start_processing)
        self.control_panel.stop_processing.connect(self.stop_processing)
    
    def start_processing(self):
        """Start the batch processing."""
        # Validate configuration
        valid, error_message = self.config_panel.validate_configuration()
        if not valid:
            QMessageBox.warning(self, "Configuration Error", error_message)
            return
        
        # Get configuration
        config = self.config_panel.get_configuration()
        proxy_config = self.proxy_panel.get_proxy_configuration()
        
        # Warn about VPN + Proxy combination
        if config['use_vpn'] and proxy_config['enabled']:
            reply = QMessageBox.question(self, "Warning", 
                "You have both VPN and Proxy enabled. This may cause conflicts.\n\n"
                "VPN mode already provides IP rotation, so proxy may not be necessary.\n\n"
                "Do you want to continue?", 
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                return
        
        # Clear output and prepare UI
        self._prepare_ui_for_processing(config, proxy_config)
        
        # Create and start processor thread
        proxy_manager = proxy_config.get('proxy_manager') if proxy_config['enabled'] else None
        
       
        processing_proxy_manager = None
        if proxy_manager:
            from src.network.proxy_manager import ProxyManager
            # Copiar la lista de proxies actual
            proxy_list_copy = list(proxy_manager.proxy_list)
            # Crear nueva instancia sin auto-eliminación
            processing_proxy_manager = ProxyManager(proxy_list=proxy_list_copy, auto_remove_failed=False)
        
        self.processor_thread = BatchProcessorThread(
            config['credentials_file'], 
            config['max_workers'], 
            "data/output/results.txt",
            config['max_retries'], 
            config['retry_delay'], 
            config['use_vpn']
        )
        
        # Set proxy manager in processor thread if enabled
        if processing_proxy_manager:
            self.processor_thread.proxy_manager = processing_proxy_manager
            self.processor_thread.proxy_strategy = proxy_config.get('strategy', 'round_robin')
        
        # Connect thread signals
        self.processor_thread.progress_updated.connect(self.results_panel.add_output_line)
        self.processor_thread.status_updated.connect(self.control_panel.update_status)
        self.processor_thread.stats_updated.connect(self.control_panel.update_stats)
        self.processor_thread.progress_percentage.connect(self.control_panel.update_progress_percentage)
        self.processor_thread.finished_processing.connect(self.processing_finished)
        self.processor_thread.vpn_status_updated.connect(self.results_panel.add_output_line)
        
        self.processor_thread.start()
        
        # Update UI state
        self.control_panel.set_processing_state(True)
    
    def stop_processing(self):
        """Stop the batch processing safely."""
        try:
            if self.processor_thread and self.processor_thread.isRunning():
                # Signal the thread to stop
                self.processor_thread.stop()
                
                # Update UI immediately
                self.control_panel.set_processing_state(False)
                self.control_panel.update_status("Stopping processing...")
                
                # Use a timer to check if thread finished instead of blocking wait
                self.stop_timer = QTimer()
                self.stop_timer.timeout.connect(self._check_thread_finished)
                self.stop_timer.start(100)  # Check every 100ms
                
        except Exception as e:
            # If anything goes wrong, just reset the UI
            self.control_panel.set_processing_state(False)
            self.control_panel.update_status("Processing stopped")
    
    def _check_thread_finished(self):
        """Check if the processing thread has finished."""
        try:
            if self.processor_thread and not self.processor_thread.isRunning():
                # Thread has finished, stop the timer and update UI
                if self.stop_timer:
                    self.stop_timer.stop()
                    self.stop_timer.deleteLater()
                    self.stop_timer = None
                
                self.control_panel.update_status("Processing stopped by user")
                self.processor_thread = None
                
        except Exception as e:
            # If anything goes wrong, just reset the UI
            if self.stop_timer:
                self.stop_timer.stop()
                self.stop_timer.deleteLater()
                self.stop_timer = None
            
            self.control_panel.set_processing_state(False)
            self.control_panel.update_status("Processing stopped")
    
    def processing_finished(self, successful: int, failed: int, total_time: float):
        """Handle processing completion."""
        rate = (successful + failed) / total_time if total_time > 0 else 0
        
        status_message = f"Completed: {successful} successful, {failed} failed"
        self.control_panel.update_status(status_message)
        
        # Add completion message to results
        self.results_panel.add_output_line(f"\n=== Processing Complete ===")
        self.results_panel.add_output_line(f"Successful: {successful}")
        self.results_panel.add_output_line(f"Failed: {failed}")
        self.results_panel.add_output_line(f"Time: {total_time:.1f}s")
        self.results_panel.add_output_line(f"Rate: {rate:.1f} req/s")
        self.results_panel.add_output_line(f"Results saved to: results.txt")
        
        # Update UI state
        self.control_panel.set_processing_state(False)
        
        # Show completion message
        QMessageBox.information(
            self, "Processing Complete",
            f"Batch processing completed!\n\n"
            f"Successful: {successful}\n"
            f"Failed: {failed}\n"
            f"Time: {total_time:.1f}s\n"
            f"Rate: {rate:.1f} req/s"
        )
    
    def _prepare_ui_for_processing(self, config: dict, proxy_config: dict):
        """Prepare UI for processing start."""
        # Clear results and reset stats
        self.results_panel.clear_output()
        self.results_panel.clear_success_table()
        self.control_panel.reset_stats()
        
        # Switch to results tab
        self.tab_widget.setCurrentIndex(2)  # Results tab is index 2
        
        # Add initial configuration info
        self.results_panel.add_initial_message("Starting batch processing...\n")
        self.results_panel.add_initial_message(f"Configuration: {config['max_workers']} threads, {config['max_retries']} retries, {config['retry_delay']}s base delay")
        
        if config['use_vpn']:
            self.results_panel.add_initial_message("VPN: Enabled (IP rotation after each batch)")
        else:
            self.results_panel.add_initial_message("VPN: Disabled")
        
        if proxy_config['enabled']:
            proxy_count = proxy_config.get('proxy_count', 0)
            healthy_count = proxy_config.get('healthy_count', 0)
            strategy = proxy_config.get('strategy', 'round_robin')
            self.results_panel.add_initial_message(f"Proxy: Enabled ({proxy_count} proxies, {healthy_count} healthy, {strategy} strategy)")
        else:
            self.results_panel.add_initial_message("Proxy: Disabled")
        
        self.results_panel.add_initial_message("")
    
 