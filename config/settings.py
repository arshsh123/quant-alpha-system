"""Advanced configuration settings for real-time quant system."""

import os
from pathlib import Path
from typing import Dict, List
import pytz

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = PROJECT_ROOT / "logs"
CACHE_DIR = PROJECT_ROOT / "cache"

# Ensure directories exist
for directory in [DATA_DIR, LOGS_DIR, CACHE_DIR]:
    directory.mkdir(exist_ok=True)

# Trading hours (Eastern Time)
TRADING_TIMEZONE = pytz.timezone('US/Eastern')
MARKET_OPEN_TIME = "09:30"
MARKET_CLOSE_TIME = "16:00"
PREMARKET_START = "04:00"
AFTERHOURS_END = "20:00"

# Real-time data sources configuration
REALTIME_SOURCES = {
    'twitter': {
        'enabled': True,
        'priority': 1,
        'weight': 0.4,
        'refresh_seconds': 5,
        'key_accounts': [
            'realDonaldTrump', 'elonmusk', 'POTUS', 'federalreserve',
            'SEC_News', 'CBSNews', 'CNBC', 'MarketWatch', 'WSJ',
            'BloombergNews', 'ReutersBiz', 'BreakingNews'
        ],
        'keywords': [
            'market', 'stocks', 'trading', 'economy', 'rates', 'inflation',
            'fed', 'earnings', 'guidance', 'merger', 'acquisition', 'ipo'
        ]
    },
    'news': {
        'enabled': True,
        'priority': 2,
        'weight': 0.3,
        'refresh_seconds': 30,
        'sources': [
            'https://feeds.reuters.com/reuters/businessNews',
            'https://feeds.finance.yahoo.com/rss/2.0/headline',
            'https://feeds.bloomberg.com/markets/news.rss',
            'https://www.cnbc.com/id/100003114/device/rss/rss.html'
        ]
    },
    'reddit': {
        'enabled': True,
        'priority': 3,
        'weight': 0.2,
        'refresh_seconds': 60,
        'subreddits': [
            'stocks', 'investing', 'SecurityAnalysis', 'ValueInvesting',
            'wallstreetbets', 'StockMarket', 'options', 'pennystocks'
        ]
    },
    'market_data': {
        'enabled': True,
        'priority': 1,
        'weight': 0.1,
        'refresh_seconds': 1,
        'symbols': ['SPY', 'QQQ', 'VIX', 'TLT', 'GLD', 'DXY']
    }
}

# Signal processing configuration
SIGNAL_PROCESSING = {
    'sentiment_window_minutes': 15,     # Rolling sentiment window
    'momentum_lookback_days': 5,        # Price momentum lookback
    'volume_threshold_multiplier': 2.0, # Unusual volume threshold
    'gap_threshold_percent': 2.0,       # Significant gap threshold
    'min_signal_confidence': 0.6,       # Minimum confidence to act
    'signal_decay_half_life_hours': 4,  # How fast signals decay
    'max_signals_per_stock': 3          # Prevent signal overload
}

# Risk management - ADVANCED
RISK_MANAGEMENT = {
    'position_sizing': {
        'method': 'kelly_criterion',           # kelly_criterion, equal_weight, vol_target
        'kelly_fraction': 0.25,                # Conservative Kelly
        'max_position_size': 0.05,             # 5% max per position
        'min_position_size': 0.005,            # 0.5% min per position
        'concentration_limit': 0.20,           # 20% max in single sector
    },
    'portfolio_limits': {
        'max_leverage': 1.5,                   # 1.5x max leverage
        'cash_reserve_minimum': 0.10,          # Keep 10% cash
        'max_positions': 20,                   # Maximum number of positions
        'rebalance_threshold': 0.02,           # Rebalance if position drifts 2%
    },
    'stop_losses': {
        'enabled': True,
        'trailing_stop_percent': 0.08,         # 8% trailing stop
        'hard_stop_percent': 0.15,             # 15% hard stop
        'profit_taking_percent': 0.25,         # Take profits at 25%
    },
    'drawdown_controls': {
        'max_daily_loss': 0.03,                # 3% max daily loss
        'max_weekly_loss': 0.08,               # 8% max weekly loss
        'cooling_off_hours': 24,               # Hours to wait after max loss
    }
}

# AI Integration settings
AI_INTEGRATION = {
    'primary_model': 'gpt-4',                  # Primary AI model
    'backup_model': 'claude-3-sonnet',         # Backup model
    'analysis_prompt_template': """
You are a quantitative trading analyst. Analyze this market data and provide trading recommendations.

Current Market Data:
{market_data}

Real-time Signals:
{signals}

Recent News/Social Sentiment:
{sentiment_data}

Provide:
1. Overall market sentiment (bullish/bearish/neutral)
2. Top 3 stock recommendations with confidence levels
3. Risk factors to watch
4. Suggested position sizes
5. Entry/exit strategy

Be concise and actionable. Format as JSON.
""",
    'confidence_threshold': 0.7,               # Min confidence for AI trades
    'max_ai_requests_per_minute': 20,          # Rate limiting
    'analysis_frequency_minutes': 5,           # How often to ask AI
}

# Performance tracking
PERFORMANCE_TRACKING = {
    'benchmark_symbol': 'SPY',
    'target_annual_return': 0.20,              # 20% target return
    'target_sharpe_ratio': 1.5,                # Target Sharpe ratio
    'target_max_drawdown': 0.15,               # 15% max drawdown
    'rebalancing_frequency': 'daily',          # daily, weekly, monthly
    'performance_attribution': True,           # Track signal contribution
}

# Market regimes
MARKET_REGIMES = {
    'vix_thresholds': {
        'low_vol': 15,                         # VIX < 15 = low vol
        'normal_vol': 25,                      # VIX 15-25 = normal
        'high_vol': 40,                        # VIX 25-40 = high vol
        'crisis': 40                           # VIX > 40 = crisis
    },
    'regime_adjustments': {
        'low_vol': {
            'social_weight': 0.5,              # Increase social weight in low vol
            'technical_weight': 0.3,
            'fundamental_weight': 0.2
        },
        'high_vol': {
            'social_weight': 0.2,              # Decrease social weight in high vol
            'technical_weight': 0.5,
            'fundamental_weight': 0.3
        },
        'crisis': {
            'social_weight': 0.1,              # Minimal social weight in crisis
            'technical_weight': 0.7,
            'fundamental_weight': 0.2
        }
    }
}

# Logging configuration
LOGGING_CONFIG = {
    'level': 'INFO',
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'handlers': {
        'file': True,
        'console': True,
        'rotating': True,
        'max_bytes': 10485760,                 # 10MB
        'backup_count': 5
    }
}