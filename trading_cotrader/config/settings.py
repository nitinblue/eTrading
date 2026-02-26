"""
Configuration Management using Pydantic Settings

Loads from environment variables with .env file support
Type-safe configuration with validation
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv

def load_env_file():
    """Load .env file from multiple possible locations"""
    possible_paths = [
        Path('.env'),
        Path(__file__).parent.parent / '.env',
        Path(__file__).parent.parent.parent / '.env',
    ]
    
    for path in possible_paths:
        if path.exists():
            load_dotenv(path)
            print(f"[OK] Loaded .env from: {path.absolute()}")
            return True

    print("[WARN] No .env file found, using environment variables")
    return False

# Load .env before defining Settings
load_env_file()

class Settings(BaseSettings):
    
    """Application settings"""
    
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore'
    )
    
    # ========================================================================
    # Tastytrade Configuration
    # ========================================================================
    
    # Make these optional since they come from YAML
    tastytrade_client_secret: str = Field(
        default="",
        description="Tastytrade client secret (loaded from YAML)"
    )
    
    tastytrade_refresh_token: str = Field(
        default="",
        description="Tastytrade refresh token (loaded from YAML)"
    )
    
    tastytrade_account_number: Optional[str] = Field(
        default=None,
        description="Specific account number (optional, will use first if not provided)"
    )
    
    is_paper_trading: bool = Field(
        default=False,
        description="Use paper trading account"
    )
    
    # ========================================================================
    # Database Configuration
    # ========================================================================
    
    database_url: str = Field(
        default="sqlite:///trading_cotrader.db",
        description="Database connection string"
    )
    
    # ========================================================================
    # Logging Configuration
    # ========================================================================
    
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )
    
    log_file: Optional[Path] = Field(
        default=Path("trading_cotrader.log"),
        description="Log file path (None for stdout only)"
    )
    
    log_format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log message format"
    )
    
    # ========================================================================
    # Application Configuration
    # ========================================================================
    
    app_name: str = Field(
        default="Trading Co-Trader",
        description="Application name"
    )
    
    sync_on_startup: bool = Field(
        default=True,
        description="Automatically sync portfolio on startup"
    )
    
    auto_validate: bool = Field(
        default=True,
        description="Automatically validate data after sync"
    )
    
    # ========================================================================
    # Risk Management Defaults
    # ========================================================================
    
    max_portfolio_delta: Optional[float] = Field(
        default=100.0,
        description="Maximum allowed portfolio delta (alert threshold)"
    )
    
    max_position_size_percent: float = Field(
        default=20.0,
        description="Maximum position size as % of portfolio"
    )
    
    default_profit_target_percent: float = Field(
        default=50.0,
        description="Default profit target %"
    )
    
    default_max_loss_percent: float = Field(
        default=100.0,
        description="Default maximum loss %"
    )
    
    # ========================================================================
    # Feature Flags
    # ========================================================================
    
    enable_greeks_calculation: bool = Field(
        default=True,
        description="Enable Greeks calculation (vs using broker Greeks only)"
    )
    
    enable_pnl_attribution: bool = Field(
        default=True,
        description="Enable P&L attribution by Greeks"
    )
    
    enable_pattern_suggestions: bool = Field(
        default=True,
        description="Enable AI pattern-based suggestions"
    )
    
    # ========================================================================
    # Performance & Caching
    # ========================================================================
    
    greeks_cache_ttl_seconds: int = Field(
        default=60,
        description="Greeks cache time-to-live in seconds"
    )
    
    market_data_cache_ttl_seconds: int = Field(
        default=10,
        description="Market data cache TTL"
    )
    
    # ========================================================================
    # Validators
    # ========================================================================
    
    @field_validator('log_level')
    @classmethod
    def validate_log_level(cls, v):
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}")
        return v.upper()
    
    @field_validator('log_file')
    @classmethod
    def ensure_path_exists(cls, v):
        if v:
            path = Path(v)
            if not path.parent.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
        return v
    
    # ========================================================================
    # Helper Methods
    # ========================================================================
    
    def get_database_engine_kwargs(self) -> dict:
        """Get SQLAlchemy engine kwargs based on database URL"""
        kwargs = {
            'echo': self.log_level == 'DEBUG',
        }
        
        if 'sqlite' in self.database_url:
            kwargs['connect_args'] = {'check_same_thread': False}
        elif 'postgresql' in self.database_url:
            kwargs['pool_size'] = 20
            kwargs['max_overflow'] = 40
            kwargs['pool_pre_ping'] = True
        
        return kwargs
    
    def is_production(self) -> bool:
        """Check if running in production mode"""
        return not self.is_paper_trading
    
    def get_tastytrade_config(self) -> dict:
        """Get Tastytrade configuration dict"""
        return {
            'client_secret': self.tastytrade_client_secret,
            'refresh_token': self.tastytrade_refresh_token,
            'account_number': self.tastytrade_account_number,
            'is_paper': self.is_paper_trading,
        }


# ============================================================================
# Global Settings Instance
# ============================================================================

_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """
    Get global settings instance (singleton pattern)
    
    Usage:
        from config.settings import get_settings
        settings = get_settings()
        print(settings.database_url)
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings():
    """Reload settings (useful for testing)"""
    global _settings
    _settings = Settings()
    return _settings


# ============================================================================
# Logging Configuration
# ============================================================================

import logging
import sys


def setup_logging(settings: Optional[Settings] = None):
    """
    Configure logging based on settings
    
    Usage:
        from config.settings import setup_logging, get_settings
        setup_logging(get_settings())
    """
    if settings is None:
        settings = get_settings()
    
    # Create formatter
    formatter = logging.Formatter(settings.log_format)
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(settings.log_level)
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(settings.log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (if configured)
    if settings.log_file:
        file_handler = logging.FileHandler(settings.log_file,  encoding='utf-8')
        file_handler.setLevel(settings.log_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    # Silence noisy libraries
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    
    root_logger.info(f"Logging configured: level={settings.log_level}, file={settings.log_file}")


# ============================================================================
# Example .env file
# ============================================================================

ENV_EXAMPLE = """
# Database
DATABASE_URL=sqlite:///trading_cotrader.db
# DATABASE_URL=postgresql://user:password@localhost/trading_cotrader

# Tastytrade
TASTYTRADE_CLIENT_SECRET=your_client_secret_here
TASTYTRADE_REFRESH_TOKEN=your_refresh_token_here
TASTYTRADE_ACCOUNT_NUMBER=your_account_number
IS_PAPER_TRADING=false

# Logging
LOG_LEVEL=INFO
LOG_FILE=trading_cotrader.log

# Application
SYNC_ON_STARTUP=true
AUTO_VALIDATE=true

# Risk Management
MAX_PORTFOLIO_DELTA=100.0
MAX_POSITION_SIZE_PERCENT=20.0
DEFAULT_PROFIT_TARGET_PERCENT=50.0
DEFAULT_MAX_LOSS_PERCENT=100.0

# Feature Flags
ENABLE_GREEKS_CALCULATION=true
ENABLE_PNL_ATTRIBUTION=true
ENABLE_PATTERN_SUGGESTIONS=true

# Performance
GREEKS_CACHE_TTL_SECONDS=60
MARKET_DATA_CACHE_TTL_SECONDS=10
"""


if __name__ == "__main__":
    # Example: Create .env.example file
    print(ENV_EXAMPLE)
    
    # Example: Load and validate settings
    try:
        settings = get_settings()
        print(f"✓ Settings loaded successfully")
        print(f"  Database: {settings.database_url}")
        print(f"  Paper Trading: {settings.is_paper_trading}")
    except Exception as e:
        print(f"✗ Settings validation failed: {e}")