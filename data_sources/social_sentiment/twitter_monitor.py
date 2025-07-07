"""Real-time Twitter/X monitoring for market-moving tweets."""

import tweepy
import asyncio
import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
from dataclasses import dataclass
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from config.api_keys import *
from config.settings import REALTIME_SOURCES

logger = logging.getLogger(__name__)

@dataclass
class TwitterSignal:
    """Twitter signal data structure."""
    author: str
    content: str
    timestamp: datetime
    followers: int
    retweets: int
    likes: int
    sentiment_score: float
    mentioned_tickers: List[str]
    urgency_score: float
    market_impact_score: float

class TwitterMonitor:
    """Real-time Twitter monitoring for market intelligence."""
    
    def __init__(self):
        self.client = self._setup_twitter_client()
        self.sentiment_analyzer = SentimentIntensityAnalyzer()
        self.active_signals = []
        self.ticker_patterns = self._compile_ticker_patterns()
        self.vip_accounts = self._setup_vip_accounts()
        
    def _setup_twitter_client(self):
        """Initialize Twitter API client."""
        try:
            if not all([TWITTER_BEARER_TOKEN, TWITTER_API_KEY, TWITTER_API_SECRET]):
                logger.warning("Twitter API keys not found - Twitter monitoring disabled")
                return None
            
            client = tweepy.Client(
                bearer_token=TWITTER_BEARER_TOKEN,
                consumer_key=TWITTER_API_KEY,
                consumer_secret=TWITTER_API_SECRET,
                access_token=TWITTER_ACCESS_TOKEN,
                access_token_secret=TWITTER_ACCESS_TOKEN_SECRET,
                wait_on_rate_limit=True
            )
            
            logger.info("✅ Twitter client initialized successfully")
            return client
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Twitter client: {e}")
            return None
    
    def _compile_ticker_patterns(self):
        """Compile regex patterns for ticker detection."""
        patterns = [
            r'\$([A-Z]{1,5})',                    # $AAPL format
            r'\b([A-Z]{2,5})\b(?=\s|$|\.|\,)',   # AAPL format (standalone)
            r'#([A-Z]{1,5})(?=\s|$)',            # #AAPL format
        ]
        return [re.compile(pattern) for pattern in patterns]
    
    def _setup_vip_accounts(self):
        """Setup VIP account monitoring with influence scores."""
        vip_accounts = {
            # Political figures (highest market impact)
            'realDonaldTrump': {'influence': 10, 'sector_focus': 'all'},
            'POTUS': {'influence': 9, 'sector_focus': 'all'},
            
            # Financial officials
            'federalreserve': {'influence': 9, 'sector_focus': 'financials'},
            'USTreasury': {'influence': 8, 'sector_focus': 'financials'},
            'SEC_News': {'influence': 7, 'sector_focus': 'all'},
            
            # CEO/Business leaders
            'elonmusk': {'influence': 8, 'sector_focus': 'tech'},
            'sundarpichai': {'influence': 6, 'sector_focus': 'tech'},
            'tim_cook': {'influence': 6, 'sector_focus': 'tech'},
            
            # Financial media
            'CNBC': {'influence': 7, 'sector_focus': 'all'},
            'MarketWatch': {'influence': 6, 'sector_focus': 'all'},
            'WSJ': {'influence': 7, 'sector_focus': 'all'},
            'BloombergNews': {'influence': 7, 'sector_focus': 'all'},
        }
        return vip_accounts
    
    async def start_monitoring(self):
        """Start real-time Twitter monitoring."""
        if not self.client:
            logger.warning("Twitter client not available - skipping Twitter monitoring")
            return
        
        logger.info("🐦 Starting real-time Twitter monitoring...")
        
        tasks = [
            self._monitor_vip_accounts(),
            self._monitor_keyword_stream(),
            self._process_signal_queue()
        ]
        
        await asyncio.gather(*tasks)
    
    async def _monitor_vip_accounts(self):
        """Monitor VIP accounts for market-moving tweets."""
        while True:
            try:
                for username, account_info in list(self.vip_accounts.items())[:5]:  # Limit to avoid rate limits
                    tweets = self._get_recent_tweets(username, count=3)
                    
                    for tweet in tweets:
                        signal = self._analyze_tweet(tweet, account_info)
                        if signal and signal.urgency_score > 0.6:
                            await self._process_high_priority_signal(signal)
                
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Error monitoring VIP accounts: {e}")
                await asyncio.sleep(60)
    
    async def _monitor_keyword_stream(self):
        """Monitor keyword-based tweet stream."""
        while True:
            try:
                keywords = REALTIME_SOURCES['twitter']['keywords']
                
                for keyword in keywords[:3]:  # Limit keywords to avoid rate limits
                    tweets = self._search_recent_tweets(keyword, count=5)
                    
                    for tweet in tweets:
                        signal = self._analyze_tweet(tweet)
                        if signal and signal.market_impact_score > 0.4:
                            self.active_signals.append(signal)
                
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Error monitoring keyword stream: {e}")
                await asyncio.sleep(120)
    
    def _get_recent_tweets(self, username: str, count: int = 5):
        """Get recent tweets from a specific user."""
        try:
            if not self.client:
                return []
            
            user = self.client.get_user(username=username)
            if not user.data:
                return []
            
            tweets = self.client.get_users_tweets(
                id=user.data.id,
                max_results=min(count, 10),  # Twitter API limit
                tweet_fields=['created_at', 'public_metrics', 'text'],
                exclude=['retweets', 'replies']
            )
            
            return tweets.data if tweets.data else []
            
        except Exception as e:
            logger.debug(f"Error fetching tweets for {username}: {e}")
            return []
    
    def _search_recent_tweets(self, query: str, count: int = 5):
        """Search for recent tweets matching query."""
        try:
            if not self.client:
                return []
            
            tweets = self.client.search_recent_tweets(
                query=f"{query} -is:retweet lang:en",
                max_results=min(count, 10),
                tweet_fields=['created_at', 'public_metrics', 'author_id']
            )
            
            return tweets.data if tweets.data else []
            
        except Exception as e:
            logger.debug(f"Error searching tweets for {query}: {e}")
            return []
    
    def _analyze_tweet(self, tweet, account_info: Dict = None) -> Optional[TwitterSignal]:
        """Analyze a tweet for market signals."""
        try:
            content = tweet.text
            timestamp = tweet.created_at
            metrics = tweet.public_metrics
            
            # Sentiment analysis
            sentiment = self.sentiment_analyzer.polarity_scores(content)
            sentiment_score = sentiment['compound']
            
            # Extract mentioned tickers
            mentioned_tickers = self._extract_tickers(content)
            
            # Calculate urgency score
            urgency_score = self._calculate_urgency(content, metrics, account_info)
            
            # Calculate market impact score
            market_impact_score = self._calculate_market_impact(
                content, mentioned_tickers, account_info, metrics
            )
            
            # Only return signal if it meets minimum thresholds
            if urgency_score > 0.3 or market_impact_score > 0.3:
                return TwitterSignal(
                    author=account_info.get('username', 'unknown') if account_info else 'unknown',
                    content=content,
                    timestamp=timestamp,
                    followers=account_info.get('followers', 0) if account_info else 0,
                    retweets=metrics.get('retweet_count', 0),
                    likes=metrics.get('like_count', 0),
                    sentiment_score=sentiment_score,
                    mentioned_tickers=mentioned_tickers,
                    urgency_score=urgency_score,
                    market_impact_score=market_impact_score
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Error analyzing tweet: {e}")
            return None
    
    def _extract_tickers(self, text: str) -> List[str]:
        """Extract stock tickers from tweet text."""
        tickers = set()
        
        for pattern in self.ticker_patterns:
            matches = pattern.findall(text.upper())
            for match in matches:
                # Filter out common false positives
                if match not in ['THE', 'AND', 'FOR', 'ARE', 'BUT', 'NOT', 'YOU', 'ALL', 'CAN']:
                    tickers.add(match)
        
        return list(tickers)
    
    def _calculate_urgency(self, content: str, metrics: Dict, account_info: Dict = None) -> float:
        """Calculate urgency score for a tweet."""
        urgency = 0.0
        
        # Urgent keywords
        urgent_keywords = ['BREAKING', 'URGENT', 'ALERT', 'JUST IN', 'HALT', 'CRASH']
        
        content_upper = content.upper()
        for keyword in urgent_keywords:
            if keyword in content_upper:
                urgency += 0.3
        
        # Account influence
        if account_info:
            influence = account_info.get('influence', 1)
            urgency += min(influence / 10, 0.5)
        
        # Engagement velocity
        engagement = metrics.get('like_count', 0) + metrics.get('retweet_count', 0) * 2
        if engagement > 1000:
            urgency += 0.2
        elif engagement > 100:
            urgency += 0.1
        
        return min(urgency, 1.0)
    
    def _calculate_market_impact(self, content: str, tickers: List[str], 
                                account_info: Dict = None, metrics: Dict = None) -> float:
        """Calculate potential market impact score."""
        impact = 0.0
        
        # High-impact keywords
        impact_keywords = {
            'earnings': 0.3, 'guidance': 0.3, 'merger': 0.4, 'acquisition': 0.4,
            'bankruptcy': 0.5, 'fda': 0.3, 'approval': 0.2, 'investigation': 0.2
        }
        
        content_lower = content.lower()
        for keyword, score in impact_keywords.items():
            if keyword in content_lower:
                impact += score
        
        # Ticker mentions
        if tickers:
            impact += min(len(tickers) * 0.1, 0.3)
        
        # Account influence
        if account_info:
            influence = account_info.get('influence', 1)
            impact += min(influence / 20, 0.4)
        
        return min(impact, 1.0)
    
    async def _process_high_priority_signal(self, signal: TwitterSignal):
        """Process high-priority signals immediately."""
        logger.warning(f"🔥 HIGH PRIORITY TWITTER SIGNAL: {signal.author} - {signal.content[:100]}...")
        
        priority_data = {
            'source': 'twitter',
            'priority': 'HIGH',
            'signal': signal,
            'timestamp': datetime.now(),
            'action_required': True
        }
        
        # Send to AI analysis
        await self._send_to_ai_analysis(priority_data)
    
    async def _send_to_ai_analysis(self, signal_data: Dict):
        """Send signal to AI analysis pipeline."""
        logger.info(f"📤 Sending {signal_data['priority']} Twitter signal to AI analysis")
        # This connects to your AI system
        pass
    
    async def _process_signal_queue(self):
        """Process accumulated signals periodically."""
        while True:
            try:
                if self.active_signals:
                    # Sort by impact score
                    self.active_signals.sort(key=lambda x: x.market_impact_score, reverse=True)
                    
                    # Process top signals
                    top_signals = self.active_signals[:10]
                    
                    # Group by tickers
                    ticker_signals = {}
                    for signal in top_signals:
                        for ticker in signal.mentioned_tickers:
                            if ticker not in ticker_signals:
                                ticker_signals[ticker] = []
                            ticker_signals[ticker].append(signal)
                    
                    # Send aggregated signals
                    if ticker_signals:
                        await self._send_aggregated_signals(ticker_signals)
                    
                    # Keep only recent signals (last hour)
                    cutoff_time = datetime.now() - timedelta(hours=1)
                    self.active_signals = [
                        s for s in self.active_signals 
                        if s.timestamp > cutoff_time
                    ]
                
                await asyncio.sleep(300)  # Process every 5 minutes
                
            except Exception as e:
                logger.error(f"Error processing signal queue: {e}")
                await asyncio.sleep(60)
    
    async def _send_aggregated_signals(self, ticker_signals: Dict):
        """Send aggregated ticker signals for analysis."""
        for ticker, signals in ticker_signals.items():
            if len(signals) >= 2:
                logger.info(f"📊 Multiple Twitter signals for {ticker}: {len(signals)} signals")
                
                aggregated_data = {
                    'source': 'twitter_aggregated',
                    'ticker': ticker,
                    'signal_count': len(signals),
                    'avg_sentiment': sum(s.sentiment_score for s in signals) / len(signals),
                    'max_impact': max(s.market_impact_score for s in signals),
                    'signals': signals,
                    'timestamp': datetime.now()
                }
                
                await self._send_to_ai_analysis(aggregated_data)
    
    def get_current_signals(self) -> List[TwitterSignal]:
        """Get current active signals."""
        cutoff_time = datetime.now() - timedelta(minutes=30)
        return [s for s in self.active_signals if s.timestamp > cutoff_time]
    
    def get_ticker_sentiment(self, ticker: str) -> Dict:
        """Get aggregated Twitter sentiment for a specific ticker."""
        relevant_signals = [
            s for s in self.active_signals 
            if ticker in s.mentioned_tickers
        ]
        
        if not relevant_signals:
            return {
                'sentiment_score': 0.0,
                'signal_count': 0,
                'confidence': 0.0
            }
        
        avg_sentiment = sum(s.sentiment_score for s in relevant_signals) / len(relevant_signals)
        confidence = min(len(relevant_signals) / 5, 1.0)
        
        return {
            'sentiment_score': avg_sentiment,
            'signal_count': len(relevant_signals),
            'confidence': confidence,
            'latest_signals': relevant_signals[-3:]
        }

# Global instance
twitter_monitor = TwitterMonitor()