"""Universal currency system for crypto portfolio tracking."""
from typing import Dict, Optional, Set, List
from collections import Counter


def detect_primary_fiat_currency(transactions: List[Dict]) -> str:
    """Auto-detect the primary fiat currency from transaction history.
    
    Args:
        transactions: List of transaction records
        
    Returns:
        Most commonly used fiat currency code (EUR, USD, etc.)
    """
    if not transactions:
        return "EUR"  # Default to EUR
    
    # Count currency usage
    currency_counts = Counter()
    currency_amounts = {}
    
    for tx in transactions:
        currency = tx.get('fiatCurrency', '').upper()
        amount = tx.get('amountFiat', 0)
        
        if currency and currency in ['EUR', 'USD', 'GBP', 'CAD', 'AUD', 'JPY']:
            currency_counts[currency] += 1
            if currency not in currency_amounts:
                currency_amounts[currency] = 0
            currency_amounts[currency] += abs(amount)
    
    if not currency_counts:
        return "EUR"  # Default fallback
    
    # Return the currency with highest transaction volume
    # (more reliable than just transaction count)
    primary_currency = max(currency_amounts.keys(), key=lambda c: currency_amounts[c])
    return primary_currency


def get_supported_fiat_currencies() -> Set[str]:
    """Get set of supported fiat currencies.
    
    Returns:
        Set of supported currency codes
    """
    return {'EUR', 'USD', 'GBP', 'CAD', 'AUD', 'JPY'}


def validate_fiat_currency(currency: str) -> bool:
    """Validate if a fiat currency is supported.
    
    Args:
        currency: Currency code to validate
        
    Returns:
        True if currency is supported, False otherwise
    """
    return currency.upper() in get_supported_fiat_currencies()






def build_price_map(tickers: Dict[str, float], base_currency: str = "EUR") -> Dict[str, float]:
    """Build a mapping from crypto assets to base currency prices.
    
    Args:
        tickers: Dictionary of symbol -> price from Binance API
        base_currency: Base fiat currency (EUR, USD, etc.)
        
    Returns:
        Dictionary mapping asset symbol to base currency price
    """
    base_currency = base_currency.upper()
    prices = {}
    
    # First, get direct pairs (e.g., BTCEUR, BTCUSD)
    base_suffix = base_currency
    for symbol, price in tickers.items():
        if symbol.endswith(base_suffix):
            asset = symbol[:-len(base_suffix)]
            prices[asset] = price
    
    # If we don't have many direct pairs, use USDT bridge
    usdt_base_price = prices.get("USDT")
    if usdt_base_price and len(prices) < 10:  # Not many direct pairs available
        for symbol, price in tickers.items():
            if symbol.endswith("USDT"):
                asset = symbol[:-4]  # Remove USDT suffix
                if asset not in prices:  # Don't override direct pairs
                    prices[asset] = price * usdt_base_price
    
    # Use BTC bridge for remaining assets
    btc_base_price = prices.get("BTC")
    if btc_base_price:
        for symbol, price in tickers.items():
            if symbol.endswith("BTC"):
                asset = symbol[:-3]  # Remove BTC suffix
                if asset not in prices:  # Don't override existing mappings
                    prices[asset] = price * btc_base_price
    
    return prices


def get_asset_price(asset: str, price_map: Dict[str, float]) -> Optional[float]:
    """Get price for a specific asset in the base currency.
    
    Args:
        asset: Asset symbol (e.g., BTC, ETH, USDT)
        price_map: Mapping from asset to base currency price
        
    Returns:
        Price in base currency if available, None otherwise
    """
    return price_map.get(asset.upper())


def calculate_portfolio_value(balances: Dict[str, float], price_map: Dict[str, float], base_currency: str = "EUR") -> float:
    """Calculate total portfolio value in the base currency.
    
    Args:
        balances: Dictionary of asset -> amount
        price_map: Mapping from asset to base currency price
        base_currency: Base currency (for base asset handling)
        
    Returns:
        Total portfolio value in base currency
    """
    total_value = 0.0
    
    for asset, amount in balances.items():
        if amount > 0:
            # Handle base currency (1:1 conversion)
            if asset.upper() == base_currency.upper():
                total_value += amount
            else:
                price = get_asset_price(asset, price_map)
                if price:
                    total_value += amount * price
    
    return total_value


# Constants for external access
SUPPORTED_FIAT_CURRENCIES = ['EUR', 'USD', 'GBP', 'CAD', 'AUD', 'JPY']


# Legacy EUR-specific functions for backward compatibility
def build_eur_price_map(tickers: Dict[str, float]) -> Dict[str, float]:
    """Build a mapping from crypto assets to EUR prices (legacy function)."""
    return build_price_map(tickers, "EUR")


def get_asset_eur_price(asset: str, eur_price_map: Dict[str, float]) -> Optional[float]:
    """Get EUR price for a specific asset (legacy function)."""
    return get_asset_price(asset, eur_price_map)


def calculate_portfolio_eur_value(balances: Dict[str, float], eur_price_map: Dict[str, float]) -> float:
    """Calculate total EUR value of a portfolio (legacy function)."""
    return calculate_portfolio_value(balances, eur_price_map, "EUR")
