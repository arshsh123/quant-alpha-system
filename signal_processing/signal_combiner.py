"""Complete Advanced multi-signal combination and normalization system."""

import asyncio
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import logging
from dataclasses import dataclass, asdict
from enum import Enum
import json
import math

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from config.settings import SIGNAL_PROCESSING, MARKET_REGIMES, RISK_MANAGEMENT

# Import monitors with error handling
try:
    from data_sources.social_sentiment.twitter_monitor import twitter_monitor
    TWITTER_AVAILABLE = True
except ImportError:
    twitter_monitor = None
    TWITTER_AVAILABLE = False

try:
    from data_sources.social_sentiment.news_monitor import news_monitor
    NEWS_AVAILABLE = True
except ImportError:
    news_monitor = None
    NEWS_AVAILABLE = False

try:
    from data_sources.earnings_signals.earnings_monitor import earnings_monitor
    EARNINGS_AVAILABLE = True
except ImportError:
    earnings_monitor = None
    EARNINGS_AVAILABLE = False

try:
    from data_sources.options_flow.options_monitor import options_monitor
    OPTIONS_AVAILABLE = True
except ImportError:
    options_monitor = None
    OPTIONS_AVAILABLE = False

logger = logging.getLogger(__name__)

class SignalType(Enum):
    """Signal type enumeration."""
    SOCIAL_SENTIMENT = "social_sentiment"
    NEWS_SENTIMENT = "news_sentiment"
    EARNINGS_SURPRISE = "earnings_surprise"
    OPTIONS_FLOW = "options_flow"
    TECHNICAL_MOMENTUM = "technical_momentum"
    MARKET_STRUCTURE = "market_structure"

class TradeAction(Enum):
    """Trade action enumeration."""
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    HOLD = "hold"
    SELL = "sell"
    STRONG_SELL = "strong_sell"

@dataclass
class NormalizedSignal:
    """Enhanced normalized signal structure with decay and confidence."""
    signal_type: SignalType
    ticker: str
    value: float  # Normalized between -1 and 1
    confidence: float  # 0 to 1
    urgency: float  # 0 to 1
    timestamp: datetime
    raw_data: Dict
    decay_half_life_hours: float = 4.0
    
    def get_decayed_value(self, current_time: datetime = None) -> float:
        """Calculate current value after time decay."""
        if current_time is None:
            current_time = datetime.now()
        
        age_hours = (current_time - self.timestamp).total_seconds() / 3600
        decay_factor = 0.5 ** (age_hours / self.decay_half_life_hours)
        
        return self.value * decay_factor
    
    def get_decayed_confidence(self, current_time: datetime = None) -> float:
        """Calculate current confidence after time decay."""
        if current_time is None:
            current_time = datetime.now()
        
        age_hours = (current_time - self.timestamp).total_seconds() / 3600
        decay_factor = 0.5 ** (age_hours / self.decay_half_life_hours)
        
        return self.confidence * decay_factor

@dataclass
class CombinedSignal:
    """Enhanced combined signal output."""
    ticker: str
    final_score: float  # -1 to 1
    confidence: float  # 0 to 1
    action: TradeAction
    signal_strength: float  # 0 to 1
    contributing_signals: List[NormalizedSignal]
    risk_adjusted_score: float
    position_size_suggestion: float
    entry_price_target: Optional[float]
    stop_loss_target: Optional[float]
    take_profit_target: Optional[float]
    timestamp: datetime
    signal_conflicts: List[str]  # Track conflicting signals
    dynamic_weights: Dict[SignalType, float]  # Actual weights used

class SignalCombiner:
    """Complete enhanced multi-signal combination engine."""
    
    def __init__(self):
        self.signal_cache = {}  # ticker -> List[NormalizedSignal]
        self.market_regime = "normal"
        self.base_weights = self._get_base_weights()
        self.signal_performance_history = {}  # Track signal performance for dynamic weighting
        self.price_cache = {}  # ticker -> recent price data
        self.volume_cache = {}  # ticker -> recent volume data
        
        # Signal decay rates (hours for 50% decay)
        self.decay_rates = {
            SignalType.SOCIAL_SENTIMENT: 2.0,     # Fast decay - Twitter sentiment
            SignalType.NEWS_SENTIMENT: 6.0,       # Medium decay - News impact
            SignalType.EARNINGS_SURPRISE: 48.0,   # Slow decay - Earnings effects
            SignalType.OPTIONS_FLOW: 8.0,         # Medium-fast decay
            SignalType.TECHNICAL_MOMENTUM: 12.0   # Medium decay
        }
        
        # Confidence scoring parameters
        self.confidence_params = {
            SignalType.SOCIAL_SENTIMENT: {
                'volume_weight': 0.3,
                'source_credibility_weight': 0.4,
                'consensus_weight': 0.3
            },
            SignalType.NEWS_SENTIMENT: {
                'source_credibility_weight': 0.5,
                'urgency_weight': 0.3,
                'specificity_weight': 0.2
            },
            SignalType.EARNINGS_SURPRISE: {
                'magnitude_weight': 0.6,
                'consistency_weight': 0.4
            }
        }
        
        logger.info(f"📊 Signal Combiner initialized with components: "
                   f"Twitter={TWITTER_AVAILABLE}, News={NEWS_AVAILABLE}, "
                   f"Earnings={EARNINGS_AVAILABLE}, Options={OPTIONS_AVAILABLE}")
        
    def _get_base_weights(self) -> Dict[SignalType, float]:
        """Get base signal weights (will be adjusted dynamically)."""
        return {
            SignalType.SOCIAL_SENTIMENT: 0.40,
            SignalType.NEWS_SENTIMENT: 0.20,
            SignalType.EARNINGS_SURPRISE: 0.25,
            SignalType.OPTIONS_FLOW: 0.10,
            SignalType.TECHNICAL_MOMENTUM: 0.05
        }
    
    async def start_processing(self):
        """Start the signal processing engine."""
        logger.info("🔄 Starting signal processing engine...")
        
        tasks = [
            self._collect_signals_continuously(),
            self._update_market_regime(),
            self._generate_combined_signals(),
            self._cleanup_old_signals()
        ]
        
        await asyncio.gather(*tasks)
    
    async def _collect_signals_continuously(self):
        """Continuously collect signals from all sources."""
        while True:
            try:
                # Collect from all active signal sources
                await self._collect_social_signals()
                await self._collect_news_signals()
                await self._collect_earnings_signals()
                await self._collect_options_signals()
                await self._collect_technical_signals()
                
                await asyncio.sleep(30)  # Collect every 30 seconds
                
            except Exception as e:
                logger.error(f"Error collecting signals: {e}")
                await asyncio.sleep(60)
    
    async def _collect_social_signals(self):
        """Collect and normalize social sentiment signals."""
        try:
            if not TWITTER_AVAILABLE or not twitter_monitor:
                return
                
            # Get Twitter signals
            twitter_signals = twitter_monitor.get_current_signals()
            
            for signal in twitter_signals:
                for ticker in signal.mentioned_tickers:
                    normalized = self._normalize_twitter_signal(signal, ticker)
                    if normalized:
                        self._add_signal_to_cache(normalized)
                        
        except Exception as e:
            logger.error(f"Error collecting social signals: {e}")
    
    async def _collect_news_signals(self):
        """Collect and normalize news sentiment signals."""
        try:
            if not NEWS_AVAILABLE or not news_monitor:
                return
                
            # Get news signals
            news_signals = news_monitor.get_current_signals()
            
            for signal in news_signals:
                for ticker in signal.mentioned_tickers:
                    normalized = self._normalize_news_signal(signal, ticker)
                    if normalized:
                        self._add_signal_to_cache(normalized)
                        
        except Exception as e:
            logger.error(f"Error collecting news signals: {e}")
    
    async def _collect_earnings_signals(self):
        """Collect and normalize earnings signals."""
        try:
            if not EARNINGS_AVAILABLE or not earnings_monitor:
                return
                
            # Get upcoming earnings for pre-positioning
            upcoming_earnings = earnings_monitor.get_upcoming_earnings(3)
            
            for earnings_entry in upcoming_earnings:
                # Create pre-earnings signal
                normalized = self._normalize_pre_earnings_signal(earnings_entry)
                if normalized:
                    self._add_signal_to_cache(normalized)
            
            # Get actual earnings surprises
            for ticker, earnings_signal in earnings_monitor.active_earnings.items():
                normalized = self._normalize_earnings_surprise_signal(earnings_signal)
                if normalized:
                    self._add_signal_to_cache(normalized)
                    
        except Exception as e:
            logger.error(f"Error collecting earnings signals: {e}")
    
    async def _collect_options_signals(self):
        """Collect and normalize options flow signals."""
        try:
            if not OPTIONS_AVAILABLE or not options_monitor:
                return
                
            # Get options signals
            options_signals = options_monitor.get_current_signals()
            
            for signal in options_signals:
                normalized = self._normalize_options_signal(signal)
                if normalized:
                    self._add_signal_to_cache(normalized)
                    
        except Exception as e:
            logger.error(f"Error collecting options signals: {e}")
    
    async def _collect_technical_signals(self):
        """Collect basic technical momentum signals."""
        try:
            # For tickers we're tracking, generate simple technical signals
            tracked_tickers = self._get_tracked_tickers()
            
            for ticker in tracked_tickers[:20]:  # Limit to avoid rate limits
                technical_signal = await self._generate_technical_signal(ticker)
                if technical_signal:
                    self._add_signal_to_cache(technical_signal)
                    
        except Exception as e:
            logger.error(f"Error collecting technical signals: {e}")
    
    def _normalize_twitter_signal(self, signal, ticker: str) -> Optional[NormalizedSignal]:
        """Normalize Twitter signal to standard format."""
        try:
            # Calculate normalized value based on sentiment and impact
            sentiment_component = signal.sentiment_score  # Already -1 to 1
            impact_component = signal.market_impact_score * 2 - 1  # Convert 0-1 to -1 to 1
            
            # Weight sentiment more heavily for social signals
            normalized_value = 0.7 * sentiment_component + 0.3 * impact_component
            
            # Confidence based on signal strength and follower count
            confidence = min(
                signal.urgency_score + 
                (signal.followers / 1000000) * 0.1 +  # Follower influence
                (1.0 / max(len(signal.mentioned_tickers), 1)) * 0.05,  # Single ticker focus
                1.0
            )
            
            return NormalizedSignal(
                signal_type=SignalType.SOCIAL_SENTIMENT,
                ticker=ticker,
                value=np.clip(normalized_value, -1, 1),
                confidence=confidence,
                urgency=signal.urgency_score,
                timestamp=signal.timestamp,
                raw_data=asdict(signal),
                decay_half_life_hours=self.decay_rates[SignalType.SOCIAL_SENTIMENT]
            )
            
        except Exception as e:
            logger.error(f"Error normalizing Twitter signal: {e}")
            return None
    
    def _normalize_news_signal(self, signal, ticker: str) -> Optional[NormalizedSignal]:
        """Normalize news signal to standard format."""
        try:
            # News sentiment is typically more reliable but less urgent than social
            sentiment_component = signal.sentiment_score
            impact_component = signal.market_impact_score * 2 - 1
            
            # Balance sentiment and impact equally for news
            normalized_value = 0.6 * sentiment_component + 0.4 * impact_component
            
            # Confidence based on source credibility and specificity
            source_weights = {
                'reuters': 0.9, 'bloomberg': 0.9, 'wsj': 0.8,
                'cnbc': 0.7, 'marketwatch': 0.6, 'yahoo': 0.5
            }
            
            source_confidence = source_weights.get(signal.source.lower(), 0.5)
            
            confidence = min(
                source_confidence +
                signal.urgency_score * 0.3 +
                (0.2 if len(signal.mentioned_tickers) == 1 else 0.0),  # Single ticker focus
                1.0
            )
            
            return NormalizedSignal(
                signal_type=SignalType.NEWS_SENTIMENT,
                ticker=ticker,
                value=np.clip(normalized_value, -1, 1),
                confidence=confidence,
                urgency=signal.urgency_score,
                timestamp=signal.timestamp,
                raw_data=asdict(signal),
                decay_half_life_hours=self.decay_rates[SignalType.NEWS_SENTIMENT]
            )
            
        except Exception as e:
            logger.error(f"Error normalizing news signal: {e}")
            return None
    
    def _normalize_earnings_surprise_signal(self, signal) -> Optional[NormalizedSignal]:
        """Normalize earnings surprise signal."""
        try:
            # Earnings surprises are very high-conviction signals
            surprise_percent = signal.surprise_percent or 0
            
            # Convert surprise percentage to normalized value
            # 20% surprise = 1.0, -20% surprise = -1.0
            normalized_value = np.clip(surprise_percent / 20, -1, 1)
            
            # High confidence for earnings signals
            confidence = min(signal.signal_strength + 0.2, 1.0)
            
            return NormalizedSignal(
                signal_type=SignalType.EARNINGS_SURPRISE,
                ticker=signal.ticker,
                value=normalized_value,
                confidence=confidence,
                urgency=0.9,  # Earnings are always urgent
                timestamp=signal.timestamp,
                raw_data=asdict(signal),
                decay_half_life_hours=self.decay_rates[SignalType.EARNINGS_SURPRISE]
            )
            
        except Exception as e:
            logger.error(f"Error normalizing earnings signal: {e}")
            return None
    
    def _normalize_pre_earnings_signal(self, earnings_entry) -> Optional[NormalizedSignal]:
        """Normalize pre-earnings positioning signal."""
        try:
            # Pre-earnings signals are positioning opportunities
            days_until = (earnings_entry.earnings_date - datetime.now()).days
            
            if days_until > 3 or days_until < 0:
                return None
            
            # Create neutral signal with time decay
            time_factor = (4 - days_until) / 4  # Stronger as earnings approach
            
            return NormalizedSignal(
                signal_type=SignalType.EARNINGS_SURPRISE,
                ticker=earnings_entry.ticker,
                value=0.0,  # Neutral positioning signal
                confidence=0.3 * time_factor,
                urgency=time_factor,
                timestamp=datetime.now(),
                raw_data={'type': 'pre_earnings', 'days_until': days_until},
                decay_half_life_hours=24.0
            )
            
        except Exception as e:
            logger.error(f"Error normalizing pre-earnings signal: {e}")
            return None
    
    def _normalize_options_signal(self, signal) -> Optional[NormalizedSignal]:
        """Normalize options flow signal."""
        try:
            # Convert options sentiment to numerical value
            sentiment_map = {'bullish': 0.5, 'bearish': -0.5, 'neutral': 0.0}
            base_value = sentiment_map.get(signal.flow_sentiment, 0.0)
            
            # Amplify based on unusual activity and smart money scores
            amplification = signal.unusual_activity_score * signal.smart_money_indicator
            normalized_value = base_value * (1 + amplification)
            
            # Confidence based on signal strength and premium size
            confidence = min(
                signal.signal_strength +
                min(signal.premium / 100000, 0.3),  # Large premium = higher confidence
                1.0
            )
            
            return NormalizedSignal(
                signal_type=SignalType.OPTIONS_FLOW,
                ticker=signal.ticker,
                value=np.clip(normalized_value, -1, 1),
                confidence=confidence,
                urgency=signal.unusual_activity_score,
                timestamp=signal.timestamp,
                raw_data=asdict(signal),
                decay_half_life_hours=self.decay_rates[SignalType.OPTIONS_FLOW]
            )
            
        except Exception as e:
            logger.error(f"Error normalizing options signal: {e}")
            return None
    
    async def _generate_technical_signal(self, ticker: str) -> Optional[NormalizedSignal]:
        """Generate simple technical momentum signal."""
        try:
            # This is a basic implementation - you'd want more sophisticated indicators
            import yfinance as yf
            
            stock = yf.Ticker(ticker)
            hist = stock.history(period="20d")
            
            if len(hist) < 10:
                return None
            
            # Simple momentum calculation
            current_price = hist['Close'].iloc[-1]
            sma_5 = hist['Close'].tail(5).mean()
            sma_20 = hist['Close'].mean()
            
            # Momentum signal
            momentum = (current_price - sma_20) / sma_20
            trend_signal = (sma_5 - sma_20) / sma_20
            
            # Combine momentum indicators
            technical_value = np.clip((momentum + trend_signal) * 2, -1, 1)
            
            # Volume confirmation
            avg_volume = hist['Volume'].mean()
            recent_volume = hist['Volume'].tail(3).mean()
            volume_factor = min(recent_volume / avg_volume, 2.0) / 2.0
            
            return NormalizedSignal(
                signal_type=SignalType.TECHNICAL_MOMENTUM,
                ticker=ticker,
                value=technical_value,
                confidence=0.3 + volume_factor * 0.3,  # Lower confidence for basic technical
                urgency=0.2,
                timestamp=datetime.now(),
                raw_data={
                    'momentum': momentum,
                    'trend': trend_signal,
                    'volume_factor': volume_factor,
                    'current_price': current_price
                },
                decay_half_life_hours=self.decay_rates[SignalType.TECHNICAL_MOMENTUM]
            )
            
        except Exception as e:
            logger.error(f"Error generating technical signal for {ticker}: {e}")
            return None
    
    def _add_signal_to_cache(self, signal: NormalizedSignal):
        """Add signal to cache with deduplication."""
        ticker = signal.ticker
        
        if ticker not in self.signal_cache:
            self.signal_cache[ticker] = []
        
        # Remove old signals of same type (keep only latest)
        self.signal_cache[ticker] = [
            s for s in self.signal_cache[ticker]
            if s.signal_type != signal.signal_type or 
            (datetime.now() - s.timestamp).total_seconds() > 3600  # Keep if older than 1 hour
        ]
        
        # Add new signal
        self.signal_cache[ticker].append(signal)
        
        # Limit cache size per ticker
        if len(self.signal_cache[ticker]) > 10:
            self.signal_cache[ticker] = sorted(
                self.signal_cache[ticker], 
                key=lambda x: x.timestamp, 
                reverse=True
            )[:10]
    
    def calculate_dynamic_confidence(self, signal: NormalizedSignal) -> float:
        """Calculate dynamic confidence score for a signal."""
        base_confidence = signal.confidence
        signal_type = signal.signal_type
        
        # Get performance history for this signal type
        performance_data = self.signal_performance_history.get(signal_type, {})
        recent_accuracy = performance_data.get('recent_accuracy', 0.5)
        
        # Adjust confidence based on recent performance
        performance_multiplier = 0.5 + (recent_accuracy * 1.0)  # 0.5 to 1.5 range
        
        # Apply signal-specific confidence factors
        if signal_type == SignalType.SOCIAL_SENTIMENT:
            # Higher confidence for signals from high-influence accounts
            influence_boost = min(signal.raw_data.get('followers', 0) / 1000000, 0.3)
            base_confidence += influence_boost
            
        elif signal_type == SignalType.NEWS_SENTIMENT:
            # Higher confidence for urgent breaking news
            urgency_boost = signal.urgency * 0.2
            base_confidence += urgency_boost
            
        elif signal_type == SignalType.EARNINGS_SURPRISE:
            # Higher confidence for large surprises
            surprise_magnitude = abs(signal.raw_data.get('surprise_percent', 0))
            magnitude_boost = min(surprise_magnitude / 20, 0.3)  # Cap at 20% surprise
            base_confidence += magnitude_boost
        
        # Apply performance multiplier and cap at 1.0
        final_confidence = min(base_confidence * performance_multiplier, 1.0)
        
        return final_confidence
    
    def calculate_dynamic_weights(self, signals: List[NormalizedSignal]) -> Dict[SignalType, float]:
        """Calculate dynamic weights based on signal confidence and performance."""
        current_time = datetime.now()
        
        # Start with base weights
        dynamic_weights = self.base_weights.copy()
        
        # Group signals by type
        signal_groups = {}
        for signal in signals:
            signal_type = signal.signal_type
            if signal_type not in signal_groups:
                signal_groups[signal_type] = []
            signal_groups[signal_type].append(signal)
        
        # Calculate confidence-adjusted weights
        total_confidence_weight = 0
        confidence_weights = {}
        
        for signal_type in dynamic_weights.keys():
            if signal_type not in signal_groups:
                confidence_weights[signal_type] = 0
                continue
                
            signal_list = signal_groups[signal_type]
            
            # Average confidence for this signal type (with decay)
            if signal_list:
                avg_confidence = sum(
                    self.calculate_dynamic_confidence(s) * s.get_decayed_confidence(current_time)
                    for s in signal_list
                ) / len(signal_list)
            else:
                avg_confidence = 0
            
            # Weight by base weight * confidence
            confidence_weights[signal_type] = dynamic_weights[signal_type] * avg_confidence
            total_confidence_weight += confidence_weights[signal_type]
        
        # Normalize weights to sum to 1
        if total_confidence_weight > 0:
            for signal_type in confidence_weights:
                dynamic_weights[signal_type] = confidence_weights[signal_type] / total_confidence_weight
        
        # Apply regime adjustments
        regime_adjustments = MARKET_REGIMES['regime_adjustments'].get(self.market_regime, {})
        if regime_adjustments:
            # Blend regime adjustments with confidence-based weights
            for signal_type in dynamic_weights:
                if signal_type == SignalType.SOCIAL_SENTIMENT:
                    regime_weight = regime_adjustments.get('social_weight', dynamic_weights[signal_type])
                elif signal_type == SignalType.TECHNICAL_MOMENTUM:
                    regime_weight = regime_adjustments.get('technical_weight', dynamic_weights[signal_type])
                else:
                    continue  # Keep confidence-based weight
                
                # Blend: 70% confidence-based, 30% regime-based
                dynamic_weights[signal_type] = (
                    0.7 * dynamic_weights[signal_type] + 
                    0.3 * regime_weight
                )
        
        # Final normalization
        total_weight = sum(dynamic_weights.values())
        if total_weight > 0:
            dynamic_weights = {k: v/total_weight for k, v in dynamic_weights.items()}
        
        return dynamic_weights
    
    def detect_signal_conflicts(self, signals: List[NormalizedSignal]) -> List[str]:
        """Detect conflicting signals and return conflict descriptions."""
        conflicts = []
        current_time = datetime.now()
        
        # Group signals by type and get decayed values
        signal_values = {}
        for signal in signals:
            signal_type = signal.signal_type
            decayed_value = signal.get_decayed_value(current_time)
            
            if signal_type not in signal_values:
                signal_values[signal_type] = []
            signal_values[signal_type].append(decayed_value)
        
        # Average values by signal type
        avg_values = {}
        for signal_type, values in signal_values.items():
            if values:
                avg_values[signal_type] = sum(values) / len(values)
        
        # Check for conflicts between signal types
        sentiment_signals = [
            SignalType.SOCIAL_SENTIMENT, 
            SignalType.NEWS_SENTIMENT
        ]
        
        fundamental_signals = [
            SignalType.EARNINGS_SURPRISE
        ]
        
        technical_signals = [
            SignalType.TECHNICAL_MOMENTUM,
            SignalType.OPTIONS_FLOW
        ]
        
        # Check sentiment vs fundamental conflicts
        if any(st in avg_values for st in sentiment_signals) and any(st in avg_values for st in fundamental_signals):
            sentiment_avg = np.mean([avg_values.get(st, 0) for st in sentiment_signals if st in avg_values])
            fundamental_avg = np.mean([avg_values.get(st, 0) for st in fundamental_signals if st in avg_values])
            
            if abs(sentiment_avg - fundamental_avg) > 0.5 and sentiment_avg * fundamental_avg < 0:
                conflicts.append(f"Sentiment ({sentiment_avg:.2f}) vs Fundamental ({fundamental_avg:.2f}) conflict")
        
        # Check for internal sentiment conflicts
        social_val = avg_values.get(SignalType.SOCIAL_SENTIMENT, 0)
        news_val = avg_values.get(SignalType.NEWS_SENTIMENT, 0)
        
        if social_val != 0 and news_val != 0 and abs(social_val - news_val) > 0.4 and social_val * news_val < 0:
            conflicts.append(f"Social ({social_val:.2f}) vs News ({news_val:.2f}) sentiment conflict")
        
        # Check options vs sentiment conflicts
        options_val = avg_values.get(SignalType.OPTIONS_FLOW, 0)
        if options_val != 0 and social_val != 0 and abs(options_val - social_val) > 0.6 and options_val * social_val < 0:
            conflicts.append(f"Options ({options_val:.2f}) vs Social ({social_val:.2f}) conflict")
        
        return conflicts
    
    async def _update_market_regime(self):
        """Update market regime detection."""
        while True:
            try:
                # Get VIX for regime detection
                import yfinance as yf
                vix = yf.Ticker("^VIX")
                vix_hist = vix.history(period="5d")
                
                if not vix_hist.empty:
                    current_vix = vix_hist['Close'].iloc[-1]
                    
                    # Determine regime
                    vix_thresholds = MARKET_REGIMES['vix_thresholds']
                    
                    if current_vix < vix_thresholds['low_vol']:
                        self.market_regime = "low_vol"
                    elif current_vix < vix_thresholds['normal_vol']:
                        self.market_regime = "normal_vol"
                    elif current_vix < vix_thresholds['crisis']:
                        self.market_regime = "high_vol"
                    else:
                        self.market_regime = "crisis"
                    
                    logger.info(f"📊 Market regime: {self.market_regime} (VIX: {current_vix:.1f})")
                
                await asyncio.sleep(1800)  # Update every 30 minutes
                
            except Exception as e:
                logger.error(f"Error updating market regime: {e}")
                await asyncio.sleep(1800)
    
    async def _generate_combined_signals(self):
        """Generate combined signals for all tickers with sufficient data."""
        while True:
            try:
                for ticker in list(self.signal_cache.keys()):
                    combined_signal = await self._combine_signals_for_ticker(ticker)
                    
                    if combined_signal and combined_signal.signal_strength > 0.5:
                        await self._process_combined_signal(combined_signal)
                
                await asyncio.sleep(60)  # Generate combined signals every minute
                
            except Exception as e:
                logger.error(f"Error generating combined signals: {e}")
                await asyncio.sleep(60)
    
    async def _combine_signals_for_ticker(self, ticker: str) -> Optional[CombinedSignal]:
        """Enhanced signal combination with decay and conflict detection."""
        try:
            signals = self.signal_cache.get(ticker, [])
            
            if not signals:
                return None
            
            current_time = datetime.now()
            
            # Filter out expired signals and apply decay
            active_signals = []
            for signal in signals:
                decayed_confidence = signal.get_decayed_confidence(current_time)
                
                if decayed_confidence > 0.1:  # Keep signals with >10% confidence
                    active_signals.append(signal)
            
            if not active_signals:
                return None
            
            # Calculate dynamic weights
            dynamic_weights = self.calculate_dynamic_weights(active_signals)
            
            # Detect conflicts
            conflicts = self.detect_signal_conflicts(active_signals)
            
            # Calculate weighted combined score
            total_weighted_value = 0
            total_weight = 0
            total_confidence = 0
            max_urgency = 0
            
            for signal in active_signals:
                weight = dynamic_weights.get(signal.signal_type, 0.1)
                decayed_value = signal.get_decayed_value(current_time)
                decayed_confidence = signal.get_decayed_confidence(current_time)
                dynamic_confidence = self.calculate_dynamic_confidence(signal)
                
                # Use dynamic confidence in weighting
                confidence_weight = weight * dynamic_confidence
                
                total_weighted_value += decayed_value * confidence_weight
                total_weight += confidence_weight
                total_confidence += dynamic_confidence * weight
                max_urgency = max(max_urgency, signal.urgency)
            
            if total_weight == 0:
                return None
            
            # Final combined score
            final_score = total_weighted_value / total_weight
            overall_confidence = total_confidence / sum(dynamic_weights.values()) if sum(dynamic_weights.values()) > 0 else 0
            
            # Apply conflict penalty
            if conflicts:
                conflict_penalty = min(len(conflicts) * 0.2, 0.6)  # Max 60% penalty
                final_score *= (1 - conflict_penalty)
                overall_confidence *= (1 - conflict_penalty * 0.5)  # Smaller confidence penalty
                
                logger.info(f"Signal conflicts detected for {ticker}: {conflicts}")
            
            # Calculate signal strength
            signal_strength = self._calculate_signal_strength(active_signals, overall_confidence, conflicts)
            
            # Determine action
            action = self._determine_action(final_score, signal_strength, overall_confidence)
            
            # Risk adjustment
            risk_adjusted_score = await self._apply_risk_adjustment(ticker, final_score, signal_strength)
            
            # Position sizing
            position_size = self._calculate_position_size(risk_adjusted_score, overall_confidence, signal_strength)
            
            # Price targets
            price_targets = await self._calculate_price_targets(ticker, final_score, signal_strength)
            
            return CombinedSignal(
                ticker=ticker,
                final_score=final_score,
                confidence=overall_confidence,
                action=action,
                signal_strength=signal_strength,
                contributing_signals=active_signals,
                risk_adjusted_score=risk_adjusted_score,
                position_size_suggestion=position_size,
                entry_price_target=price_targets.get('entry'),
                stop_loss_target=price_targets.get('stop_loss'),
                take_profit_target=price_targets.get('take_profit'),
                timestamp=current_time,
                signal_conflicts=conflicts,
                dynamic_weights=dynamic_weights
            )
            
        except Exception as e:
            logger.error(f"Error combining signals for {ticker}: {e}")
            return None
    
    def _calculate_signal_strength(self, signals: List[NormalizedSignal], confidence: float, conflicts: List[str]) -> float:
        """Enhanced signal strength calculation considering conflicts."""
        # Base calculation
        signal_type_diversity = len(set(s.signal_type for s in signals)) / len(SignalType)
        high_conf_signals = sum(1 for s in signals if self.calculate_dynamic_confidence(s) > 0.7)
        high_conf_factor = min(high_conf_signals / len(signals), 1.0) if signals else 0
        avg_urgency = sum(s.urgency for s in signals) / len(signals) if signals else 0
        
        # Base strength
        strength = (signal_type_diversity * 0.4 + 
                   high_conf_factor * 0.3 + 
                   confidence * 0.2 + 
                   avg_urgency * 0.1)
        
        # Apply conflict penalty
        if conflicts:
            conflict_penalty = min(len(conflicts) * 0.15, 0.5)  # Max 50% penalty
            strength *= (1 - conflict_penalty)
        
        return min(strength, 1.0)
    
    def _determine_action(self, final_score: float, signal_strength: float, confidence: float) -> TradeAction:
        """Determine trading action based on combined signal."""
        min_confidence = SIGNAL_PROCESSING['min_signal_confidence']
        
        if confidence < min_confidence:
            return TradeAction.HOLD
        
        # Adjust thresholds based on signal strength
        strong_threshold = 0.6 - (signal_strength * 0.2)
        buy_threshold = 0.3 - (signal_strength * 0.1)
        
        if final_score > strong_threshold:
            return TradeAction.STRONG_BUY
        elif final_score > buy_threshold:
            return TradeAction.BUY
        elif final_score < -strong_threshold:
            return TradeAction.STRONG_SELL
        elif final_score < -buy_threshold:
            return TradeAction.SELL
        else:
            return TradeAction.HOLD
    
    async def _apply_risk_adjustment(self, ticker: str, score: float, signal_strength: float) -> float:
        """Apply risk adjustments to the signal score."""
        try:
            # Get current portfolio exposure (would integrate with portfolio manager)
            current_exposure = 0.0  # Placeholder
            
            # Reduce score if already heavily exposed
            if current_exposure > 0.03:  # 3% position
                score *= 0.5
            
            # Volatility adjustment
            import yfinance as yf
            stock = yf.Ticker(ticker)
            hist = stock.history(period="30d")
            
            if len(hist) > 5:
                volatility = hist['Close'].pct_change().std() * np.sqrt(252)  # Annualized vol
                
                # Reduce score for very high volatility stocks (>80% annual vol)
                if volatility > 0.8:
                    vol_adjustment = max(0.3, 1 - (volatility - 0.8))
                    score *= vol_adjustment
            
            return score
            
        except Exception as e:
            logger.error(f"Error applying risk adjustment for {ticker}: {e}")
            return score
    
    def _calculate_position_size(self, score: float, confidence: float, signal_strength: float) -> float:
        """Calculate suggested position size."""
        risk_config = RISK_MANAGEMENT['position_sizing']
        
        # Base size on signal strength and confidence
        base_size = min(
            abs(score) * confidence * signal_strength,
            risk_config['max_position_size']
        )
        
        # Ensure minimum size for actionable signals
        if base_size > 0:
            base_size = max(base_size, risk_config['min_position_size'])
        
        return base_size
    
    async def _calculate_price_targets(self, ticker: str, score: float, signal_strength: float) -> Dict[str, float]:
        """Calculate entry, stop loss, and take profit targets."""
        try:
            import yfinance as yf
            stock = yf.Ticker(ticker)
            current_price = stock.history(period="1d")['Close'].iloc[-1]
            
            # Calculate ATR for stops
            hist = stock.history(period="20d")
            if len(hist) > 14:
                high_low = hist['High'] - hist['Low']
                high_close = abs(hist['High'] - hist['Close'].shift())
                low_close = abs(hist['Low'] - hist['Close'].shift())
                true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
                atr = true_range.rolling(14).mean().iloc[-1]
            else:
                atr = current_price * 0.02  # 2% default
            
            # Entry target (current price with small buffer)
            entry_buffer = 0.001 if score > 0 else -0.001
            entry_target = current_price * (1 + entry_buffer)
            
            # Stop loss (risk management)
            stop_multiplier = RISK_MANAGEMENT['stop_losses']['trailing_stop_percent']
            if score > 0:
                stop_loss = current_price * (1 - stop_multiplier)
            else:
                stop_loss = current_price * (1 + stop_multiplier)
            
            # Take profit (based on signal strength)
            profit_multiplier = signal_strength * 0.15  # Up to 15% target
            if score > 0:
                take_profit = current_price * (1 + profit_multiplier)
            else:
                take_profit = current_price * (1 - profit_multiplier)
            
            return {
                'entry': entry_target,
                'stop_loss': stop_loss,
                'take_profit': take_profit
            }
            
        except Exception as e:
            logger.error(f"Error calculating price targets for {ticker}: {e}")
            return {}
    
    async def _process_combined_signal(self, signal: CombinedSignal):
        """Process high-quality combined signals."""
        if signal.action in [TradeAction.STRONG_BUY, TradeAction.STRONG_SELL]:
            logger.warning(f"🎯 STRONG SIGNAL: {signal.ticker} - {signal.action.value.upper()} "
                          f"(Score: {signal.final_score:.2f}, Strength: {signal.signal_strength:.2f}, "
                          f"Confidence: {signal.confidence:.2f})")
        elif signal.action in [TradeAction.BUY, TradeAction.SELL]:
            logger.info(f"📈 SIGNAL: {signal.ticker} - {signal.action.value.upper()} "
                       f"(Score: {signal.final_score:.2f}, Strength: {signal.signal_strength:.2f})")
        
        # Log conflicts if present
        if signal.signal_conflicts:
            logger.warning(f"⚠️  Conflicts detected: {', '.join(signal.signal_conflicts)}")
        
        # Log dynamic weights used
        weights_str = ', '.join([f"{k.value}: {v:.2f}" for k, v in signal.dynamic_weights.items() if v > 0])
        logger.info(f"🎚️  Dynamic weights: {weights_str}")
        
        # Send to execution engine
        await self._send_to_execution_engine(signal)
    
    async def _send_to_execution_engine(self, signal: CombinedSignal):
        """Send signal to execution engine."""
        logger.info(f"📤 Sending combined signal to execution: {signal.ticker}")
        # This will integrate with your execution engine
        pass
    
    async def _cleanup_old_signals(self):
        """Clean up old signals from cache."""
        while True:
            try:
                current_time = datetime.now()
                
                for ticker in list(self.signal_cache.keys()):
                    # Remove signals older than 24 hours
                    cutoff_time = current_time - timedelta(hours=24)
                    
                    self.signal_cache[ticker] = [
                        s for s in self.signal_cache[ticker]
                        if s.timestamp > cutoff_time
                    ]
                    
                    # Remove empty entries
                    if not self.signal_cache[ticker]:
                        del self.signal_cache[ticker]
                
                await asyncio.sleep(3600)  # Cleanup every hour
                
            except Exception as e:
                logger.error(f"Error cleaning up signals: {e}")
                await asyncio.sleep(3600)
    
    def _get_tracked_tickers(self) -> List[str]:
        """Get list of tickers being tracked."""
        # Get unique tickers from signal cache plus common ones
        cached_tickers = list(self.signal_cache.keys())
        
        common_tickers = [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA',
            'SPY', 'QQQ', 'IWM', 'VTI', 'TQQQ', 'SQQQ'
        ]
        
        return list(set(cached_tickers + common_tickers))
    
    def update_signal_performance(self, signal_type: SignalType, was_correct: bool):
        """Update performance tracking for dynamic weighting."""
        if signal_type not in self.signal_performance_history:
            self.signal_performance_history[signal_type] = {
                'total_signals': 0,
                'correct_signals': 0,
                'recent_accuracy': 0.5,
                'recent_results': []  # Last 20 results
            }
        
        performance = self.signal_performance_history[signal_type]
        performance['total_signals'] += 1
        
        if was_correct:
            performance['correct_signals'] += 1
        
        # Track recent results (rolling window)
        performance['recent_results'].append(was_correct)
        if len(performance['recent_results']) > 20:
            performance['recent_results'] = performance['recent_results'][-20:]
        
        # Calculate recent accuracy
        if performance['recent_results']:
            performance['recent_accuracy'] = sum(performance['recent_results']) / len(performance['recent_results'])
        
        logger.info(f"Updated {signal_type.value} performance: {performance['recent_accuracy']:.2f} accuracy")
    
    def get_final_signal(self, ticker: str) -> Optional[CombinedSignal]:
        """Get the latest combined signal for a ticker."""
        # This would be called by your main trading logic
        return asyncio.run(self._combine_signals_for_ticker(ticker))
    
    def get_all_active_signals(self) -> List[CombinedSignal]:
        """Get all current active combined signals."""
        signals = []
        
        for ticker in self.signal_cache.keys():
            try:
                combined = asyncio.run(self._combine_signals_for_ticker(ticker))
                if combined and combined.action != TradeAction.HOLD:
                    signals.append(combined)
            except Exception as e:
                logger.error(f"Error getting signal for {ticker}: {e}")
        
        # Sort by signal strength
        signals.sort(key=lambda x: x.signal_strength, reverse=True)
        return signals
    
    def get_signal_summary(self) -> Dict:
        """Enhanced signal summary with performance metrics."""
        all_signals = self.get_all_active_signals()
        
        # Performance summary
        performance_summary = {}
        for signal_type, perf_data in self.signal_performance_history.items():
            performance_summary[signal_type.value] = {
                'accuracy': perf_data.get('recent_accuracy', 0.5),
                'total_signals': perf_data.get('total_signals', 0)
            }
        
        return {
            'total_signals': len(all_signals),
            'strong_buy': len([s for s in all_signals if s.action == TradeAction.STRONG_BUY]),
            'buy': len([s for s in all_signals if s.action == TradeAction.BUY]),
            'sell': len([s for s in all_signals if s.action == TradeAction.SELL]),
            'strong_sell': len([s for s in all_signals if s.action == TradeAction.STRONG_SELL]),
            'market_regime': self.market_regime,
            'base_weights': self.base_weights,
            'performance_summary': performance_summary,
            'top_signals': all_signals[:5],
            'signals_with_conflicts': len([s for s in all_signals if s.signal_conflicts]),
            'component_availability': {
                'twitter': TWITTER_AVAILABLE,
                'news': NEWS_AVAILABLE,
                'earnings': EARNINGS_AVAILABLE,
                'options': OPTIONS_AVAILABLE
            }
        }
    
    def get_ticker_sentiment_summary(self, ticker: str) -> Dict:
        """Get comprehensive sentiment summary for a specific ticker."""
        signals = self.signal_cache.get(ticker, [])
        
        if not signals:
            return {
                'overall_sentiment': 'neutral',
                'signal_count': 0,
                'confidence': 0.0,
                'latest_action': 'hold'
            }
        
        # Get current combined signal
        combined_signal = asyncio.run(self._combine_signals_for_ticker(ticker))
        
        # Aggregate by signal type
        signal_breakdown = {}
        current_time = datetime.now()
        
        for signal in signals:
            signal_type = signal.signal_type.value
            if signal_type not in signal_breakdown:
                signal_breakdown[signal_type] = []
            
            # Apply decay
            decayed_value = signal.get_decayed_value(current_time)
            decayed_confidence = signal.get_decayed_confidence(current_time)
            
            if decayed_confidence > 0.1:  # Only include non-expired signals
                signal_breakdown[signal_type].append({
                    'value': decayed_value,
                    'confidence': decayed_confidence,
                    'timestamp': signal.timestamp,
                    'urgency': signal.urgency
                })
        
        # Calculate averages by signal type
        signal_averages = {}
        for signal_type, type_signals in signal_breakdown.items():
            if type_signals:
                avg_value = sum(s['value'] for s in type_signals) / len(type_signals)
                avg_confidence = sum(s['confidence'] for s in type_signals) / len(type_signals)
                signal_averages[signal_type] = {
                    'average_value': avg_value,
                    'average_confidence': avg_confidence,
                    'signal_count': len(type_signals)
                }
        
        return {
            'overall_sentiment': combined_signal.action.value if combined_signal else 'hold',
            'final_score': combined_signal.final_score if combined_signal else 0.0,
            'confidence': combined_signal.confidence if combined_signal else 0.0,
            'signal_strength': combined_signal.signal_strength if combined_signal else 0.0,
            'signal_count': len(signals),
            'conflicts': combined_signal.signal_conflicts if combined_signal else [],
            'signal_breakdown': signal_averages,
            'dynamic_weights': combined_signal.dynamic_weights if combined_signal else {},
            'last_updated': current_time
        }

# Global instance
signal_combiner = SignalCombiner()