"""Real-time earnings monitoring and surprise detection system."""

import yfinance as yf
import asyncio
import aiohttp
import json
from datetime import datetime, timedelta, time
from typing import Dict, List, Optional, Tuple
import logging
from dataclasses import dataclass
import pandas as pd
import numpy as np
from alpha_vantage.fundamentaldata import FundamentalData
from finnhub import Client as FinnhubClient

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from config.api_keys import *
from config.settings import REALTIME_SOURCES

logger = logging.getLogger(__name__)

@dataclass
class EarningsSignal:
    """Earnings signal data structure."""
    ticker: str
    company_name: str
    earnings_date: datetime
    actual_eps: Optional[float]
    estimated_eps: Optional[float]
    surprise_percent: Optional[float]
    actual_revenue: Optional[float]
    estimated_revenue: Optional[float]
    revenue_surprise_percent: Optional[float]
    guidance_update: Optional[str]  # raised, lowered, maintained
    market_reaction: float  # price change %
    pre_earnings_sentiment: float
    signal_strength: float
    timestamp: datetime
    earnings_time: str  # BMO, AMC, unknown

@dataclass
class EarningsCalendar:
    """Earnings calendar entry."""
    ticker: str
    company_name: str
    earnings_date: datetime
    estimated_eps: Optional[float]
    estimated_revenue: Optional[float]
    earnings_time: str
    market_cap: Optional[float]

class EarningsMonitor:
    """Advanced earnings monitoring and surprise detection."""
    
    def __init__(self):
        self.session = None
        self.av_client = self._setup_alpha_vantage()
        self.finnhub_client = self._setup_finnhub()
        self.active_earnings = {}  # ticker -> EarningsSignal
        self.earnings_calendar = {}  # date -> List[EarningsCalendar]
        self.tracked_tickers = self._get_tracked_tickers()
        self.earnings_history = {}  # For pattern analysis
        
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30)
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    def _setup_alpha_vantage(self):
        """Setup Alpha Vantage client for earnings data."""
        try:
            if ALPHA_VANTAGE_KEY:
                return FundamentalData(key=ALPHA_VANTAGE_KEY, output_format='pandas')
            else:
                logger.warning("Alpha Vantage API key not found")
                return None
        except Exception as e:
            logger.error(f"Failed to setup Alpha Vantage client: {e}")
            return None
    
    def _setup_finnhub(self):
        """Setup Finnhub client for earnings data."""
        try:
            if FINNHUB_KEY:
                return FinnhubClient(api_key=FINNHUB_KEY)
            else:
                logger.warning("Finnhub API key not found")
                return None
        except Exception as e:
            logger.error(f"Failed to setup Finnhub client: {e}")
            return None
    
    def _get_tracked_tickers(self) -> List[str]:
        """Get list of tickers to track for earnings."""
        # S&P 500 major components + high-volume names
        sp500_major = [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA', 'BRK.B',
            'UNH', 'JNJ', 'V', 'PG', 'JPM', 'HD', 'MA', 'BAC', 'ABBV', 'PFE',
            'KO', 'AVGO', 'PEP', 'TMO', 'COST', 'WMT', 'DIS', 'ABT', 'DHR',
            'VZ', 'BMY', 'LIN', 'ADBE', 'NFLX', 'CRM', 'ACN', 'NKE', 'MCD',
            'NEE', 'PM', 'CVX', 'MDT', 'QCOM', 'TXN', 'UNP', 'HON', 'LMT',
            'LOW', 'ORCL', 'AMD', 'IBM', 'RTX', 'UPS', 'C', 'AMGN', 'CAT'
        ]
        
        # Add popular meme/retail stocks
        meme_stocks = [
            'GME', 'AMC', 'PLTR', 'RBLX', 'COIN', 'HOOD', 'SOFI', 'WISH',
            'CLOV', 'BB', 'NOK', 'SNDL', 'TLRY', 'RIOT', 'MARA'
        ]
        
        return sp500_major + meme_stocks
    
    async def start_monitoring(self):
        """Start earnings monitoring system."""
        logger.info("📈 Starting earnings monitoring system...")
        
        # Initialize earnings calendar
        await self._update_earnings_calendar()
        
        tasks = [
            self._monitor_earnings_releases(),
            self._track_pre_earnings_setup(),
            self._update_calendar_daily(),
            self._cleanup_old_data()
        ]
        
        await asyncio.gather(*tasks)
    
    async def _update_earnings_calendar(self):
        """Update earnings calendar for next 30 days."""
        try:
            if not self.finnhub_client:
                logger.warning("Finnhub client not available for earnings calendar")
                return
            
            # Get earnings calendar
            start_date = datetime.now().strftime('%Y-%m-%d')
            end_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
            
            earnings_calendar = self.finnhub_client.earnings_calendar(
                _from=start_date, 
                to=end_date
            )
            
            # Process and store calendar data
            for earning in earnings_calendar.get('earningsCalendar', []):
                date_str = earning.get('date')
                if date_str:
                    earnings_date = datetime.strptime(date_str, '%Y-%m-%d')
                    
                    calendar_entry = EarningsCalendar(
                        ticker=earning.get('symbol', ''),
                        company_name='',  # Will fetch separately
                        earnings_date=earnings_date,
                        estimated_eps=earning.get('epsEstimate'),
                        estimated_revenue=earning.get('revenueEstimate'),
                        earnings_time=earning.get('hour', 'unknown'),
                        market_cap=None
                    )
                    
                    if date_str not in self.earnings_calendar:
                        self.earnings_calendar[date_str] = []
                    self.earnings_calendar[date_str].append(calendar_entry)
            
            logger.info(f"Updated earnings calendar with {len(earnings_calendar.get('earningsCalendar', []))} entries")
            
        except Exception as e:
            logger.error(f"Error updating earnings calendar: {e}")
    
    async def _monitor_earnings_releases(self):
        """Monitor for real-time earnings releases."""
        while True:
            try:
                # Check if it's earnings season (market hours or just after)
                if self._is_earnings_time():
                    # Get today's earnings
                    today = datetime.now().strftime('%Y-%m-%d')
                    todays_earnings = self.earnings_calendar.get(today, [])
                    
                    for earnings_entry in todays_earnings:
                        await self._check_earnings_release(earnings_entry)
                
                # Check every 5 minutes during market hours, 30 minutes otherwise
                sleep_time = 300 if self._is_market_hours() else 1800
                await asyncio.sleep(sleep_time)
                
            except Exception as e:
                logger.error(f"Error monitoring earnings releases: {e}")
                await asyncio.sleep(300)
    
    async def _check_earnings_release(self, earnings_entry: EarningsCalendar):
        """Check if earnings have been released and analyze."""
        try:
            ticker = earnings_entry.ticker
            
            # Skip if we've already processed this earnings
            if ticker in self.active_earnings:
                return
            
            # Try to get actual earnings data
            actual_data = await self._fetch_actual_earnings(ticker)
            
            if actual_data:
                # Calculate surprise
                surprise_data = self._calculate_earnings_surprise(earnings_entry, actual_data)
                
                if surprise_data:
                    # Get market reaction
                    market_reaction = await self._get_market_reaction(ticker)
                    
                    # Create earnings signal
                    signal = EarningsSignal(
                        ticker=ticker,
                        company_name=earnings_entry.company_name,
                        earnings_date=earnings_entry.earnings_date,
                        actual_eps=actual_data.get('actual_eps'),
                        estimated_eps=earnings_entry.estimated_eps,
                        surprise_percent=surprise_data.get('eps_surprise_percent'),
                        actual_revenue=actual_data.get('actual_revenue'),
                        estimated_revenue=earnings_entry.estimated_revenue,
                        revenue_surprise_percent=surprise_data.get('revenue_surprise_percent'),
                        guidance_update=actual_data.get('guidance_update'),
                        market_reaction=market_reaction,
                        pre_earnings_sentiment=0.0,  # Will be filled by sentiment analysis
                        signal_strength=self._calculate_signal_strength(surprise_data, market_reaction),
                        timestamp=datetime.now(),
                        earnings_time=earnings_entry.earnings_time
                    )
                    
                    self.active_earnings[ticker] = signal
                    
                    # Send high-priority signal if significant surprise
                    if abs(surprise_data.get('eps_surprise_percent', 0)) > 10:
                        await self._process_earnings_surprise(signal)
                        
        except Exception as e:
            logger.error(f"Error checking earnings release for {earnings_entry.ticker}: {e}")
    
    async def _fetch_actual_earnings(self, ticker: str) -> Optional[Dict]:
        """Fetch actual earnings data from multiple sources."""
        try:
            # Try Yahoo Finance first (free and reliable)
            stock = yf.Ticker(ticker)
            
            # Get quarterly earnings
            quarterly_earnings = stock.quarterly_earnings
            if not quarterly_earnings.empty:
                latest_earnings = quarterly_earnings.iloc[0]
                
                # Get quarterly revenue  
                quarterly_revenue = stock.quarterly_financials
                latest_revenue = None
                if not quarterly_revenue.empty and 'Total Revenue' in quarterly_revenue.index:
                    latest_revenue = quarterly_revenue.loc['Total Revenue'].iloc[0]
                
                return {
                    'actual_eps': latest_earnings.get('Earnings', None),
                    'actual_revenue': latest_revenue,
                    'guidance_update': None  # Will try to extract from news
                }
            
            # Fallback to Finnhub if available
            if self.finnhub_client:
                earnings = self.finnhub_client.company_earnings(ticker, limit=1)
                if earnings:
                    latest = earnings[0]
                    return {
                        'actual_eps': latest.get('actual'),
                        'actual_revenue': None,  # Not always available
                        'guidance_update': None
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Error fetching actual earnings for {ticker}: {e}")
            return None
    
    def _calculate_earnings_surprise(self, earnings_entry: EarningsCalendar, 
                                   actual_data: Dict) -> Optional[Dict]:
        """Calculate earnings surprise percentages."""
        try:
            surprise_data = {}
            
            # EPS surprise
            actual_eps = actual_data.get('actual_eps')
            estimated_eps = earnings_entry.estimated_eps
            
            if actual_eps is not None and estimated_eps is not None:
                eps_surprise = ((actual_eps - estimated_eps) / abs(estimated_eps)) * 100
                surprise_data['eps_surprise_percent'] = eps_surprise
            
            # Revenue surprise
            actual_revenue = actual_data.get('actual_revenue')
            estimated_revenue = earnings_entry.estimated_revenue
            
            if actual_revenue is not None and estimated_revenue is not None:
                revenue_surprise = ((actual_revenue - estimated_revenue) / abs(estimated_revenue)) * 100
                surprise_data['revenue_surprise_percent'] = revenue_surprise
            
            return surprise_data if surprise_data else None
            
        except Exception as e:
            logger.error(f"Error calculating earnings surprise: {e}")
            return None
    
    async def _get_market_reaction(self, ticker: str) -> float:
        """Get immediate market reaction to earnings."""
        try:
            # Get stock data
            stock = yf.Ticker(ticker)
            hist = stock.history(period="2d", interval="1h")
            
            if len(hist) >= 2:
                # Calculate percentage change from pre-earnings to current
                pre_earnings_close = hist['Close'].iloc[-2]
                current_price = hist['Close'].iloc[-1]
                
                reaction = ((current_price - pre_earnings_close) / pre_earnings_close) * 100
                return reaction
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Error getting market reaction for {ticker}: {e}")
            return 0.0
    
    def _calculate_signal_strength(self, surprise_data: Dict, market_reaction: float) -> float:
        """Calculate overall signal strength for earnings."""
        strength = 0.0
        
        # EPS surprise component
        eps_surprise = surprise_data.get('eps_surprise_percent', 0)
        if abs(eps_surprise) > 20:
            strength += 0.4
        elif abs(eps_surprise) > 10:
            strength += 0.3
        elif abs(eps_surprise) > 5:
            strength += 0.2
        
        # Revenue surprise component
        rev_surprise = surprise_data.get('revenue_surprise_percent', 0)
        if abs(rev_surprise) > 10:
            strength += 0.3
        elif abs(rev_surprise) > 5:
            strength += 0.2
        
        # Market reaction alignment
        if eps_surprise > 0 and market_reaction > 0:  # Positive surprise + positive reaction
            strength += 0.3
        elif eps_surprise < 0 and market_reaction < 0:  # Negative surprise + negative reaction
            strength += 0.3
        elif eps_surprise > 0 and market_reaction < 0:  # Positive surprise but negative reaction
            strength += 0.4  # This is interesting - potential oversold opportunity
        
        return min(strength, 1.0)
    
    async def _process_earnings_surprise(self, signal: EarningsSignal):
        """Process significant earnings surprises."""
        surprise_type = "BEAT" if signal.surprise_percent > 0 else "MISS"
        
        logger.warning(f"🎯 EARNINGS {surprise_type}: {signal.ticker} - "
                      f"EPS surprise: {signal.surprise_percent:.1f}%, "
                      f"Market reaction: {signal.market_reaction:.1f}%")
        
        priority_data = {
            'source': 'earnings',
            'priority': 'HIGH',
            'signal': signal,
            'timestamp': datetime.now(),
            'action_required': True
        }
        
        await self._send_to_ai_analysis(priority_data)
    
    async def _track_pre_earnings_setup(self):
        """Track stocks approaching earnings for setup signals."""
        while True:
            try:
                # Look for earnings in next 3 days
                for days_ahead in range(1, 4):
                    check_date = (datetime.now() + timedelta(days=days_ahead)).strftime('%Y-%m-%d')
                    upcoming_earnings = self.earnings_calendar.get(check_date, [])
                    
                    for earnings_entry in upcoming_earnings:
                        await self._analyze_pre_earnings_setup(earnings_entry, days_ahead)
                
                # Check every 4 hours
                await asyncio.sleep(14400)
                
            except Exception as e:
                logger.error(f"Error tracking pre-earnings setup: {e}")
                await asyncio.sleep(3600)
    
    async def _analyze_pre_earnings_setup(self, earnings_entry: EarningsCalendar, days_ahead: int):
        """Analyze pre-earnings setup for potential trades."""
        try:
            ticker = earnings_entry.ticker
            
            # Get options activity if available
            options_activity = await self._get_options_activity(ticker)
            
            # Get recent price action
            price_momentum = await self._get_price_momentum(ticker)
            
            # Get analyst sentiment
            analyst_sentiment = await self._get_analyst_sentiment(ticker)
            
            # Calculate pre-earnings signal strength
            setup_strength = self._calculate_pre_earnings_strength(
                options_activity, price_momentum, analyst_sentiment, days_ahead
            )
            
            if setup_strength > 0.6:
                logger.info(f"📊 Strong pre-earnings setup for {ticker} "
                           f"(earnings in {days_ahead} days): {setup_strength:.2f}")
                
                setup_data = {
                    'source': 'pre_earnings',
                    'ticker': ticker,
                    'earnings_date': earnings_entry.earnings_date,
                    'days_until_earnings': days_ahead,
                    'setup_strength': setup_strength,
                    'options_activity': options_activity,
                    'price_momentum': price_momentum,
                    'analyst_sentiment': analyst_sentiment,
                    'timestamp': datetime.now()
                }
                
                await self._send_to_ai_analysis(setup_data)
                
        except Exception as e:
            logger.error(f"Error analyzing pre-earnings setup for {earnings_entry.ticker}: {e}")
    
    async def _get_options_activity(self, ticker: str) -> Dict:
        """Get options activity data for ticker."""
        try:
            # This would integrate with options data provider
            # For now, return placeholder structure
            return {
                'put_call_ratio': 0.0,
                'implied_volatility': 0.0,
                'unusual_activity': False,
                'volume_ratio': 1.0
            }
        except Exception as e:
            logger.error(f"Error getting options activity for {ticker}: {e}")
            return {}
    
    async def _get_price_momentum(self, ticker: str) -> Dict:
        """Get price momentum indicators."""
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="30d")
            
            if len(hist) < 10:
                return {}
            
            # Calculate momentum indicators
            current_price = hist['Close'].iloc[-1]
            price_5d = hist['Close'].iloc[-5] if len(hist) >= 5 else current_price
            price_20d = hist['Close'].iloc[-20] if len(hist) >= 20 else current_price
            
            momentum_5d = ((current_price - price_5d) / price_5d) * 100
            momentum_20d = ((current_price - price_20d) / price_20d) * 100
            
            # Volume analysis
            avg_volume = hist['Volume'].mean()
            recent_volume = hist['Volume'].iloc[-5:].mean()
            volume_ratio = recent_volume / avg_volume
            
            return {
                'momentum_5d': momentum_5d,
                'momentum_20d': momentum_20d,
                'volume_ratio': volume_ratio,
                'current_price': current_price
            }
            
        except Exception as e:
            logger.error(f"Error getting price momentum for {ticker}: {e}")
            return {}
    
    async def _get_analyst_sentiment(self, ticker: str) -> Dict:
        """Get analyst sentiment and estimates."""
        try:
            if self.finnhub_client:
                # Get analyst recommendations
                recommendations = self.finnhub_client.recommendation_trends(ticker)
                
                if recommendations:
                    latest = recommendations[0]
                    
                    # Calculate sentiment score
                    total_ratings = (latest.get('strongBuy', 0) + latest.get('buy', 0) + 
                                   latest.get('hold', 0) + latest.get('sell', 0) + 
                                   latest.get('strongSell', 0))
                    
                    if total_ratings > 0:
                        bullish_ratings = latest.get('strongBuy', 0) + latest.get('buy', 0)
                        sentiment_score = bullish_ratings / total_ratings
                        
                        return {
                            'sentiment_score': sentiment_score,
                            'total_analysts': total_ratings,
                            'strong_buy': latest.get('strongBuy', 0),
                            'buy': latest.get('buy', 0),
                            'hold': latest.get('hold', 0),
                            'sell': latest.get('sell', 0),
                            'strong_sell': latest.get('strongSell', 0)
                        }
            
            return {}
            
        except Exception as e:
            logger.error(f"Error getting analyst sentiment for {ticker}: {e}")
            return {}
    
    def _calculate_pre_earnings_strength(self, options_activity: Dict, 
                                       price_momentum: Dict, analyst_sentiment: Dict,
                                       days_ahead: int) -> float:
        """Calculate pre-earnings setup strength."""
        strength = 0.0
        
        # Price momentum component
        momentum_5d = price_momentum.get('momentum_5d', 0)
        if abs(momentum_5d) > 5:
            strength += 0.2
        
        # Volume activity
        volume_ratio = price_momentum.get('volume_ratio', 1.0)
        if volume_ratio > 1.5:
            strength += 0.2
        
        # Analyst sentiment
        sentiment_score = analyst_sentiment.get('sentiment_score', 0.5)
        if sentiment_score > 0.7:
            strength += 0.3
        elif sentiment_score < 0.3:
            strength += 0.3  # Contrarian opportunity
        
        # Time decay (closer to earnings = higher strength)
        time_factor = max(0.1, (4 - days_ahead) / 3)
        strength *= time_factor
        
        return min(strength, 1.0)
    
    def _is_earnings_time(self) -> bool:
        """Check if it's a time when earnings are typically released."""
        now = datetime.now()
        current_time = now.time()
        
        # Before market open (6:00-9:30 AM ET) or after market close (4:00-8:00 PM ET)
        bmo_start = time(6, 0)
        market_open = time(9, 30)
        market_close = time(16, 0)
        amc_end = time(20, 0)
        
        return (bmo_start <= current_time <= market_open) or (market_close <= current_time <= amc_end)
    
    def _is_market_hours(self) -> bool:
        """Check if it's during market hours."""
        now = datetime.now()
        current_time = now.time()
        
        # Market hours: 9:30 AM - 4:00 PM ET
        market_open = time(9, 30)
        market_close = time(16, 0)
        
        return market_open <= current_time <= market_close and now.weekday() < 5
    
    async def _update_calendar_daily(self):
        """Update earnings calendar daily."""
        while True:
            try:
                # Update calendar at 6 AM daily
                now = datetime.now()
                next_update = now.replace(hour=6, minute=0, second=0, microsecond=0)
                if now >= next_update:
                    next_update += timedelta(days=1)
                
                sleep_seconds = (next_update - now).total_seconds()
                await asyncio.sleep(sleep_seconds)
                
                await self._update_earnings_calendar()
                
            except Exception as e:
                logger.error(f"Error in daily calendar update: {e}")
                await asyncio.sleep(3600)
    
    async def _cleanup_old_data(self):
        """Clean up old earnings data."""
        while True:
            try:
                # Remove earnings older than 7 days
                cutoff_date = datetime.now() - timedelta(days=7)
                
                self.active_earnings = {
                    ticker: signal for ticker, signal in self.active_earnings.items()
                    if signal.timestamp > cutoff_date
                }
                
                # Clean up old calendar entries
                old_dates = [
                    date_str for date_str in self.earnings_calendar.keys()
                    if datetime.strptime(date_str, '%Y-%m-%d') < cutoff_date
                ]
                
                for date_str in old_dates:
                    del self.earnings_calendar[date_str]
                
                await asyncio.sleep(86400)  # Clean up daily
                
            except Exception as e:
                logger.error(f"Error in cleanup: {e}")
                await asyncio.sleep(86400)
    
    async def _send_to_ai_analysis(self, signal_data: Dict):
        """Send signal to AI analysis pipeline."""
        logger.info(f"📤 Sending earnings signal to AI analysis: {signal_data.get('ticker', 'unknown')}")
        # This will integrate with your AI analysis system
        pass
    
    def get_upcoming_earnings(self, days_ahead: int = 7) -> List[EarningsCalendar]:
        """Get upcoming earnings for next N days."""
        upcoming = []
        
        for i in range(days_ahead):
            check_date = (datetime.now() + timedelta(days=i)).strftime('%Y-%m-%d')
            day_earnings = self.earnings_calendar.get(check_date, [])
            upcoming.extend(day_earnings)
        
        return upcoming
    
    def get_earnings_signal(self, ticker: str) -> Optional[EarningsSignal]:
        """Get latest earnings signal for ticker."""
        return self.active_earnings.get(ticker)

# Global instance
earnings_monitor = EarningsMonitor()