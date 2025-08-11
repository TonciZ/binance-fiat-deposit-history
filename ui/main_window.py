"""Main window UI with toolbar, summary tiles, chart, and data tables."""
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QToolBar, QPushButton, QLabel, QTabWidget, QTableWidget, QTableWidgetItem,
    QProgressBar, QTextEdit, QFrame, QSplitter, QMessageBox, QFileDialog, QDialog,
    QApplication, QSizePolicy, QHeaderView
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont, QPixmap, QIcon, QPalette
import pyqtgraph as pg

from core.config import get_config, load_config, set_config, Config
from core.json_data_manager import JSONDataManager
from core.currency import build_eur_price_map, calculate_portfolio_eur_value
from api.binance_client import BinanceAPIClient
from api.fiat import FiatOrdersFetcher
from .settings_dialog import SettingsDialog


class FetchWorker(QThread):
    """Worker thread for fetching data from Binance API."""
    
    progress = Signal(str, int, int)  # message, current, total
    finished = Signal(dict)  # results
    error = Signal(str)  # error message
    
    def __init__(self, fetch_type: str, config: Config, data_manager: JSONDataManager):
        super().__init__()
        self.fetch_type = fetch_type
        self.config = config
        self.data_manager = data_manager
        self._stop_requested = False
    
    def request_stop(self):
        """Request the worker to stop gracefully."""
        self._stop_requested = True
    
    def run(self):
        """Run the fetch operation in background thread."""
        try:
            if self._stop_requested:
                return
                
            with BinanceAPIClient(self.config.binance_api_key, self.config.binance_api_secret) as client:
                
                if self.fetch_type == "purchases":
                    # First, fetch current portfolio (fast operation for immediate results)
                    self.progress.emit("Fetching current portfolio data...", 0, 3)
                    
                    if self._stop_requested:
                        return
                    
                    # Get spot balances with retry on rate limit
                    account_info = self._retry_api_call(lambda: client.get_account_info(), "account info")
                    if account_info is None:
                        return  # Failed to get portfolio data
                    
                    balances = {}
                    for balance in account_info.get('balances', []):
                        asset = balance['asset']
                        free = float(balance['free'])
                        locked = float(balance['locked'])
                        if free > 0 or locked > 0:
                            balances[asset] = {'free': free, 'locked': locked}
                    
                    self.data_manager.save_spot_balances(balances)
                    self.progress.emit("Fetching current prices...", 1, 3)
                    
                    if self._stop_requested:
                        return
                    
                    # Get current prices with retry on rate limit
                    prices = self._retry_api_call(lambda: client.get_all_prices(), "price data")
                    if prices is None:
                        return  # Failed to get price data
                    
                    self.data_manager.save_prices(prices)
                    
                    self.progress.emit("Portfolio updated - Now fetching transaction history...", 2, 3)
                    
                    # Build EUR price map for immediate portfolio value display
                    eur_price_map = build_eur_price_map(prices)
                    total_balances = {asset: info['free'] + info['locked'] for asset, info in balances.items()}
                    portfolio_value = calculate_portfolio_eur_value(total_balances, eur_price_map)
                    
                    # Show immediate portfolio results while fetching transactions
                    self.progress.emit(f"Portfolio: €{portfolio_value:.2f} - Starting transaction fetch...", 2, 3)
                    
                    if self._stop_requested:
                        # Return portfolio data even if user stops before transaction fetch
                        portfolio_only_result = {
                            'balances_count': len(balances),
                            'prices_count': len(prices),
                            'portfolio_value_eur': portfolio_value,
                            'portfolio_fetched': True,
                            'total_fetched': 0,  # No transactions fetched yet
                            'timestamp': datetime.now().isoformat()
                        }
                        self.finished.emit(portfolio_only_result)
                        return
                    
                    # Now fetch fiat orders/purchases (longer operation)
                    fetcher = FiatOrdersFetcher(
                        client, 
                        self.data_manager, 
                        self.config.exports_dir,
                        self.config.api_delay_ms / 1000.0  # Convert ms to seconds
                    )
                    fetcher.set_progress_callback(self.progress.emit)
                    purchases_result = fetcher.fetch_all_purchases(self.config.start_year)
                    
                    if self._stop_requested:
                        # Return portfolio data even if purchases fetch was stopped
                        portfolio_only_result = {
                            'balances_count': len(balances),
                            'prices_count': len(prices),
                            'portfolio_value_eur': portfolio_value,
                            'portfolio_fetched': True,
                            'total_fetched': 0,  # Transactions fetch was stopped
                            'timestamp': datetime.now().isoformat()
                        }
                        self.finished.emit(portfolio_only_result)
                        return
                    
                    # Combine both results
                    combined_result = {
                        'total_fetched': purchases_result.get('total_fetched', 0),
                        'raw_fetched': purchases_result.get('raw_fetched', 0),
                        'duplicates_removed': purchases_result.get('duplicates_removed', 0),
                        'windows_processed': purchases_result.get('windows_processed', 0),
                        'total_windows': purchases_result.get('total_windows', 0),
                        'completed': purchases_result.get('completed', False),
                        'balances_count': len(balances),
                        'prices_count': len(prices),
                        'portfolio_value_eur': portfolio_value,
                        'portfolio_fetched': True,
                        'timestamp': datetime.now().isoformat()
                    }
                    
                    self.progress.emit("Complete - Portfolio + transaction history fetched", 3, 3)
                    
                    if not self._stop_requested:
                        self.finished.emit(combined_result)
                
                elif self.fetch_type == "portfolio":
                    self.progress.emit("Fetching account balances...", 0, 3)
                    
                    if self._stop_requested:
                        return
                    
                    # Get spot balances with retry on rate limit
                    account_info = self._retry_api_call(lambda: client.get_account_info(), "account info")
                    if account_info is None:
                        return  # Stopped or failed
                    
                    balances = {}
                    for balance in account_info.get('balances', []):
                        asset = balance['asset']
                        free = float(balance['free'])
                        locked = float(balance['locked'])
                        if free > 0 or locked > 0:
                            balances[asset] = {'free': free, 'locked': locked}
                    
                    self.data_manager.save_spot_balances(balances)
                    self.progress.emit("Fetching current prices...", 1, 3)
                    
                    if self._stop_requested:
                        return
                    
                    # Get current prices with retry on rate limit
                    prices = self._retry_api_call(lambda: client.get_all_prices(), "price data")
                    if prices is None:
                        return  # Stopped or failed
                    
                    self.data_manager.save_prices(prices)
                    
                    self.progress.emit("Calculating portfolio value...", 2, 3)
                    
                    # Build EUR price map
                    eur_price_map = build_eur_price_map(prices)
                    
                    # Calculate total portfolio value
                    total_balances = {asset: info['free'] + info['locked'] for asset, info in balances.items()}
                    portfolio_value = calculate_portfolio_eur_value(total_balances, eur_price_map)
                    
                    result = {
                        'balances_count': len(balances),
                        'prices_count': len(prices),
                        'portfolio_value_eur': portfolio_value,
                        'timestamp': datetime.now().isoformat()
                    }
                    
                    self.progress.emit("Portfolio fetch completed", 3, 3)
                    
                    if not self._stop_requested:
                        self.finished.emit(result)
                
        except Exception as e:
            if not self._stop_requested:
                self.error.emit(str(e))
    
    def _retry_api_call(self, api_func, description: str, max_retries: int = 3):
        """Retry API call on rate limits with exponential backoff."""
        import time
        
        for attempt in range(max_retries + 1):
            if self._stop_requested:
                return None
                
            try:
                return api_func()
                
            except Exception as e:
                error_msg = str(e).lower()
                
                if "rate_limited" in error_msg or "429" in error_msg or "418" in error_msg:
                    if attempt < max_retries:
                        # Extract retry delay from error if available
                        retry_delay = 60  # Default delay
                        if "retry after" in error_msg:
                            try:
                                # Extract number from "retry after Xs"
                                import re
                                match = re.search(r'retry after (\d+)', error_msg)
                                if match:
                                    retry_delay = int(match.group(1))
                            except:
                                pass
                        
                        wait_time = min(retry_delay, 2 ** attempt * 30)  # Exponential backoff with cap
                        self.progress.emit(f"Rate limited. Retrying {description} in {wait_time}s... ({attempt + 1}/{max_retries + 1})", 0, 0)
                        
                        # Sleep in 1-second increments to allow stopping
                        for i in range(wait_time):
                            if self._stop_requested:
                                return None
                            time.sleep(1)
                            
                        continue
                    else:
                        raise Exception(f"Rate limit exceeded for {description} after {max_retries + 1} attempts: {e}")
                else:
                    # Non-rate-limit error, re-raise immediately
                    raise e
        
        return None


class SummaryTile(QFrame):
    """Custom widget for displaying summary statistics with theme support."""
    
    def __init__(self, title: str, value: str = "0", subtitle: str = ""):
        super().__init__()
        self.setFrameStyle(QFrame.Box)
        
        # Set dynamic sizing with minimum size to prevent truncation
        self.setMinimumWidth(180)  # Minimum width for content
        self.setMinimumHeight(90)   # Minimum height for content
        
        # Set size policy to expand and fill available space
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        
        # Theme-aware styling
        self.setStyleSheet("""
            QFrame {
                background-color: palette(base);
                border: 1px solid palette(mid);
                border-radius: 8px;
                margin: 4px;
                color: palette(text);
            }
        """)
        
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # Title
        self.title_label = QLabel(title)
        title_font = QFont()
        title_font.setPointSize(10)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)
        
        # Value
        self.value_label = QLabel(value)
        value_font = QFont()
        value_font.setPointSize(14)  # Slightly smaller to fit better
        value_font.setBold(True)
        self.value_label.setFont(value_font)
        self.value_label.setAlignment(Qt.AlignCenter)
        self.value_label.setWordWrap(True)
        layout.addWidget(self.value_label)
        
        # Subtitle
        if subtitle:
            self.subtitle_label = QLabel(subtitle)
            self.subtitle_label.setAlignment(Qt.AlignCenter)
            self.subtitle_label.setWordWrap(True)
            subtitle_font = QFont()
            subtitle_font.setPointSize(9)
            self.subtitle_label.setFont(subtitle_font)
            layout.addWidget(self.subtitle_label)
        else:
            self.subtitle_label = None
        
        self.setLayout(layout)
    
    def update_value(self, value: str):
        """Update the displayed value."""
        self.value_label.setText(value)
    
    def update_subtitle(self, subtitle: str):
        """Update the subtitle text."""
        if self.subtitle_label:
            self.subtitle_label.setText(subtitle)


class MainWindow(QMainWindow):
    """Main application window."""
    
    def __init__(self, data_manager: JSONDataManager, app_dir: Path):
        super().__init__()
        self.data_manager = data_manager
        self.app_dir = app_dir
        self.fetch_worker: Optional[FetchWorker] = None
        
        self.setWindowTitle("Binance Credit Card Purchase Tracker v1.0")
        
        # Set initial size before maximizing (fallback for smaller screens)
        self.setMinimumSize(1024, 600)
        self.setGeometry(100, 100, 1400, 800)
        
        self.setup_ui()
        
        # Start in maximized mode for optimal screen usage
        self.showMaximized()
        
        # Migrate existing purchase data to fix zero amounts
        try:
            migrated_count = self.data_manager.migrate_purchase_data()
            if migrated_count > 0:
                print(f"Migrated {migrated_count} purchase records with correct amounts")
        except Exception as e:
            print(f"Error during data migration: {e}")
        
        self.load_data()
        
        # Auto-refresh timer
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_summary)
        self.refresh_timer.start(30000)  # Refresh every 30 seconds
    
    def setup_ui(self):
        """Set up the user interface with simple layout."""
        # Apply theme-aware styling
        self.apply_theme()
        
        # Create toolbar
        self.create_toolbar()
        
        # Create main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(5)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        # Create summary section
        summary_widget = self.create_summary_section()
        main_layout.addWidget(summary_widget)
        
        # Create horizontal splitter for main content
        main_splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(main_splitter)
        
        # Left side - vertical splitter for logs and chart
        left_splitter = QSplitter(Qt.Vertical)
        main_splitter.addWidget(left_splitter)
        
        # Add logs section
        logs_widget = self.create_logs_section()
        left_splitter.addWidget(logs_widget)
        
        # Add chart section
        chart_widget = self.create_chart_section()
        left_splitter.addWidget(chart_widget)
        
        # Right side - tables
        tables_widget = self.create_tables_section()
        main_splitter.addWidget(tables_widget)
        
        # Set splitter proportions optimized for laptop screens - balanced for chart and logs readability
        main_splitter.setSizes([650, 450])  # More space to chart area
        left_splitter.setSizes([120, 480])  # Logs readable, chart still gets most space
        
        # Status bar with better styling
        status_bar = self.statusBar()
        status_bar.showMessage("Ready")
        status_bar.setStyleSheet("""
            QStatusBar {
                background-color: palette(window);
                border-top: 1px solid palette(mid);
                color: palette(text);
            }
        """)
    
    def apply_theme(self):
        """Apply theme-aware styling to the application."""
        # Set main window styling
        self.setStyleSheet("""
            QMainWindow {
                background-color: palette(window);
                color: palette(text);
            }
            QToolBar {
                background-color: palette(window);
                border: 1px solid palette(mid);
                color: palette(text);
                spacing: 3px;
            }
            QToolBar::handle {
                background: palette(mid);
                width: 10px;
                height: 10px;
            }
            QPushButton {
                background-color: palette(button);
                border: 1px solid palette(mid);
                border-radius: 4px;
                color: palette(text);
                padding: 4px 8px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: palette(highlight);
                border-color: palette(highlight);
            }
            QPushButton:pressed {
                background-color: palette(dark);
            }
            QDockWidget {
                background-color: palette(window);
                color: palette(text);
                titlebar-close-icon: url(none);
                titlebar-normal-icon: url(none);
            }
            QDockWidget::title {
                background-color: palette(button);
                color: palette(text);
                border: 1px solid palette(mid);
                border-radius: 4px;
                padding: 4px;
                text-align: center;
            }
            QTabWidget::pane {
                border: 1px solid palette(mid);
                background-color: palette(base);
            }
            QTabBar::tab {
                background-color: palette(button);
                color: palette(text);
                border: 1px solid palette(mid);
                padding: 6px 12px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: palette(highlight);
                color: palette(highlighted-text);
            }
            QTableWidget {
                background-color: palette(base);
                alternate-background-color: palette(alternate-base);
                color: palette(text);
                gridline-color: palette(mid);
                selection-background-color: palette(highlight);
            }
            QTextEdit {
                background-color: palette(base);
                color: palette(text);
                border: 1px solid palette(mid);
                font-family: 'Consolas', 'Monaco', monospace;
            }
            /* Ensure chart widgets have proper spacing and margins */
            ChartWidget, QWidget[objectName="chart_container"] {
                margin: 5px;
                padding: 5px;
                border: 1px solid palette(mid);
                border-radius: 4px;
                background-color: palette(base);
            }
        """)
    
    
    def create_toolbar(self):
        """Create application toolbar."""
        toolbar = QToolBar()
        toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        toolbar.setMovable(True)
        self.addToolBar(toolbar)
        
        # Fetch purchases button
        self.fetch_purchases_btn = QPushButton("📥 Fetch Fiat Orders")
        self.fetch_purchases_btn.clicked.connect(self.fetch_purchases)
        toolbar.addWidget(self.fetch_purchases_btn)
        
        toolbar.addSeparator()
        
        # Get portfolio button
        self.fetch_portfolio_btn = QPushButton("💰 Get Current Portfolio")
        self.fetch_portfolio_btn.clicked.connect(self.fetch_portfolio)
        toolbar.addWidget(self.fetch_portfolio_btn)
        
        toolbar.addSeparator()
        
        # Export buttons
        export_json_btn = QPushButton("📁 Export JSON")
        export_json_btn.clicked.connect(lambda: self.export_data("json"))
        toolbar.addWidget(export_json_btn)
        
        export_csv_btn = QPushButton("📊 Export CSV")
        export_csv_btn.clicked.connect(lambda: self.export_data("csv"))
        toolbar.addWidget(export_csv_btn)
        
        toolbar.addSeparator()
        
        # Settings button
        settings_btn = QPushButton("⚙️ Settings")
        settings_btn.clicked.connect(self.show_settings_dialog)
        toolbar.addWidget(settings_btn)
        
        toolbar.addSeparator()
        
        # Clear data button
        clear_data_btn = QPushButton("🗑️ Clear Data")
        clear_data_btn.clicked.connect(self.clear_all_data)
        clear_data_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff6b6b;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ff5252;
            }
            QPushButton:pressed {
                background-color: #e53935;
            }
        """)
        toolbar.addWidget(clear_data_btn)
        
        # Stop button (hidden by default)
        toolbar.addSeparator()
        self.stop_btn = QPushButton("⏹️ Stop")
        self.stop_btn.clicked.connect(self.stop_fetch_operation)
        self.stop_btn.setVisible(False)
        toolbar.addWidget(self.stop_btn)
        
        # Progress bar (hidden by default)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumWidth(200)
        toolbar.addWidget(self.progress_bar)
    
    
    def create_summary_section(self) -> QWidget:
        """Create summary tiles section."""
        summary_widget = QWidget()
        summary_widget.setMaximumHeight(120)
        
        layout = QHBoxLayout(summary_widget)
        
        # Create summary tiles - now 5 tiles total
        self.total_fiat_tile = SummaryTile("Total Fiat In", "€0.00")
        self.total_fees_tile = SummaryTile("Total Fees", "€0.00")
        self.current_value_tile = SummaryTile("Current Value", "€0.00")
        self.net_pl_tile = SummaryTile("Net P/L", "€0.00")  # No percentage subtitle
        self.pl_percent_tile = SummaryTile("P/L %", "0.00%")  # Separate percentage tile
        
        layout.addWidget(self.total_fiat_tile)
        layout.addWidget(self.total_fees_tile)
        layout.addWidget(self.current_value_tile)
        layout.addWidget(self.net_pl_tile)
        layout.addWidget(self.pl_percent_tile)
        
        return summary_widget
    
    def create_chart_section(self) -> QWidget:
        """Create chart section with dynamic library selection."""
        try:
            from ui.chart_widget import create_chart_widget
            from core.config import get_config
            
            # Get chart library from config
            config = get_config()
            chart_library = getattr(config, 'chart_library', 'pyqtgraph')
            
            # Create chart widget using the configured library
            chart_widget, self.chart_impl = create_chart_widget(chart_library, self)
            
            return chart_widget
            
        except Exception as e:
            # Fallback to pyqtgraph if there's an issue
            print(f"Error creating chart with configured library, falling back to pyqtgraph: {e}")
            try:
                from ui.chart_widget import create_chart_widget
                chart_widget, self.chart_impl = create_chart_widget('pyqtgraph', self)
                return chart_widget
            except Exception as fallback_error:
                # Ultimate fallback - simple widget
                print(f"Error with pyqtgraph fallback: {fallback_error}")
                return self._create_fallback_chart_widget()
    
    def _create_fallback_chart_widget(self) -> QWidget:
        """Create fallback chart widget when libraries are unavailable."""
        fallback_widget = QWidget()
        layout = QVBoxLayout(fallback_widget)
        
        title_label = QLabel("Chart Display")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        
        message_label = QLabel("Chart libraries not available - please install matplotlib or pyqtgraph")
        message_label.setAlignment(Qt.AlignCenter)
        message_label.setStyleSheet("color: #666; font-style: italic; padding: 40px;")
        layout.addWidget(message_label)
        
        return fallback_widget
    
    def create_tables_section(self) -> QWidget:
        """Create tables section with tabs in a styled container."""
        # Create container frame
        tables_container = QFrame()
        tables_container.setFrameStyle(QFrame.StyledPanel)
        tables_container.setLineWidth(1)
        tables_container.setStyleSheet("""
            QFrame {
                background-color: palette(base);
                border: 1px solid palette(mid);
                border-radius: 4px;
                margin: 2px;
            }
        """)
        
        container_layout = QVBoxLayout(tables_container)
        container_layout.setContentsMargins(5, 5, 5, 5)
        
        self.tab_widget = QTabWidget()
        
        # Purchases tab
        self.purchases_table = QTableWidget()
        self.tab_widget.addTab(self.purchases_table, "Purchases")
        
        # Balances tab
        self.balances_table = QTableWidget()
        self.tab_widget.addTab(self.balances_table, "Spot Balances")
        
        # Price map tab
        self.prices_table = QTableWidget()
        self.tab_widget.addTab(self.prices_table, "Price Map")
        
        container_layout.addWidget(self.tab_widget)
        
        return tables_container
    
    def create_logs_section(self) -> QWidget:
        """Create logs section with real-time operation visibility in a styled container."""
        # Create container frame
        logs_container = QFrame()
        logs_container.setFrameStyle(QFrame.StyledPanel)
        logs_container.setLineWidth(1)
        logs_container.setStyleSheet("""
            QFrame {
                background-color: palette(base);
                border: 1px solid palette(mid);
                border-radius: 4px;
                margin: 2px;
            }
        """)
        
        container_layout = QVBoxLayout(logs_container)
        container_layout.setContentsMargins(5, 5, 5, 5)
        
        # Logs title
        title_label = QLabel("Operation Logs")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_label.setFont(title_font)
        container_layout.addWidget(title_label)
        
        # Create logs text area with better sizing for readability
        self.logs_text = QTextEdit()
        self.logs_text.setReadOnly(True)
        self.logs_text.setMinimumHeight(80)   # Reduced but still readable
        self.logs_text.setMaximumHeight(150)  # Limit maximum height
        self.logs_text.setStyleSheet("""
            QTextEdit {
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 9pt;
                background-color: palette(base);
                border: 1px solid palette(mid);
                line-height: 1.2;
            }
        """)
        container_layout.addWidget(self.logs_text)
        
        # Clear logs button
        clear_btn = QPushButton("Clear Logs")
        clear_btn.clicked.connect(self.clear_logs)
        container_layout.addWidget(clear_btn)
        
        return logs_container
    
    def log_message(self, message: str, level: str = "INFO"):
        """Add a beautified timestamped message to the logs."""
        timestamp = datetime.now().strftime('%H:%M:%S')
        
        # Get current palette for theme-aware colors
        palette = self.palette()
        
        # Format message with emojis and styling based on level using theme-aware colors
        if level == "ERROR":
            emoji = "❌"
            color = "#e74c3c"  # Keep red for errors (universal)
            prefix = "ERROR"
        elif level == "WARNING":
            emoji = "⚠️"
            color = "#f39c12"  # Keep orange for warnings (universal)
            prefix = "WARN"
        elif level == "SUCCESS":
            emoji = "✅"
            color = "#27ae60"  # Keep green for success (universal)
            prefix = "DONE"
        else:
            # INFO level - use theme-aware text color
            text_color = palette.color(QPalette.ColorRole.Text)
            color = text_color.name()  # Convert to hex color
            prefix = ""
            if "Fetching" in message and "portfolio" in message:
                emoji = "💰"
            elif "Fetching" in message and "prices" in message:
                emoji = "💹"
            elif "Calculating" in message:
                emoji = "🧮"
            elif "fiat/payments" in message or "BUY" in message or "SELL" in message:
                emoji = "🔄"
            elif "Complete" in message or "fetched" in message:
                emoji = "🎉"
            elif "Starting" in message or "Now fetching" in message:
                emoji = "🚀"
            elif "Updated" in message or "updated" in message:
                emoji = "📊"
            elif "Cleared" in message or "cleared" in message:
                emoji = "🧹"
            elif "Exported" in message or "exported" in message:
                emoji = "📁"
            elif "API" in message:
                emoji = "🔗"
            elif "Rate limited" in message:
                emoji = "⏳"
            elif "Stopping" in message or "stopped" in message:
                emoji = "⏹️"
            else:
                emoji = "ℹ️"
        
        # Create formatted message
        if prefix:
            formatted_message = f"[{timestamp}] {emoji} {prefix}: {message}"
        else:
            formatted_message = f"[{timestamp}] {emoji} {message}"
        
        # Add colored message with monospace font
        html_message = f'<span style="color: {color}; font-family: Consolas, Monaco, monospace;">{formatted_message}</span>'
        self.logs_text.append(html_message)
        
        # Auto-scroll to bottom
        self.logs_text.ensureCursorVisible()
    
    def clear_logs(self):
        """Clear the logs display."""
        self.logs_text.clear()
        self.log_message("Logs cleared", "INFO")
    
    def show_settings_dialog(self, required: bool = False):
        """Show settings configuration dialog."""
        dialog = SettingsDialog(self, self.app_dir)
        if required:
            dialog.setWindowTitle("Setup Required - Enter API Keys")
        
        if dialog.exec() == QDialog.Accepted:
            # Reload configuration after settings change
            try:
                config = load_config(self.app_dir)
                set_config(config)
                self.statusBar().showMessage("Configuration updated", 3000)
                
                # Test API connection
                self.test_api_connection()
                
            except Exception as e:
                QMessageBox.warning(self, "Configuration Error", f"Failed to load configuration: {str(e)}")
    
    def test_api_connection(self):
        """Test API connection in background."""
        try:
            config = get_config()
            with BinanceAPIClient(config.binance_api_key, config.binance_api_secret) as client:
                if client.test_connection():
                    self.statusBar().showMessage("API connection successful", 5000)
                else:
                    self.statusBar().showMessage("API connection failed", 5000)
        except Exception as e:
            self.statusBar().showMessage(f"API test failed: {str(e)}", 5000)
    
    def fetch_purchases(self):
        """Start fetching credit card purchases."""
        if self.fetch_worker and self.fetch_worker.isRunning():
            QMessageBox.information(self, "Fetch in Progress", "Another fetch operation is already running.")
            return
        
        try:
            config = get_config()
            self.start_fetch_operation("purchases")
        except Exception as e:
            QMessageBox.warning(self, "Configuration Error", f"Please configure API settings first: {str(e)}")
            self.show_settings_dialog(required=True)
    
    def fetch_portfolio(self):
        """Start fetching current portfolio data."""
        if self.fetch_worker and self.fetch_worker.isRunning():
            QMessageBox.information(self, "Fetch in Progress", "Another fetch operation is already running.")
            return
        
        try:
            config = get_config()
            self.start_fetch_operation("portfolio")
        except Exception as e:
            QMessageBox.warning(self, "Configuration Error", f"Please configure API settings first: {str(e)}")
            self.show_settings_dialog(required=True)
    
    def start_fetch_operation(self, fetch_type: str):
        """Start a fetch operation in background thread."""
        config = get_config()
        
        # Update UI state to "fetching"
        self._set_fetch_ui_state(True)
        
        # Create and start worker thread
        self.fetch_worker = FetchWorker(fetch_type, config, self.data_manager)
        self.fetch_worker.progress.connect(self.update_progress)
        self.fetch_worker.finished.connect(self.fetch_completed)
        self.fetch_worker.error.connect(self.fetch_error)
        self.fetch_worker.start()
    
    def stop_fetch_operation(self):
        """Stop the current fetch operation."""
        if self.fetch_worker and self.fetch_worker.isRunning():
            self.statusBar().showMessage("Stopping operation...")
            self.fetch_worker.request_stop()
            
            # Give it a few seconds to stop gracefully
            if not self.fetch_worker.wait(5000):  # Wait up to 5 seconds
                self.fetch_worker.terminate()
                self.fetch_worker.wait(2000)
            
            self._set_fetch_ui_state(False)
            self.statusBar().showMessage("Operation stopped by user", 5000)
    
    def _set_fetch_ui_state(self, is_fetching: bool):
        """Update UI state during fetch operations."""
        # Enable/disable buttons
        self.fetch_purchases_btn.setEnabled(not is_fetching)
        self.fetch_portfolio_btn.setEnabled(not is_fetching)
        
        # Show/hide progress elements
        self.progress_bar.setVisible(is_fetching)
        self.stop_btn.setVisible(is_fetching)
        
        if is_fetching:
            self.progress_bar.setValue(0)
        else:
            self.progress_bar.setValue(0)
    
    def update_progress(self, message: str, current: int, total: int):
        """Update progress display and log."""
        self.statusBar().showMessage(message)
        self.log_message(message, "INFO")
        
        if total > 0:
            progress = int((current / total) * 100)
            self.progress_bar.setValue(progress)
    
    def fetch_completed(self, result: Dict[str, Any]):
        """Handle fetch completion."""
        self._set_fetch_ui_state(False)
        
        # Show result message
        if 'total_fetched' in result:
            if result['total_fetched'] == 0:
                message = "No credit card purchases found"
                self.log_message(message, "WARNING")
                # Show helpful dialog
                self.show_no_purchases_info()
            else:
                # Check if this was a combined operation (purchases + portfolio)
                if result.get('portfolio_fetched', False):
                    message = f"✅ Complete: Fetched {result['total_fetched']} purchases + portfolio (€{result['portfolio_value_eur']:.2f})"
                else:
                    message = f"Fetched {result['total_fetched']} purchases successfully"
                self.log_message(message, "SUCCESS")
        elif 'portfolio_value_eur' in result:
            message = f"Portfolio updated - Value: €{result['portfolio_value_eur']:.2f}"
            self.log_message(message, "SUCCESS")
        else:
            message = "Operation completed successfully"
            self.log_message(message, "SUCCESS")
        
        self.statusBar().showMessage(message, 10000)
        
        # Refresh display
        self.load_data()
    
    def fetch_error(self, error_message: str):
        """Handle fetch error."""
        self._set_fetch_ui_state(False)
        
        self.log_message(f"Operation failed: {error_message}", "ERROR")
        self.statusBar().showMessage(f"Error: {error_message}", 10000)
        QMessageBox.critical(self, "Fetch Error", f"Operation failed:\n\n{error_message}")
    
    def show_no_purchases_info(self):
        """Show informational dialog when no purchases are found."""
        msg = QMessageBox(self)
        msg.setWindowTitle("No Credit Card Purchases Found")
        msg.setIcon(QMessageBox.Information)
        
        text = (
            "No credit card purchases were found in your Binance account.\n\n"
            "We searched both /fiat/orders and /fiat/payments endpoints for:\n"
            "• BUY transactions (fiat → crypto)\n"
            "• SELL transactions (crypto → fiat)\n\n"
            "This could mean:\n"
            "• No credit card purchases have been made on this account\n"
            "• Purchases were made outside the fetching date range\n"
            "• API permissions may not include fiat payment history\n"
            "• Purchases may be in a different payment method (P2P, bank transfer)\n\n"
            "You can try:\n"
            "• Check your Binance account's payment history manually\n"
            "• Verify API key permissions include payment data\n"
            "• Adjust the start year in Settings if purchases are older\n"
            "• Export CSV from Binance website for historical data"
        )
        
        msg.setText(text)
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec()
    
    def load_data(self):
        """Load data from database and update display."""
        self.load_purchases_table()
        self.load_balances_table()
        self.load_prices_table()
        self.refresh_summary()
        self.update_chart()
    
    def load_purchases_table(self):
        """Load purchases into table."""
        purchases = self.data_manager.get_purchases(limit=1000)  # Limit for performance
        
        self.purchases_table.setColumnCount(9)
        self.purchases_table.setHorizontalHeaderLabels([
            "Date", "Type", "Order ID", "Fiat Currency", "Fiat Amount", 
            "Crypto", "Crypto Amount", "Price", "Fee"
        ])
        
        self.purchases_table.setRowCount(len(purchases))
        
        for row, purchase in enumerate(purchases):
            # Format timestamp - use createTime from JSON data
            timestamp = purchase.get('createTime', 0)
            if timestamp:
                date_str = datetime.fromtimestamp(timestamp / 1000).strftime('%Y-%m-%d %H:%M')
            else:
                date_str = ""
            
            # Determine transaction type - use transactionType directly from JSON
            trans_type = 'BUY'  # Default
            transaction_type_code = purchase.get('transactionType', '0')
            if transaction_type_code == '1':
                trans_type = 'SELL'
            else:
                trans_type = 'BUY'
            
            self.purchases_table.setItem(row, 0, QTableWidgetItem(date_str))
            
            # Add transaction type with color coding
            type_item = QTableWidgetItem(trans_type)
            if trans_type == 'BUY':
                from PySide6.QtGui import QColor
                type_item.setBackground(QColor(0, 255, 0, 50))  # Light green
            else:
                from PySide6.QtGui import QColor
                type_item.setBackground(QColor(255, 0, 0, 50))  # Light red
            self.purchases_table.setItem(row, 1, type_item)
            
            self.purchases_table.setItem(row, 2, QTableWidgetItem(str(purchase.get('orderId', ''))))
            self.purchases_table.setItem(row, 3, QTableWidgetItem(purchase.get('fiatCurrency', '')))
            self.purchases_table.setItem(row, 4, QTableWidgetItem(f"{purchase.get('amountFiat', 0):.2f}"))
            self.purchases_table.setItem(row, 5, QTableWidgetItem(purchase.get('cryptoCurrency', '')))
            self.purchases_table.setItem(row, 6, QTableWidgetItem(f"{purchase.get('amountCrypto', 0):.6f}"))
            self.purchases_table.setItem(row, 7, QTableWidgetItem(f"{purchase.get('price', 0):.6f}"))
            self.purchases_table.setItem(row, 8, QTableWidgetItem(f"{purchase.get('fee', 0):.2f}"))
        
        # Set proper column sizing for purchases table - all resize to contents to prevent truncation
        header = self.purchases_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Date
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Type
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Order ID
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Fiat Currency
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Fiat Amount
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # Crypto
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # Crypto Amount
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)  # Price
        header.setSectionResizeMode(8, QHeaderView.ResizeToContents)  # Fee
        
        # Enable horizontal scrolling when content is wider than table
        self.purchases_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.purchases_table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Fix row header width to show complete row numbers (including 3+ digits)
        vertical_header = self.purchases_table.verticalHeader()
        vertical_header.setFixedWidth(50)  # Wide enough for 3-digit numbers + padding
    
    def load_balances_table(self):
        """Load spot balances into table."""
        balances = self.data_manager.get_spot_balances()
        
        self.balances_table.setColumnCount(4)
        self.balances_table.setHorizontalHeaderLabels([
            "Asset", "Free", "Locked", "Total"
        ])
        
        self.balances_table.setRowCount(len(balances))
        
        for row, (asset, balance_info) in enumerate(balances.items()):
            free = balance_info['free']
            locked = balance_info['locked']
            total = free + locked
            
            self.balances_table.setItem(row, 0, QTableWidgetItem(asset))
            self.balances_table.setItem(row, 1, QTableWidgetItem(f"{free:.6f}"))
            self.balances_table.setItem(row, 2, QTableWidgetItem(f"{locked:.6f}"))
            self.balances_table.setItem(row, 3, QTableWidgetItem(f"{total:.6f}"))
        
        # Set flexible column sizing for balances table
        header = self.balances_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Asset
        header.setSectionResizeMode(1, QHeaderView.Stretch)          # Free - stretch
        header.setSectionResizeMode(2, QHeaderView.Stretch)          # Locked - stretch
        header.setSectionResizeMode(3, QHeaderView.Stretch)          # Total - stretch
        
        # Fix row header width to show complete row numbers
        vertical_header = self.balances_table.verticalHeader()
        vertical_header.setFixedWidth(50)  # Wide enough for 3-digit numbers + padding
    
    def load_prices_table(self):
        """Load prices into table (sample)."""
        prices = self.data_manager.get_prices()
        
        # Show only EUR-related pairs for relevance
        eur_related = {k: v for k, v in prices.items() if 'EUR' in k or 'USDT' in k}
        
        self.prices_table.setColumnCount(2)
        self.prices_table.setHorizontalHeaderLabels(["Symbol", "Price"])
        self.prices_table.setRowCount(len(eur_related))
        
        for row, (symbol, price) in enumerate(eur_related.items()):
            self.prices_table.setItem(row, 0, QTableWidgetItem(symbol))
            self.prices_table.setItem(row, 1, QTableWidgetItem(f"{price:.6f}"))
        
        # Set flexible column sizing for prices table
        header = self.prices_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Symbol
        header.setSectionResizeMode(1, QHeaderView.Stretch)          # Price - stretch
        
        # Fix row header width to show complete row numbers
        vertical_header = self.prices_table.verticalHeader()
        vertical_header.setFixedWidth(50)  # Wide enough for 3-digit numbers + padding
    
    def refresh_summary(self):
        """Refresh summary tiles with current data - EUR only, simple."""
        try:
            # Calculate purchase and sale totals - EUR only
            purchases = self.data_manager.get_purchases()
            total_buy_eur = 0.0
            total_sell_eur = 0.0
            total_fees_eur = 0.0
            
            for purchase in purchases:
                # All amounts are in EUR from the database
                fiat_amount = purchase.get('amountFiat', 0)
                fee = purchase.get('fee', 0)
                
                # Check transaction type from raw JSON
                import json
                trans_type = '0'  # Default to BUY
                raw_json = purchase.get('rawJson', '')
                if raw_json:
                    try:
                        raw_data = json.loads(raw_json)
                        trans_type = raw_data.get('transactionType', '0')
                    except json.JSONDecodeError:
                        pass
                
                if trans_type == '0':  # BUY transaction
                    total_buy_eur += fiat_amount
                elif trans_type == '1':  # SELL transaction
                    total_sell_eur += fiat_amount
                
                total_fees_eur += fee
            
            # Calculate net investment (BUY - SELL)
            net_invested = total_buy_eur - total_sell_eur
            
            # Calculate current portfolio value in EUR
            balances = self.data_manager.get_spot_balances()
            prices = self.data_manager.get_prices()
            
            current_value = 0.0
            if balances and prices:
                eur_price_map = build_eur_price_map(prices)
                total_balances = {asset: info['free'] + info['locked'] for asset, info in balances.items()}
                current_value = calculate_portfolio_eur_value(total_balances, eur_price_map)
            
            # Calculate P/L based on net investment
            net_pl = current_value - net_invested
            net_pl_percent = (net_pl / net_invested * 100) if net_invested > 0 else 0
            
            # Update tiles - always EUR
            if total_sell_eur > 0:
                # Show net investment when sells exist
                self.total_fiat_tile.title_label.setText("Net Invested")
                self.total_fiat_tile.update_value(f"€{net_invested:.2f}")
            else:
                # Show total buys when no sells
                self.total_fiat_tile.title_label.setText("Total Fiat In")
                self.total_fiat_tile.update_value(f"€{total_buy_eur:.2f}")
            
            self.total_fees_tile.update_value(f"€{total_fees_eur:.2f}")
            self.current_value_tile.update_value(f"€{current_value:.2f}")
            
            pl_color = "green" if net_pl >= 0 else "red"
            pl_sign = "+" if net_pl >= 0 else ""
            percent_sign = "+" if net_pl_percent >= 0 else ""
            
            # Update Net P/L EUR tile
            self.net_pl_tile.update_value(f"€{pl_sign}{net_pl:.2f}")
            self.net_pl_tile.value_label.setStyleSheet(f"color: {pl_color};")
            
            # Update separate P/L percentage tile
            self.pl_percent_tile.update_value(f"{percent_sign}{net_pl_percent:.2f}%")
            self.pl_percent_tile.value_label.setStyleSheet(f"color: {pl_color};")
            
        except Exception as e:
            print(f"Error refreshing summary: {e}")
    
    def update_chart(self):
        """Update the portfolio value chart using the configured chart implementation."""
        if hasattr(self, 'chart_impl') and self.chart_impl:
            try:
                purchases = self.data_manager.get_purchases()
                self.chart_impl.update_chart_data(purchases)
                return
            except Exception as e:
                print(f"Error updating chart with chart_impl: {e}")
        
        # Fallback to old method if chart_impl is not available
        if not hasattr(self, 'plot_widget') or not self.plot_widget:
            return
            
        self.plot_widget.clear()
        
        try:
            # Get purchases data sorted by time
            purchases = self.data_manager.get_purchases()
            if not purchases:
                # No data to display
                self.plot_widget.setTitle("No purchase data available")
                return
                
            # Sort purchases by timestamp - use createTime from JSON data
            purchases_sorted = sorted(purchases, key=lambda x: x.get('createTime', 0))
            
            # Separate BUY and SELL transactions
            buy_transactions = []
            sell_transactions = []
            
            config = get_config()
            
            for purchase in purchases_sorted:
                timestamp = purchase.get('createTime', 0)
                if timestamp == 0:
                    continue
                
                # Check transaction type - use transactionType directly from JSON
                trans_type = purchase.get('transactionType', '0')
                
                # Amount is already in EUR after normalization
                fiat_eur = purchase.get('amountFiat', 0)
                
                timestamp_sec = timestamp / 1000
                
                if trans_type == '0':  # BUY
                    buy_transactions.append((timestamp_sec, fiat_eur))
                elif trans_type == '1':  # SELL
                    sell_transactions.append((timestamp_sec, fiat_eur))
            
            # Calculate cumulative investment (BUY - SELL)
            all_transactions = sorted(buy_transactions + sell_transactions, key=lambda x: x[0])
            
            if not all_transactions:
                self.plot_widget.setTitle("No valid timestamp data")
                return
            
            # Calculate cumulative net investment over time
            timestamps = []
            cumulative_net_eur = []
            running_total = 0.0
            
            for timestamp_sec, amount_eur in all_transactions:
                # Determine if this timestamp is a BUY or SELL
                is_buy = any(t for t in buy_transactions if t[0] == timestamp_sec and t[1] == amount_eur)
                
                if is_buy:
                    running_total += amount_eur  # Add for purchases
                else:
                    running_total -= amount_eur  # Subtract for sales
                
                timestamps.append(timestamp_sec)
                cumulative_net_eur.append(running_total)
            
            # Plot cumulative net investment as a stepped line
            # For stepMode, we need to add one more timestamp at the end
            if len(timestamps) > 0:
                step_timestamps = timestamps + [timestamps[-1] + 86400]  # Add one day to the last timestamp
                self.plot_widget.plot(
                    step_timestamps, cumulative_net_eur, 
                    pen=pg.mkPen(color='b', width=2), 
                    name='Net Investment (EUR)',
                    stepMode=True
                )
            else:
                self.plot_widget.plot(
                    timestamps, cumulative_net_eur, 
                    pen=pg.mkPen(color='b', width=2), 
                    name='Net Investment (EUR)'
                )
            
            # Store transaction data for interactive features
            self.transaction_bars_data = []
            
            # Add individual transaction bars with interactive features
            if buy_transactions:
                # Group buy transactions by date for better visualization
                from collections import defaultdict
                buy_by_date = defaultdict(list)
                
                for purchase in purchases_sorted:
                    timestamp = purchase.get('createTime', 0)
                    if timestamp == 0:
                        continue
                    
                    # Check if it's a BUY transaction - use transactionType directly from JSON
                    trans_type = purchase.get('transactionType', '0')
                    
                    if trans_type == '0':  # BUY
                        timestamp_sec = timestamp / 1000
                        # Amount is already in EUR after normalization
                        fiat_eur = purchase.get('amountFiat', 0)
                        
                        # Group by day (rounded to nearest day)
                        day_timestamp = int(timestamp_sec // 86400) * 86400
                        buy_by_date[day_timestamp].append({
                            'purchase': purchase,
                            'amount_eur': fiat_eur,
                            'timestamp_sec': timestamp_sec
                        })
                
                # Create bars for each day
                for day_timestamp, day_purchases in buy_by_date.items():
                    total_amount = sum(p['amount_eur'] for p in day_purchases)
                    
                    # Create tooltip text
                    tooltip_lines = [f"PURCHASES - Date: {datetime.fromtimestamp(day_timestamp).strftime('%Y-%m-%d')}"]
                    tooltip_lines.append(f"Total Purchased: €{total_amount:.2f}")
                    tooltip_lines.append(f"Transactions: {len(day_purchases)}")
                    tooltip_lines.append("---")
                    
                    for p in day_purchases:
                        purchase = p['purchase']
                        order_id = purchase.get('orderId', 'N/A')
                        crypto = purchase.get('cryptoCurrency', 'N/A')
                        amount = p['amount_eur']
                        tooltip_lines.append(f"#{order_id}: €{amount:.2f} → {crypto} (BUY)")
                    
                    tooltip_text = "\n".join(tooltip_lines)
                    
                    # Create custom bar with tooltip - more prominent styling
                    bar_item = pg.BarGraphItem(
                        x=[day_timestamp], 
                        height=[total_amount],
                        width=86400,  # 1 day width in seconds
                        brush=pg.mkBrush(color=(34, 139, 34), alpha=0.8),  # Forest Green with high opacity
                        pen=pg.mkPen(color=(34, 139, 34), width=2)  # Green border for definition
                    )
                    
                    # Store data for click handling
                    bar_data = {
                        'type': 'BUY',
                        'timestamp': day_timestamp,
                        'purchases': day_purchases,
                        'tooltip': tooltip_text,
                        'bar_item': bar_item
                    }
                    self.transaction_bars_data.append(bar_data)
                    
                    # Set tooltip
                    bar_item.setToolTip(tooltip_text)
                    self.plot_widget.addItem(bar_item)
                
                # Add legend entry for purchases
                if buy_by_date:
                    dummy_buy = pg.BarGraphItem(x=[0], height=[0], width=0, 
                                               brush=pg.mkBrush(color='g', alpha=0.6), name='Purchases')
                    self.plot_widget.addItem(dummy_buy)
            
            if sell_transactions:
                # Similar grouping for sell transactions
                from collections import defaultdict
                sell_by_date = defaultdict(list)
                
                for purchase in purchases_sorted:
                    timestamp = purchase.get('createTime', 0)
                    if timestamp == 0:
                        continue
                    
                    # Check if it's a SELL transaction - use transactionType directly from JSON
                    trans_type = purchase.get('transactionType', '0')
                    
                    if trans_type == '1':  # SELL
                        timestamp_sec = timestamp / 1000
                        # Amount is already in EUR after normalization
                        fiat_eur = purchase.get('amountFiat', 0)
                        
                        day_timestamp = int(timestamp_sec // 86400) * 86400
                        sell_by_date[day_timestamp].append({
                            'purchase': purchase,
                            'amount_eur': fiat_eur,
                            'timestamp_sec': timestamp_sec
                        })
                
                # Create bars for sell transactions (negative)
                for day_timestamp, day_purchases in sell_by_date.items():
                    total_amount = sum(p['amount_eur'] for p in day_purchases)
                    
                    tooltip_lines = [f"SALES - Date: {datetime.fromtimestamp(day_timestamp).strftime('%Y-%m-%d')}"]
                    tooltip_lines.append(f"Total Sold: €{total_amount:.2f}")
                    tooltip_lines.append(f"Transactions: {len(day_purchases)}")
                    tooltip_lines.append("---")
                    
                    for p in day_purchases:
                        purchase = p['purchase']
                        order_id = purchase.get('orderId', 'N/A')
                        crypto = purchase.get('cryptoCurrency', 'N/A')
                        amount = p['amount_eur']
                        tooltip_lines.append(f"#{order_id}: €{amount:.2f} ← {crypto} (SELL)")
                    
                    tooltip_text = "\n".join(tooltip_lines)
                    
                    bar_item = pg.BarGraphItem(
                        x=[day_timestamp], 
                        height=[-total_amount],  # Negative for sells
                        width=86400,
                        brush=pg.mkBrush(color='r', alpha=0.6)
                    )
                    
                    bar_data = {
                        'type': 'SELL',
                        'timestamp': day_timestamp,
                        'purchases': day_purchases,
                        'tooltip': tooltip_text,
                        'bar_item': bar_item
                    }
                    self.transaction_bars_data.append(bar_data)
                    
                    bar_item.setToolTip(tooltip_text)
                    self.plot_widget.addItem(bar_item)
                
                # Add legend entry for sales
                if sell_by_date:
                    dummy_sell = pg.BarGraphItem(x=[0], height=[0], width=0, 
                                               brush=pg.mkBrush(color='r', alpha=0.6), name='Sales')
                    self.plot_widget.addItem(dummy_sell)
            
            # Get current portfolio value for comparison line
            balances = self.data_manager.get_spot_balances()
            prices = self.data_manager.get_prices()
            
            if balances and prices:
                from core.currency import build_eur_price_map, calculate_portfolio_eur_value
                eur_price_map = build_eur_price_map(prices)
                total_balances = {asset: info['free'] + info['locked'] for asset, info in balances.items()}
                current_value = calculate_portfolio_eur_value(total_balances, eur_price_map)
                
                # Add horizontal line for current portfolio value
                if current_value > 0 and timestamps:
                    current_line = [current_value] * len(timestamps)
                    self.plot_widget.plot(
                        timestamps, current_line,
                        pen=pg.mkPen(color='orange', width=2, style=pg.QtCore.Qt.DashLine),
                        name=f'Current Value (€{current_value:.0f})'
                    )
            
            # Configure X-axis to show months for better granularity
            class MonthAxisItem(pg.AxisItem):
                def __init__(self, orientation='bottom', **kwargs):
                    super().__init__(orientation=orientation, **kwargs)
                
                def tickStrings(self, values, scale, spacing):
                    """Return tick strings formatted as months."""
                    strings = []
                    for v in values:
                        try:
                            # Convert timestamp to datetime and format as month/year
                            dt = datetime.fromtimestamp(v)
                            # Use short month names for better readability
                            strings.append(dt.strftime('%b %Y'))  # e.g., "Jan 2023"
                        except (ValueError, OSError):
                            strings.append('')
                    return strings
                
                def tickSpacing(self, minVal, maxVal, size):
                    """Calculate tick spacing to show monthly intervals."""
                    try:
                        # Calculate the range in months
                        min_dt = datetime.fromtimestamp(minVal)
                        max_dt = datetime.fromtimestamp(maxVal)
                        
                        # Calculate months difference
                        month_diff = (max_dt.year - min_dt.year) * 12 + (max_dt.month - min_dt.month)
                        
                        # Determine appropriate spacing based on range
                        if month_diff <= 12:  # Less than 1 year
                            # Show every month, minor ticks every 2 weeks
                            major_spacing = 30.44 * 24 * 3600  # ~1 month in seconds
                            minor_spacing = 14 * 24 * 3600      # 2 weeks
                        elif month_diff <= 24:  # 1-2 years
                            # Show every 2 months, minor ticks monthly
                            major_spacing = 60.88 * 24 * 3600  # ~2 months
                            minor_spacing = 30.44 * 24 * 3600  # ~1 month
                        elif month_diff <= 60:  # 2-5 years
                            # Show every 3 months (quarterly), minor ticks every 6 weeks
                            major_spacing = 91.31 * 24 * 3600  # ~3 months
                            minor_spacing = 45.66 * 24 * 3600  # ~1.5 months
                        else:  # More than 5 years
                            # Show every 6 months, minor ticks quarterly
                            major_spacing = 182.62 * 24 * 3600  # ~6 months
                            minor_spacing = 91.31 * 24 * 3600   # ~3 months
                        
                        return [(major_spacing, 0), (minor_spacing, 0)]
                    except (ValueError, OSError):
                        # Fallback to default spacing
                        return super().tickSpacing(minVal, maxVal, size)
            
            # Apply custom month-based axis
            month_axis = MonthAxisItem(orientation='bottom')
            self.plot_widget.setAxisItems({'bottom': month_axis})
            
            # Set FIXED X-axis range from 2017 to 2025 (no zoom changes)
            start_timestamp = datetime(2017, 1, 1).timestamp()
            end_timestamp = datetime(2025, 12, 31).timestamp()
            
            # Force fixed range that doesn't change with zoom
            self.plot_widget.setXRange(start_timestamp, end_timestamp, padding=0)
            self.plot_widget.getViewBox().setLimits(xMin=start_timestamp, xMax=end_timestamp)
            
            # Set SMART Y-axis range - Industry standard for investment charts
            if cumulative_net_eur:
                data_min = min(min(cumulative_net_eur), 0)  # Include 0 or lowest value
                data_max = max(cumulative_net_eur)
                
                # Industry standard: Use data range but ensure reasonable context
                data_range = data_max - data_min
                
                if data_range < 1000:  # Small investments (< 1k EUR)
                    # Show tight range but with context
                    padding = max(data_range * 0.3, 50)  # 30% padding or 50 EUR min
                    y_min = max(0, data_min - padding)
                    y_max = data_max + padding
                    
                elif data_range < 5000:  # Medium investments (1k-5k EUR)
                    # Balanced approach
                    padding = max(data_range * 0.25, 200)  # 25% padding or 200 EUR min
                    y_min = max(0, data_min - padding)
                    y_max = data_max + padding
                    
                else:  # Large investments (5k+ EUR)
                    # More context for large amounts
                    padding = data_range * 0.2  # 20% padding
                    y_min = max(0, data_min - padding)
                    y_max = data_max + padding
                    
                # Ensure minimum useful range
                if (y_max - y_min) < 100:
                    y_max = y_min + 100
                    
            else:
                y_min = 0
                y_max = 1000  # Default range if no data
            
            # Set smart Y range - allow negative values for sell bars
            # Adjust y_min to accommodate negative sell bars
            if sell_transactions:
                # Calculate the maximum sell amount for proper scaling
                max_sell_amount = max(amount for _, amount in sell_transactions) if sell_transactions else 0
                # Ensure we show negative bars by extending y_min
                y_min = min(y_min, -max_sell_amount - (max_sell_amount * 0.1))  # 10% padding below
            
            self.plot_widget.setYRange(y_min, y_max, padding=0.02)
            # Remove hard Y limits to allow both positive and negative values
            self.plot_widget.getViewBox().setLimits(yMin=None, yMax=None)
            
            # Set chart title with net investment
            final_net_invested = cumulative_net_eur[-1] if cumulative_net_eur else 0
            buy_total = sum(amount for _, amount in buy_transactions)
            sell_total = sum(amount for _, amount in sell_transactions)
            
            title = f"Investment Timeline - Bought: €{buy_total:.0f}"
            if sell_total > 0:
                title += f", Sold: €{sell_total:.0f}"
            title += f", Net: €{final_net_invested:.0f}"
            
            self.plot_widget.setTitle(title)
            
        except Exception as e:
            print(f"Error updating chart: {e}")
            import traceback
            traceback.print_exc()
            self.plot_widget.setTitle(f"Chart error: {str(e)}")
    
    def clear_all_data(self):
        """Clear all data from the database with confirmation dialog."""
        # Show confirmation dialog
        reply = QMessageBox.question(
            self,
            "Clear All Data - Are You Sure?",
            "⚠️ WARNING: This will permanently delete ALL data from the database:\n\n"
            "• All purchase records\n"
            "• Current portfolio balances\n"
            "• Price history\n"
            "• All cached metadata\n\n"
            "This action cannot be undone!\n\n"
            "Are you sure you want to continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No  # Default to No for safety
        )
        
        if reply == QMessageBox.Yes:
            try:
                # Clear all data
                deleted_counts = self.data_manager.clear_all_data()
                
                # Log the operation
                total_deleted = sum(deleted_counts.values())
                self.log_message(f"Cleared all data: {deleted_counts}", "WARNING")
                
                # Show success message
                message = (
                    f"Successfully cleared all data:\n"
                    f"• Purchases: {deleted_counts['purchases']}\n"
                    f"• Balances: {deleted_counts['balances']}\n"
                    f"• Prices: {deleted_counts['prices']}\n\n"
                    f"Total records deleted: {total_deleted}"
                )
                
                QMessageBox.information(self, "Data Cleared", message)
                self.statusBar().showMessage(f"All data cleared - {total_deleted} records deleted", 10000)
                
                # Refresh the UI to show empty state
                self.load_data()
                
            except Exception as e:
                error_msg = f"Failed to clear data: {str(e)}"
                self.log_message(error_msg, "ERROR")
                QMessageBox.critical(self, "Clear Data Error", error_msg)
        else:
            self.log_message("Clear data operation cancelled by user", "INFO")
    
    def export_data(self, format_type: str):
        """Export data to file."""
        try:
            config = get_config()
            exports_dir = config.exports_dir
            
            if format_type == "json":
                file_path = exports_dir / f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                
                export_data = {
                    "exported_at": datetime.now().isoformat(),
                    "purchases": self.data_manager.get_purchases(),
                    "balances": self.data_manager.get_spot_balances(),
                    "prices": self.data_manager.get_prices(),
                    "statistics": self.data_manager.get_purchase_statistics()
                }
                
                # Check if we have any data to export
                total_items = (
                    len(export_data["purchases"]) + 
                    len(export_data["balances"]) + 
                    len(export_data["prices"])
                )
                
                if total_items == 0:
                    QMessageBox.information(
                        self,
                        "No Data to Export",
                        "No data available to export.\n\n"
                        "Please fetch your fiat orders and portfolio data first."
                    )
                    return
                
                with open(file_path, 'w') as f:
                    json.dump(export_data, f, indent=2)
                
                self.log_message(f"Exported complete dataset to {file_path.name}", "SUCCESS")
                
                success_msg = f"Successfully exported complete dataset to {file_path.name}"
                self.statusBar().showMessage(success_msg, 5000)
                
                # Show success dialog matching CSV export style
                QMessageBox.information(
                    self,
                    "JSON Export Complete",
                    f"Successfully exported complete dataset to:\n\n"
                    f"📄 {file_path.name}\n\n"
                    f"📁 Location: {exports_dir}\n\n"
                    f"📊 Data included:\n"
                    f"• {len(export_data['purchases'])} transactions\n"
                    f"• {len(export_data['balances'])} portfolio balances\n"
                    f"• {len(export_data['prices'])} current prices\n"
                    f"• Summary statistics\n\n"
                    f"The JSON file contains all your data and can be imported into other applications."
                )
            
            elif format_type == "csv":
                # Implement comprehensive CSV export
                self._export_csv_data(exports_dir)
        
        except Exception as e:
            QMessageBox.warning(self, "Export Error", f"Failed to export data: {str(e)}")
    
    
    def closeEvent(self, event):
        """Handle application close."""
        if self.fetch_worker and self.fetch_worker.isRunning():
            reply = QMessageBox.question(
                self, 
                "Fetch in Progress",
                "A fetch operation is running. Do you want to quit anyway?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.No:
                event.ignore()
                return
            
            self.fetch_worker.terminate()
            self.fetch_worker.wait(3000)  # Wait up to 3 seconds
        
        event.accept()
    
    def on_chart_clicked(self, event):
        """Handle mouse clicks on chart bars to highlight corresponding table rows."""
        try:
            # Get the click position
            pos = event.scenePos()
            view_pos = self.plot_widget.plotItem.vb.mapSceneToView(pos)
            click_timestamp = view_pos.x()
            click_value = view_pos.y()
            
            # Find the closest bar
            clicked_bar_data = None
            min_distance = float('inf')
            
            if hasattr(self, 'transaction_bars_data'):
                for bar_data in self.transaction_bars_data:
                    bar_timestamp = bar_data['timestamp']
                    # Check if click is within the bar's time range (1 day width)
                    time_distance = abs(click_timestamp - bar_timestamp)
                    
                    if time_distance < 43200:  # Half day tolerance
                        # Check if click is within reasonable value range for this bar
                        bar_purchases = bar_data['purchases']
                        total_amount = sum(p['amount_eur'] for p in bar_purchases)
                        
                        # For SELL transactions, the bar height is negative
                        expected_value = total_amount if bar_data['type'] == 'BUY' else -total_amount
                        value_distance = abs(click_value - expected_value / 2)  # Check against bar center
                        
                        if value_distance < abs(expected_value) / 2:  # Within bar height
                            combined_distance = time_distance + value_distance * 0.1  # Weight time more
                            if combined_distance < min_distance:
                                min_distance = combined_distance
                                clicked_bar_data = bar_data
            
            if clicked_bar_data:
                # Highlight transactions in the table
                self.highlight_transactions_in_table(clicked_bar_data['purchases'])
                
                # Show details in logs
                total_amount = sum(p['amount_eur'] for p in clicked_bar_data['purchases'])
                date_str = datetime.fromtimestamp(clicked_bar_data['timestamp']).strftime('%Y-%m-%d')
                transaction_type = clicked_bar_data['type']
                count = len(clicked_bar_data['purchases'])
                
                self.log_message(
                    f"Clicked {transaction_type} bar: {date_str} - €{total_amount:.2f} ({count} transactions)",
                    "INFO"
                )
                
                # Switch to purchases tab to show highlighted rows
                self.tab_widget.setCurrentIndex(0)  # Purchases tab is index 0
        
        except Exception as e:
            print(f"Error handling chart click: {e}")
    
    def highlight_transactions_in_table(self, selected_purchases):
        """Highlight specific transactions in the purchases table."""
        try:
            # Extract order IDs from selected purchases
            selected_order_ids = set()
            for purchase_data in selected_purchases:
                purchase = purchase_data['purchase']
                order_id = str(purchase.get('orderId', ''))
                if order_id:
                    selected_order_ids.add(order_id)
            
            # Clear existing selection
            self.purchases_table.clearSelection()
            
            # Find and select matching rows
            highlighted_count = 0
            for row in range(self.purchases_table.rowCount()):
                # Order ID is in column 2
                order_id_item = self.purchases_table.item(row, 2)
                if order_id_item:
                    order_id = order_id_item.text()
                    if order_id in selected_order_ids:
                        # Select the entire row
                        self.purchases_table.selectRow(row)
                        highlighted_count += 1
            
            if highlighted_count > 0:
                # Scroll to first selected row
                selected_ranges = self.purchases_table.selectionModel().selectedRows()
                if selected_ranges:
                    first_row = selected_ranges[0].row()
                    self.purchases_table.scrollToItem(
                        self.purchases_table.item(first_row, 0), 
                        self.purchases_table.PositionAtCenter
                    )
                
                self.statusBar().showMessage(
                    f"Highlighted {highlighted_count} transactions in table", 
                    3000
                )
            
        except Exception as e:
            print(f"Error highlighting table rows: {e}")
    
    def _export_csv_data(self, exports_dir: Path):
        """Export purchases data to a single CSV file matching the Purchases table."""
        import csv
        
        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        try:
            purchases_file = exports_dir / f"purchases_{timestamp_str}.csv"
            purchases = self.data_manager.get_purchases()
            
            if not purchases:
                QMessageBox.information(
                    self,
                    "No Data to Export",
                    "No purchase data available to export.\n\n"
                    "Please fetch your fiat orders first using the 'Fetch Fiat Orders' button."
                )
                return
            
            with open(purchases_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # CSV headers matching the Purchases table
                writer.writerow([
                    'Date', 'Type', 'Order ID', 'Fiat Currency', 'Fiat Amount', 
                    'Crypto', 'Crypto Amount', 'Price', 'Fee'
                ])
                
                for purchase in purchases:
                    # Format timestamp
                    timestamp = purchase.get('createTime', 0)
                    if timestamp:
                        date_str = datetime.fromtimestamp(timestamp / 1000).strftime('%Y-%m-%d %H:%M')
                    else:
                        date_str = ''
                    
                    # Transaction type
                    trans_type = purchase.get('transactionType', '0')
                    trans_type_display = 'BUY' if trans_type == '0' else 'SELL'
                    
                    writer.writerow([
                        date_str,
                        trans_type_display,
                        purchase.get('orderId', ''),
                        purchase.get('fiatCurrency', ''),
                        f"{purchase.get('amountFiat', 0):.2f}",
                        purchase.get('cryptoCurrency', ''),
                        f"{purchase.get('amountCrypto', 0):.6f}",
                        f"{purchase.get('price', 0):.6f}",
                        f"{purchase.get('fee', 0):.2f}"
                    ])
            
            self.log_message(f"Exported {len(purchases)} purchases to {purchases_file.name}", "SUCCESS")
            
            success_msg = f"Successfully exported {len(purchases)} transactions to {purchases_file.name}"
            self.statusBar().showMessage(success_msg, 5000)
            
            # Show simple completion dialog
            QMessageBox.information(
                self,
                "CSV Export Complete",
                f"Successfully exported {len(purchases)} transactions to:\n\n"
                f"📄 {purchases_file.name}\n\n"
                f"📁 Location: {exports_dir}\n\n"
                f"The CSV file can be opened in Excel, Google Sheets, or any spreadsheet application."
            )
        
        except Exception as e:
            error_msg = f"CSV export failed: {str(e)}"
            self.log_message(error_msg, "ERROR")
            QMessageBox.critical(self, "CSV Export Error", error_msg)
    
    def center_window(self):
        """Center the window on the primary screen."""
        from PySide6.QtGui import QGuiApplication
        
        # Get the primary screen
        screen = QGuiApplication.primaryScreen()
        if screen:
            screen_geometry = screen.availableGeometry()
            window_geometry = self.frameGeometry()
            
            # Calculate center position
            center_x = (screen_geometry.width() - window_geometry.width()) // 2
            center_y = (screen_geometry.height() - window_geometry.height()) // 2
            
            # Move window to center
            self.move(screen_geometry.x() + center_x, screen_geometry.y() + center_y)
