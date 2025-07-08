"""Main orchestrator with enhanced error handling and missing component management."""

import asyncio
import logging
import signal
import sys
from datetime import datetime, time, timedelta
from typing import Dict, List
import json
import traceback
from pathlib import Path

# Configure logging first
from config.settings import LOGGING_CONFIG, TRADING_TIMEZONE
from signal_processing.signal_combiner import signal_combiner

# Import monitors with error handling
try:
    from data_sources.social_sentiment.twitter_monitor import twitter_monitor
    TWITTER_AVAILABLE = True
except Exception as e:
    logger = logging.getLogger(__name__)
    logger.warning(f"Twitter monitor not available: {e}")
    twitter_monitor = None
    TWITTER_AVAILABLE = False

try:
    from data_sources.social_sentiment.news_monitor import news_monitor
    NEWS_AVAILABLE = True
except Exception as e:
    logger = logging.getLogger(__name__)
    logger.warning(f"News monitor not available: {e}")
    news_monitor = None
    NEWS_AVAILABLE = False

try:
    from data_sources.earnings_signals.earnings_monitor import earnings_monitor
    EARNINGS_AVAILABLE = True
except Exception as e:
    logger = logging.getLogger(__name__)
    logger.warning(f"Earnings monitor not available: {e}")
    earnings_monitor = None
    EARNINGS_AVAILABLE = False

try:
    from data_sources.options_flow.options_monitor import options_monitor
    OPTIONS_AVAILABLE = True
except Exception as e:
    logger = logging.getLogger(__name__)
    logger.warning(f"Options monitor not available: {e}")
    options_monitor = None
    OPTIONS_AVAILABLE = False

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
    """Main orchestrator with enhanced error handling."""
    
    def __init__(self):
        self.is_running = False
        self.startup_time = None
        self.components = self._initialize_available_components()
        self.health_status = {}
        self.component_tasks = {}  # Track running tasks
        
    def _initialize_available_components(self):
        """Initialize only available components."""
        components = {}
        
        if TWITTER_AVAILABLE and twitter_monitor:
            components['twitter_monitor'] = twitter_monitor
        
        if NEWS_AVAILABLE and news_monitor:
            components['news_monitor'] = news_monitor
            
        if EARNINGS_AVAILABLE and earnings_monitor:
            components['earnings_monitor'] = earnings_monitor
            
        if OPTIONS_AVAILABLE and options_monitor:
            components['options_monitor'] = options_monitor
            
        components['signal_combiner'] = signal_combiner
        
        logger.info(f"✅ Initialized {len(components)} components: {list(components.keys())}")
        return components
        
    async def start(self):
        """Start the complete trading system with enhanced error handling."""
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
        
        # Check system resources
        system_checks = self._check_system_resources()
        
        # Check component availability
        component_status = self._check_component_availability()
        
        # Log results
        logger.info(f"✅ API Keys: {sum(api_checks.values())}/{len(api_checks)} available")
        logger.info(f"📊 Market Status: {market_status}")
        logger.info(f"💻 System Resources: {system_checks}")
        logger.info(f"🔧 Components: {component_status}")
        
        if not any(api_checks.values()):
            logger.warning("⚠️  No API keys available - running in limited mode")
            
        if len(self.components) < 2:
            logger.error("❌ Insufficient components available - need at least 2")
            raise RuntimeError("Insufficient components for operation")
    
    def _check_component_availability(self) -> str:
        """Check which components are available."""
        available = []
        missing = []
        
        if TWITTER_AVAILABLE:
            available.append("Twitter")
        else:
            missing.append("Twitter")
            
        if NEWS_AVAILABLE:
            available.append("News")
        else:
            missing.append("News")
            
        if EARNINGS_AVAILABLE:
            available.append("Earnings")
        else:
            missing.append("Earnings")
            
        if OPTIONS_AVAILABLE:
            available.append("Options")
        else:
            missing.append("Options")
        
        status = f"Available: {', '.join(available)}"
        if missing:
            status += f" | Missing: {', '.join(missing)}"
            
        return status
    
    async def _check_api_keys(self) -> Dict[str, bool]:
        """Check availability of API keys."""
        try:
            api_status = {}
            
            # Check Twitter API
            if TWITTER_AVAILABLE:
                try:
                    from config.api_keys import TWITTER_BEARER_TOKEN
                    api_status['twitter'] = bool(TWITTER_BEARER_TOKEN)
                except ImportError:
                    api_status['twitter'] = False
            else:
                api_status['twitter'] = False
            
            # Check financial APIs
            try:
                from config.api_keys import FMP_API_KEY, ALPHA_VANTAGE_KEY
                api_status['fmp'] = bool(FMP_API_KEY)
                api_status['alpha_vantage'] = bool(ALPHA_VANTAGE_KEY)
            except ImportError:
                api_status['fmp'] = False
                api_status['alpha_vantage'] = False
            
            # Check AI APIs
            try:
                from config.api_keys import OPENAI_API_KEY
                api_status['openai'] = bool(OPENAI_API_KEY)
            except ImportError:
                api_status['openai'] = False
            
            return api_status
            
        except Exception as e:
            logger.error(f"Error checking API keys: {e}")
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
    
    async def safe_component_wrapper(self, component_name: str, component_func):
        """Safely run a component with error handling and restart capability."""
        restart_count = 0
        max_restarts = 5
        
        while self.is_running and restart_count < max_restarts:
            try:
                logger.info(f"🔧 Starting {component_name}...")
                await component_func()
                
            except Exception as e:
                restart_count += 1
                logger.error(f"❌ {component_name} crashed (attempt {restart_count}/{max_restarts}): {e}")
                
                if restart_count < max_restarts:
                    wait_time = min(60 * restart_count, 300)  # Exponential backoff, max 5 min
                    logger.info(f"⏳ Restarting {component_name} in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"💀 {component_name} failed permanently, marking as unhealthy")
                    self.health_status[component_name] = False
                    break
    
    async def _start_all_components(self):
        """Start all available components with error handling."""
        logger.info("🔧 Starting system components...")
        
        startup_tasks = []
        
        # Start available data collection components
        if 'twitter_monitor' in self.components:
            task = asyncio.create_task(
                self.safe_component_wrapper('twitter_monitor', self._start_twitter_monitoring)
            )
            startup_tasks.append(task)
            self.component_tasks['twitter_monitor'] = task
        
        if 'news_monitor' in self.components:
            task = asyncio.create_task(
                self.safe_component_wrapper('news_monitor', self._start_news_monitoring)
            )
            startup_tasks.append(task)
            self.component_tasks['news_monitor'] = task
            
        if 'earnings_monitor' in self.components:
            task = asyncio.create_task(
                self.safe_component_wrapper('earnings_monitor', self._start_earnings_monitoring)
            )
            startup_tasks.append(task)
            self.component_tasks['earnings_monitor'] = task
            
        if 'options_monitor' in self.components:
            task = asyncio.create_task(
                self.safe_component_wrapper('options_monitor', self._start_options_monitoring)
            )
            startup_tasks.append(task)
            self.component_tasks['options_monitor'] = task
        
        # Start signal processing
        task = asyncio.create_task(
            self.safe_component_wrapper('signal_combiner', self._start_signal_processing)
        )
        startup_tasks.append(task)
        self.component_tasks['signal_combiner'] = task
        
        # Start monitoring tasks
        startup_tasks.append(asyncio.create_task(self._start_health_monitoring()))
        startup_tasks.append(asyncio.create_task(self._start_main_loop()))
        
        # Run all components concurrently
        try:
            await asyncio.gather(*startup_tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"Error in component startup: {e}")
    
    async def _start_twitter_monitoring(self):
        """Start Twitter monitoring component."""
        if twitter_monitor:
            async with twitter_monitor:
                await twitter_monitor.start_monitoring()
        else:
            logger.warning("Twitter monitor not available")
    
    async def _start_news_monitoring(self):
        """Start news monitoring component."""
        if news_monitor:
            async with news_monitor:
                await news_monitor.start_monitoring()
        else:
            logger.warning("News monitor not available")
    
    async def _start_earnings_monitoring(self):
        """Start earnings monitoring component."""
        if earnings_monitor:
            async with earnings_monitor:
                await earnings_monitor.start_monitoring()
        else:
            logger.warning("Earnings monitor not available")
    
    async def _start_options_monitoring(self):
        """Start options monitoring component."""
        if options_monitor:
            async with options_monitor:
                await options_monitor.start_monitoring()
        else:
            logger.warning("Options monitor not available")
    
    async def _start_signal_processing(self):
        """Start signal processing component."""
        await signal_combiner.start_processing()
    
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
        logger.info(f"   Conflicts: {signal_summary.get('signals_with_conflicts', 0)} signals with conflicts")
        
        # Log component health
        healthy_components = sum(1 for status in self.health_status.values() if status)
        total_components = len(self.components)
        logger.info(f"   Component Health: {healthy_components}/{total_components}")
        
        # Log performance metrics if available
        performance_summary = signal_summary.get('performance_summary', {})
        if performance_summary:
            logger.info("   Signal Performance:")
            for signal_type, metrics in performance_summary.items():
                accuracy = metrics.get('accuracy', 0.5)
                total = metrics.get('total_signals', 0)
                logger.info(f"     {signal_type}: {accuracy:.2f} accuracy ({total} signals)")
    
    async def _process_strong_signals(self, strong_signals: List):
        """Process strong trading signals."""
        for signal in strong_signals:
            logger.warning(f"⚡ PROCESSING STRONG SIGNAL: {signal.ticker} - {signal.action.value}")
            
            # Log signal details
            logger.info(f"   Score: {signal.final_score:.3f}")
            logger.info(f"   Confidence: {signal.confidence:.3f}")
            logger.info(f"   Position Size: {signal.position_size_suggestion:.3f}")
            logger.info(f"   Signal Strength: {signal.signal_strength:.3f}")
            
            if hasattr(signal, 'signal_conflicts') and signal.signal_conflicts:
                logger.warning(f"   ⚠️  Conflicts: {', '.join(signal.signal_conflicts)}")
            
            if hasattr(signal, 'dynamic_weights') and signal.dynamic_weights:
                weights_str = ', '.join([f"{k.value}: {v:.2f}" for k, v in signal.dynamic_weights.items()])
                logger.info(f"   Weights Used: {weights_str}")
            
            if hasattr(signal, 'entry_price_target') and signal.entry_price_target:
                logger.info(f"   Entry Target: ${signal.entry_price_target:.2f}")
                
            if hasattr(signal, 'stop_loss_target') and signal.stop_loss_target:
                logger.info(f"   Stop Loss: ${signal.stop_loss_target:.2f}")
                
            # Here you would integrate with your execution engine
            await self._send_to_execution_engine(signal)
    
    async def _send_to_execution_engine(self, signal):
        """Send signal to execution engine."""
        logger.info(f"📤 Sending to execution: {signal.ticker} - {signal.action.value}")
        
        # Placeholder for execution engine integration
        execution_data = {
            'ticker': signal.ticker,
            'action': signal.action.value,
            'quantity': signal.position_size_suggestion,
            'entry_price': getattr(signal, 'entry_price_target', None),
            'stop_loss': getattr(signal, 'stop_loss_target', None),
            'take_profit': getattr(signal, 'take_profit_target', None),
            'confidence': signal.confidence,
            'timestamp': signal.timestamp,
            'signal_id': f"{signal.ticker}_{signal.timestamp.strftime('%Y%m%d_%H%M%S')}"
        }
        
        # Log the execution order (in production, this would go to broker)
        logger.info(f"📋 EXECUTION ORDER: {json.dumps(execution_data, default=str, indent=2)}")
    
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
            
            # Check for stuck components
            await self._check_component_tasks()
            
        except Exception as e:
            logger.error(f"Error in health checks: {e}")
    
    async def _check_signal_freshness(self):
        """Check if signals are being generated regularly."""
        try:
            signal_summary = signal_combiner.get_signal_summary()
            
            if signal_summary.get('total_signals', 0) == 0:
                logger.warning("⚠️  No active signals detected")
            
            # Check if we're getting new signals from each source
            market_status = self._check_market_status()
            
            if TWITTER_AVAILABLE and twitter_monitor:
                try:
                    twitter_signals = twitter_monitor.get_current_signals()
                    if len(twitter_signals) == 0 and market_status == "MARKET_OPEN":
                        logger.warning("⚠️  No recent Twitter signals during market hours")
                except Exception:
                    pass
            
            if NEWS_AVAILABLE and news_monitor:
                try:
                    news_signals = news_monitor.get_current_signals()
                    if len(news_signals) == 0:
                        logger.info("ℹ️  No recent news signals (may be normal)")
                except Exception:
                    pass
            
            if OPTIONS_AVAILABLE and options_monitor:
                try:
                    options_signals = options_monitor.get_current_signals()
                    logger.info(f"📊 Options signals: {len(options_signals)} active")
                except Exception:
                    pass
                
        except Exception as e:
            logger.error(f"Error checking signal freshness: {e}")
    
    async def _check_component_tasks(self):
        """Check if component tasks are still running."""
        for component_name, task in self.component_tasks.items():
            if task.done():
                if task.exception():
                    logger.error(f"💀 {component_name} task died with exception: {task.exception()}")
                else:
                    logger.warning(f"⚠️  {component_name} task completed unexpectedly")
                
                self.health_status[component_name] = False
    
    async def shutdown(self):
        """Gracefully shutdown the system."""
        logger.info("🛑 Initiating system shutdown...")
        
        self.is_running = False
        
        # Cancel all component tasks
        for component_name, task in self.component_tasks.items():
            if not task.done():
                logger.info(f"🛑 Cancelling {component_name} task...")
                task.cancel()
                try:
                    await asyncio.wait_for(task, timeout=5.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass
        
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
                'component_availability': {
                    'twitter': TWITTER_AVAILABLE,
                    'news': NEWS_AVAILABLE,
                    'earnings': EARNINGS_AVAILABLE,
                    'options': OPTIONS_AVAILABLE
                },
                'last_signals': [
                    {
                        'ticker': s.ticker,
                        'action': s.action.value if hasattr(s.action, 'value') else str(s.action),
                        'score': s.final_score,
                        'confidence': s.confidence,
                        'timestamp': s.timestamp.isoformat(),
                        'conflicts': getattr(s, 'signal_conflicts', [])
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
            'healthy_components': sum(1 for status in self.health_status.values() if status),
            'available_components': {
                'twitter': TWITTER_AVAILABLE,
                'news': NEWS_AVAILABLE,
                'earnings': EARNINGS_AVAILABLE,
                'options': OPTIONS_AVAILABLE
            }
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
    parser.add_argument("--components", help="Comma-separated list of components to enable",
                       default="all")
    
    args = parser.parse_args()
    
    # Update logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # Print startup banner
    print("""
╔═══════════════════════════════════════════════════════════════╗
║                    QUANT ALPHA SYSTEM v2.0                   ║
║              Enhanced Multi-Signal Trading Bot               ║
║                                                               ║
║  📊 Social Sentiment • 📰 News Analysis • 📈 Earnings        ║
║  📊 Options Flow • 🎯 Dynamic Signal Fusion • ⚡ Real-time   ║
║                                                               ║
║  ✨ NEW: Signal Decay • Conflict Detection • Smart Weights  ║
╚═══════════════════════════════════════════════════════════════╝
    """)
    
    logger.info(f"🚀 Starting in {args.mode.upper()} mode")
    
    # Component availability status
    components_status = []
    if TWITTER_AVAILABLE:
        components_status.append("✅ Twitter")
    else:
        components_status.append("❌ Twitter")
        
    if NEWS_AVAILABLE:
        components_status.append("✅ News")
    else:
        components_status.append("❌ News")
        
    if EARNINGS_AVAILABLE:
        components_status.append("✅ Earnings")
    else:
        components_status.append("❌ Earnings")
        
    if OPTIONS_AVAILABLE:
        components_status.append("✅ Options")
    else:
        components_status.append("❌ Options")
    
    logger.info(f"📦 Component Status: {' | '.join(components_status)}")
    
    # Start the system
    cli = TradingSystemCLI()
    
    try:
        asyncio.run(cli.run())
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)