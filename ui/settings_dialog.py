"""Settings dialog for configuring API keys and application settings."""
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout,
    QLineEdit, QSpinBox, QPushButton, QLabel,
    QTabWidget, QWidget, QTextEdit, QGroupBox, QMessageBox,
    QCheckBox, QFileDialog, QSlider
)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QFont, QDesktopServices
from datetime import datetime


class SettingsDialog(QDialog):
    """Settings configuration dialog."""
    
    def __init__(self, parent=None, app_dir: Path = None):
        super().__init__(parent)
        self.app_dir = app_dir or Path.cwd()
        self.env_path = self.app_dir / ".env"
        
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.resize(500, 600)
        
        self.setup_ui()
        self.load_settings()
    
    def setup_ui(self):
        """Set up the settings dialog UI."""
        layout = QVBoxLayout(self)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # Create tabs
        self.create_api_tab()
        self.create_general_tab()
        self.create_donation_tab()
        self.create_about_tab()
        
        # Buttons
        button_layout = QHBoxLayout()
        
        # Test connection button
        self.test_btn = QPushButton("🔍 Test Connection")
        self.test_btn.clicked.connect(self.test_connection)
        button_layout.addWidget(self.test_btn)
        
        button_layout.addStretch()
        
        # OK/Cancel buttons
        self.ok_btn = QPushButton("OK")
        self.ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.ok_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
    
    def create_api_tab(self):
        """Create API configuration tab."""
        api_widget = QWidget()
        layout = QVBoxLayout(api_widget)
        
        # API Keys section
        api_group = QGroupBox("Binance API Configuration")
        api_form = QFormLayout(api_group)
        
        # API Key
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        api_form.addRow("API Key:", self.api_key_edit)
        
        # Show/Hide API key
        show_api_key_cb = QCheckBox("Show API Key")
        show_api_key_cb.toggled.connect(
            lambda checked: self.api_key_edit.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password)
        )
        api_form.addRow("", show_api_key_cb)
        
        # API Secret
        self.api_secret_edit = QLineEdit()
        self.api_secret_edit.setEchoMode(QLineEdit.Password)
        api_form.addRow("API Secret:", self.api_secret_edit)
        
        # Show/Hide API secret
        show_api_secret_cb = QCheckBox("Show API Secret")
        show_api_secret_cb.toggled.connect(
            lambda checked: self.api_secret_edit.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password)
        )
        api_form.addRow("", show_api_secret_cb)
        
        layout.addWidget(api_group)
        
        # Instructions
        instructions = QTextEdit()
        instructions.setMaximumHeight(150)
        instructions.setReadOnly(True)
        instructions.setHtml("""
        <h4>API Setup Instructions:</h4>
        <ol>
        <li>Go to <a href="https://www.binance.com/en/my/settings/api-management">Binance API Management</a></li>
        <li>Create a new API key with <b>read-only</b> permissions</li>
        <li>Enable "Enable Reading" permission only</li>
        <li>Copy the API Key and Secret here</li>
        <li>Click "Test Connection" to verify</li>
        </ol>
        <p><b>Security:</b> Only read-only permissions are required. Never share your API keys.</p>
        """)
        # Connect the anchorClicked signal to open links
        instructions.anchorClicked.connect(self.open_external_link)
        layout.addWidget(instructions)
        
        layout.addStretch()
        self.tab_widget.addTab(api_widget, "API Keys")
    
    def create_general_tab(self):
        """Create general settings tab with year range slider."""
        general_widget = QWidget()
        layout = QVBoxLayout(general_widget)

        # Fetch Settings Group
        fetch_group = QGroupBox("Fetch Settings")
        fetch_layout = QVBoxLayout(fetch_group)

        # API delay setting
        delay_layout = QHBoxLayout()
        delay_label = QLabel("API Call Delay:")
        self.api_delay_spin = QSpinBox()
        self.api_delay_spin.setRange(10, 2000)  # 10ms to 2000ms
        self.api_delay_spin.setValue(35)  # Optimal tested value
        self.api_delay_spin.setSuffix(" ms")
        self.api_delay_spin.setToolTip("Delay between API calls (lower = faster, but higher risk of rate limiting)")
        
        delay_layout.addWidget(delay_label)
        delay_layout.addWidget(self.api_delay_spin)
        delay_layout.addStretch()
        
        # Performance indicator
        self.performance_label = QLabel()
        self.performance_label.setStyleSheet("color: #666; font-size: 11px;")
        self.api_delay_spin.valueChanged.connect(self.update_performance_indicator)
        
        fetch_layout.addLayout(delay_layout)
        fetch_layout.addWidget(self.performance_label)

        # Year range display label
        self.year_range_label = QLabel()
        self.year_range_label.setAlignment(Qt.AlignCenter)
        self.year_range_label.setStyleSheet("font-weight: bold; padding: 5px;")
        fetch_layout.addWidget(self.year_range_label)

        # Dual year range sliders
        year_slider_layout = QGridLayout()
        year_slider_layout.setHorizontalSpacing(20)

        # Start year slider
        start_year_label = QLabel("Start Year")
        start_year_label.setAlignment(Qt.AlignCenter)
        year_slider_layout.addWidget(start_year_label, 0, 0)

        self.start_year_slider = QSlider(Qt.Horizontal)
        self.start_year_slider.setMinimum(2010)
        self.start_year_slider.setMaximum(2030)
        self.start_year_slider.setValue(2016)
        self.start_year_slider.setTickInterval(5)
        self.start_year_slider.setTickPosition(QSlider.TicksBelow)
        year_slider_layout.addWidget(self.start_year_slider, 1, 0)

        # End year slider  
        end_year_label = QLabel("End Year")
        end_year_label.setAlignment(Qt.AlignCenter)
        year_slider_layout.addWidget(end_year_label, 0, 1)

        self.end_year_slider = QSlider(Qt.Horizontal)
        self.end_year_slider.setMinimum(2010)
        self.end_year_slider.setMaximum(2030)
        self.end_year_slider.setValue(datetime.now().year + 1)
        self.end_year_slider.setTickInterval(5)
        self.end_year_slider.setTickPosition(QSlider.TicksBelow)
        year_slider_layout.addWidget(self.end_year_slider, 1, 1)

        fetch_layout.addLayout(year_slider_layout)
        layout.addWidget(fetch_group)

        # File Paths
        paths_group = QGroupBox("File Locations")
        paths_form = QFormLayout(paths_group)

        # Data directory
        data_layout = QHBoxLayout()
        self.data_dir_edit = QLineEdit()
        self.data_dir_edit.setReadOnly(True)
        browse_data_btn = QPushButton("Browse")
        browse_data_btn.clicked.connect(self.browse_data_directory)
        data_layout.addWidget(self.data_dir_edit)
        data_layout.addWidget(browse_data_btn)
        paths_form.addRow("Data directory:", data_layout)

        # Exports directory
        exports_layout = QHBoxLayout()
        self.exports_dir_edit = QLineEdit()
        self.exports_dir_edit.setReadOnly(True)
        browse_exports_btn = QPushButton("Browse")
        browse_exports_btn.clicked.connect(self.browse_exports_directory)
        exports_layout.addWidget(self.exports_dir_edit)
        exports_layout.addWidget(browse_exports_btn)
        paths_form.addRow("Exports directory:", exports_layout)

        layout.addWidget(paths_group)

        # UI Settings group removed - using only PyQtGraph for simplicity

        layout.addStretch()
        self.tab_widget.addTab(general_widget, "General")

        # Connect sliders to update function
        self.start_year_slider.valueChanged.connect(self.update_year_range_label)
        self.end_year_slider.valueChanged.connect(self.update_year_range_label)
        self.start_year_slider.valueChanged.connect(self.validate_year_range)
        self.end_year_slider.valueChanged.connect(self.validate_year_range)

        # Initialize labels
        self.update_year_range_label()
        self.update_performance_indicator()
    
    def create_donation_tab(self):
        """Create support tab with hardcoded donation links."""
        donation_widget = QWidget()
        layout = QVBoxLayout(donation_widget)
        
        # Support header
        support_group = QGroupBox("💝 Support Development")
        support_layout = QVBoxLayout(support_group)
        
        # Thank you message
        thank_you_text = QTextEdit()
        thank_you_text.setMaximumHeight(120)
        thank_you_text.setReadOnly(True)
        thank_you_text.setHtml("""
        <p><strong>Thank you for using Binance Full Deposit History Tool!</strong></p>
        <p>If this tool has been helpful in tracking your crypto investments and calculating your P/L, 
        consider supporting its continued development and maintenance.</p>
        <p>Every contribution helps keep this project free and open source! ❤️</p>
        """)
        support_layout.addWidget(thank_you_text)
        
        # Donation buttons
        buttons_layout = QHBoxLayout()
        
        # PayPal button
        paypal_btn = QPushButton("💳 PayPal Donation")
        paypal_btn.setStyleSheet("""
            QPushButton {
                background-color: #0070ba;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 8px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #005ea6;
            }
            QPushButton:pressed {
                background-color: #003087;
            }
        """)
        paypal_btn.clicked.connect(self.open_paypal)
        buttons_layout.addWidget(paypal_btn)
        
        # Stripe button
        stripe_btn = QPushButton("Buy me a coffee ☕")
        stripe_btn.setStyleSheet("""
            QPushButton {
                background-color: #635bff;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 8px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #5a52e8;
            }
            QPushButton:pressed {
                background-color: #4f46e5;
            }
        """)
        stripe_btn.clicked.connect(self.open_stripe)
        buttons_layout.addWidget(stripe_btn)
        
        support_layout.addLayout(buttons_layout)
        layout.addWidget(support_group)
        
        # Alternative support methods
        alternatives_group = QGroupBox("🚀 Other Ways to Help")
        alternatives_layout = QVBoxLayout(alternatives_group)
        
        alternatives_text = QTextEdit()
        alternatives_text.setMaximumHeight(100)
        alternatives_text.setReadOnly(True)
        alternatives_text.setHtml("""
        <ul>
        <li><strong>Share:</strong> Tell other crypto traders about this tool</li>
        <li><strong>Feedback:</strong> Report bugs or suggest new features</li>
        <li><strong>Rate:</strong> Leave a positive review if you find it useful</li>
        </ul>
        """)
        alternatives_layout.addWidget(alternatives_text)
        layout.addWidget(alternatives_group)
        
        layout.addStretch()
        self.tab_widget.addTab(donation_widget, "💝 Support")
    
    def open_paypal(self):
        """Open PayPal donation link."""
        paypal_url = "https://paypal.me/tzizic"
        QDesktopServices.openUrl(QUrl(paypal_url))
    
    def open_stripe(self):
        """Open Stripe donation link."""
        stripe_url = "https://donate.stripe.com/5kQcN7flK40Da2veQQ08g00"
        QDesktopServices.openUrl(QUrl(stripe_url))
    
    def open_external_link(self, url):
        """Open external link in browser."""
        QDesktopServices.openUrl(url)
    
    def create_about_tab(self):
        """Create about/help tab."""
        about_widget = QWidget()
        layout = QVBoxLayout(about_widget)
        
        # Title
        title_label = QLabel("Binance Full Deposit History Tool")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # Version
        version_label = QLabel("Version 1.0.0")
        version_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(version_label)
        
        # Description
        description = QTextEdit()
        description.setReadOnly(True)
        description.setHtml("""
        <h4>About</h4>
        <p>This application helps track your complete Binance deposit history 
        and analyze your cryptocurrency investment performance.</p>
        
        <h4>Features</h4>
        <ul>
        <li>Fetch all historical credit card purchases from Binance</li>
        <li>Get current spot portfolio balances and prices</li>
        <li>Calculate EUR-normalized profit/loss</li>
        <li>Export data to JSON and CSV formats</li>
        <li>Resume interrupted fetch operations</li>
        </ul>
        
        <h4>Security</h4>
        <p>This application only requires <b>read-only</b> API permissions. Your API keys are 
        stored locally in a .env file and never transmitted anywhere except to Binance's official API.</p>
        
        <h4>Support</h4>
        <p>For help or to report issues, please check the documentation or contact support.</p>
        """)
        layout.addWidget(description)
        
        self.tab_widget.addTab(about_widget, "About")
    
    def update_performance_indicator(self):
        """Update performance indicator based on API delay setting."""
        delay = self.api_delay_spin.value()
        
        if delay <= 25:
            color = "#e74c3c"  # Red
            risk = "High Risk"
            speed = "Very Fast"
        elif delay <= 50:
            color = "#f39c12"  # Orange
            risk = "Medium Risk"
            speed = "Fast"
        elif delay <= 100:
            color = "#27ae60"  # Green
            risk = "Low Risk"
            speed = "Moderate"
        else:
            color = "#3498db"  # Blue
            risk = "Very Safe"
            speed = "Slow"
        
        # Calculate throughput
        throughput = round(60000 / delay, 1)
        
        self.performance_label.setText(f"<span style='color: {color};'>{speed} - {risk}</span> (~{throughput} requests/min)")
        self.performance_label.setStyleSheet(f"color: {color}; font-size: 11px;")
    
    def update_year_range_label(self):
        """Update the year range display label."""
        start_year = self.start_year_slider.value()
        end_year = self.end_year_slider.value()
        self.year_range_label.setText(f"Fetch Range: {start_year} - {end_year}")
    
    def validate_year_range(self):
        """Ensure start year is not greater than end year."""
        start_year = self.start_year_slider.value()
        end_year = self.end_year_slider.value()
        
        if start_year > end_year:
            # Adjust the slider that was just moved
            sender = self.sender()
            if sender == self.start_year_slider:
                self.end_year_slider.setValue(start_year)
            else:
                self.start_year_slider.setValue(end_year)
    
    def browse_data_directory(self):
        """Browse for data directory."""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Data Directory", str(self.app_dir / "data")
        )
        if directory:
            self.data_dir_edit.setText(directory)
    
    def browse_exports_directory(self):
        """Browse for exports directory."""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Exports Directory", str(self.app_dir / "exports")
        )
        if directory:
            self.exports_dir_edit.setText(directory)
    
    def load_settings(self):
        """Load current settings from .env file."""
        if not self.env_path.exists():
            # Set defaults
            self.data_dir_edit.setText(str(self.app_dir / "data"))
            self.exports_dir_edit.setText(str(self.app_dir / "exports"))
            return
        
        # Read .env file
        env_vars = {}
        with open(self.env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
        
        # Load values
        self.api_key_edit.setText(env_vars.get('BINANCE_API_KEY', ''))
        self.api_secret_edit.setText(env_vars.get('BINANCE_API_SECRET', ''))
        
        # Load API delay setting
        api_delay = int(env_vars.get('API_DELAY_MS', '35'))
        self.api_delay_spin.setValue(api_delay)
        
        # Load year range values
        start_year = int(env_vars.get('START_YEAR', '2016'))
        end_year = int(env_vars.get('END_YEAR', str(datetime.now().year + 1)))
        
        self.start_year_slider.setValue(start_year)
        self.end_year_slider.setValue(end_year)
        
        # Chart library is now hardcoded to PyQtGraph - no UI setting needed
        
        self.update_year_range_label()
        self.update_performance_indicator()
        
        # Set directory paths
        self.data_dir_edit.setText(str(self.app_dir / "data"))
        self.exports_dir_edit.setText(str(self.app_dir / "exports"))
    
    def save_settings(self):
        """Save settings to .env file."""
        # Validate required fields
        if not self.api_key_edit.text().strip():
            QMessageBox.warning(self, "Validation Error", "API Key is required.")
            return False
        
        if not self.api_secret_edit.text().strip():
            QMessageBox.warning(self, "Validation Error", "API Secret is required.")
            return False
        
        # Chart library is now hardcoded to pyqtgraph
        chart_library = "pyqtgraph"
        
        # Prepare .env content with all settings
        env_content = f"""# Binance API Configuration
BINANCE_API_KEY={self.api_key_edit.text().strip()}
BINANCE_API_SECRET={self.api_secret_edit.text().strip()}

# Application Settings
API_DELAY_MS={self.api_delay_spin.value()}
START_YEAR={self.start_year_slider.value()}
END_YEAR={self.end_year_slider.value()}
CHART_LIBRARY={chart_library}
"""
        
        # Create directories if they don't exist
        data_dir = Path(self.data_dir_edit.text())
        exports_dir = Path(self.exports_dir_edit.text())
        data_dir.mkdir(exist_ok=True)
        exports_dir.mkdir(exist_ok=True)
        
        # Write .env file
        try:
            with open(self.env_path, 'w') as f:
                f.write(env_content)
            return True
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save settings: {str(e)}")
            return False
    
    def test_connection(self):
        """Test API connection with current settings."""
        if not self.api_key_edit.text().strip() or not self.api_secret_edit.text().strip():
            QMessageBox.warning(self, "Test Error", "Please enter API Key and Secret first.")
            return
        
        try:
            # Import here to avoid circular imports
            from api.binance_client import BinanceAPIClient
            
            self.test_btn.setEnabled(False)
            self.test_btn.setText("Testing...")
            
            with BinanceAPIClient(self.api_key_edit.text().strip(), self.api_secret_edit.text().strip()) as client:
                if client.test_connection():
                    QMessageBox.information(self, "Connection Test", "✅ API connection successful!")
                else:
                    QMessageBox.warning(self, "Connection Test", "❌ API connection failed. Please check your credentials.")
            
        except Exception as e:
            QMessageBox.critical(self, "Connection Test", f"❌ Connection test failed:\n\n{str(e)}")
        finally:
            self.test_btn.setEnabled(True)
            self.test_btn.setText("🔍 Test Connection")
    
    def accept(self):
        """Accept dialog and save settings."""
        if self.save_settings():
            super().accept()
    
    
    def reject(self):
        """Reject dialog without saving."""
        super().reject()
