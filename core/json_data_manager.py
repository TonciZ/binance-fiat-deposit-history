"""Simple JSON-based data manager for purchases, balances, and prices."""
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional


class JSONDataManager:
    """Manages data storage using simple JSON files instead of SQLite database."""
    
    def __init__(self, data_dir: Path):
        """Initialize data manager with data directory."""
        self.data_dir = data_dir
        self.data_dir.mkdir(exist_ok=True)
        
        # Define file paths
        self.purchases_file = self.data_dir / "purchases.json"
        self.balances_file = self.data_dir / "balances.json"
        self.prices_file = self.data_dir / "prices.json"
        
        # Initialize empty files if they don't exist
        for file_path in [self.purchases_file, self.balances_file, self.prices_file]:
            if not file_path.exists():
                self._save_json(file_path, [])
    
    def _load_json(self, file_path: Path) -> Any:
        """Load JSON data from file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []
    
    def _save_json(self, file_path: Path, data: Any) -> None:
        """Save JSON data to file."""
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def save_purchases(self, purchases: List[Dict[str, Any]]) -> int:
        """Save purchases to JSON file, handling duplicates."""
        existing_purchases = self._load_json(self.purchases_file)
        
        # Create a set of existing order IDs for quick lookup
        existing_order_ids = {p.get('orderId') for p in existing_purchases if p.get('orderId')}
        
        # Add new purchases that don't already exist
        new_count = 0
        for purchase in purchases:
            order_id = purchase.get('orderId')
            if order_id and order_id not in existing_order_ids:
                # Add timestamp for when we saved it
                purchase['savedAt'] = datetime.now().isoformat()
                existing_purchases.append(purchase)
                existing_order_ids.add(order_id)
                new_count += 1
        
        # Sort by createTime (newest first)
        existing_purchases.sort(key=lambda x: x.get('createTime', 0), reverse=True)
        
        self._save_json(self.purchases_file, existing_purchases)
        return new_count
    
    def get_purchases(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Retrieve purchases from JSON file."""
        purchases = self._load_json(self.purchases_file)
        
        if limit:
            return purchases[:limit]
        return purchases
    
    def save_spot_balances(self, balances: Dict[str, Dict[str, float]]) -> int:
        """Save spot balances to JSON file."""
        balance_data = {
            "fetchedAt": datetime.now().isoformat(),
            "balances": balances
        }
        self._save_json(self.balances_file, balance_data)
        return len(balances)
    
    def get_spot_balances(self) -> Dict[str, Dict[str, float]]:
        """Retrieve spot balances from JSON file."""
        balance_data = self._load_json(self.balances_file)
        if isinstance(balance_data, dict) and 'balances' in balance_data:
            return balance_data['balances']
        return {}
    
    def save_prices(self, prices: Dict[str, float]) -> int:
        """Save current prices to JSON file."""
        price_data = {
            "fetchedAt": datetime.now().isoformat(),
            "prices": prices
        }
        self._save_json(self.prices_file, price_data)
        return len(prices)
    
    def get_prices(self) -> Dict[str, float]:
        """Retrieve prices from JSON file."""
        price_data = self._load_json(self.prices_file)
        if isinstance(price_data, dict) and 'prices' in price_data:
            return price_data['prices']
        return {}
    
    def clear_all_data(self) -> Dict[str, int]:
        """Clear all data files and return count of deleted items."""
        counts = {}
        
        # Count existing items before clearing
        purchases = self.get_purchases()
        balances = self.get_spot_balances()
        prices = self.get_prices()
        
        counts['purchases'] = len(purchases)
        counts['balances'] = len(balances)
        counts['prices'] = len(prices)
        
        # Clear all files
        self._save_json(self.purchases_file, [])
        self._save_json(self.balances_file, {})
        self._save_json(self.prices_file, {})
        
        return counts
    
    def get_purchase_statistics(self) -> Dict[str, Any]:
        """Get basic statistics about purchases."""
        purchases = self.get_purchases()
        
        if not purchases:
            return {
                'total_count': 0,
                'date_range': None,
                'currencies': [],
                'payment_methods': []
            }
        
        # Extract statistics
        currencies = set()
        payment_methods = set()
        amounts = []
        timestamps = []
        
        for purchase in purchases:
            if 'originalCurrency' in purchase:
                currencies.add(purchase['originalCurrency'])
            if 'paymentMethod' in purchase:
                payment_methods.add(purchase['paymentMethod'])
            if 'amountFiat' in purchase:
                amounts.append(purchase['amountFiat'])
            if 'createTime' in purchase and purchase['createTime']:
                timestamps.append(purchase['createTime'])
        
        date_range = None
        if timestamps:
            min_ts = min(timestamps)
            max_ts = max(timestamps)
            date_range = {
                'earliest': datetime.fromtimestamp(min_ts / 1000).isoformat(),
                'latest': datetime.fromtimestamp(max_ts / 1000).isoformat()
            }
        
        return {
            'total_count': len(purchases),
            'date_range': date_range,
            'currencies': sorted(list(currencies)),
            'payment_methods': sorted(list(payment_methods)),
            'total_amount_eur': sum(amounts) if amounts else 0,
            'average_amount_eur': sum(amounts) / len(amounts) if amounts else 0
        }
    
    def migrate_purchase_data(self) -> int:
        """Migrate existing purchase data (placeholder for compatibility)."""
        # This was used for database migration, not needed for JSON
        return 0
