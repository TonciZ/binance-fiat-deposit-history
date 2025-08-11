"""Configuration management for Binance Credit Card Purchase Tracker."""
import os
from pathlib import Path
from typing import Optional
from pydantic import BaseModel
from dotenv import load_dotenv


class Config(BaseModel):
    """Application configuration."""
    
    # API Configuration
    binance_api_key: str
    binance_api_secret: str
    
    # Application Settings
    api_delay_ms: int = 35  # API call delay in milliseconds
    start_year: int = 2016
    end_year: int = 2025
    preferred_fiat_currency: Optional[str] = None  # Auto-detect from transactions if not set
    chart_library: str = "pyqtgraph"  # Chart library: "pyqtgraph" or "matplotlib"
    
    # File paths
    app_dir: Path
    data_dir: Path
    exports_dir: Path
    
    # Optional donation settings
    donation_btc_address: Optional[str] = None
    donation_eth_address: Optional[str] = None
    donation_url: Optional[str] = None
    
    class Config:
        arbitrary_types_allowed = True


def load_config(app_dir: Optional[Path] = None) -> Config:
    """Load configuration from environment variables and .env file."""
    if app_dir is None:
        app_dir = Path(__file__).parent.parent
    
    # Load .env file if it exists
    env_path = app_dir / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    
    # Set up directories
    data_dir = app_dir / "data"
    exports_dir = app_dir / "exports"
    data_dir.mkdir(exist_ok=True)
    exports_dir.mkdir(exist_ok=True)
    
    # Get required API credentials
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")
    
    if not api_key or not api_secret:
        raise ValueError("BINANCE_API_KEY and BINANCE_API_SECRET must be set in .env file")
    
    return Config(
        binance_api_key=api_key,
        binance_api_secret=api_secret,
        api_delay_ms=int(os.getenv("API_DELAY_MS", "35")),
        start_year=int(os.getenv("START_YEAR", "2016")),
        end_year=int(os.getenv("END_YEAR", "2025")),
        preferred_fiat_currency=os.getenv("PREFERRED_FIAT_CURRENCY"),  # Auto-detect if not set
        chart_library=os.getenv("CHART_LIBRARY", "pyqtgraph"),  # Default to pyqtgraph
        app_dir=app_dir,
        data_dir=data_dir,
        exports_dir=exports_dir,
        # Note: Using JSON storage, no database needed
        donation_btc_address=os.getenv("DONATION_BTC_ADDRESS"),
        donation_eth_address=os.getenv("DONATION_ETH_ADDRESS"),
        donation_url=os.getenv("DONATION_URL"),
    )


# Global config instance - will be initialized when needed
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def set_config(config: Config) -> None:
    """Set the global configuration instance."""
    global _config
    _config = config
