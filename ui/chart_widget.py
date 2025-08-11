"""Chart widget for displaying investment data."""
from typing import List, Dict, Any
from datetime import datetime
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


class ChartWidget(QWidget):
    """Simple chart widget for displaying purchase/investment data."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.plot_widget = None
        self.title_label = None
        self.purchase_data = {}  # Store purchase data by timestamp for tooltips
        self.main_window = parent  # Reference to main window for table highlighting
        self._init_ui()
    
    def _init_ui(self):
        """Initialize the user interface."""
        try:
            import pyqtgraph as pg
            
            # Create main container frame matching other sections
            from PySide6.QtWidgets import QFrame, QSizePolicy
            chart_container = QFrame()
            chart_container.setFrameStyle(QFrame.StyledPanel)
            chart_container.setLineWidth(1)
            chart_container.setStyleSheet("""
                QFrame {
                    background-color: palette(base);
                    border: 1px solid palette(mid);
                    border-radius: 4px;
                    margin: 2px;
                }
            """)
            
            # Set main widget layout with container - optimized for smaller screens
            main_layout = QVBoxLayout(self)
            main_layout.setContentsMargins(2, 2, 2, 2)  # Minimal margins to prevent cutoff
            main_layout.setSpacing(0)
            main_layout.addWidget(chart_container)
            
            # Container layout with minimal margins for maximum chart space
            container_layout = QVBoxLayout(chart_container)
            container_layout.setContentsMargins(2, 2, 2, 2)  # Minimal margins for laptop screens
            container_layout.setSpacing(2)
            
            # Chart title
            self.title_label = QLabel("📈 Investment Timeline")
            title_font = QFont()
            title_font.setPointSize(12)
            title_font.setBold(True)
            self.title_label.setFont(title_font)
            self.title_label.setAlignment(Qt.AlignCenter)
            container_layout.addWidget(self.title_label)
            
            # Create plot widget with time axis
            self.plot_widget = pg.PlotWidget()
            self.plot_widget.setLabel('left', 'Amount (EUR)', color='black', size='10pt')
            self.plot_widget.setLabel('bottom', 'Time', color='black', size='10pt')
            self.plot_widget.showGrid(x=True, y=True, alpha=0.5)  # 50% opacity grid
            
            # Optimize sizing for maximum chart visibility on laptop screens
            self.plot_widget.setMinimumHeight(280)  # Further reduced for compactness
            self.plot_widget.setMinimumWidth(380)   # Slightly smaller minimum width
            
            # Set aggressive expanding size policy for maximum space usage
            self.plot_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            chart_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            
            # Enable size hinting for better layout adaptation
            self.plot_widget.setMaximumHeight(16777215)  # Remove height restrictions
            chart_container.setMaximumHeight(16777215)
            
            # Configure the plot item to ensure axes have enough space but adapt to screen size
            plot_item = self.plot_widget.getPlotItem()
            
            # Set axis sizes optimized for laptop screens with proper spacing
            try:
                # Reduce axis sizes further for better space utilization
                plot_item.getAxis('bottom').setHeight(45)  # Compact bottom axis
                plot_item.getAxis('left').setWidth(60)     # Compact left axis
                plot_item.getAxis('bottom').setPen('black')  # Ensure axis is visible
                plot_item.getAxis('left').setPen('black')   # Ensure axis is visible
                
                # Set tight margins to maximize chart area
                plot_item.setContentsMargins(5, 5, 5, 5)
                
                # Configure axis label styles for better readability in compact space
                plot_item.getAxis('left').setStyle(tickTextOffset=3)  # Reduce tick offset
                plot_item.getAxis('bottom').setStyle(tickTextOffset=3)
            except Exception as e:
                print(f"Warning: Could not configure axis sizes: {e}")
            
            # Add plot widget directly to container
            container_layout.addWidget(self.plot_widget)
            
            # Enable mouse interaction - disable Y-axis panning to keep 0 at bottom
            self.plot_widget.setMouseEnabled(x=True, y=True)
            self.plot_widget.enableAutoRange(axis='xy', enable=True)
            
            # Configure time axis
            time_axis = pg.DateAxisItem(orientation='bottom')
            self.plot_widget.setAxisItems({'bottom': time_axis})
            
            # Connect to view range change to enforce Y-axis minimum at 0
            view_box = self.plot_widget.getViewBox()
            view_box.sigRangeChanged.connect(self._on_view_range_changed)
            
            # Set default chart options: Auto X/Y axis and Visible Data Only
            self._set_default_chart_options()
            
        except ImportError:
            # Fallback if pyqtgraph is not available
            layout = QVBoxLayout(self)
            label = QLabel("Chart library (PyQtGraph) not available")
            label.setAlignment(Qt.AlignCenter)
            layout.addWidget(label)
    
    def clear_chart(self):
        """Clear all data from the chart."""
        if self.plot_widget:
            self.plot_widget.clear()
    
    def set_chart_title(self, title: str):
        """Set the chart title."""
        if self.title_label:
            self.title_label.setText(title)
    
    def _set_default_chart_options(self):
        """Set default chart options: Auto X/Y axis and Visible Data Only with built-in grid."""
        if not self.plot_widget:
            return
        
        try:
            # Get the view box and plot item
            view_box = self.plot_widget.getViewBox()
            plot_item = self.plot_widget.getPlotItem()
            
            # Enable Auto X and Y axis scaling
            view_box.enableAutoRange(x=True, y=True)
            
            # Enable "Visible Data Only" - auto-scale to visible data only
            view_box.setAutoVisible(x=True, y=True)
            
            # Ensure mouse interactions are enabled
            view_box.setMouseEnabled(x=True, y=True)
            
            # Use built-in grid functionality with clean styling
            plot_item.showGrid(x=True, y=True, alpha=0.3)  # Light grid for better readability
            
            # Verify that options are correctly set
            auto_x_enabled = view_box.autoRangeEnabled()[0]
            auto_y_enabled = view_box.autoRangeEnabled()[1]
            visible_data_x = view_box.autoVisibleOnly[0] if hasattr(view_box, 'autoVisibleOnly') else True
            visible_data_y = view_box.autoVisibleOnly[1] if hasattr(view_box, 'autoVisibleOnly') else True
            
            print(f"Chart options: Auto X: {auto_x_enabled}, Auto Y: {auto_y_enabled}, Grid: enabled")
            
        except Exception as e:
            print(f"Error setting chart options: {e}")
    
    def _on_view_range_changed(self, view, ranges):
        """Allow Y-axis to show both positive and negative values for buy/sell bars."""
        try:
            # No longer enforce Y-axis minimum at 0 to allow sell bars (negative values) to be visible
            # This method can be used for other range validations if needed in the future
            pass
                
        except Exception as e:
            print(f"Error in view range change handler: {e}")
    
    def update_chart_data(self, purchases: List[Dict[str, Any]]):
        """Update chart with purchase data, Net P/L line, and purchase bars."""
        if not self.plot_widget:
            return
        
        try:
            import pyqtgraph as pg
            from collections import defaultdict
            
            self.clear_chart()
            
            if not purchases:
                self.set_chart_title("📈 Investment Timeline - No Data")
                return
            
            # Sort purchases by timestamp
            purchases_sorted = sorted(purchases, key=lambda x: x.get('createTime', 0))
            
            # Prepare data for plotting
            investment_timestamps = []
            investment_amounts = []
            portfolio_timestamps = []
            portfolio_values = []
            purchase_bars_x = []
            purchase_bars_y = []
            
            buy_total = 0.0
            sell_total = 0.0
            net_investment = 0.0
            current_portfolio_value = 0.0
            sell_bars_x = []
            sell_bars_y = []
            
            # Get current portfolio value if available
            try:
                from core.config import get_config
                from core.json_data_manager import JSONDataManager
                from core.currency import build_eur_price_map, calculate_portfolio_eur_value
                
                config = get_config()
                data_manager = JSONDataManager(config)
                
                # Get current balances and calculate portfolio value
                balances = data_manager.load_balances()
                if balances:
                    price_map = build_eur_price_map(balances, config)
                    current_portfolio_value = calculate_portfolio_eur_value(balances, price_map)
            except Exception:
                # If we can't get portfolio value, use investment total as fallback
                pass
            
            # Process ALL transactions (both BUY and SELL)
            for purchase in purchases_sorted:
                timestamp = purchase.get('createTime', 0)
                if timestamp == 0:
                    continue
                
                trans_type = purchase.get('transactionType', '0')
                fiat_eur = purchase.get('amountFiat', 0)
                timestamp_sec = timestamp / 1000
                
                if trans_type == '0':  # BUY transaction
                    buy_total += fiat_eur
                    net_investment += fiat_eur
                    investment_timestamps.append(timestamp_sec)
                    investment_amounts.append(net_investment)  # Use net investment instead of buy_total
                    
                    # Add purchase bar data
                    purchase_bars_x.append(timestamp_sec)
                    purchase_bars_y.append(fiat_eur)
                    
                elif trans_type == '1':  # SELL transaction
                    sell_total += fiat_eur
                    net_investment -= fiat_eur  # Subtract sells from net investment
                    investment_timestamps.append(timestamp_sec)
                    investment_amounts.append(net_investment)  # Update net investment line
                    
                    # Add sell bar data (negative for visual distinction)
                    sell_bars_x.append(timestamp_sec)
                    sell_bars_y.append(fiat_eur)
            
            # Create portfolio value line (simplified - assuming current value for recent purchases)
            if investment_timestamps and current_portfolio_value > 0:
                # Create a simple portfolio value line that ends at current value
                portfolio_timestamps = investment_timestamps.copy()
                # Linear interpolation from final investment to current portfolio value
                final_investment = investment_amounts[-1] if investment_amounts else 0
                for i, inv_amount in enumerate(investment_amounts):
                    # Simple approximation: scale current portfolio value by investment ratio
                    ratio = inv_amount / final_investment if final_investment > 0 else 0
                    portfolio_values.append(ratio * current_portfolio_value)
            
            # Plot 1: Portfolio value line over time (BLUE)
            if portfolio_timestamps and portfolio_values:
                self.plot_widget.plot(
                    portfolio_timestamps, portfolio_values,
                    pen=pg.mkPen(color='#2E86AB', width=3),
                    name='💼 Portfolio Value'
                )
            
            # Plot 2: Net investment line (cumulative fiat invested minus sold) - lighter blue for reference
            if investment_timestamps and investment_amounts:
                self.plot_widget.plot(
                    investment_timestamps, investment_amounts,
                    pen=pg.mkPen(color='#87CEEB', width=2, style=pg.QtCore.Qt.DashLine),
                    name='📊 Net Investment'
                )
            
            # Plot 2b: NET P/L line (Portfolio Value - Net Investment) - GREEN/RED based on profit/loss
            if portfolio_timestamps and portfolio_values and investment_timestamps and investment_amounts:
                # Calculate P/L for each timestamp
                pl_timestamps = []
                pl_values = []
                
                # Align timestamps and calculate P/L
                for i, timestamp in enumerate(portfolio_timestamps):
                    if i < len(investment_amounts):
                        portfolio_value = portfolio_values[i]
                        net_investment = investment_amounts[i]
                        pl_value = portfolio_value - net_investment
                        
                        pl_timestamps.append(timestamp)
                        pl_values.append(pl_value)
                
                if pl_timestamps and pl_values:
                    # Determine line color based on final P/L
                    final_pl = pl_values[-1] if pl_values else 0
                    pl_color = '#27AE60' if final_pl >= 0 else '#E74C3C'  # Green for profit, Red for loss
                    pl_style = pg.QtCore.Qt.SolidLine if final_pl >= 0 else pg.QtCore.Qt.DashLine
                    
                    self.plot_widget.plot(
                        pl_timestamps, pl_values,
                        pen=pg.mkPen(color=pl_color, width=2, style=pl_style),
                        name=f'💰 Net P/L (€{final_pl:.0f})'
                    )
            
            # Plot 3: Current wallet amount (YELLOW horizontal line)
            if current_portfolio_value > 0:
                current_line = pg.InfiniteLine(
                    pos=current_portfolio_value, 
                    angle=0,  # Horizontal line
                    pen=pg.mkPen(color='#F1C40F', width=4, style=pg.QtCore.Qt.SolidLine),
                    label='Current Wallet: €{:.0f}'.format(current_portfolio_value),
                    labelOpts={'position': 0.1, 'color': '#F1C40F', 'fill': '#F1C40F'}
                )
                self.plot_widget.addItem(current_line)
            
            # Plot 3b: Add prominent horizontal zero line (CRITICAL for buy/sell separation)
            zero_line = pg.InfiniteLine(
                pos=0,  # At Y = 0 EUR
                angle=0,  # Horizontal line
                pen=pg.mkPen(color='#2C3E50', width=2, style=pg.QtCore.Qt.SolidLine),  # Dark blue-gray, thick line
                label='€0 (Buy/Sell Separator)',
                labelOpts={'position': 0.95, 'color': '#2C3E50', 'fill': (44, 62, 80, 100)}
            )
            self.plot_widget.addItem(zero_line)
            
            # Plot 4: Interactive Buy bars (GREEN) and Sell bars (RED)
            # Group transactions by day for both BUY and SELL
            daily_transactions = defaultdict(lambda: {'buys': [], 'sells': []})
            self.purchase_data = {}  # Clear previous data
            
            # Process BUY transactions
            buy_index = 0
            for i, purchase in enumerate(purchases_sorted):
                if purchase.get('transactionType') == '0':  # BUY
                    if buy_index < len(purchase_bars_x):
                        timestamp = purchase_bars_x[buy_index]
                        amount = purchase_bars_y[buy_index]
                        day_key = int(timestamp // 86400) * 86400  # Round to day
                        
                        buy_info = {
                            'amount': amount,
                            'timestamp': timestamp,
                            'original_purchase': purchase,
                            'date': datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M'),
                            'type': 'BUY'
                        }
                        daily_transactions[day_key]['buys'].append(buy_info)
                        buy_index += 1
            
            # Process SELL transactions  
            sell_index = 0
            for i, purchase in enumerate(purchases_sorted):
                if purchase.get('transactionType') == '1':  # SELL
                    if sell_index < len(sell_bars_x):
                        timestamp = sell_bars_x[sell_index]
                        amount = sell_bars_y[sell_index]
                        day_key = int(timestamp // 86400) * 86400  # Round to day
                        
                        sell_info = {
                            'amount': amount,
                            'timestamp': timestamp,
                            'original_purchase': purchase,
                            'date': datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M'),
                            'type': 'SELL'
                        }
                        daily_transactions[day_key]['sells'].append(sell_info)
                        sell_index += 1
            
            # Store transaction data and create bars
            if daily_transactions:
                # Store transaction data for each day (combining buys and sells)
                for day_timestamp, day_data in daily_transactions.items():
                    all_transactions = day_data['buys'] + day_data['sells']
                    buy_total = sum(t['amount'] for t in day_data['buys'])
                    sell_total = sum(t['amount'] for t in day_data['sells'])
                    
                    self.purchase_data[day_timestamp] = {
                        'buy_total': buy_total,
                        'sell_total': sell_total, 
                        'net_total': buy_total - sell_total,
                        'transactions': all_transactions,
                        'count': len(all_transactions),
                        'buy_count': len(day_data['buys']),
                        'sell_count': len(day_data['sells'])
                    }
                
                # Create clickable bar class
                class ClickableBarGraphItem(pg.BarGraphItem):
                    def __init__(self, *args, **kwargs):
                        self.chart_widget = kwargs.pop('chart_widget', None)
                        self.day_timestamp = kwargs.pop('day_timestamp', None)
                        super().__init__(*args, **kwargs)
                    
                    def mouseClickEvent(self, ev):
                        if ev.button() == pg.QtCore.Qt.LeftButton and self.chart_widget and self.day_timestamp:
                            print(f"Bar clicked for day: {datetime.fromtimestamp(self.day_timestamp).strftime('%Y-%m-%d')}")
                            self.chart_widget._on_transaction_clicked(self.day_timestamp)
                        
                        # Call parent class method if it exists
                        if hasattr(pg.BarGraphItem, 'mouseClickEvent'):
                            pg.BarGraphItem.mouseClickEvent(self, ev)
                
                # Create bars for each day with transactions
                for day_timestamp, day_data in daily_transactions.items():
                    # Create BUY bars (GREEN, above zero)
                    if day_data['buys']:
                        buy_total = sum(t['amount'] for t in day_data['buys'])
                        buy_bar = ClickableBarGraphItem(
                            x=[day_timestamp], 
                            height=[buy_total], 
                            width=86400,  # 24 hours width
                            brush=pg.mkBrush(color=(46, 204, 113, 220)),  # Green for buys
                            pen=pg.mkPen(color='#27AE60', width=2),
                            chart_widget=self,
                            day_timestamp=day_timestamp
                        )
                        
                        # Create tooltip for buy bar
                        buy_tooltip_lines = [
                            f"📅 {datetime.fromtimestamp(day_timestamp).strftime('%Y-%m-%d')}",
                            f"💰 Total: €{buy_total:.2f}",
                            f"📊 {len(day_data['buys'])} purchase(s)",
                            "",
                            "🔼 PURCHASES:"
                        ]
                        
                        for transaction in day_data['buys']:
                            crypto = transaction['original_purchase'].get('cryptoCurrency', 'Unknown')
                            amount = transaction['amount']
                            time_str = transaction['date'].split(' ')[1] if ' ' in transaction['date'] else transaction['date']
                            buy_tooltip_lines.append(f"  • {time_str}: {crypto} - €{amount:.2f} (BUY)")
                        
                        buy_bar.setToolTip("\n".join(buy_tooltip_lines))
                        self.plot_widget.addItem(buy_bar)
                    
                    # Create SELL bars (RED, below zero)
                    if day_data['sells']:
                        sell_total = sum(t['amount'] for t in day_data['sells'])
                        sell_bar = ClickableBarGraphItem(
                            x=[day_timestamp], 
                            height=[-sell_total],  # Negative height for below-zero bars
                            width=86400,  # 24 hours width
                            brush=pg.mkBrush(color=(231, 76, 60, 220)),  # Red for sells
                            pen=pg.mkPen(color='#C0392B', width=2),
                            chart_widget=self,
                            day_timestamp=day_timestamp
                        )
                        
                        # Create tooltip for sell bar
                        sell_tooltip_lines = [
                            f"📅 {datetime.fromtimestamp(day_timestamp).strftime('%Y-%m-%d')}",
                            f"💰 Total Sold: €{sell_total:.2f}",
                            f"📊 {len(day_data['sells'])} sale(s)",
                            "",
                            "🔻 SALES:"
                        ]
                        
                        for transaction in day_data['sells']:
                            crypto = transaction['original_purchase'].get('cryptoCurrency', 'Unknown')
                            amount = transaction['amount']
                            time_str = transaction['date'].split(' ')[1] if ' ' in transaction['date'] else transaction['date']
                            sell_tooltip_lines.append(f"  • {time_str}: {crypto} - €{amount:.2f} (SELL)")
                        
                        sell_bar.setToolTip("\n".join(sell_tooltip_lines))
                        self.plot_widget.addItem(sell_bar)
            
                # Add legend and configure proper zoom level
            if investment_timestamps:
                # Create and configure a prominent legend
                legend = self.plot_widget.addLegend()
                legend.setParentItem(self.plot_widget.getPlotItem())
                
                # Style the legend for better visibility
                try:
                    # Set legend properties for better visibility
                    legend.setBrush(pg.mkBrush(color=(255, 255, 255, 200)))  # White background with transparency
                    legend.setPen(pg.mkPen(color=(0, 0, 0), width=1))  # Black border
                    legend.setOffset((10, 10))  # Position offset from top-left
                    
                    # Try to set text style if supported
                    if hasattr(legend, 'setLabelTextColor'):
                        legend.setLabelTextColor((0, 0, 0))  # Black text
                    
                    print("✅ Legend styled successfully")
                    
                except Exception as e:
                    print(f"⚠️ Legend styling failed: {e}")
                
                print("✅ Legend added to chart")
                
                # Configure proper view range with padding for axis labels
                view_box = self.plot_widget.getViewBox()
                
                # Calculate data bounds including sell bars (negative values)
                min_timestamp = min(investment_timestamps)
                max_timestamp = max(investment_timestamps)
                min_value = min(investment_amounts) if investment_amounts else 0
                max_value = max(investment_amounts) if investment_amounts else 1000
                
                # Consider sell bar values for Y-axis range (they go below zero)
                max_sell_amount = 0
                if daily_transactions:
                    for day_data in daily_transactions.values():
                        if day_data['sells']:
                            sell_amount = sum(t['amount'] for t in day_data['sells'])
                            max_sell_amount = max(max_sell_amount, sell_amount)
                
                # Add padding for better visibility and axis labels
                time_range = max_timestamp - min_timestamp
                value_range = max_value - min_value
                
                # X-axis padding (8% on each side for better visibility)
                x_padding = time_range * 0.08 if time_range > 0 else 86400 * 30  # 30 days fallback
                x_min = min_timestamp - x_padding
                x_max = max_timestamp + x_padding
                
                # Y-axis padding - include space for sell bars below zero
                y_padding_top = value_range * 0.15 if value_range > 0 else 150  # 15% at top
                y_padding_bottom = max_sell_amount * 0.15 if max_sell_amount > 0 else 0  # 15% below for sells
                
                y_min = -max_sell_amount - y_padding_bottom if max_sell_amount > 0 else 0  # Allow negative for sell bars
                y_max = max_value + y_padding_top
                
                # Ensure minimum ranges
                if (x_max - x_min) < 86400 * 7:  # Minimum 7 days width
                    center_x = (x_min + x_max) / 2
                    x_min = center_x - 86400 * 3.5
                    x_max = center_x + 86400 * 3.5
                    
                if (y_max - y_min) < 200:  # Minimum 200 EUR height for better axis visibility
                    center_y = (y_min + y_max) / 2
                    # Allow negative Y values if we have sell bars
                    if max_sell_amount > 0:
                        y_min = center_y - 100  # Don't force to 0 if we have sells
                    else:
                        y_min = max(0, center_y - 100)  # Only force to 0 if no sells
                    y_max = center_y + 100
                
                # Apply the view range with generous padding to ensure axis visibility
                self.plot_widget.setXRange(x_min, x_max, padding=0)
                self.plot_widget.setYRange(y_min, y_max, padding=0)
                
                # Disable auto-range now that we've set explicit ranges
                view_box.enableAutoRange(x=False, y=False)
                
                # Allow manual zooming but set reasonable limits
                # Update limits to allow negative values for sell bars
                max_negative = -max_sell_amount - y_padding_bottom if max_sell_amount > 0 else 0
                view_box.setLimits(
                    xMin=min_timestamp - time_range * 2,  # Allow more zoom out
                    xMax=max_timestamp + time_range * 2,
                    yMin=max_negative * 2,  # Allow zooming to see sell bars (negative values)
                    yMax=max_value * 3  # Allow zooming up to 3x max value
                )
                
                # Set simple static title
                self.set_chart_title("📈 Investment Timeline")
            else:
                self.set_chart_title("📈 Investment Timeline - No Data")
            
            # Reapply default chart options after data update with built-in grid
            self._set_default_chart_options()
        
        except Exception as e:
            print(f"Error updating chart: {e}")
            self.set_chart_title(f"📈 Chart Error: {str(e)}")
    
    def _on_transaction_clicked(self, day_timestamp):
        """Handle click events on transaction bars (both buy and sell) to highlight in table."""
        try:
            if day_timestamp not in self.purchase_data:
                return
            
            transaction_info = self.purchase_data[day_timestamp]
            all_transactions = transaction_info['transactions']
            
            # Create tooltip info for both buys and sells
            tooltip_lines = [
                f"📅 Date: {datetime.fromtimestamp(day_timestamp).strftime('%Y-%m-%d')}"
            ]
            
            # Add buy info if any
            if transaction_info['buy_count'] > 0:
                tooltip_lines.extend([
                    f"🔼 Total Purchases: €{transaction_info['buy_total']:.2f}",
                    f"📊 {transaction_info['buy_count']} purchase(s)"
                ])
            
            # Add sell info if any
            if transaction_info['sell_count'] > 0:
                tooltip_lines.extend([
                    f"🔻 Total Sales: €{transaction_info['sell_total']:.2f}",
                    f"📊 {transaction_info['sell_count']} sale(s)"
                ])
            
            # Add net info
            net_total = transaction_info['net_total']
            net_type = "profit" if net_total > 0 else "loss" if net_total < 0 else "neutral"
            tooltip_lines.append(f"💵 Net: €{net_total:.2f} ({net_type})")
            
            tooltip_lines.extend(["", "Transactions on this day:"])
            
            # Add individual transaction details
            for transaction in all_transactions:
                crypto = transaction['original_purchase'].get('cryptoCurrency', 'Unknown')
                amount = transaction['amount']
                trans_type = transaction['type']
                time_str = transaction['date'].split(' ')[1] if ' ' in transaction['date'] else transaction['date']
                
                arrow = "↑" if trans_type == 'BUY' else "↓"
                tooltip_lines.append(f"  {arrow} {time_str}: {crypto} - €{amount:.2f} ({trans_type})")
            
            tooltip_text = "\n".join(tooltip_lines)
            
            print(f"Transaction clicked: {tooltip_text}")
            
            # Try to highlight transactions in the table
            highlighted_count = self._highlight_transactions_in_table(all_transactions)
            
            # Show tooltip info in chart title temporarily with feedback
            original_title = self.title_label.text() if self.title_label else ""
            if highlighted_count > 0:
                temp_title = f"✅ {datetime.fromtimestamp(day_timestamp).strftime('%Y-%m-%d')}: {highlighted_count} transactions highlighted in table"
            else:
                temp_title = f"📅 {datetime.fromtimestamp(day_timestamp).strftime('%Y-%m-%d')}: {transaction_info['count']} transactions, Net: €{net_total:.0f}"
            self.set_chart_title(temp_title)
            
            # Reset title after 4 seconds
            from PySide6.QtCore import QTimer
            QTimer.singleShot(4000, lambda: self.set_chart_title(original_title))
            
        except Exception as e:
            print(f"Error handling transaction click: {e}")
    
    def _on_purchase_clicked(self, day_timestamp, points):
        """Handle click events on purchase bars to highlight in table (legacy method)."""
        # Redirect to the new transaction handler
        self._on_transaction_clicked(day_timestamp)
    
    def _highlight_transactions_in_table(self, transactions):
        """Highlight the clicked transactions (both buys and sells) in the main table and return count of highlighted rows."""
        highlighted_count = 0
        try:
            # Navigate to the main window and highlight table rows
            main_window = self.main_window
            while main_window and not hasattr(main_window, 'purchases_table'):
                main_window = getattr(main_window, 'parent', lambda: None)()
            
            if not main_window or not hasattr(main_window, 'purchases_table'):
                print("Could not find main window or purchases table")
                return highlighted_count
            
            purchases_table = main_window.purchases_table
            
            # Switch to the Purchases tab if the main window has tab_widget
            if hasattr(main_window, 'tab_widget'):
                # Find the Purchases tab and switch to it
                tab_widget = main_window.tab_widget
                for tab_index in range(tab_widget.count()):
                    if tab_widget.tabText(tab_index) == "Purchases":
                        tab_widget.setCurrentIndex(tab_index)
                        print("Switched to Purchases tab")
                        break
            
            # Clear previous selection
            purchases_table.clearSelection()
            
            # Find and select matching rows
            for transaction in transactions:
                original_transaction = transaction['original_purchase']
                transaction_timestamp = original_transaction.get('createTime', 0)
                trans_type = transaction['type']
                
                # Search through table rows to find matching transactions
                # Table columns: Date(0), Type(1), OrderID(2), FiatCurrency(3), FiatAmount(4), Crypto(5), CryptoAmount(6), Price(7), Fee(8)
                for row in range(purchases_table.rowCount()):
                    try:
                        # Get transaction details for matching
                        order_id_item = purchases_table.item(row, 2)  # Order ID in column 2
                        crypto_item = purchases_table.item(row, 5)    # Crypto in column 5
                        amount_item = purchases_table.item(row, 4)    # Fiat amount in column 4
                        type_item = purchases_table.item(row, 1)      # Type in column 1
                        
                        if order_id_item and crypto_item and amount_item and type_item:
                            table_order_id = order_id_item.text().strip()
                            table_crypto = crypto_item.text().strip()
                            table_amount = float(amount_item.text().replace('€', '').replace(',', '').strip())
                            table_type = type_item.text().strip()
                            
                            transaction_order_id = str(original_transaction.get('orderId', '')).strip()
                            transaction_crypto = original_transaction.get('cryptoCurrency', '').strip()
                            transaction_amount = original_transaction.get('amountFiat', 0)
                            
                            # Match transaction type (BUY/SELL)
                            expected_type = "BUY" if trans_type == 'BUY' else "SELL"
                            type_match = table_type == expected_type
                            
                            # Primary match: Order ID + Type (most reliable)
                            # Secondary match: Crypto + Amount + Type (for edge cases)
                            order_id_match = (table_order_id and transaction_order_id and 
                                            table_order_id == transaction_order_id and type_match)
                            crypto_amount_match = (table_crypto == transaction_crypto and 
                                                 abs(table_amount - transaction_amount) < 0.01 and type_match)
                            
                            if order_id_match or crypto_amount_match:
                                # Highlight this row
                                purchases_table.selectRow(row)
                                purchases_table.scrollToItem(purchases_table.item(row, 0))
                                match_type = "OrderID+Type" if order_id_match else "Crypto+Amount+Type"
                                print(f"Highlighted {trans_type} ({match_type}): {transaction_crypto} - €{transaction_amount:.2f} (OrderID: {transaction_order_id})")
                                highlighted_count += 1
                                break
                    except (ValueError, AttributeError) as e:
                        continue  # Skip problematic rows
            
        except Exception as e:
            print(f"Error highlighting transactions in table: {e}")
        
        return highlighted_count
    
    def _highlight_purchases_in_table(self, purchases):
        """Highlight the clicked purchases in the main table and return count of highlighted rows (legacy method)."""
        # Redirect to the new transaction handler
        return self._highlight_transactions_in_table(purchases)
    


# Factory function for backward compatibility
def create_chart_widget(chart_library: str = "pyqtgraph", parent=None):
    """Create a chart widget. For compatibility with existing code."""
    widget = ChartWidget(parent)
    
    # Add interface compatibility methods directly to the widget
    widget.create_widget = lambda: widget  # Return self for interface compatibility
    
    return widget, widget  # Return widget twice for interface compatibility
