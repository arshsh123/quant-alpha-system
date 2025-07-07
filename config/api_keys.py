"""Updated API Keys configuration with all your actual keys."""

import os
from dotenv import load_dotenv

load_dotenv()

# ============================================================================
# TWITTER API (Your core edge - social sentiment)
# ============================================================================
TWITTER_API_KEY = os.getenv('TWITTER_API_KEY')
TWITTER_API_SECRET = os.getenv('TWITTER_API_SECRET')
TWITTER_BEARER_TOKEN = os.getenv('TWITTER_BEARER_TOKEN')
TWITTER_ACCESS_TOKEN = os.getenv('TWITTER_ACCESS_TOKEN')
TWITTER_ACCESS_TOKEN_SECRET = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')

# ============================================================================
# REDDIT API (Social sentiment enhancement)
# ============================================================================
REDDIT_CLIENT_ID = os.getenv('REDDIT_CLIENT_ID')
REDDIT_CLIENT_SECRET = os.getenv('REDDIT_CLIENT_SECRET')
REDDIT_USER_AGENT = os.getenv('REDDIT_USER_AGENT', 'QuantAlphaBot/1.0')

# ============================================================================
# FINANCIAL DATA APIs
# ============================================================================
# Financial Modeling Prep - 250 requests/day FREE
FMP_API_KEY = os.getenv('FMP_API_KEY')

# Alpha Vantage - 25 requests/day FREE  
ALPHA_VANTAGE_KEY = os.getenv('ALPHA_VANTAGE_KEY')

# ============================================================================
# AI INTEGRATION
# ============================================================================
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')

# ============================================================================
# PAPER TRADING BROKER (Alpaca - FREE)
# ============================================================================
ALPACA_API_KEY = os.getenv('ALPACA_API_KEY')
ALPACA_SECRET_KEY = os.getenv('ALPACA_SECRET_KEY')
ALPACA_BASE_URL = os.getenv('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')  # Paper trading

# ============================================================================
# TRADING CONFIGURATION
# ============================================================================
PAPER_TRADING_MODE = os.getenv('PAPER_TRADING_MODE', 'true').lower() == 'true'
LIVE_TRADING_ENABLED = os.getenv('LIVE_TRADING_ENABLED', 'false').lower() == 'true'
RISK_LIMIT_PER_TRADE = float(os.getenv('RISK_LIMIT_PER_TRADE', '0.02'))
MAX_DAILY_TRADES = int(os.getenv('MAX_DAILY_TRADES', '50'))

