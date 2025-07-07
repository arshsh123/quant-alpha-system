"""Main orchestrator for the Quant Alpha trading system."""

import asyncio
import logging
import signal
import sys
from datetime import datetime, time, timedelta
from typing import Dict, List
import json
import traceback
from pathlib import Path

# Configure logging
from config.settings import LOGGING_CONFIG, TRADING_TIMEZONE
from signal_processing.signal_combiner import signal_combiner
from data_sources.social_sentiment.twitter_monitor import twitter_monitor
from data_sources.social_sentiment.news_monitor import news_monitor
from data_sources.earnings_signals.earnings_monitor import earnings_monitor
from data_sources.options_flow.options_monitor import options_monitor

# Setup logging
logging.basicConfig(
    level=getattr(logging, LOGGING_CONFIG['level']),
    format=LOGGING_CONFIG['format'],
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/quant_alpha_system.log')
    ]
)

logger = logging.getLogger(__name__)

class QuantAlphaSystem:
    """Main orchestrator for the multi-signal trading system."""
    
    def __init__(self):
        self.is_running = False
        self.startup_time = None
        self.components = {
            'twitter_monitor': twitter_monitor,
            'news_monitor': news_monitor,
            'earnings_monitor': earnings_monitor,
            'options_monitor': options_monitor,
            'signal_combiner': signal_combiner
        }
        self.health_status = {}
        
    async def start(self):
        """Start the complete trading system."""
        try:
            self.startup_time = datetime.now()
            logger.info("🚀 Starting Quant Alpha Trading System...")
            logger.info(f"⏰ System time: {self.startup_time}")
            logger.info(f"📍 Trading timezone: {TRADING_TIMEZONE}")
            
            # Setup graceful shutdown
            self._setup_signal_handlers()
            
            # Pre-flight checks
            await self._run_preflight_checks()
            
            # Start all components
            self.is_running = True
            await self._start_all_components()
            
        except Exception as e:
            logger.error(f"❌ Failed to start system: {e}")
            logger.error(traceback.format_exc())
            await self.shutdown()
    
    def _setup_signal_handlers(self):
        """Setup graceful shutdown handlers."""
        def signal_handler(sig, frame):
            logger.info(f"📢 Received signal {sig}, initiating graceful shutdown...")
            asyncio.create_task(self.shutdown())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def _run_preflight_checks(self):
        """Run system health checks before starting."""
        logger.info("🔍 Running pre-flight checks...")
        
        # Check API keys
        api_checks = await self._check_api_keys()
        
        # Check market hours
        market_status = self._check_market_status()
        
        # Check disk space and memory
        system_checks = self._check_system_resources()
        
        # Log results
        logger.info(f"✅ API Keys: {sum(api_checks.values())}/{len(api_checks)} available")
        logger.info(f"📊 Market Status: {market_status}")
        logger.info(f"💻 System Resources: {system_checks}")
        
        if not any(api_checks.values()):
            logger.warning("⚠️  No API keys available - running in limited mode")
    
    async def _check_api_keys(self) -> Dict[str, bool]:
        """Check availability of API keys."""
        try:
            from config.api_keys import (
                TWITTER_BEARER_TOKEN, OPENAI_API_KEY
            )
            
            # Check optional APIs
            api_status = {
                'twitter': bool(TWITTER_BEARER_TOKEN),
                'openai': bool(OPENAI_API_KEY)
            }
            
            # Check free tier APIs if available
            try:
                from config.api_keys import FMP_API_KEY, IEX_API_KEY
                api_status['fmp'] = bool(FMP_API_KEY)
                api_status['iex'] = bool(IEX_API_KEY)
            except ImportError:
                pass
            
            # Check Reddit API
            try:
                from config.api_keys import REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET
                api_status['reddit'] = bool(REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET)
            except ImportError:
                api_status['reddit'] = False
            
            return api_status
            
        except ImportError as e:
            logger.error(f"Error importing API keys: {e}")
            return {'error': False}
    
    def _check_market_status(self) -> str:
        """Check current market status."""
        now = datetime.now(TRADING_TIMEZONE)
        current_time = now.time()
        
        # Market hours: 9:30 AM - 4:00 PM ET
        market_open = time(9, 30)
        market_close = time(16, 0)
        
        if now.weekday() >= 5:  # Weekend
            return "WEEKEND"
        elif current_time < time(4, 0):
            return "OVERNIGHT"
        elif current_time < market_open:
            return "PREMARKET"
        elif current_time <= market_close:
            return "MARKET_OPEN"
        else:
            return "AFTERHOURS"
    
    def _check_system_resources(self) -> Dict[str, str]:
        """Check system resources."""
        try:
            import psutil
            import shutil
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_status = f"{memory.percent:.1f}% used"
            
            # Disk space
            disk = shutil.disk_usage('/')
            disk_free_gb = disk.free / (1024**3)
            disk_status = f"{disk_free_gb:.1f}GB free"
            
            # CPU usage
            cpu_status = f"{psutil.cpu_percent(interval=1):.1f}% used"
            
            return {
                'memory': memory_status,
                'disk': disk_status,
                'cpu': cpu_status
            }
        except ImportError:
            return {'status': 'psutil not available'}
    
    async def _start_all_components(self):
        """Start all system components."""
        logger.info("🔧 Starting system components...")
        
        # Start components in order of dependency
        startup_tasks = []
        
        # 1. Start data collection components
        startup_tasks.append(self._start_twitter_monitoring())
        startup_tasks.append(self._start_news_monitoring())
        startup_tasks.append(self._start_earnings_monitoring())
        startup_tasks.append(self._start_options_monitoring())
        
        # 2. Start signal processing
        startup_tasks.append(self._start_signal_processing())
        
        # 3. Start health monitoring
        startup_tasks.append(self._start_health_monitoring())
        
        # 4. Start main control loop
        startup_tasks.append(self._start_main_loop())
        
        # Run all components concurrently
        await asyncio.gather(*startup_tasks, return_exceptions=True)
    
    async def _start_twitter_monitoring(self):
        """Start Twitter monitoring component."""
        try:
            logger.info("🐦 Starting Twitter monitoring...")
            async with twitter_monitor:
                await twitter_monitor.start_monitoring()
        except Exception as e:
            logger.error(f"❌ Twitter monitoring failed: {e}")
            self.health_status['twitter'] = False
    
    async def _start_news_monitoring(self):
        """Start news monitoring component."""
        try:
            logger.info("📰 Starting news monitoring...")
            async with news_monitor:
                await news_monitor.start_monitoring()
        except Exception as e:
            logger.error(f"❌ News monitoring failed: {e}")
            self.health_status['news'] = False
    
    async def _start_earnings_monitoring(self):
        """Start earnings monitoring component."""
        try:
            logger.info("📈 Starting earnings monitoring...")
            async with earnings_monitor:
                await earnings_monitor.start_monitoring()
        except Exception as e:
            logger.error(f"❌ Earnings monitoring failed: {e}")
            self.health_status['earnings'] = False
    
    async def _start_options_monitoring(self):
        """Start options monitoring component."""
        try:
            logger.info("📊 Starting options monitoring...")
            async with options_monitor:
                await options_monitor.start_monitoring()
        except Exception as e:
            logger.error(f"❌ Options monitoring failed: {e}")
            self.health_status['options'] = False
    
    async def _start_signal_processing(self):
        """Start signal processing component."""
        try:
            logger.info("🔄 Starting signal processing engine...")
            await signal_combiner.start_processing()
        except Exception as e:
            logger.error(f"❌ Signal processing failed: {e}")
            self.health_status['signal_combiner'] = False
    
    async def _start_health_monitoring(self):
        """Start health monitoring."""
        logger.info("❤️  Starting health monitoring...")
        
        while self.is_running:
            try:
                await self._run_health_checks()
                await asyncio.sleep(300)  # Check every 5 minutes
            except Exception as e:
                logger.error(f"Health monitoring error: {e}")
                await asyncio.sleep(60)
    
    async def _start_main_loop(self):
        """Start main control loop."""
        logger.info("🎮 Starting main control loop...")
        
        while self.is_running:
            try:
                await self._main_loop_iteration()
                await asyncio.sleep(60)  # Main loop every minute
            except Exception as e:
                logger.error(f"Main loop error: {e}")
                await asyncio.sleep(60)
    
    async def _main_loop_iteration(self):
        """Single iteration of main control loop."""
        try:
            # Get current signal summary
            signal_summary = signal_combiner.get_signal_summary()
            
            # Log periodic status
            if datetime.now().minute % 15 == 0:  # Every 15 minutes
                self._log_system_status(signal_summary)
            
            # Process high-priority signals
            strong_signals = [
                s for s in signal_summary.get('top_signals', [])
                if hasattr(s, 'action') and hasattr(s.action, 'value') and 
                s.action.value in ['strong_buy', 'strong_sell']
            ]
            
            if strong_signals:
                await self._process_strong_signals(strong_signals)
            
        except Exception as e:
            logger.error(f"Error in main loop iteration: {e}")
    
    def _log_system_status(self, signal_summary: Dict):
        """Log periodic system status."""
        uptime = datetime.now() - self.startup_time
        
        logger.info(f"📊 SYSTEM STATUS - Uptime: {uptime}")
        logger.info(f"   Signals: {signal_summary.get('total_signals', 0)} active")
        logger.info(f"   Buy/Sell: {signal_summary.get('buy', 0)}/{signal_summary.get('sell', 0)}")
        logger.info(f"   Strong: {signal_summary.get('strong_buy', 0)}/{signal_summary.get('strong_sell', 0)}")
        logger.info(f"   Market Regime: {signal_summary.get('market_regime', 'unknown')}")
        
        # Log component health
        healthy_components = sum(1 for status in self.health_status.values() if status)
        total_components = len(self.components)
        logger.info(f"   Component Health: {healthy_components}/{total_components}")
    
    async def _process_strong_signals(self, strong_signals: List):
        """Process strong trading signals."""
        for signal in strong_signals:
            logger.warning(f"⚡ PROCESSING STRONG SIGNAL: {signal.ticker} - {signal.action.value}")
            
            # Here you would integrate with your execution engine
            # For now, just log the signal details
            logger.info(f"   Score: {signal.final_score:.3f}")
            logger.info(f"   Confidence: {signal.confidence:.3f}")
            logger.info(f"   Position Size: {signal.position_size_suggestion:.3f}")
            if hasattr(signal, 'entry_price_target') and signal.entry_price_target:
                logger.info(f"   Entry Target: ${signal.entry_price_target:.2f}")
    
    async def _run_health_checks(self):
        """Run comprehensive health checks."""
        try:
            # Check component responsiveness
            for component_name, component in self.components.items():
                try:
                    # Basic health check - component should respond
                    if hasattr(component, 'get_current_signals'):
                        signals = component.get_current_signals()
                        self.health_status[component_name] = True
                    else:
                        self.health_status[component_name] = True
                except Exception as e:
                    logger.warning(f"Health check failed for {component_name}: {e}")
                    self.health_status[component_name] = False
            
            # Check memory usage
            try:
                import psutil
                memory_usage = psutil.virtual_memory().percent
                if memory_usage > 90:
                    logger.warning(f"⚠️  High memory usage: {memory_usage:.1f}%")
            except ImportError:
                pass
            
            # Check signal freshness
            await self._check_signal_freshness()
            
        except Exception as e:
            logger.error(f"Error in health checks: {e}")
    
    async def _check_signal_freshness(self):
        """Check if signals are being generated regularly."""
        try:
            signal_summary = signal_combiner.get_signal_summary()
            
            if signal_summary.get('total_signals', 0) == 0:
                logger.warning("⚠️  No active signals detected")
            
            # Check if we're getting new signals from each source
            try:
                # Twitter signals should be frequent during market hours
                twitter_signals = twitter_monitor.get_current_signals()
                if len(twitter_signals) == 0 and self._check_market_status() == "MARKET_OPEN":
                    logger.warning("⚠️  No recent Twitter signals during market hours")
            except Exception:
                pass
            
            try:
                # News signals should be regular
                news_signals = news_monitor.get_current_signals()
                if len(news_signals) == 0:
                    logger.info("ℹ️  No recent news signals (may be normal)")
            except Exception:
                pass
                
        except Exception as e:
            logger.error(f"Error checking signal freshness: {e}")
    
    async def shutdown(self):
        """Gracefully shutdown the system."""
        logger.info("🛑 Initiating system shutdown...")
        
        self.is_running = False
        
        # Save current state
        await self._save_system_state()
        
        # Close all connections
        await self._cleanup_resources()
        
        # Final status
        uptime = datetime.now() - self.startup_time if self.startup_time else "unknown"
        logger.info(f"✅ System shutdown complete. Total uptime: {uptime}")
        
        sys.exit(0)
    
    async def _save_system_state(self):
        """Save current system state for recovery."""
        try:
            signal_summary = signal_combiner.get_signal_summary()
            all_signals = signal_combiner.get_all_active_signals()
            
            state = {
                'shutdown_time': datetime.now().isoformat(),
                'uptime_seconds': (datetime.now() - self.startup_time).total_seconds() if self.startup_time else 0,
                'health_status': self.health_status,
                'signal_summary': signal_summary,
                'last_signals': [
                    {
                        'ticker': s.ticker,
                        'action': s.action.value if hasattr(s.action, 'value') else str(s.action),
                        'score': s.final_score,
                        'confidence': s.confidence,
                        'timestamp': s.timestamp.isoformat()
                    }
                    for s in all_signals[:10]
                ]
            }
            
            # Save to file
            state_file = Path("data/last_system_state.json")
            state_file.parent.mkdir(exist_ok=True)
            
            with open(state_file, 'w') as f:
                json.dump(state, f, indent=2, default=str)
            
            logger.info(f"💾 System state saved to {state_file}")
            
        except Exception as e:
            logger.error(f"Error saving system state: {e}")
    
    async def _cleanup_resources(self):
        """Clean up all system resources."""
        try:
            # Close any open connections
            for component_name, component in self.components.items():
                if hasattr(component, 'session') and component.session:
                    try:
                        await component.session.close()
                        logger.info(f"✅ Closed {component_name} session")
                    except Exception as e:
                        logger.warning(f"⚠️  Error closing {component_name} session: {e}")
            
            logger.info("🧹 Resource cleanup complete")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    def get_system_status(self) -> Dict:
        """Get comprehensive system status."""
        uptime = datetime.now() - self.startup_time if self.startup_time else timedelta(0)
        
        return {
            'is_running': self.is_running,
            'uptime': str(uptime),
            'startup_time': self.startup_time.isoformat() if self.startup_time else None,
            'market_status': self._check_market_status(),
            'health_status': self.health_status,
            'signal_summary': signal_combiner.get_signal_summary(),
            'component_count': len(self.components),
            'healthy_components': sum(1 for status in self.health_status.values() if status)
        }

class TradingSystemCLI:
    """Command line interface for the trading system."""
    
    def __init__(self):
        self.system = QuantAlphaSystem()
    
    async def run(self):
        """Run the CLI interface."""
        try:
            await self.system.start()
        except KeyboardInterrupt:
            logger.info("👋 Received keyboard interrupt")
            await self.system.shutdown()
        except Exception as e:
            logger.error(f"❌ System error: {e}")
            logger.error(traceback.format_exc())
            await self.system.shutdown()

# Global system instance
trading_system = QuantAlphaSystem()

if __name__ == "__main__":
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Quant Alpha Trading System")
    parser.add_argument("--mode", choices=["live", "paper", "backtest"], 
                       default="paper", help="Trading mode")
    parser.add_argument("--config", help="Custom config file path")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], 
                       default="INFO", help="Logging level")
    
    args = parser.parse_args()
    
    # Update logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # Print startup banner
    print("""
╔═══════════════════════════════════════════════════════════════╗
║                    QUANT ALPHA SYSTEM                        ║
║                   Multi-Signal Trading Bot                   ║
║                                                               ║
║  📊 Social Sentiment • 📰 News Analysis • 📈 Earnings        ║
║  🎯 Multi-Signal Fusion • ⚡ Real-time Execution             ║
╚═══════════════════════════════════════════════════════════════╝
    """)
    
    logger.info(f"🚀 Starting in {args.mode.upper()} mode")
    
    # Start the system
    cli = TradingSystemCLI()
    
    try:
        asyncio.run(cli.run())
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)