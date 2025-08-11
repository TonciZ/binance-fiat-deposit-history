"""Fiat orders fetching with time-based chunking for historical data."""
import time
import json
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional, Tuple, Callable
from pathlib import Path
from .binance_client import BinanceAPIClient


class FiatOrdersFetcher:
    """Handles fetching fiat orders with chunking and resume functionality."""
    
    def __init__(
        self, 
        client: BinanceAPIClient, 
        db_manager, 
        exports_dir: Path,
        sleep_seconds: float = 1.0
    ):
        """Initialize fetcher with client and storage."""
        self.client = client
        self.db_manager = db_manager
        self.exports_dir = exports_dir
        self.sleep_seconds = sleep_seconds
        self.progress_callback: Optional[Callable] = None
    
    def set_progress_callback(self, callback: Callable[[str, int, int], None]):
        """Set callback for progress updates."""
        self.progress_callback = callback
    
    def _emit_progress(self, message: str, current: int = 0, total: int = 0):
        """Emit progress update if callback is set."""
        if self.progress_callback:
            self.progress_callback(message, current, total)
    
    def generate_quarter_windows(self, start_year: int, end_year: int) -> List[Tuple[int, int]]:
        """Generate quarterly time windows for API calls (max 90-day spans).
        
        Returns list of (begin_time, end_time) tuples in milliseconds.
        """
        def ms(dt): 
            return int(dt.replace(tzinfo=timezone.utc).timestamp() * 1000)
        
        def quarter_windows(year):
            quarters = [(1,3), (4,6), (7,9), (10,12)]
            for start_month, end_month in quarters:
                start = datetime(year, start_month, 1, tzinfo=timezone.utc)
                # End is last day of end_month
                if end_month == 12:
                    next_start = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
                else:
                    next_start = datetime(year, end_month + 1, 1, tzinfo=timezone.utc)
                end = next_start - timedelta(milliseconds=1)
                yield start, end
        
        windows = []
        for year in range(start_year, end_year + 1):
            for start_date, end_date in quarter_windows(year):
                # Don't fetch future quarters
                if start_date > datetime.now(timezone.utc):
                    continue
                    
                begin_time = ms(start_date)
                end_time = ms(end_date)
                windows.append((begin_time, end_time))
        
        return windows
    
    def _normalize_purchase(self, purchase: Dict[str, Any], trans_type: str, endpoint: str) -> Dict[str, Any]:
        """Normalize purchase data - convert all currencies to EUR.
        
        Args:
            purchase: Raw purchase data from API
            trans_type: Transaction type ("0" for buy, "1" for sell)
            endpoint: Which endpoint this came from ("orders" or "payments")
        """
        # Get original currency and convert to EUR
        original_currency = purchase.get('fiatCurrency', '').upper()
        print(f"Processing {original_currency} transaction")
        
        # Create normalized record
        normalized = {
            'transactionType': trans_type,
            'endpoint': endpoint,  # Track which endpoint this came from
            'createTime': purchase.get('createTime', purchase.get('orderCreateTime', 0)),
            'updateTime': purchase.get('updateTime', purchase.get('orderUpdateTime', 0)),
            'status': purchase.get('status', ''),
            'paymentMethod': purchase.get('method', purchase.get('paymentMethod', '')),
        }
        
        # Handle different ID fields
        if 'orderNo' in purchase:
            normalized['orderId'] = purchase['orderNo']
        elif 'paymentId' in purchase:
            normalized['orderId'] = purchase['paymentId']
        elif 'orderId' in purchase:
            normalized['orderId'] = purchase['orderId']
        else:
            normalized['orderId'] = ''
        
        # Get crypto currency
        normalized['cryptoCurrency'] = purchase.get('cryptoCurrency', purchase.get('coin', ''))
        
        # Handle different amount fields and convert to EUR
        if 'sourceAmount' in purchase:
            original_amount = float(purchase['sourceAmount'])
        elif 'amount' in purchase:
            original_amount = float(purchase['amount'])
        elif 'totalAmount' in purchase:
            original_amount = float(purchase['totalAmount'])
        elif 'indicatedAmount' in purchase:
            original_amount = float(purchase['indicatedAmount'])
        else:
            original_amount = 0.0
        
        # Convert to EUR using simple conversion rates
        eur_amount = self._convert_to_eur(original_amount, original_currency)
        normalized['amountFiat'] = eur_amount
        normalized['fiatCurrency'] = 'EUR'
        normalized['originalCurrency'] = original_currency
        normalized['originalAmount'] = original_amount
            
        # Handle crypto amount
        if 'obtainAmount' in purchase:
            normalized['amountCrypto'] = float(purchase['obtainAmount'])
        elif 'cryptoAmount' in purchase:
            normalized['amountCrypto'] = float(purchase['cryptoAmount'])
        else:
            normalized['amountCrypto'] = 0.0
        
        # Handle fees - EUR only
        if 'totalFee' in purchase:
            fee_amount = float(purchase['totalFee'])
        elif 'fee' in purchase:
            fee_amount = float(purchase['fee'])
        else:
            fee_amount = 0.0
        
        normalized['fee'] = fee_amount
        
        # Calculate price in EUR per crypto unit
        if normalized['amountCrypto'] > 0:
            normalized['price'] = normalized['amountFiat'] / normalized['amountCrypto']
        else:
            normalized['price'] = 0.0
            
        # Keep original data for debugging
        normalized['_original'] = purchase
        
        return normalized
    
    def _convert_to_eur(self, amount: float, currency: str) -> float:
        """Convert amount from given currency to EUR using approximate rates.
        
        Note: These are approximate conversion rates. For precise tracking,
        you should use historical exchange rates from the actual transaction dates.
        """
        if currency == 'EUR':
            return amount
        
        # Approximate conversion rates (you may want to update these)
        conversion_rates = {
            'USD': 0.85,    # 1 USD ≈ 0.85 EUR
            'GBP': 1.15,    # 1 GBP ≈ 1.15 EUR
            'CHF': 0.95,    # 1 CHF ≈ 0.95 EUR
            'CAD': 0.65,    # 1 CAD ≈ 0.65 EUR
            'AUD': 0.60,    # 1 AUD ≈ 0.60 EUR
            'JPY': 0.0065,  # 1 JPY ≈ 0.0065 EUR
            'CNY': 0.125,   # 1 CNY ≈ 0.125 EUR
            'HRK': 0.133,   # 1 HRK ≈ 0.133 EUR (7.5 HRK = 1 EUR)
            'SEK': 0.090,   # 1 SEK ≈ 0.090 EUR
            'NOK': 0.085,   # 1 NOK ≈ 0.085 EUR
            'PLN': 0.22,    # 1 PLN ≈ 0.22 EUR
        }
        
        rate = conversion_rates.get(currency, 1.0)  # Default to 1.0 if unknown
        eur_amount = amount * rate
        
        print(f"  Converting {amount:.2f} {currency} to {eur_amount:.2f} EUR (rate: {rate})")
        return eur_amount
    
    def _deduplicate_purchases(self, purchases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate purchases based on time, amount, and crypto.
        
        Uses a 5-minute time window to match potentially duplicate records.
        """
        if not purchases:
            return []
        
        deduplicated = []
        seen_keys = set()
        
        for purchase in purchases:
            # Create dedup key based on time (±5min), fiat amount, currency, crypto amount
            time_ms = purchase.get('createTime', 0)
            time_window = time_ms // (5 * 60 * 1000)  # 5-minute buckets
            
            dedup_key = (
                time_window,
                purchase.get('fiatCurrency', ''),
                round(purchase.get('amountFiat', 0), 2),  # Round to avoid floating point issues
                purchase.get('cryptoCurrency', ''),
                round(purchase.get('amountCrypto', 0), 6)
            )
            
            if dedup_key not in seen_keys:
                seen_keys.add(dedup_key)
                deduplicated.append(purchase)
        
        return deduplicated
    
    def _exponential_backoff(self, attempt: int) -> int:
        """Calculate exponential backoff time.
        
        Starting at 2s, max 60s as per spec.
        """
        base_delay = 2
        max_delay = 60
        delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
        return delay
    
    def save_checkpoint(self, year: int, quarter: int, page: int, total_fetched: int):
        """Save progress checkpoint."""
        checkpoint = {
            "year": year,
            "quarter": quarter,
            "page": page,
            "total_fetched": total_fetched,
            "timestamp": datetime.now().isoformat()
        }
        
        checkpoint_file = self.exports_dir / "fetch_checkpoint.json"
        with open(checkpoint_file, 'w') as f:
            json.dump(checkpoint, f, indent=2)
    
    def load_checkpoint(self) -> Optional[Dict[str, Any]]:
        """Load progress checkpoint if exists."""
        checkpoint_file = self.exports_dir / "fetch_checkpoint.json"
        if checkpoint_file.exists():
            with open(checkpoint_file, 'r') as f:
                return json.load(f)
        return None
    
    def clear_checkpoint(self):
        """Clear progress checkpoint."""
        checkpoint_file = self.exports_dir / "fetch_checkpoint.json"
        if checkpoint_file.exists():
            checkpoint_file.unlink()
    
    def fetch_all_purchases(
        self, 
        start_year: int = 2016, 
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """Fetch all fiat orders (both BUY and SELL) with chunking and resume.
        
        Args:
            start_year: Year to start fetching from
            dry_run: If True, only count expected API calls without fetching
            
        Returns:
            Dictionary with results summary
        """
        current_year = datetime.now().year
        windows = self.generate_quarter_windows(start_year, current_year)
        
        if dry_run:
            return self._dry_run_analysis(windows)
        
        # Check for existing checkpoint
        checkpoint = self.load_checkpoint()
        start_window_index = 0
        start_page = 1
        total_fetched = 0
        
        if checkpoint:
            # Find where to resume
            for i, (begin_time, end_time) in enumerate(windows):
                year = datetime.fromtimestamp(begin_time / 1000).year
                quarter = (datetime.fromtimestamp(begin_time / 1000).month - 1) // 3 + 1
                
                if year == checkpoint["year"] and quarter == checkpoint["quarter"]:
                    start_window_index = i
                    start_page = checkpoint["page"]
                    total_fetched = checkpoint["total_fetched"]
                    self._emit_progress(
                        f"Resuming from {year} Q{quarter}, page {start_page}", 
                        start_window_index, len(windows)
                    )
                    break
        
        all_purchases = []
        
        try:
            # Fetch both BUY (0) and SELL (1) transactions from /fiat/payments (primary)
            # /fiat/orders is severely rate-limited and often unusable
            for trans_type in ["0", "1"]:
                trans_name = "BUY" if trans_type == "0" else "SELL"
                
                # Use only /fiat/payments as it works reliably
                endpoint_name, endpoint_func = "payments", self.client.get_fiat_payments
                self._emit_progress(f"Fetching {trans_name} from /fiat/{endpoint_name}...", 0, len(windows) * 2)
                
                trans_purchases = []  # Collect all purchases for this transaction type
                    
                for window_index in range(start_window_index, len(windows)):
                    begin_time, end_time = windows[window_index]
                    start_date = datetime.fromtimestamp(begin_time / 1000)
                    year = start_date.year
                    quarter = (start_date.month - 1) // 3 + 1
                    
                    self._emit_progress(
                        f"{trans_name} /fiat/{endpoint_name} {year} Q{quarter}...", 
                        window_index, len(windows)
                    )
                    
                    page = start_page if window_index == start_window_index else 1
                    window_purchases = []
                    
                    while True:
                        try:
                            # Fetch page using the appropriate endpoint
                            response = endpoint_func(
                                transaction_type=trans_type,  # BUY or SELL
                                begin_time=begin_time,
                                end_time=end_time,
                                page=page,
                                rows=500
                            )
                            
                            purchases = response.get('data', [])
                            
                            if not purchases:
                                # No more data for this window - this is normal for empty periods
                                break
                            
                            # Normalize and tag each purchase (convert all to EUR)
                            normalized_purchases = []
                            for purchase in purchases:
                                # Only process successful transactions
                                status = purchase.get('status', '').lower()
                                if status in ['completed', 'successful', 'finished']:
                                    normalized = self._normalize_purchase(purchase, trans_type, endpoint_name)
                                    if normalized is not None:
                                        normalized_purchases.append(normalized)
                                else:
                                    print(f"  Skipping transaction with status: {status}")
                            
                            # Add to collections
                            window_purchases.extend(normalized_purchases)
                            total_fetched += len(normalized_purchases)
                            
                            self._emit_progress(
                                f"{trans_name} /fiat/{endpoint_name} {year} Q{quarter} page {page}: {len(normalized_purchases)} orders", 
                                window_index, len(windows)
                            )
                            
                            page += 1
                            
                            # Rate limiting between pages using configured delay
                            time.sleep(self.sleep_seconds)
                                
                        except Exception as e:
                            error_msg = f"Error fetching {trans_name} /fiat/{endpoint_name} {year} Q{quarter} page {page}: {str(e)}"
                            self._emit_progress(error_msg, window_index, len(windows))
                            
                            # For authentication or critical errors, stop completely
                            if "Authentication failed" in str(e) or "signature" in str(e).lower():
                                raise e
                            
                            # Handle rate limiting with exponential backoff
                            if "rate_limited" in str(e):
                                backoff_time = self._exponential_backoff(page)
                                self._emit_progress(
                                    f"Rate limited - backing off for {backoff_time}s", 
                                    window_index, len(windows)
                                )
                                time.sleep(backoff_time)
                                continue  # Retry the same page
                            
                            # For other errors, skip to next window after short delay
                            time.sleep(5)
                            break
                    
                    # Add this window's purchases to transaction collection
                    trans_purchases.extend(window_purchases)
                    
                    # Sleep between windows using configured delay (slightly longer)
                    if window_index < len(windows) - 1:
                        time.sleep(self.sleep_seconds * 2.0)
                
                # Add all purchases from this transaction type to main collection
                all_purchases.extend(trans_purchases)
                
                # Reset for next transaction type
                start_page = 1
        
        except KeyboardInterrupt:
            self._emit_progress("Fetch interrupted by user", 0, 0)
        except Exception as e:
            self._emit_progress(f"Fetch failed: {str(e)}", 0, 0)
            raise
        
        # Clear checkpoint on successful completion
        if window_index >= len(windows) - 1:
            self.clear_checkpoint()
        
        # Deduplicate merged results
        self._emit_progress("Deduplicating merged results...", 0, 1)
        deduplicated_purchases = self._deduplicate_purchases(all_purchases)
        
        # Save deduplicated results to database
        if deduplicated_purchases:
            saved_count = self.db_manager.save_purchases(deduplicated_purchases)
            self._emit_progress(f"Saved {saved_count} unique purchases to database", 1, 1)
        
        # Final export
        self._export_final_results(deduplicated_purchases)
        
        return {
            "total_fetched": len(deduplicated_purchases),
            "raw_fetched": total_fetched,
            "duplicates_removed": total_fetched - len(deduplicated_purchases),
            "windows_processed": window_index + 1,
            "total_windows": len(windows),
            "completed": window_index >= len(windows) - 1
        }
    
    def _dry_run_analysis(self, windows: List[Tuple[int, int]]) -> Dict[str, Any]:
        """Analyze expected API calls without making them."""
        return {
            "total_windows": len(windows),
            "estimated_min_calls": len(windows),  # At least 1 call per window
            "estimated_max_calls": len(windows) * 20,  # Assuming max 10,000 orders per window
            "time_range": {
                "start": datetime.fromtimestamp(windows[0][0] / 1000).isoformat() if windows else None,
                "end": datetime.fromtimestamp(windows[-1][1] / 1000).isoformat() if windows else None
            },
            "estimated_duration_minutes": len(windows) * 2  # Rough estimate
        }
    
    def _export_incremental_backup(self, purchases: List[Dict[str, Any]], year: int, quarter: int):
        """Export incremental backup for a specific quarter."""
        if not purchases:
            return
        
        backup_file = self.exports_dir / f"purchases_backup_{year}_Q{quarter}.json"
        with open(backup_file, 'w') as f:
            json.dump({
                "year": year,
                "quarter": quarter,
                "count": len(purchases),
                "exported_at": datetime.now().isoformat(),
                "purchases": purchases
            }, f, indent=2)
    
    def _export_final_results(self, all_purchases: List[Dict[str, Any]]):
        """Export final consolidated results."""
        if not all_purchases:
            return
        
        # Export JSON
        json_file = self.exports_dir / "purchases.json"
        with open(json_file, 'w') as f:
            json.dump({
                "total_count": len(all_purchases),
                "exported_at": datetime.now().isoformat(),
                "purchases": all_purchases
            }, f, indent=2)
        
        # Export CSV
        if all_purchases:
            self._export_purchases_csv(all_purchases)
    
    def _export_purchases_csv(self, purchases: List[Dict[str, Any]]):
        """Export purchases to CSV format with original currency data."""
        import csv
        
        csv_file = self.exports_dir / "purchases.csv"
        
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # CSV headers - keep original currency as primary data
            writer.writerow([
                'time_iso', 'orderId', 'transactionType', 'fiatCurrency', 'amountFiat', 
                'crypto', 'amountCrypto', 'unitPrice', 'fee', 'paymentMethod', 'endpoint'
            ])
            
            for purchase in purchases:
                # Format timestamp
                timestamp = purchase.get('createTime', purchase.get('time', 0))
                time_iso = datetime.fromtimestamp(timestamp / 1000).isoformat() if timestamp else ''
                
                # Use the normalized data (already processed)
                fiat_amount = purchase.get('amountFiat', 0)
                fiat_currency = purchase.get('fiatCurrency', '')
                crypto_amount = purchase.get('amountCrypto', 0)
                unit_price = purchase.get('price', 0)
                fee = purchase.get('fee', 0)
                
                # Transaction type display
                trans_type = purchase.get('transactionType', '0')
                trans_type_display = 'BUY' if trans_type == '0' else 'SELL'
                
                writer.writerow([
                    time_iso,
                    purchase.get('orderId', ''),
                    trans_type_display,
                    fiat_currency,
                    round(fiat_amount, 2),
                    purchase.get('cryptoCurrency', ''),
                    crypto_amount,
                    round(unit_price, 6),
                    round(fee, 2),
                    purchase.get('paymentMethod', ''),
                    purchase.get('endpoint', '')
                ])
