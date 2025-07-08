"""Real-time options flow monitoring for unusual activity detection."""

import yfinance as yf
import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
from dataclasses import dataclass
import warnings

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from config.settings import REALTIME_SOURCES

warnings.filterwarnings('ignore')
logger = logging.getLogger(__name__)

@dataclass
class OptionsSignal:
    """Options flow signal data structure."""
    ticker: str
    option_type: str  # 'call' or 'put'
    strike: float
    expiry: str
    volume: int
    open_interest: int
    premium: float
    unusual_activity_score: float
    smart_money_indicator: float
    flow_sentiment: str  # 'bullish', 'bearish', 'neutral'
    signal_strength: float
    timestamp: datetime
    put_call_ratio: float
    iv_rank: float  # Implied volatility rank

class OptionsMonitor:
    """Real-time options flow monitoring system."""
    
    def __init__(self):
        self.active_signals = []
        self.tracked_tickers = self._get_tracked_tickers()
        self.options_cache = {}  # Cache options data to avoid excessive API calls
        self.historical_volume = {}  # Track normal volume patterns
        
    def _get_tracked_tickers(self) -> List[str]:
        """Get list of tickers to monitor for options activity."""
        # Focus on liquid options with high activity
        liquid_tickers = [
            # Major tech
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA',
            # ETFs with heavy options activity
            'SPY', 'QQQ', 'IWM', 'XLF', 'XLE', 'XLK',
            # High-volume individual names
            'AMD', 'NFLX', 'CRM', 'UBER', 'PYPL', 'SQ', 'ROKU',
            # Meme stocks with active options
            'GME', 'AMC', 'PLTR', 'BB', 'NOK'
        ]
        return liquid_tickers
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        pass
    
    async def start_monitoring(self):
        """Start options flow monitoring."""
        logger.info("📊 Starting options flow monitoring...")
        
        tasks = [
            self._monitor_unusual_activity(),
            self._track_put_call_ratios(),
            self._detect_smart_money_flow(),
            self._cleanup_old_signals()
        ]
        
        await asyncio.gather(*tasks)
    
    async def _monitor_unusual_activity(self):
        """Monitor for unusual options activity."""
        while True:
            try:
                for ticker in self.tracked_tickers[:10]:  # Limit to avoid rate limits
                    try:
                        unusual_signals = await self._analyze_options_activity(ticker)
                        
                        for signal in unusual_signals:
                            if signal.unusual_activity_score > 0.6:
                                await self._process_unusual_activity_signal(signal)
                                self.active_signals.append(signal)
                        
                        # Small delay to avoid overwhelming APIs
                        await asyncio.sleep(2)
                        
                    except Exception as e:
                        logger.debug(f"Error analyzing options for {ticker}: {e}")
                        continue
                
                # Check every 10 minutes (options data doesn't change as frequently)
                await asyncio.sleep(600)
                
            except Exception as e:
                logger.error(f"Error in options monitoring loop: {e}")
                await asyncio.sleep(300)
    
    async def _analyze_options_activity(self, ticker: str) -> List[OptionsSignal]:
        """Analyze options activity for a specific ticker."""
        try:
            stock = yf.Ticker(ticker)
            
            # Get options chain
            options_dates = stock.options
            if not options_dates:
                return []
            
            # Focus on near-term options (next 2 expiration dates)
            near_term_dates = options_dates[:2]
            signals = []
            
            for exp_date in near_term_dates:
                try:
                    options_chain = stock.option_chain(exp_date)
                    calls = options_chain.calls
                    puts = options_chain.puts
                    
                    # Analyze calls
                    call_signals = self._analyze_options_data(ticker, calls, 'call', exp_date)
                    signals.extend(call_signals)
                    
                    # Analyze puts
                    put_signals = self._analyze_options_data(ticker, puts, 'put', exp_date)
                    signals.extend(put_signals)
                    
                except Exception as e:
                    logger.debug(f"Error getting options chain for {ticker} {exp_date}: {e}")
                    continue
            
            return signals
            
        except Exception as e:
            logger.debug(f"Error analyzing options activity for {ticker}: {e}")
            return []
    
    def _analyze_options_data(self, ticker: str, options_df: pd.DataFrame, 
                            option_type: str, expiry: str) -> List[OptionsSignal]:
        """Analyze options data for unusual activity."""
        if options_df.empty:
            return []
        
        signals = []
        
        try:
            # Calculate volume metrics
            options_df['volume'] = options_df['volume'].fillna(0)
            options_df['openInterest'] = options_df['openInterest'].fillna(0)
            
            # Filter out low-volume options
            active_options = options_df[options_df['volume'] > 10]
            
            if active_options.empty:
                return []
            
            # Calculate unusual activity metrics
            avg_volume = active_options['volume'].mean()
            volume_threshold = avg_volume * 2  # 2x average volume
            
            # Find unusual volume
            unusual_volume = active_options[active_options['volume'] > volume_threshold]
            
            for idx, option in unusual_volume.iterrows():
                try:
                    # Calculate activity scores
                    volume_ratio = option['volume'] / max(avg_volume, 1)
                    oi_ratio = option['volume'] / max(option['openInterest'], 1)
                    
                    # Unusual activity score
                    unusual_activity_score = min(
                        (volume_ratio - 1) * 0.3 + 
                        min(oi_ratio, 5) * 0.2,  # Cap OI ratio impact
                        1.0
                    )
                    
                    # Smart money indicator (higher for ITM/ATM options with high premium)
                    current_price = self._get_current_price(ticker)
                    if current_price is None:
                        continue
                    
                    strike = option['strike']
                    if option_type == 'call':
                        moneyness = current_price / strike
                    else:
                        moneyness = strike / current_price
                    
                    # Smart money prefers ATM/slightly OTM options
                    smart_money_indicator = max(0, 1 - abs(moneyness - 1) * 2)
                    
                    # Premium size (larger premiums suggest institutional activity)
                    premium = option['lastPrice'] * option['volume'] * 100  # Contract multiplier
                    premium_score = min(premium / 50000, 1.0)  # Normalize to $50k
                    
                    smart_money_indicator = (smart_money_indicator * 0.6 + premium_score * 0.4)
                    
                    # Flow sentiment
                    if option_type == 'call':
                        flow_sentiment = 'bullish' if unusual_activity_score > 0.5 else 'neutral'
                    else:
                        flow_sentiment = 'bearish' if unusual_activity_score > 0.5 else 'neutral'
                    
                    # Signal strength
                    signal_strength = (unusual_activity_score * 0.6 + smart_money_indicator * 0.4)
                    
                    # Only create signal if it meets minimum thresholds
                    if signal_strength > 0.3:
                        # Calculate put/call ratio for context
                        put_call_ratio = self._calculate_put_call_ratio(ticker)
                        
                        # IV rank (simplified - would need historical IV data for accurate calculation)
                        iv_rank = min(option.get('impliedVolatility', 0.3) / 0.5, 1.0)
                        
                        signal = OptionsSignal(
                            ticker=ticker,
                            option_type=option_type,
                            strike=strike,
                            expiry=expiry,
                            volume=int(option['volume']),
                            open_interest=int(option['openInterest']),
                            premium=premium,
                            unusual_activity_score=unusual_activity_score,
                            smart_money_indicator=smart_money_indicator,
                            flow_sentiment=flow_sentiment,
                            signal_strength=signal_strength,
                            timestamp=datetime.now(),
                            put_call_ratio=put_call_ratio,
                            iv_rank=iv_rank
                        )
                        
                        signals.append(signal)
                        
                except Exception as e:
                    logger.debug(f"Error processing option: {e}")
                    continue
            
        except Exception as e:
            logger.debug(f"Error in options data analysis: {e}")
        
        return signals
    
    def _get_current_price(self, ticker: str) -> Optional[float]:
        """Get current stock price."""
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1d")
            if not hist.empty:
                return hist['Close'].iloc[-1]
            return None
        except:
            return None
    
    def _calculate_put_call_ratio(self, ticker: str) -> float:
        """Calculate put/call ratio for the ticker."""
        try:
            if ticker not in self.options_cache:
                return 1.0  # Neutral ratio
            
            # This would require more sophisticated data
            # For now, return a simplified calculation
            return 1.0
            
        except Exception:
            return 1.0
    
    async def _track_put_call_ratios(self):
        """Track put/call ratios for market sentiment."""
        while True:
            try:
                for ticker in self.tracked_tickers[:5]:  # Sample subset
                    try:
                        ratio = self._calculate_detailed_put_call_ratio(ticker)
                        
                        # Store in cache for other methods to use
                        if ticker not in self.options_cache:
                            self.options_cache[ticker] = {}
                        self.options_cache[ticker]['put_call_ratio'] = ratio
                        self.options_cache[ticker]['last_updated'] = datetime.now()
                        
                    except Exception as e:
                        logger.debug(f"Error calculating P/C ratio for {ticker}: {e}")
                
                await asyncio.sleep(1800)  # Update every 30 minutes
                
            except Exception as e:
                logger.error(f"Error in put/call ratio tracking: {e}")
                await asyncio.sleep(1800)
    
    def _calculate_detailed_put_call_ratio(self, ticker: str) -> float:
        """Calculate detailed put/call ratio."""
        try:
            stock = yf.Ticker(ticker)
            options_dates = stock.options
            
            if not options_dates:
                return 1.0
            
            total_call_volume = 0
            total_put_volume = 0
            
            # Look at first 2 expiration dates
            for exp_date in options_dates[:2]:
                try:
                    options_chain = stock.option_chain(exp_date)
                    
                    # Sum call volumes
                    calls = options_chain.calls
                    if not calls.empty:
                        total_call_volume += calls['volume'].fillna(0).sum()
                    
                    # Sum put volumes
                    puts = options_chain.puts
                    if not puts.empty:
                        total_put_volume += puts['volume'].fillna(0).sum()
                        
                except Exception:
                    continue
            
            if total_call_volume == 0:
                return 10.0  # Very bearish if no call activity
            
            return total_put_volume / total_call_volume
            
        except Exception:
            return 1.0
    
    async def _detect_smart_money_flow(self):
        """Detect potential smart money/institutional flow."""
        while True:
            try:
                # Look for patterns that suggest institutional activity
                smart_money_signals = []
                
                for ticker in self.tracked_tickers[:8]:
                    try:
                        signals = await self._analyze_smart_money_patterns(ticker)
                        smart_money_signals.extend(signals)
                        
                    except Exception as e:
                        logger.debug(f"Error analyzing smart money for {ticker}: {e}")
                
                # Process significant smart money signals
                for signal in smart_money_signals:
                    if signal.smart_money_indicator > 0.7:
                        await self._process_smart_money_signal(signal)
                
                await asyncio.sleep(900)  # Check every 15 minutes
                
            except Exception as e:
                logger.error(f"Error in smart money detection: {e}")
                await asyncio.sleep(900)
    
    async def _analyze_smart_money_patterns(self, ticker: str) -> List[OptionsSignal]:
        """Analyze patterns that suggest smart money activity."""
        try:
            stock = yf.Ticker(ticker)
            options_dates = stock.options
            
            if not options_dates:
                return []
            
            smart_signals = []
            current_price = self._get_current_price(ticker)
            
            if current_price is None:
                return []
            
            for exp_date in options_dates[:3]:  # Check first 3 expiration dates
                try:
                    options_chain = stock.option_chain(exp_date)
                    
                    # Look for smart money indicators in calls
                    calls = options_chain.calls
                    if not calls.empty:
                        smart_call_signals = self._identify_smart_money_options(
                            ticker, calls, 'call', exp_date, current_price
                        )
                        smart_signals.extend(smart_call_signals)
                    
                    # Look for smart money indicators in puts
                    puts = options_chain.puts
                    if not puts.empty:
                        smart_put_signals = self._identify_smart_money_options(
                            ticker, puts, 'put', exp_date, current_price
                        )
                        smart_signals.extend(smart_put_signals)
                        
                except Exception:
                    continue
            
            return smart_signals
            
        except Exception as e:
            logger.debug(f"Error analyzing smart money patterns for {ticker}: {e}")
            return []
    
    def _identify_smart_money_options(self, ticker: str, options_df: pd.DataFrame, 
                                    option_type: str, expiry: str, current_price: float) -> List[OptionsSignal]:
        """Identify options that show smart money characteristics."""
        smart_signals = []
        
        try:
            if options_df.empty:
                return []
            
            # Fill NaN values
            options_df['volume'] = options_df['volume'].fillna(0)
            options_df['openInterest'] = options_df['openInterest'].fillna(0)
            options_df['lastPrice'] = options_df['lastPrice'].fillna(0)
            
            # Smart money indicators:
            # 1. High volume relative to open interest (new positions)
            # 2. Large premium transactions
            # 3. ATM or slightly OTM options
            # 4. Longer-dated options (30-90 days)
            
            for idx, option in options_df.iterrows():
                try:
                    volume = option['volume']
                    open_interest = max(option['openInterest'], 1)
                    premium = option['lastPrice']
                    strike = option['strike']
                    
                    # Skip low activity options
                    if volume < 20 or premium < 0.10:
                        continue
                    
                    # Calculate smart money indicators
                    
                    # 1. Volume to OI ratio (new money coming in)
                    vol_oi_ratio = volume / open_interest
                    vol_score = min(vol_oi_ratio / 2, 1.0)  # Normalize
                    
                    # 2. Premium size (institutional size)
                    total_premium = premium * volume * 100  # Contract multiplier
                    premium_score = min(total_premium / 100000, 1.0)  # $100k normalize
                    
                    # 3. Strike selection (smart money prefers efficiency)
                    if option_type == 'call':
                        moneyness = strike / current_price  # For calls
                        # Prefer strikes 0.95 to 1.10 (ATM to slightly OTM)
                        if 0.95 <= moneyness <= 1.10:
                            strike_score = 1.0
                        elif 0.90 <= moneyness <= 1.15:
                            strike_score = 0.7
                        else:
                            strike_score = 0.3
                    else:  # puts
                        moneyness = current_price / strike  # For puts
                        # Prefer strikes 0.95 to 1.10 (ATM to slightly OTM)
                        if 0.95 <= moneyness <= 1.10:
                            strike_score = 1.0
                        elif 0.90 <= moneyness <= 1.15:
                            strike_score = 0.7
                        else:
                            strike_score = 0.3
                    
                    # 4. Time to expiration (smart money prefers 30-90 days)
                    try:
                        exp_datetime = datetime.strptime(expiry, '%Y-%m-%d')
                        days_to_exp = (exp_datetime - datetime.now()).days
                        
                        if 30 <= days_to_exp <= 90:
                            time_score = 1.0
                        elif 15 <= days_to_exp <= 120:
                            time_score = 0.7
                        else:
                            time_score = 0.3
                    except:
                        time_score = 0.5
                    
                    # Combined smart money indicator
                    smart_money_indicator = (
                        vol_score * 0.3 +
                        premium_score * 0.3 +
                        strike_score * 0.25 +
                        time_score * 0.15
                    )
                    
                    # Unusual activity score
                    unusual_activity_score = min(vol_score + premium_score * 0.5, 1.0)
                    
                    # Only flag if it meets smart money thresholds
                    if smart_money_indicator > 0.6 and unusual_activity_score > 0.4:
                        
                        # Determine flow sentiment
                        if option_type == 'call':
                            flow_sentiment = 'bullish'
                        else:
                            flow_sentiment = 'bearish'
                        
                        # Calculate signal strength
                        signal_strength = (smart_money_indicator * 0.7 + unusual_activity_score * 0.3)
                        
                        signal = OptionsSignal(
                            ticker=ticker,
                            option_type=option_type,
                            strike=strike,
                            expiry=expiry,
                            volume=int(volume),
                            open_interest=int(open_interest),
                            premium=total_premium,
                            unusual_activity_score=unusual_activity_score,
                            smart_money_indicator=smart_money_indicator,
                            flow_sentiment=flow_sentiment,
                            signal_strength=signal_strength,
                            timestamp=datetime.now(),
                            put_call_ratio=self._calculate_put_call_ratio(ticker),
                            iv_rank=min(option.get('impliedVolatility', 0.3) / 0.5, 1.0)
                        )
                        
                        smart_signals.append(signal)
                        
                except Exception as e:
                    logger.debug(f"Error processing option for smart money: {e}")
                    continue
            
        except Exception as e:
            logger.debug(f"Error identifying smart money options: {e}")
        
        return smart_signals
    
    async def _process_unusual_activity_signal(self, signal: OptionsSignal):
        """Process unusual options activity signals."""
        logger.info(f"🔥 UNUSUAL OPTIONS ACTIVITY: {signal.ticker} {signal.option_type.upper()} "
                   f"{signal.strike} {signal.expiry} - Volume: {signal.volume}, "
                   f"Premium: ${signal.premium:,.0f}")
        
        # Send to main signal processor
        signal_data = {
            'source': 'options_unusual_activity',
            'priority': 'MEDIUM',
            'signal': signal,
            'timestamp': datetime.now()
        }
        
        await self._send_to_signal_processor(signal_data)
    
    async def _process_smart_money_signal(self, signal: OptionsSignal):
        """Process smart money flow signals."""
        logger.warning(f"💰 SMART MONEY FLOW: {signal.ticker} {signal.option_type.upper()} "
                      f"{signal.strike} - Smart Money Score: {signal.smart_money_indicator:.2f}")
        
        # Send to main signal processor with high priority
        signal_data = {
            'source': 'options_smart_money',
            'priority': 'HIGH',
            'signal': signal,
            'timestamp': datetime.now()
        }
        
        await self._send_to_signal_processor(signal_data)
    
    async def _send_to_signal_processor(self, signal_data: Dict):
        """Send signal to main signal processing pipeline."""
        logger.info(f"📤 Sending options signal to processor: {signal_data['signal'].ticker}")
        # This will integrate with your signal combiner
        pass
    
    async def _cleanup_old_signals(self):
        """Clean up old options signals."""
        while True:
            try:
                # Remove signals older than 4 hours
                cutoff_time = datetime.now() - timedelta(hours=4)
                self.active_signals = [
                    s for s in self.active_signals 
                    if s.timestamp > cutoff_time
                ]
                
                # Clean up cache entries older than 1 day
                cutoff_cache = datetime.now() - timedelta(days=1)
                for ticker in list(self.options_cache.keys()):
                    if self.options_cache[ticker].get('last_updated', cutoff_cache) < cutoff_cache:
                        del self.options_cache[ticker]
                
                await asyncio.sleep(3600)  # Cleanup every hour
                
            except Exception as e:
                logger.error(f"Error in options cleanup: {e}")
                await asyncio.sleep(3600)
    
    def get_current_signals(self) -> List[OptionsSignal]:
        """Get current active options signals."""
        cutoff_time = datetime.now() - timedelta(hours=1)
        return [s for s in self.active_signals if s.timestamp > cutoff_time]
    
    def get_ticker_options_sentiment(self, ticker: str) -> Dict:
        """Get aggregated options sentiment for a ticker."""
        relevant_signals = [
            s for s in self.active_signals 
            if s.ticker == ticker
        ]
        
        if not relevant_signals:
            return {
                'sentiment': 'neutral',
                'signal_count': 0,
                'smart_money_signals': 0,
                'put_call_ratio': 1.0,
                'confidence': 0.0
            }
        
        # Aggregate signals
        bullish_signals = [s for s in relevant_signals if s.flow_sentiment == 'bullish']
        bearish_signals = [s for s in relevant_signals if s.flow_sentiment == 'bearish']
        smart_money_signals = [s for s in relevant_signals if s.smart_money_indicator > 0.7]
        
        # Determine overall sentiment
        if len(bullish_signals) > len(bearish_signals) * 1.5:
            sentiment = 'bullish'
        elif len(bearish_signals) > len(bullish_signals) * 1.5:
            sentiment = 'bearish'
        else:
            sentiment = 'neutral'
        
        # Confidence based on signal strength and smart money presence
        avg_strength = sum(s.signal_strength for s in relevant_signals) / len(relevant_signals)
        smart_money_boost = min(len(smart_money_signals) * 0.2, 0.4)
        confidence = min(avg_strength + smart_money_boost, 1.0)
        
        # Get latest put/call ratio
        latest_pcr = 1.0
        if self.options_cache.get(ticker):
            latest_pcr = self.options_cache[ticker].get('put_call_ratio', 1.0)
        
        return {
            'sentiment': sentiment,
            'signal_count': len(relevant_signals),
            'smart_money_signals': len(smart_money_signals),
            'put_call_ratio': latest_pcr,
            'confidence': confidence,
            'latest_signals': relevant_signals[-3:]
        }

# Global instance
options_monitor = OptionsMonitor()