"""
Configuration management for the arbitrage system.
Centralizes all environment variables, exchange configurations, and system parameters.
"""
import os
from dataclasses import dataclass
from typing import Dict, List, Optional
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore
import logging

# Load environment variables
load_dotenv()

@dataclass
class ExchangeConfig:
    """Configuration for a cryptocurrency exchange"""
    name: str
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    enable_trading: bool = False
    trading_fee: float = 0.001  # Default 0.1%
    withdrawal_fee: Dict[str, float] = None
    supported_pairs: List[str] = None
    
    def __post_init__(self):
        if self.withdrawal_fee is None:
            self.withdrawal_fee = {"BTC": 0.0005, "ETH": 0.005}
        if self.supported_pairs is None:
            self.supported_pairs = ["BTC/USDT", "ETH/USDT", "BTC/ETH"]

@dataclass
class ArbitrageConfig:
    """Arbitrage detection parameters"""
    min_profit_threshold: float = 0.003  # 0.3% minimum profit
    max_slippage: float = 0.002  # 0.2% max slippage
    volume_multiplier: float = 0.1  # Trade 10% of available volume
    cool_down_period: int = 60  # 60 seconds between same pair checks
    max_concurrent_trades: int = 3
    risk_per_trade: float = 0.02  # 2% of portfolio per trade

class SystemConfig:
    """Main system configuration singleton"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize configuration from environment variables"""
        # Exchange configurations
        self.exchanges = {
            "binance": ExchangeConfig(
                name="binance",
                api_key=os.getenv("BINANCE_API_KEY"),
                api_secret=os.getenv("BINANCE_API_SECRET"),
                enable_trading=os.getenv("ENABLE_BINANCE_TRADING", "false").lower() == "true",
                trading_fee=0.001
            ),
            "coinbase": ExchangeConfig(
                name="coinbase",
                api_key=os.getenv("COINBASE_API_KEY"),
                api_secret=os.getenv("COINBASE_API_SECRET"),
                enable_trading=os.getenv("ENABLE_COINBASE_TRADING", "false").lower() == "true",
                trading_fee=0.005
            ),
            "kraken": ExchangeConfig(
                name="kraken",
                api_key=os.getenv("KRAKEN_API_KEY"),
                api_secret=os.getenv("KRAKEN_API_SECRET"),
                enable_trading=os.getenv("ENABLE_KRAKEN_TRADING", "false").lower() == "true",
                trading_fee=0.0026
            )
        }
        
        # Arbitrage configuration
        self.arbitrage = ArbitrageConfig(
            min_profit_threshold=float(os.getenv("MIN_PROFIT_THRESHOLD", "0.003")),
            max_slippage=float(os.getenv("MAX_SLIPPAGE", "0.002")),
            volume_multiplier=float(os.getenv("VOLUME_MULTIPLIER", "0.1"))
        )
        
        # Firebase configuration
        firebase_creds = {
            "type": os.getenv("FIREBASE_TYPE"),
            "project_id": os.getenv("FIREBASE_PROJECT_ID"),
            "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID"),
            "private_key": os.getenv("FIREBASE_PRIVATE_KEY", "").replace('\\n', '\n'),
            "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
            "client_id": os.getenv("FIREBASE_CLIENT_ID"),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": os.getenv("FIREBASE_CLIENT_CERT_URL")
        }
        
        # Initialize Firebase only if credentials are provided
        if all(firebase_creds.values()):
            try:
                cred = credentials.Certificate(firebase_creds)
                firebase_admin.initialize_app(cred)
                self.db = firestore.client()
                logging.info("Firebase initialized successfully")
            except Exception as e:
                logging.warning(f"Firebase initialization failed: {e}. Using local storage.")
                self.db = None
        else:
            logging.warning("Firebase credentials not found. Using local storage.")
            self.db = None
        
        # System parameters
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        self.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.update_interval = int(os.getenv("UPDATE_INTERVAL", "10"))
        self.max_retries = int(os.getenv("MAX_RETRIES", "3"))
        
    def get_enabled_exchanges(self) -> List[str]:
        """Get list of exchanges with trading enabled"""
        return [name for name, config in self.exchanges.items() 
                if config.enable_trading]
    
    def validate_configuration(self) -> bool:
        """Validate that all required configurations are present"""
        issues = []
        
        # Check for at least one enabled exchange
        enabled = self.get_enabled_exchanges()