#!/usr/bin/env python3
"""
TrendBot - Automated Tech Trends Analysis and Publishing System

A comprehensive bot that collects, analyzes, visualizes, and publishes
technology trends from multiple sources including Twitter, GitHub, Reddit, and Hacker News.
"""

import sys
import os
import argparse
import signal
import time
import resource
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from pathlib import Path

# Import configuration first
from config import get_config, get_logger, validate_environment_quick

# Import our modules
from database import TrendDatabase
from collectors import DataCollector
from analyzer import TrendAnalyzer
from visualizer import TrendVisualizer
from publisher import TwitterPublisher
from scheduler import TrendBotScheduler

class TrendBot:
    """Main orchestrator class for the TrendBot system."""
    
    def __init__(self, config_file: Optional[str] = None):
        """Initialize TrendBot with configuration."""
        try:
            # Initialize configuration and logging
            self.config = get_config()
            if config_file:
                self.config = get_config()  # Re-initialize with config file if needed
            
            self.logger = get_logger(__name__)
            self.logger.info("Initializing TrendBot...")
            
            # Validate environment
            if not validate_environment_quick():
                raise EnvironmentError("Environment validation failed")
            
            # Initialize components with error handling
            self._initialize_components()
            
            # State tracking
            self.is_running = False
            self.last_collection_time = None
            self.last_analysis_time = None
            self.last_publish_time = None
            self.initialization_time = datetime.now()
            self.error_count = 0
            self.success_count = 0
            
            # Health monitoring
            # Memory monitoring removed for MVP simplicity
            
            # Setup signal handlers for graceful shutdown
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
            
            self.logger.info("TrendBot initialized successfully")
            self._log_system_info()
            
        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.error(f"Failed to initialize TrendBot: {e}", exc_info=True)
            else:
                print(f"Failed to initialize TrendBot: {e}")
            raise
    
    def _initialize_components(self):
        """Initialize all TrendBot components with error handling."""
        component_errors = []
        
        try:
            self.database = TrendDatabase(config=self.config)
            self.logger.info("Database component initialized")
        except Exception as e:
            error_msg = f"Database initialization failed: {e}"
            self.logger.error(error_msg, exc_info=True)
            component_errors.append(error_msg)
        
        try:
            self.collector = DataCollector(config=self.config)
            self.logger.info("Data collector initialized")
        except Exception as e:
            error_msg = f"Data collector initialization failed: {e}"
            self.logger.error(error_msg, exc_info=True)
            component_errors.append(error_msg)
        
        try:
            self.analyzer = TrendAnalyzer(config=self.config)
            self.logger.info("Trend analyzer initialized")
        except Exception as e:
            error_msg = f"Trend analyzer initialization failed: {e}"
            self.logger.error(error_msg, exc_info=True)
            component_errors.append(error_msg)
        
        try:
            self.visualizer = TrendVisualizer(
                output_dir=self.config.get('viz_output_dir', 'visualizations'),
                config=self.config
            )
            self.logger.info("Visualizer initialized")
        except Exception as e:
            error_msg = f"Visualizer initialization failed: {e}"
            self.logger.error(error_msg, exc_info=True)
            component_errors.append(error_msg)
        
        try:
            self.publisher = TwitterPublisher(config=self.config)
            self.logger.info("Twitter publisher initialized")
        except Exception as e:
            error_msg = f"Twitter publisher initialization failed: {e}"
            self.logger.error(error_msg, exc_info=True)
            component_errors.append(error_msg)
        
        try:
            self.scheduler = TrendBotScheduler(config=self.config)
            self.logger.info("Scheduler initialized")
        except Exception as e:
            error_msg = f"Scheduler initialization failed: {e}"
            self.logger.error(error_msg, exc_info=True)
            component_errors.append(error_msg)
        
        if component_errors:
            error_summary = "\n".join(component_errors)
            raise RuntimeError(f"Component initialization failed:\n{error_summary}")
    
    def _log_system_info(self):
        """Log system information for debugging."""
        try:
            import platform
            self.logger.info(f"Python version: {sys.version}")
            self.logger.info(f"Platform: {platform.platform()}")
            self.logger.info(f"Working directory: {os.getcwd()}")
            
            # Memory info using resource module
            try:
                import resource
                memory_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                # On macOS ru_maxrss is in bytes, on Linux it's in KB
                import platform
                if platform.system() == 'Darwin':
                    memory_mb = memory_kb / (1024 * 1024)
                else:
                    memory_mb = memory_kb / 1024
                self.logger.info(f"Initial memory usage: {memory_mb:.2f} MB")
            except Exception as e:
                self.logger.debug(f"Could not get memory info: {e}")
            
        except Exception as e:
            self.logger.debug(f"Could not log system info: {e}")
    
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        self.logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.stop()
        sys.exit(0)
    
    def collect_trends(self) -> Dict[str, Any]:
        """Collect trends from all data sources with comprehensive error handling."""
        start_time = datetime.now()
        operation_id = f"collect_{int(start_time.timestamp())}"
        
        self.logger.info(f"[{operation_id}] Starting trend collection...")
        
        try:
            # Pre-flight checks
            if not self._pre_flight_checks():
                error_msg = "Pre-flight checks failed"
                self.logger.error(f"[{operation_id}] {error_msg}")
                self.error_count += 1
                return {'success': False, 'message': error_msg, 'count': 0, 'operation_id': operation_id}
            
            # Memory check removed for MVP simplicity
            
            # Collect from all sources with timeout
            trends_data = self._collect_with_timeout()
            
            if not trends_data:
                self.logger.warning(f"[{operation_id}] No trends collected from any source")
                return {
                    'success': False, 
                    'message': 'No trends collected', 
                    'count': 0,
                    'operation_id': operation_id,
                    'duration_seconds': (datetime.now() - start_time).total_seconds()
                }
            
            # Store in database with batch processing
            stored_count = self._store_trends_batch(trends_data, operation_id)
            
            self.last_collection_time = datetime.now()
            duration = (self.last_collection_time - start_time).total_seconds()
            
            result = {
                'success': True,
                'message': f'Collected and stored {stored_count} trends',
                'count': stored_count,
                'collected_count': len(trends_data),
                'timestamp': self.last_collection_time.isoformat(),
                'operation_id': operation_id,
                'duration_seconds': duration
            }
            
            self.success_count += 1
            self.logger.info(f"[{operation_id}] Trend collection completed: {stored_count}/{len(trends_data)} trends stored in {duration:.2f}s")
            return result
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.error_count += 1
            self.logger.error(f"[{operation_id}] Error in trend collection: {e}", exc_info=True)
            return {
                'success': False, 
                'message': str(e), 
                'count': 0,
                'operation_id': operation_id,
                'duration_seconds': duration
            }
    
    def _collect_with_timeout(self) -> list:
        """Collect trends with timeout protection."""
        import concurrent.futures
        
        timeout = self.config.get('collection_timeout', 300)  # 5 minutes
        
        try:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(self.collector.collect_all_trends)
                return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            self.logger.error("Trend collection timed out")
            raise TimeoutError(f"Collection timed out after {timeout} seconds")
    
    def _store_trends_batch(self, trends_data: list, operation_id: str) -> int:
        """Store trends in database with batch processing and error handling."""
        stored_count = 0
        failed_count = 0
        
        for i, trend in enumerate(trends_data):
            try:
                trend_id = self.database.insert_trend_data(
                    source=trend['source'],
                    topic=trend['topic'],
                    content=trend.get('content'),
                    url=trend.get('url'),
                    engagement_score=trend.get('engagement_score', 0),
                    metadata=trend.get('metadata')
                )
                stored_count += 1
                
                if i % 10 == 0:  # Log progress every 10 items
                    self.logger.debug(f"[{operation_id}] Stored {stored_count}/{len(trends_data)} trends")
                    
            except Exception as e:
                failed_count += 1
                self.logger.warning(f"[{operation_id}] Failed to store trend {i+1}: {e}")
                
                # Stop if too many failures
                if failed_count > len(trends_data) * 0.5:  # More than 50% failures
                    self.logger.error(f"[{operation_id}] Too many storage failures ({failed_count}), stopping")
                    break
                    
                continue
        
        if failed_count > 0:
            self.logger.warning(f"[{operation_id}] Storage completed with {failed_count} failures")
        
        return stored_count
    
    def _pre_flight_checks(self) -> bool:
        """Perform pre-flight checks before operations."""
        try:
            # Check database connectivity
            if not hasattr(self, 'database') or not self.database:
                self.logger.error("Database not available")
                return False
            
            # Check disk space
            if not self.config.validate_disk_space(100):  # 100MB minimum
                self.logger.error("Insufficient disk space")
                return False
            
            # Check API availability (basic)
            if not hasattr(self, 'collector') or not self.collector:
                self.logger.error("Data collector not available")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Pre-flight check failed: {e}")
            return False
    
    def analyze_trends(self, hours_back: int = 24) -> Dict[str, Any]:
        """Analyze recent trends and generate insights."""
        try:
            self.logger.info(f"Starting trend analysis for last {hours_back} hours...")
            
            # Get recent trends from database
            recent_trends = self.database.get_recent_trend_data(hours=hours_back)
            
            if not recent_trends:
                self.logger.warning("No recent trends found for analysis")
                return {'success': False, 'message': 'No recent trends found'}
            
            # Perform analysis
            analysis_result = self.analyzer.analyze_trends_batch(recent_trends)
            
            # Validate analysis quality
            is_valid, validation_msg = self.analyzer.validate_analysis_quality(analysis_result)
            if not is_valid:
                self.logger.warning(f"Analysis validation failed: {validation_msg}")
                return {'success': False, 'message': f'Analysis validation failed: {validation_msg}'}
            
            # Store analysis in database
            analysis_id = self.database.insert_trend_analysis(
                trends_summary=analysis_result['summary'],
                sentiment_score=analysis_result['sentiment_score'],
                insights=analysis_result['insights'],
                data_points_count=len(recent_trends)
            )
            
            analysis_result['analysis_id'] = analysis_id
            self.last_analysis_time = datetime.now()
            
            self.logger.info(f"Trend analysis completed: ID {analysis_id}")
            return {'success': True, 'analysis': analysis_result}
            
        except Exception as e:
            self.logger.error(f"Error in trend analysis: {e}")
            return {'success': False, 'message': str(e)}
    
    def generate_visualizations(self, hours_back: int = 24) -> Dict[str, Any]:
        """Generate visualizations from recent data."""
        try:
            self.logger.info("Generating visualizations...")
            
            # Get recent data
            recent_trends = self.database.get_recent_trend_data(hours=hours_back)
            recent_analyses = []  # Would need to implement get_recent_analyses in database
            
            generated_files = []
            
            # Generate different types of visualizations
            if recent_trends:
                # Source breakdown
                source_chart = self.visualizer.create_source_breakdown_chart(recent_trends)
                if source_chart:
                    generated_files.append(source_chart)
                
                # Top topics
                topics_chart = self.visualizer.create_top_topics_bar(recent_trends)
                if topics_chart:
                    generated_files.append(topics_chart)
                
                # Engagement scatter
                engagement_chart = self.visualizer.create_engagement_scatter(recent_trends)
                if engagement_chart:
                    generated_files.append(engagement_chart)
                
                # Comprehensive dashboard
                dashboard = self.visualizer.create_comprehensive_dashboard(
                    recent_analyses, recent_trends
                )
                if dashboard:
                    generated_files.append(dashboard)
            
            self.logger.info(f"Generated {len(generated_files)} visualizations")
            return {
                'success': True,
                'files': generated_files,
                'count': len(generated_files)
            }
            
        except Exception as e:
            self.logger.error(f"Error generating visualizations: {e}")
            return {'success': False, 'message': str(e)}
    
    def publish_analysis(self, analysis_result: Optional[Dict] = None) -> Dict[str, Any]:
        """Publish analysis results to social media."""
        try:
            self.logger.info("Starting analysis publishing...")
            
            # Use provided analysis or get latest from database
            if not analysis_result:
                latest_analysis = self.database.get_latest_analysis()
                if not latest_analysis:
                    return {'success': False, 'message': 'No analysis available for publishing'}
                analysis_result = latest_analysis
            
            # Check if we can post today
            posting_status = self.publisher.get_posting_status(self.database)
            if not posting_status.get('can_post_today', False):
                return {
                    'success': False, 
                    'message': f"Daily limit reached: {posting_status.get('posts_today', 0)}/{posting_status.get('daily_limit', 3)}"
                }
            
            # Create compliant Twitter thread
            thread = self.publisher.create_compliant_thread(analysis_result)
            
            if not thread:
                return {'success': False, 'message': 'Failed to create Twitter thread'}
            
            # Post the thread
            success, message, tweet_ids = self.publisher.post_thread(thread, self.database)
            
            if success:
                self.last_publish_time = datetime.now()
                
                result = {
                    'success': True,
                    'message': message,
                    'tweet_ids': tweet_ids,
                    'tweets_posted': len(tweet_ids),
                    'timestamp': self.last_publish_time.isoformat()
                }
                
                self.logger.info(f"Successfully published {len(tweet_ids)} tweets")
                return result
            else:
                self.logger.error(f"Failed to publish thread: {message}")
                return {'success': False, 'message': message}
                
        except Exception as e:
            self.logger.error(f"Error in publishing: {e}")
            return {'success': False, 'message': str(e)}
    
    def run_full_cycle(self) -> Dict[str, Any]:
        """Run a complete cycle: collect -> analyze -> visualize -> publish."""
        try:
            self.logger.info("Starting full TrendBot cycle...")
            results = {}
            
            # 1. Collect trends
            collection_result = self.collect_trends()
            results['collection'] = collection_result
            
            if not collection_result['success']:
                return results
            
            # 2. Analyze trends
            analysis_result = self.analyze_trends()
            results['analysis'] = analysis_result
            
            if not analysis_result['success']:
                return results
            
            # 3. Generate visualizations
            viz_result = self.generate_visualizations()
            results['visualization'] = viz_result
            
            # 4. Publish (only if we have good analysis)
            if analysis_result['success']:
                publish_result = self.publish_analysis(analysis_result.get('analysis'))
                results['publishing'] = publish_result
            
            self.logger.info("Full TrendBot cycle completed")
            return results
            
        except Exception as e:
            self.logger.error(f"Error in full cycle: {e}")
            return {'error': str(e)}
    
    def start_scheduled_operation(self):
        """Start the bot in scheduled operation mode."""
        try:
            self.logger.info("Starting TrendBot in scheduled mode...")
            
            # Schedule jobs
            self.scheduler.add_data_collection_job(self.collect_trends)
            self.scheduler.add_analysis_job(lambda: self.analyze_trends())
            self.scheduler.add_publishing_jobs(lambda: self.publish_analysis())
            self.scheduler.add_cleanup_job(lambda: self.cleanup_old_data())
            self.scheduler.add_visualization_job(lambda: self.generate_visualizations())
            
            # Start scheduler
            self.scheduler.start()
            self.is_running = True
            
            self.logger.info("TrendBot scheduled operation started successfully")
            
            # Run initial cycle
            self.logger.info("Running initial cycle...")
            initial_result = self.run_full_cycle()
            self.logger.info(f"Initial cycle result: {initial_result}")
            
        except Exception as e:
            self.logger.error(f"Error starting scheduled operation: {e}")
            raise
    
    def stop(self):
        """Stop the bot and cleanup resources."""
        try:
            self.logger.info("Stopping TrendBot...")
            
            if self.scheduler and self.is_running:
                self.scheduler.shutdown()
            
            self.is_running = False
            self.logger.info("TrendBot stopped successfully")
            
        except Exception as e:
            self.logger.error(f"Error stopping TrendBot: {e}")
    
    def cleanup_old_data(self, days: int = 30):
        """Clean up old data from database and visualizations."""
        try:
            self.logger.info(f"Cleaning up data older than {days} days...")
            
            # Cleanup database
            self.database.cleanup_old_data(days)
            
            # Cleanup visualizations
            self.visualizer.cleanup_old_visualizations(days // 4)  # Keep visualizations longer
            
            self.logger.info("Cleanup completed successfully")
            
        except Exception as e:
            self.logger.error(f"Error in cleanup: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status of the bot."""
        try:
            status = {
                'is_running': self.is_running,
                'last_collection': self.last_collection_time.isoformat() if self.last_collection_time else None,
                'last_analysis': self.last_analysis_time.isoformat() if self.last_analysis_time else None,
                'last_publish': self.last_publish_time.isoformat() if self.last_publish_time else None,
                'database_status': 'connected',
                'scheduler_status': self.scheduler.get_job_status() if self.scheduler else 'not_started',
                'publisher_status': self.publisher.get_posting_status(self.database),
                'visualization_summary': self.visualizer.get_visualization_summary()
            }
            
            return status
            
        except Exception as e:
            self.logger.error(f"Error getting status: {e}")
            return {'error': str(e)}

def main():
    """Main entry point for the TrendBot application with comprehensive error handling."""
    parser = argparse.ArgumentParser(
        description='TrendBot - Automated Tech Trends Analysis and Publishing System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --mode scheduled                    # Run in scheduled mode
  %(prog)s --mode single --config config.json # Run single cycle with config
  %(prog)s --mode collect --log-level DEBUG    # Collect trends with debug logging
  %(prog)s --mode analyze --hours-back 48      # Analyze last 48 hours of trends
  %(prog)s --mode status                       # Show detailed status
"""
    )
    
    parser.add_argument(
        '--mode', 
        choices=['scheduled', 'single', 'collect', 'analyze', 'publish', 'status', 'health'], 
        default='scheduled', 
        help='Operation mode (default: %(default)s)'
    )
    parser.add_argument(
        '--config', 
        help='Path to configuration JSON file'
    )
    parser.add_argument(
        '--log-level', 
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], 
        help='Override logging level'
    )
    parser.add_argument(
        '--hours-back', 
        type=int, 
        default=24, 
        help='Hours to look back for analysis (default: %(default)s)'
    )
    parser.add_argument(
        '--dry-run', 
        action='store_true',
        help='Run without making any external API calls or publishing'
    )
    parser.add_argument(
        '--max-memory', 
        type=int,
        help='Maximum memory usage in MB'
    )
    
    args = parser.parse_args()
    
    # Initialize TrendBot with comprehensive error handling
    bot = None
    exit_code = 0
    
    try:
        # Override environment with command line args if provided
        if args.log_level:
            os.environ['LOG_LEVEL'] = args.log_level
        if args.max_memory:
            os.environ['MAX_MEMORY_MB'] = str(args.max_memory)
        
        # Initialize TrendBot
        bot = TrendBot(config_file=args.config)
        
        if args.dry_run:
            bot.logger.info("Running in DRY RUN mode - no external calls will be made")
        
        # Execute based on mode
        if args.mode == 'scheduled':
            _run_scheduled_mode(bot, args.dry_run)
            
        elif args.mode == 'single':
            result = _run_single_cycle(bot, args.dry_run)
            _print_operation_result(result, "Single Cycle")
            
        elif args.mode == 'collect':
            result = _run_collect_mode(bot, args.dry_run)
            _print_operation_result(result, "Collection")
            
        elif args.mode == 'analyze':
            result = _run_analyze_mode(bot, args.hours_back, args.dry_run)
            _print_operation_result(result, "Analysis")
            
        elif args.mode == 'publish':
            result = _run_publish_mode(bot, args.dry_run)
            _print_operation_result(result, "Publishing")
            
        elif args.mode == 'status':
            _run_status_mode(bot)
            
        elif args.mode == 'health':
            _run_health_mode(bot)
        
    except KeyboardInterrupt:
        print("\n⚠️  Operation cancelled by user")
        if bot:
            bot.logger.info("Graceful shutdown initiated by user")
            bot.stop()
        exit_code = 130  # Standard exit code for SIGINT
        
    except EnvironmentError as e:
        print(f"❌ Environment Error: {e}")
        print("\n💡 Please check your .env file and ensure all required API keys are set.")
        exit_code = 1
        
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")
        if bot and hasattr(bot, 'logger'):
            bot.logger.error(f"Unexpected error in main: {e}", exc_info=True)
        exit_code = 1
        
    finally:
        # Cleanup
        if bot:
            try:
                bot.stop()
            except Exception as e:
                print(f"Warning: Error during cleanup: {e}")
        
        if exit_code == 0:
            print("\n✅ TrendBot completed successfully")
        
        sys.exit(exit_code)


def _run_scheduled_mode(bot, dry_run: bool):
    """Run TrendBot in scheduled mode."""
    bot.logger.info("Starting TrendBot in scheduled mode...")
    
    if dry_run:
        bot.logger.info("DRY RUN: Would start scheduled operations")
        print("🔍 DRY RUN: Scheduled mode simulation completed")
        return
    
    # Start scheduled operation
    bot.start_scheduled_operation()
    
    # Keep running until interrupted
    try:
        print("🚀 TrendBot is running in scheduled mode. Press Ctrl+C to stop.")
        while bot.is_running:
            time.sleep(10)
            
            # Periodic health checks removed for MVP simplicity
                
    except KeyboardInterrupt:
        raise  # Re-raise to be handled in main


def _run_single_cycle(bot, dry_run: bool) -> dict:
    """Run a single full cycle."""
    if dry_run:
        bot.logger.info("DRY RUN: Would run full cycle")
        return {'success': True, 'message': 'DRY RUN completed', 'dry_run': True}
    
    return bot.run_full_cycle()


def _run_collect_mode(bot, dry_run: bool) -> dict:
    """Run collection only."""
    if dry_run:
        bot.logger.info("DRY RUN: Would collect trends")
        return {'success': True, 'message': 'DRY RUN collection completed', 'dry_run': True}
    
    return bot.collect_trends()


def _run_analyze_mode(bot, hours_back: int, dry_run: bool) -> dict:
    """Run analysis only."""
    if dry_run:
        bot.logger.info(f"DRY RUN: Would analyze trends from last {hours_back} hours")
        return {'success': True, 'message': f'DRY RUN analysis for {hours_back}h completed', 'dry_run': True}
    
    return bot.analyze_trends(hours_back)


def _run_publish_mode(bot, dry_run: bool) -> dict:
    """Run publishing only."""
    if dry_run:
        bot.logger.info("DRY RUN: Would publish latest analysis")
        return {'success': True, 'message': 'DRY RUN publishing completed', 'dry_run': True}
    
    return bot.publish_analysis()


def _run_status_mode(bot):
    """Show detailed status."""
    status = bot.get_status()
    
    import json
    from utils import safe_json_serialize
    
    print("📊 TrendBot Status Report")
    print("=" * 50)
    print(safe_json_serialize(status))


def _run_health_mode(bot):
    """Show health check results."""
    from utils import HealthChecker
    
    health_checker = HealthChecker(bot.config)
    health_status = health_checker.perform_full_health_check(bot)
    
    print("🏥 TrendBot Health Check")
    print("=" * 50)
    
    overall_status = health_status.get('overall_status', 'unknown')
    print(f"Overall Status: {_get_status_emoji(overall_status)} {overall_status.upper()}")
    
    for check_name, check_result in health_status.get('checks', {}).items():
        status = check_result.get('status', 'unknown')
        message = check_result.get('message', 'No details')
        print(f"{check_name.title()}: {_get_status_emoji(status)} {message}")
    
    print(f"\nUptime: {health_status.get('uptime_hours', 0):.1f} hours")


def _get_status_emoji(status: str) -> str:
    """Get emoji for status."""
    status_emojis = {
        'healthy': '✅',
        'warning': '⚠️',
        'unhealthy': '❌',
        'critical': '🚨',
        'unknown': '❓',
        'unavailable': '⭕'
    }
    return status_emojis.get(status.lower(), '❓')


def _print_operation_result(result: dict, operation_name: str):
    """Print operation result in a user-friendly format."""
    print(f"\n📋 {operation_name} Results")
    print("=" * 50)
    
    success = result.get('success', False)
    emoji = "✅" if success else "❌"
    
    print(f"Status: {emoji} {'SUCCESS' if success else 'FAILED'}")
    
    if 'message' in result:
        print(f"Message: {result['message']}")
    
    # Show key metrics if available
    metrics = {
        'count': 'Items processed',
        'duration_seconds': 'Duration',
        'operation_id': 'Operation ID'
    }
    
    for key, label in metrics.items():
        if key in result:
            value = result[key]
            if key == 'duration_seconds':
                from utils import format_duration
                value = format_duration(float(value))
            print(f"{label}: {value}")
    
    # Show additional details if verbose
    if result.get('dry_run'):
        print("\n🔍 This was a DRY RUN - no actual operations were performed")

if __name__ == '__main__':
    main()