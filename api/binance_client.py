"""Binance API client with authentication and rate limiting."""
import hashlib
import hmac
import time
from typing import Dict, Any, Optional
from urllib.parse import urlencode
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential


class BinanceAPIClient:
    """Binance API client with authentication and error handling."""
    
    BASE_URL = "https://api.binance.com"
    
    def __init__(self, api_key: str, api_secret: str):
        """Initialize client with API credentials."""
        self.api_key = api_key
        self.api_secret = api_secret
        self.session = None
        self._ts_offset = 0  # Time offset from server
    
    def __enter__(self):
        self.session = httpx.Client(
            timeout=30.0,
            http2=True,
            headers={"X-MBX-APIKEY": self.api_key}
        )
        # Sync time with server on connect
        self._sync_server_time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            self.session.close()
            self.session = None
    
    def _generate_signature(self, params: Dict[str, Any]) -> str:
        """Generate HMAC SHA256 signature for authenticated requests."""
        query_string = urlencode(params)
        return hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    def _sync_server_time(self):
        """Synchronize with server time to avoid timestamp errors."""
        try:
            response = self.session.get(f"{self.BASE_URL}/api/v3/time", timeout=10)
            response.raise_for_status()
            server_time = response.json()["serverTime"]
            client_time = int(time.time() * 1000)
            self._ts_offset = server_time - client_time
            print(f"Time sync: server={server_time}, client={client_time}, offset={self._ts_offset}ms")
        except Exception as e:
            print(f"Warning: Failed to sync server time: {e}")
            self._ts_offset = 0
    
    def _add_timestamp(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Add timestamp and recvWindow to parameters."""
        params = params.copy()
        # Use server-synchronized timestamp
        params['timestamp'] = int(time.time() * 1000) + self._ts_offset
        # Add recvWindow to reduce timestamp drift errors
        params['recvWindow'] = 60000
        return params
    
    def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        params: Optional[Dict[str, Any]] = None,
        signed: bool = False
    ) -> Dict[str, Any]:
        """Make HTTP request to Binance API."""
        url = f"{self.BASE_URL}{endpoint}"
        headers = {"X-MBX-APIKEY": self.api_key}
        
        if params is None:
            params = {}
        
        if signed:
            params = self._add_timestamp(params)
            params['signature'] = self._generate_signature(params)
        
        try:
            if method.upper() == "GET":
                response = self.session.get(url, params=params, headers=headers)
            elif method.upper() == "POST":
                response = self.session.post(url, data=params, headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            # Check for rate limit warnings in headers
            weight_used = response.headers.get('X-MBX-USED-WEIGHT-1M')
            if weight_used and int(weight_used) > 800:  # 80% of 1000 limit
                print(f"Warning: High API weight usage: {weight_used}/1000")
                time.sleep(5)  # Preventive sleep
            
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (429, 418):
                # Rate limit exceeded (429) or I'm a teapot (418 = IP banned)
                retry_after = e.response.headers.get('Retry-After', '60')
                error_data = e.response.json() if e.response.content else {}
                error_msg = error_data.get('msg', f'Rate limited (HTTP {e.response.status_code})')
                raise Exception(f"rate_limited: {error_msg} (retry after {retry_after}s)")
            elif e.response.status_code in (401, 403):
                # Authentication error
                error_data = e.response.json() if e.response.content else {}
                error_msg = error_data.get('msg', 'Authentication failed')
                raise Exception(f"Authentication failed: {error_msg}")
            else:
                # Other HTTP error
                error_data = e.response.json() if e.response.content else {}
                error_msg = error_data.get('msg', f'HTTP {e.response.status_code} error')
                raise Exception(f"API request failed: {error_msg}")
        except httpx.RequestError as e:
            raise Exception(f"Network error: {str(e)}")
        except Exception as e:
            raise Exception(f"Unexpected error: {str(e)}")
    
    def get_fiat_orders(
        self, 
        transaction_type: str = "0",  # 0: buy, 1: sell
        begin_time: Optional[int] = None,
        end_time: Optional[int] = None,
        page: int = 1,
        rows: int = 500
    ) -> Dict[str, Any]:
        """Get fiat order history (credit card purchases).
        
        Args:
            transaction_type: 0 for buy, 1 for sell
            begin_time: Start time in milliseconds
            end_time: End time in milliseconds
            page: Page number (starts from 1)
            rows: Number of records per page (max 500)
        """
        params = {
            "transactionType": transaction_type,
            "page": page,
            "rows": rows
        }
        
        if begin_time:
            params["beginTime"] = begin_time
        if end_time:
            params["endTime"] = end_time
        
        return self._make_request("GET", "/sapi/v1/fiat/orders", params, signed=True)
    
    def get_fiat_payments(
        self, 
        transaction_type: str = "0",  # 0: buy, 1: sell
        begin_time: Optional[int] = None,
        end_time: Optional[int] = None,
        page: int = 1,
        rows: int = 500
    ) -> Dict[str, Any]:
        """Get fiat payment history (alternative endpoint for credit card purchases).
        
        Args:
            transaction_type: 0 for buy, 1 for sell
            begin_time: Start time in milliseconds
            end_time: End time in milliseconds
            page: Page number (starts from 1)
            rows: Number of records per page (max 500)
        """
        params = {
            "transactionType": transaction_type,
            "page": page,
            "rows": rows
        }
        
        if begin_time:
            params["beginTime"] = begin_time
        if end_time:
            params["endTime"] = end_time
        
        return self._make_request("GET", "/sapi/v1/fiat/payments", params, signed=True)
    
    def get_account_info(self) -> Dict[str, Any]:
        """Get account information including spot balances."""
        return self._make_request("GET", "/api/v3/account", signed=True)
    
    def get_all_prices(self) -> Dict[str, float]:
        """Get current prices for all symbols."""
        response = self._make_request("GET", "/api/v3/ticker/price")
        
        # Convert list of dicts to dict of symbol -> price
        price_dict = {}
        for item in response:
            symbol = item['symbol']
            price = float(item['price'])
            price_dict[symbol] = price
        
        return price_dict
    
    def get_server_time(self) -> int:
        """Get server time for timestamp synchronization."""
        response = self._make_request("GET", "/api/v3/time")
        return response['serverTime']
    
    def test_connection(self) -> bool:
        """Test API connection and credentials."""
        try:
            self.get_server_time()
            self.get_account_info()
            return True
        except Exception:
            return False
