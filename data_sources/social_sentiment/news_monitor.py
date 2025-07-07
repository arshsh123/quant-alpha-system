"""Real-time financial news monitoring and sentiment analysis."""

import aiohttp
import asyncio
import feedparser
import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
import logging
from dataclasses import dataclass
from urllib.parse import urlparse
import hashlib
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from textblob import TextBlob

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from config.api_keys import *
from config.settings import REALTIME_SOURCES

logger = logging.getLogger(__name__)

@dataclass
class NewsSignal:
    """News signal data structure."""
    headline: str
    summary: str
    source: str
    url: str
    timestamp: datetime
    author: str
    sentiment_score: float
    mentioned_tickers: List[str]
    urgency_score: float
    market_impact_score: float
    content_hash: str
    category: str  # breaking, earnings, merger, etc.

class NewsMonitor:
    """Real-time financial news monitoring system."""
    
    def __init__(self):
        self.session = None
        self.sentiment_analyzer = SentimentIntensityAnalyzer()
        self.active_signals = []
        self.processed_articles = set()  # Prevent duplicates
        self.ticker_patterns = self._compile_ticker_patterns()
        self.news_sources = self._setup_news_sources()
        self.breaking_keywords = self._setup_breaking_keywords()
        
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={'User-Agent': 'QuantAlpha-NewsBot/1.0'}
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    def _compile_ticker_patterns(self):
        """Compile regex patterns for ticker detection in news."""
        patterns = [
            r'\b([A-Z]{1,5})\s+\([A-Z]{1,5}:[A-Z]{2,5}\)',  # Apple (NASDAQ:AAPL)
            r'\([A-Z]{1,5}:[A-Z]{2,5}\)',                    # (NASDAQ:AAPL)
            r'\$([A-Z]{1,5})\b',                             # $AAPL
            r'\b([A-Z]{2,5})\s+shares?\b',                   # AAPL shares
            r'\b([A-Z]{2,5})\s+stock\b',                     # AAPL stock
        ]
        return [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
    
    def _setup_news_sources(self):
        """Setup news sources with priorities and refresh rates."""
        sources = {
            # Tier 1: Breaking news (highest priority)
            'reuters_business': {
                'url': 'https://feeds.reuters.com/reuters/businessNews',
                'priority': 1,
                'refresh_seconds': 15,
                'source_weight': 0.9
            },
            'bloomberg_markets': {
                'url': 'https://feeds.bloomberg.com/markets/news.rss',
                'priority': 1,
                'refresh_seconds': 15,
                'source_weight': 0.9
            },
            
            # Tier 2: Financial news
            'yahoo_finance': {
                'url': 'https://feeds.finance.yahoo.com/rss/2.0/headline',
                'priority': 2,
                'refresh_seconds': 30,
                'source_weight': 0.7
            },
            'cnbc_top': {
                'url': 'https://www.cnbc.com/id/100003114/device/rss/rss.html',
                'priority': 2,
                'refresh_seconds': 30,
                'source_weight': 0.8
            },
            'marketwatch': {
                'url': 'https://feeds.marketwatch.com/marketwatch/marketpulse/',
                'priority': 2,
                'refresh_seconds': 45,
                'source_weight': 0.7
            },
            
            # Tier 3: Specialized sources
            'seeking_alpha': {
                'url': 'https://seekingalpha.com/feed.xml',
                'priority': 3,
                'refresh_seconds': 60,
                'source_weight': 0.6
            },
            'fool': {
                'url': 'https://www.fool.com/feeds/index.aspx',
                'priority': 3,
                'refresh_seconds': 120,
                'source_weight': 0.5
            }
        }
        return sources
    
    def _setup_breaking_keywords(self):
        """Setup keywords that indicate breaking/urgent news."""
        return {
            'urgent': ['BREAKING', 'URGENT', 'ALERT', 'DEVELOPING', 'JUST IN'],
            'market_moving': [
                'earnings', 'guidance', 'merger', 'acquisition', 'buyout',
                'bankruptcy', 'lawsuit', 'investigation', 'raid',
                'fda approval', 'drug approval', 'recall',
                'interest rates', 'fed decision', 'fed meeting'
            ],
            'company_events': [
                'ceo', 'resignation', 'fired', 'appointed',
                'layoffs', 'restructuring', 'spinoff',
                'ipo', 'going public', 'delisting'
            ]
        }
    
    async def start_monitoring(self):
        """Start real-time news monitoring."""
        logger.info("📰 Starting real-time news monitoring...")
        
        tasks = [
            self._monitor_news_feeds(),
            self._process_signal_queue(),
            self._cleanup_old_signals()
        ]
        
        await asyncio.gather(*tasks)
    
    async def _monitor_news_feeds(self):
        """Monitor multiple news feeds concurrently."""
        while True:
            try:
                tasks = []
                
                for source_name, source_config in self.news_sources.items():
                    task = self._fetch_and_process_feed(source_name, source_config)
                    tasks.append(task)
                
                # Process all feeds concurrently
                await asyncio.gather(*tasks, return_exceptions=True)
                
                # Wait before next cycle (use shortest refresh interval)
                min_refresh = min(s['refresh_seconds'] for s in self.news_sources.values())
                await asyncio.sleep(min_refresh)
                
            except Exception as e:
                logger.error(f"Error in news monitoring loop: {e}")
                await asyncio.sleep(60)
    
    async def _fetch_and_process_feed(self, source_name: str, source_config: Dict):
        """Fetch and process a single news feed."""
        try:
            # Check if it's time to refresh this source
            now = datetime.now()
            last_check_key = f"last_check_{source_name}"
            
            if hasattr(self, last_check_key):
                last_check = getattr(self, last_check_key)
                if (now - last_check).seconds < source_config['refresh_seconds']:
                    return
            
            setattr(self, last_check_key, now)
            
            async with self.session.get(source_config['url']) as response:
                if response.status == 200:
                    content = await response.text()
                    await self._parse_feed_content(content, source_name, source_config)
                else:
                    logger.warning(f"Failed to fetch {source_name}: HTTP {response.status}")
                    
        except Exception as e:
            logger.error(f"Error fetching feed {source_name}: {e}")
    
    async def _parse_feed_content(self, content: str, source_name: str, source_config: Dict):
        """Parse RSS feed content and extract signals."""
        try:
            feed = feedparser.parse(content)
            
            for entry in feed.entries[:10]:  # Process latest 10 articles
                # Create unique hash for deduplication
                content_hash = hashlib.md5(
                    (entry.get('title', '') + entry.get('link', '')).encode()
                ).hexdigest()
                
                if content_hash in self.processed_articles:
                    continue
                
                self.processed_articles.add(content_hash)
                
                # Extract article data
                signal = await self._analyze_news_article(entry, source_name, source_config, content_hash)
                
                if signal:
                    if signal.urgency_score > 0.7:
                        await self._process_high_priority_signal(signal)
                    elif signal.market_impact_score > 0.4:
                        self.active_signals.append(signal)
                        
        except Exception as e:
            logger.error(f"Error parsing feed content for {source_name}: {e}")
    
    async def _analyze_news_article(self, entry, source_name: str, 
                                  source_config: Dict, content_hash: str) -> Optional[NewsSignal]:
        """Analyze a news article for trading signals."""
        try:
            title = entry.get('title', '')
            summary = entry.get('summary', entry.get('description', ''))
            url = entry.get('link', '')
            author = entry.get('author', 'Unknown')
            
            # Parse timestamp
            pub_date = entry.get('published_parsed')
            if pub_date:
                timestamp = datetime(*pub_date[:6])
            else:
                timestamp = datetime.now()
            
            # Skip old articles (older than 2 hours)
            if (datetime.now() - timestamp).hours > 2:
                return None
            
            # Combine title and summary for analysis
            full_text = f"{title}. {summary}"
            
            # Sentiment analysis
            sentiment_score = self._calculate_sentiment(full_text)
            
            # Extract mentioned tickers
            mentioned_tickers = self._extract_tickers_from_news(full_text, title)
            
            # Calculate urgency score
            urgency_score = self._calculate_news_urgency(full_text, source_config)
            
            # Calculate market impact score
            market_impact_score = self._calculate_news_market_impact(
                full_text, mentioned_tickers, source_config
            )
            
            # Categorize news
            category = self._categorize_news(full_text)
            
            # Only create signal if it meets minimum thresholds
            if urgency_score > 0.3 or market_impact_score > 0.3 or mentioned_tickers:
                return NewsSignal(
                    headline=title,
                    summary=summary[:500],  # Limit summary length
                    source=source_name,
                    url=url,
                    timestamp=timestamp,
                    author=author,
                    sentiment_score=sentiment_score,
                    mentioned_tickers=mentioned_tickers,
                    urgency_score=urgency_score,
                    market_impact_score=market_impact_score,
                    content_hash=content_hash,
                    category=category
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Error analyzing news article: {e}")
            return None
    
    def _calculate_sentiment(self, text: str) -> float:
        """Calculate sentiment score using multiple methods."""
        # VADER sentiment
        vader_score = self.sentiment_analyzer.polarity_scores(text)['compound']
        
        # TextBlob sentiment
        blob = TextBlob(text)
        textblob_score = blob.sentiment.polarity
        
        # Weighted average (VADER is better for social media/news)
        final_score = 0.7 * vader_score + 0.3 * textblob_score
        
        return final_score
    
    def _extract_tickers_from_news(self, text: str, title: str) -> List[str]:
        """Extract stock tickers from news text."""
        tickers = set()
        
        # Focus more on title as it's more likely to contain relevant tickers
        combined_text = f"{title} {text}"
        
        for pattern in self.ticker_patterns:
            matches = pattern.findall(combined_text)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]  # Extract from capture group
                
                # Clean and validate ticker
                ticker = match.upper().strip()
                if self._is_valid_ticker(ticker):
                    tickers.add(ticker)
        
        return list(tickers)
    
    def _is_valid_ticker(self, ticker: str) -> bool:
        """Validate if a string is likely a real stock ticker."""
        if len(ticker) < 1 or len(ticker) > 5:
            return False
        
        # Filter out common false positives
        false_positives = {
            'THE', 'AND', 'FOR', 'ARE', 'BUT', 'NOT', 'YOU', 'ALL', 'CAN',
            'NEW', 'TOP', 'GET', 'HOW', 'WHY', 'WHO', 'NOW', 'ONE', 'TWO',
            'CEO', 'CFO', 'CTO', 'IPO', 'SEC', 'FDA', 'FED', 'USA', 'USD'
        }
        
        return ticker not in false_positives
    
    def _calculate_news_urgency(self, text: str, source_config: Dict) -> float:
        """Calculate urgency score for news article."""
        urgency = 0.0
        text_upper = text.upper()
        
        # Urgent keywords
        for keyword in self.breaking_keywords['urgent']:
            if keyword in text_upper:
                urgency += 0.3
        
        # Source credibility
        source_weight = source_config.get('source_weight', 0.5)
        urgency += source_weight * 0.3
        
        # Time sensitivity (newer = more urgent)
        urgency += 0.2
        
        return min(urgency, 1.0)
    
    def _calculate_news_market_impact(self, text: str, tickers: List[str], 
                                    source_config: Dict) -> float:
        """Calculate potential market impact of news."""
        impact = 0.0
        text_lower = text.lower()
        
        # Market-moving keywords
        for keyword in self.breaking_keywords['market_moving']:
            if keyword in text_lower:
                impact += 0.3
        
        # Company event keywords
        for keyword in self.breaking_keywords['company_events']:
            if keyword in text_lower:
                impact += 0.2
        
        # Ticker mentions boost impact
        if tickers:
            impact += min(len(tickers) * 0.15, 0.4)
        
        # Source credibility
        source_weight = source_config.get('source_weight', 0.5)
        impact += source_weight * 0.2
        
        return min(impact, 1.0)
    
    def _categorize_news(self, text: str) -> str:
        """Categorize news article by type."""
        text_lower = text.lower()
        
        if any(word in text_lower for word in ['earnings', 'revenue', 'profit', 'loss']):
            return 'earnings'
        elif any(word in text_lower for word in ['merger', 'acquisition', 'buyout']):
            return 'ma'
        elif any(word in text_lower for word in ['fda', 'drug', 'approval', 'trial']):
            return 'regulatory'
        elif any(word in text_lower for word in ['lawsuit', 'investigation', 'fraud']):
            return 'legal'
        elif any(word in text_lower for word in ['fed', 'interest', 'rates', 'inflation']):
            return 'monetary'
        elif any(word in text_lower for word in ['breaking', 'urgent', 'alert']):
            return 'breaking'
        else:
            return 'general'
    
    async def _process_high_priority_signal(self, signal: NewsSignal):
        """Process high-priority news signals immediately."""
        logger.warning(f"🚨 HIGH PRIORITY NEWS: {signal.source} - {signal.headline}")
        
        priority_data = {
            'source': 'news',
            'priority': 'HIGH',
            'signal': signal,
            'timestamp': datetime.now(),
            'action_required': True
        }
        
        # Send to AI analysis pipeline
        await self._send_to_ai_analysis(priority_data)
    
    async def _send_to_ai_analysis(self, signal_data: Dict):
        """Send signal to AI analysis pipeline."""
        logger.info(f"📤 Sending {signal_data['priority']} news signal to AI analysis")
        # This will integrate with your AI analysis system
        pass
    
    async def _process_signal_queue(self):
        """Process accumulated news signals periodically."""
        while True:
            try:
                if self.active_signals:
                    # Sort by market impact score
                    self.active_signals.sort(key=lambda x: x.market_impact_score, reverse=True)
                    
                    # Group signals by ticker
                    ticker_signals = {}
                    for signal in self.active_signals[:20]:  # Top 20 signals
                        for ticker in signal.mentioned_tickers:
                            if ticker not in ticker_signals:
                                ticker_signals[ticker] = []
                            ticker_signals[ticker].append(signal)
                    
                    # Send aggregated signals
                    if ticker_signals:
                        await self._send_aggregated_news_signals(ticker_signals)
                
                await asyncio.sleep(300)  # Process every 5 minutes
                
            except Exception as e:
                logger.error(f"Error processing news signal queue: {e}")
                await asyncio.sleep(60)
    
    async def _send_aggregated_news_signals(self, ticker_signals: Dict):
        """Send aggregated ticker news signals."""
        for ticker, signals in ticker_signals.items():
            if len(signals) >= 2:  # Multiple news items for same ticker
                logger.info(f"📊 Multiple news signals for {ticker}: {len(signals)} articles")
                
                aggregated_data = {
                    'source': 'news_aggregated',
                    'ticker': ticker,
                    'signal_count': len(signals),
                    'avg_sentiment': sum(s.sentiment_score for s in signals) / len(signals),
                    'max_impact': max(s.market_impact_score for s in signals),
                    'categories': list(set(s.category for s in signals)),
                    'signals': signals,
                    'timestamp': datetime.now()
                }
                
                await self._send_to_ai_analysis(aggregated_data)
    
    async def _cleanup_old_signals(self):
        """Clean up old signals and processed articles."""
        while True:
            try:
                # Remove signals older than 4 hours
                cutoff_time = datetime.now() - timedelta(hours=4)
                self.active_signals = [
                    s for s in self.active_signals 
                    if s.timestamp > cutoff_time
                ]
                
                # Limit processed articles cache to prevent memory bloat
                if len(self.processed_articles) > 10000:
                    # Keep only the most recent 5000
                    self.processed_articles = set(list(self.processed_articles)[-5000:])
                
                await asyncio.sleep(3600)  # Cleanup every hour
                
            except Exception as e:
                logger.error(f"Error in cleanup: {e}")
                await asyncio.sleep(3600)
    
    def get_current_signals(self) -> List[NewsSignal]:
        """Get current active news signals."""
        cutoff_time = datetime.now() - timedelta(hours=1)
        return [s for s in self.active_signals if s.timestamp > cutoff_time]
    
    def get_ticker_news_sentiment(self, ticker: str) -> Dict:
        """Get aggregated news sentiment for a specific ticker."""
        relevant_signals = [
            s for s in self.active_signals 
            if ticker in s.mentioned_tickers
        ]
        
        if not relevant_signals:
            return {
                'sentiment_score': 0.0,
                'signal_count': 0,
                'confidence': 0.0,
                'categories': []
            }
        
        avg_sentiment = sum(s.sentiment_score for s in relevant_signals) / len(relevant_signals)
        confidence = min(len(relevant_signals) / 3, 1.0)
        categories = list(set(s.category for s in relevant_signals))
        
        return {
            'sentiment_score': avg_sentiment,
            'signal_count': len(relevant_signals),
            'confidence': confidence,
            'categories': categories,
            'latest_signals': relevant_signals[-5:]
        }

# Global instance
news_monitor = NewsMonitor()