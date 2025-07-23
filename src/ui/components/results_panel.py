#!/usr/bin/env python3
"""Results panel component for the Endesa batch processor."""

from typing import List

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QTextEdit,
    QTableWidget, QTableWidgetItem, QPushButton, QLabel,
    QHeaderView, QSizePolicy
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from src.ui.styles import (
    TAB_WIDGET_STYLE, TEXT_EDIT_STYLE, TABLE_WIDGET_STYLE,
    CLEAR_BUTTON_STYLE
)


class ResultsPanel(QWidget):
    """Results panel for displaying output logs and success table."""
    
    def __init__(self):
        super().__init__()
        self.output_lines: List[str] = []
        self.success_data: List[dict] = []
        self.max_output_lines = 500
        self.batch_update_counter = 0
        self.batch_update_threshold = 10
        self.init_ui()
        
    def init_ui(self):
        """Initialize the results panel UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet(TAB_WIDGET_STYLE)
        self.tab_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        self._create_output_tab()
        self._create_success_table_tab()
        
        # Add tabs to tab widget
        self.tab_widget.addTab(self.output_tab, "📋 Output Log")
        self.tab_widget.addTab(self.table_tab, "✅ Success Table")
        
        layout.addWidget(self.tab_widget)
    
    def _create_output_tab(self):
        """Create the output log tab."""
        self.output_tab = QWidget()
        output_tab_layout = QVBoxLayout(self.output_tab)
        
        # Output controls
        output_controls_layout = QHBoxLayout()
        
        self.clear_output_button = QPushButton("Clear Output")
        self.clear_output_button.clicked.connect(self.clear_output)
        self.clear_output_button.setStyleSheet(CLEAR_BUTTON_STYLE)
        
        self.output_info_label = QLabel("Output will auto-scroll and show last 500 lines for performance")
        self.output_info_label.setStyleSheet("color: #888888; font-size: 11px; font-style: italic;")
        
        output_controls_layout.addWidget(self.clear_output_button)
        output_controls_layout.addStretch()
        output_controls_layout.addWidget(self.output_info_label)
        
        output_tab_layout.addLayout(output_controls_layout)
        
        # Output text area
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setMinimumHeight(500)
        self.output_text.setStyleSheet(TEXT_EDIT_STYLE)
        self.output_text.setAcceptRichText(True)
        self.output_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        output_tab_layout.addWidget(self.output_text)
    
    def _create_success_table_tab(self):
        """Create the success table tab."""
        self.table_tab = QWidget()
        table_tab_layout = QVBoxLayout(self.table_tab)
        
        # Table controls
        table_controls_layout = QHBoxLayout()
        
        self.clear_table_button = QPushButton("Clear Table")
        self.clear_table_button.clicked.connect(self.clear_success_table)
        self.clear_table_button.setStyleSheet(CLEAR_BUTTON_STYLE)
        
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
        self.success_table.setMinimumHeight(500)
        self.success_table.setStyleSheet(TABLE_WIDGET_STYLE)
        
        # Set responsive column widths
        self.success_table.horizontalHeader().setStretchLastSection(False)
        self.success_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)  # Line - fixed width
        self.success_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # Email - stretch
        self.success_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)  # Password - stretch
        self.success_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)  # IBAN - stretch
        self.success_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)  # Phone - stretch
        
        # Set initial column widths
        self.success_table.setColumnWidth(0, 60)   # Line - fixed width
        
        self.success_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        table_tab_layout.addWidget(self.success_table)
    
    def add_output_line(self, message: str):
        """Add a line to the output display with color coding."""
        # Skip spam messages to reduce UI load
        if message.startswith("Processed:"):
            return
        
        # Color code different message types
        if message.startswith("SUCCESS"):
            colored_message = f'<span style="color: #00ff00;">{message}</span>'
            self._parse_and_add_success_entry(message)
        elif message.startswith("NO_DATA"):
            colored_message = f'<span style="color: #ffff00;">{message}</span>'
            self._parse_and_add_no_data_entry(message)
        elif message.startswith("ERROR"):
            colored_message = f'<span style="color: #ff4444;">{message}</span>'
        elif message.startswith("INVALID"):
            colored_message = f'<span style="color: #ff0000;">{message}</span>'
        elif message.startswith("LOGIN_FAILED"):
            colored_message = f'<span style="color: #ff0000;">{message}</span>'
        elif message.startswith("BANNED"):
            colored_message = f'<span style="color: #ff8800;">{message}</span>'
        elif message.startswith("SKIP"):
            colored_message = f'<span style="color: #888888;">{message}</span>'
        elif message.startswith("LOGGIN_ERROR"):
            colored_message = f'<span style="color: #ff6666;">{message}</span>'
        elif message.startswith("TIMEOUT"):
            colored_message = f'<span style="color: #ff9900;">{message}</span>'

        else:
            colored_message = f'<span style="color: #ffffff;">{message}</span>'
        
        # Add to output lines list for management
        self.output_lines.append(colored_message)
        
        # Increment batch counter
        self.batch_update_counter += 1
        
        # Trim lines when limit exceeded
        if len(self.output_lines) > self.max_output_lines:
            keep_lines = int(self.max_output_lines * 0.8)
            self.output_lines = self.output_lines[-keep_lines:]
            
            # Update display and reset counter
            self._update_output_display()
            self.batch_update_counter = 0
        # Update display periodically
        elif self.batch_update_counter >= self.batch_update_threshold:
            self._update_output_display()
            self.batch_update_counter = 0
    
    def _parse_and_add_success_entry(self, message: str):
        """Parse success message and add to table."""
        try:
            # Format: "SUCCESS: Line X - email:password - IBAN: xxx Phone: xxx"
            parts = message.split(" - ")
            
            if len(parts) >= 3:
                line_part = parts[0].replace("SUCCESS: Line ", "")
                credentials_part = parts[1]
                iban_part = parts[2]  # "IBAN: xxx Phone: xxx"
                
                # Extract components
                line_num = line_part.strip()
                
                if ':' in credentials_part:
                    email, password = credentials_part.split(':', 1)
                    email = email.strip()
                    password = password.strip()
                else:
                    email = credentials_part.strip()
                    password = ""
                
                iban = iban_part.replace("IBAN: ", "").split(" Phone:")[0].strip()
                phone = iban_part.split(" Phone:")[1].strip() if " Phone:" in iban_part else ""
                
                self.add_success_to_table(line_num, email, password, iban, phone)
        except Exception:
            pass  # If parsing fails, just continue with normal output
    
    def _parse_and_add_no_data_entry(self, message: str):
        """Parse no data message and add to table."""
        try:
            # Format: "NO_DATA: Line X - email:password - No data retrieved"
            parts = message.split(" - ")
            
            if len(parts) >= 2:
                line_part = parts[0].replace("NO_DATA: Line ", "")
                credentials_part = parts[1]
                
                # Extract components
                line_num = line_part.strip()
                
                if ':' in credentials_part:
                    email, password = credentials_part.split(':', 1)
                    email = email.strip()
                    password = password.strip()
                else:
                    email = credentials_part.strip()
                    password = ""
                
                self.add_success_to_table(line_num, email, password, "No Data", "No Data")
        except Exception:
            pass  # If parsing fails, just continue with normal output
    
    def _update_output_display(self):
        """Efficiently update the output display."""
        try:
            # Clear and rebuild with current lines
            self.output_text.clear()
            self.output_text.setHtml('<br>'.join(self.output_lines))
            
            # Auto-scroll to bottom
            scrollbar = self.output_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
        except Exception as e:
            # If update fails, just continue - don't crash the app
            print(f"Output display update failed: {e}")
    
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
    
    def clear_success_table(self):
        """Clear the success table."""
        self.success_table.setRowCount(0)
        self.success_data = []
        self.add_output_line("Success table cleared.")
    
    def add_initial_message(self, message: str):
        """Add an initial message to the output."""
        self.output_text.append(message) 