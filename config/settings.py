"""Advanced configuration settings for real-time quant system."""

import os
from pathlib import Path
from typing import Dict, List
import pytz

# ============================================================================
# PROJECT STRUCTURE
# ============================================================================
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = PROJECT_ROOT / "logs"
CACHE_DIR = PROJECT_ROOT / "cache"

# Ensure directories exist
for directory in [DATA_DIR, LOGS_DIR, CACHE_DIR]:
    directory.mkdir(exist_ok=True)

# ============================================================================
# TRADING SCHEDULE (Eastern Time)
# ============================================================================
TRADING_TIMEZONE = pytz.timezone('US/Eastern')
MARKET_OPEN_TIME = "09:30"
MARKET_CLOSE_TIME = "16:00"
PREMARKET_START = "04:00"
AFTERHOURS_END = "20:00"

# ============================================================================
# SIGNAL SOURCES CONFIGURATION
# ============================================================================
REALTIME_SOURCES = {
    'twitter': {
        'enabled': True,
        'priority': 1,
        'weight': 0.40,                        # 40% of social sentiment
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
        'weight': 0.20,                        # 20% news sentiment
        'refresh_seconds': 30,
        'sources': [
            'https://feeds.reuters.com/reuters/businessNews',
            'https://feeds.finance.yahoo.com/rss/2.0/headline',
            'https://feeds.bloomberg.com/markets/news.rss',
            'https://www.cnbc.com/id/100003114/device/rss/rss.html'
        ]
    },
    'earnings': {
        'enabled': True,
        'priority': 1,
        'weight': 0.25,                        # 25% earnings signals
        'refresh_seconds': 300,                # Check every 5 minutes
        'pre_earnings_days': 3,                # Track 3 days before earnings
        'surprise_threshold': 5.0              # 5% surprise threshold
    },
    'options_flow': {
        'enabled': True,
        'priority': 2,
        'weight': 0.10,                        # 10% options flow
        'refresh_seconds': 600,                # Check every 10 minutes
        'volume_threshold_multiplier': 2.0,    # 2x normal volume = unusual
        'smart_money_threshold': 0.7           # 70% confidence for smart money
    },
    'technical': {
        'enabled': True,
        'priority': 3,
        'weight': 0.05,                        # 5% technical momentum
        'refresh_seconds': 900,                # Check every 15 minutes
        'lookback_days': 20                    # 20-day technical analysis
    }
}

# ============================================================================
# SIGNAL PROCESSING ENGINE
# ============================================================================
SIGNAL_PROCESSING = {
    # Time windows
    'sentiment_window_minutes': 15,           # Rolling sentiment analysis
    'momentum_lookback_days': 5,              # Price momentum lookback
    'signal_decay_half_life_hours': 4,        # How fast signals lose strength
    
    # Signal quality filters
    'min_signal_confidence': 0.60,            # 60% min confidence to act
    'max_signals_per_stock': 3,               # Prevent signal overload
    'conflict_penalty_factor': 0.20,          # 20% penalty for conflicting signals
    
    # Market activity thresholds
    'volume_threshold_multiplier': 2.0,       # 2x normal volume = significant
    'gap_threshold_percent': 2.0,             # 2% gap = significant
    'volatility_spike_threshold': 1.5,        # 1.5x normal volatility
    
    # Dynamic weighting parameters
    'confidence_weight_factor': 0.3,          # How much confidence affects weights
    'performance_weight_factor': 0.2,         # How much past performance affects weights
    'regime_weight_factor': 0.3               # How much market regime affects weights
}

# ============================================================================
# RISK MANAGEMENT SYSTEM
# ============================================================================
RISK_MANAGEMENT = {
    'position_sizing': {
        'method': 'kelly_criterion',           # kelly_criterion, equal_weight, vol_target
        'kelly_fraction': 0.25,                # Conservative 25% Kelly
        'max_position_size': 0.05,             # 5% max per position
        'min_position_size': 0.005,            # 0.5% min per position
        'concentration_limit': 0.20,           # 20% max in single sector
        'correlation_limit': 0.70,             # Don't hold correlated positions
    },
    'portfolio_limits': {
        'max_leverage': 1.5,                   # 1.5x max leverage
        'cash_reserve_minimum': 0.10,          # Keep 10% cash
        'max_positions': 20,                   # Maximum 20 positions
        'rebalance_threshold': 0.02,           # Rebalance if position drifts 2%
        'sector_concentration_limit': 0.30,    # 30% max in one sector
    },
    'stop_losses': {
        'enabled': True,
        'trailing_stop_percent': 0.08,         # 8% trailing stop
        'hard_stop_percent': 0.15,             # 15% hard stop loss
        'profit_taking_percent': 0.25,         # Take profits at 25% gain
        'time_stop_days': 14,                  # Close position after 14 days
    },
    'drawdown_controls': {
        'max_daily_loss': 0.03,                # 3% max daily portfolio loss
        'max_weekly_loss': 0.08,               # 8% max weekly portfolio loss
        'max_monthly_loss': 0.15,              # 15% max monthly portfolio loss
        'cooling_off_hours': 24,               # Hours to wait after max loss hit
        'reduce_size_after_loss': True,        # Reduce position sizes after losses
    }
}

# ============================================================================
# MARKET REGIME DETECTION
# ============================================================================
MARKET_REGIMES = {
    'vix_thresholds': {
        'low_vol': 15,                         # VIX < 15 = low volatility regime
        'normal_vol': 25,                      # VIX 15-25 = normal regime  
        'high_vol': 40,                        # VIX 25-40 = high volatility
        'crisis': 40                           # VIX > 40 = crisis mode
    },
    'regime_adjustments': {
        'low_vol': {
            'social_weight': 0.50,              # Higher social weight in calm markets
            'technical_weight': 0.25,
            'fundamental_weight': 0.25
        },
        'normal_vol': {
            'social_weight': 0.40,              # Balanced approach
            'technical_weight': 0.30,
            'fundamental_weight': 0.30
        },
        'high_vol': {
            'social_weight': 0.20,              # Reduce social weight in volatile markets
            'technical_weight': 0.50,
            'fundamental_weight': 0.30
        },
        'crisis': {
            'social_weight': 0.10,              # Minimal social weight in crisis
            'technical_weight': 0.60,
            'fundamental_weight': 0.30
        }
    },
    'regime_detection': {
        'lookback_days': 10,                   # Days to analyze for regime
        'change_threshold': 0.20,              # 20% change triggers regime shift
        'confirmation_days': 2                 # Days to confirm regime change
    }
}

# ============================================================================
# AI INTEGRATION SETTINGS
# ============================================================================
AI_INTEGRATION = {
    'enabled': True,                           # Enable AI analysis
    'primary_model': 'gpt-4',                 # Primary AI model
    'backup_model': 'claude-3-sonnet',        # Backup model
    'confidence_threshold': 0.70,             # 70% min confidence for AI trades
    'max_requests_per_minute': 20,            # Rate limiting
    'analysis_frequency_minutes': 5,          # Analyze every 5 minutes
    'use_for_conflicts': True,                # Use AI to resolve signal conflicts
    'use_for_regime_detection': True,         # Use AI for market regime analysis
    
    'analysis_prompt_template': """
You are an expert quantitative trading analyst. Analyze the provided market data and signals.

MARKET DATA:
{market_data}

ACTIVE SIGNALS:
{signals}

SENTIMENT DATA:
{sentiment_data}

CURRENT REGIME: {market_regime}

Provide a JSON response with:
1. overall_sentiment: "bullish"|"bearish"|"neutral"
2. top_recommendations: [{"ticker": "AAPL", "action": "buy"|"sell"|"hold", "confidence": 0.0-1.0}]
3. risk_factors: ["factor1", "factor2"]
4. position_sizes: {"AAPL": 0.05}
5. reasoning: "brief explanation"

Be concise and actionable. Focus on high-conviction trades only.
"""
}

# ============================================================================
# PERFORMANCE TRACKING
# ============================================================================
PERFORMANCE_TRACKING = {
    'enabled': True,
    'benchmark_symbol': 'SPY',                # Compare performance to SPY
    'target_annual_return': 0.20,             # 20% annual return target
    'target_sharpe_ratio': 1.5,               # 1.5 Sharpe ratio target
    'target_max_drawdown': 0.15,              # 15% max drawdown target
    'target_win_rate': 0.55,                  # 55% win rate target
    
    'rebalancing': {
        'frequency': 'daily',                  # daily, weekly, monthly
        'drift_threshold': 0.05,               # 5% drift triggers rebalance
        'min_rebalance_amount': 0.01           # 1% minimum rebalance
    },
    
    'attribution': {
        'track_by_signal_type': True,          # Track performance by signal type
        'track_by_ticker': True,               # Track performance by ticker
        'track_by_sector': True,               # Track performance by sector
        'track_by_regime': True                # Track performance by market regime
    }
}

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================
LOGGING_CONFIG = {
    'level': 'INFO',                          # INFO, DEBUG, WARNING, ERROR
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'date_format': '%Y-%m-%d %H:%M:%S',
    
    'handlers': {
        'console': {
            'enabled': True,
            'level': 'INFO'
        },
        'file': {
            'enabled': True,
            'level': 'INFO',
            'filename': 'logs/quant_alpha_system.log'
        },
        'rotating': {
            'enabled': True,
            'max_bytes': 10485760,              # 10MB per file
            'backup_count': 5,                  # Keep 5 backup files
            'filename': 'logs/quant_alpha_rotating.log'
        },
        'error_file': {
            'enabled': True,
            'level': 'ERROR',
            'filename': 'logs/errors.log'
        }
    },
    
    'loggers': {
        'trading_signals': 'DEBUG',            # Detailed signal logging
        'risk_management': 'INFO',             # Risk management events
        'performance': 'INFO',                 # Performance tracking
        'api_calls': 'WARNING'                 # Only log API issues
    }
}

# ============================================================================
# SYSTEM MONITORING
# ============================================================================
MONITORING = {
    'health_check_interval_seconds': 300,     # Check system health every 5 minutes
    'max_memory_usage_percent': 80,           # Alert if memory usage > 80%
    'max_cpu_usage_percent': 90,              # Alert if CPU usage > 90%
    'api_timeout_seconds': 30,                # 30 second API timeout
    'max_consecutive_errors': 5,              # Max errors before component restart
    'component_restart_delay_seconds': 60,    # Wait 60s before restarting component
    
    'alerts': {
        'enabled': True,
        'email_alerts': False,                 # Set to True with email config
        'log_alerts': True,                    # Log important alerts
        'critical_alerts_only': True          # Only critical system alerts
    }
}

# ============================================================================
# DEVELOPMENT/TESTING SETTINGS
# ============================================================================
DEVELOPMENT = {
    'mode': 'production',                     # 'development', 'testing', 'production'
    'paper_trading': True,                    # Always use paper trading initially
    'simulation_mode': False,                 # Set to True for backtesting
    'fast_mode': False,                       # Skip some checks for faster testing
    'debug_signals': False,                   # Extra debug output for signals
    'save_all_signals': False,                # Save all signals for analysis
    'mock_api_calls': False                   # Mock API calls for testing
}