"""
Centralized configuration and logging setup for TrendBot.

This module provides:
- Logging configuration with rotating file handlers
- Environment variable validation
- Centralized configuration management
- Health check utilities
"""

import os
import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Dict, Any, Optional
import json

def load_env_from_file(env_file_path: str = '.env'):
    """Load environment variables from .env file using only standard library."""
    try:
        if not os.path.exists(env_file_path):
            return
        
        with open(env_file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # Remove quotes if present
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]
                    
                    # Only set if not already in environment
                    if key not in os.environ:
                        os.environ[key] = value
    except Exception as e:
        print(f"Warning: Could not load .env file: {e}")

# Load environment variables
load_env_from_file()

class TrendBotConfig:
    """Centralized configuration management for TrendBot."""
    
    def __init__(self, config_file: Optional[str] = None):
        """Initialize configuration with validation."""
        self.config_file = config_file
        self.config = self._load_default_config()
        
        # Load from file if provided
        if config_file and Path(config_file).exists():
            try:
                with open(config_file, 'r') as f:
                    file_config = json.load(f)
                    self.config.update(file_config)
            except Exception as e:
                print(f"Warning: Could not load config file {config_file}: {e}")
        
        # Validate required environment variables
        self._validate_environment()
        
        # Setup logging
        self._setup_logging()
    
    def _load_default_config(self) -> Dict[str, Any]:
        """Load default configuration values."""
        return {
            # Logging configuration
            'log_level': os.getenv('LOG_LEVEL', 'INFO').upper(),
            'log_dir': os.getenv('LOG_DIR', 'data/logs'),
            'max_log_size': int(os.getenv('MAX_LOG_SIZE', '10485760')),  # 10MB
            'backup_count': int(os.getenv('LOG_BACKUP_COUNT', '5')),
            
            # Database configuration
            'database_path': os.getenv('DATABASE_PATH', 'trends.db'),
            'db_timeout': int(os.getenv('DB_TIMEOUT', '30')),
            'db_check_same_thread': False,
            
            # API rate limiting
            'api_retry_attempts': int(os.getenv('API_RETRY_ATTEMPTS', '3')),
            'api_retry_delay': float(os.getenv('API_RETRY_DELAY', '1.0')),
            'api_backoff_factor': float(os.getenv('API_BACKOFF_FACTOR', '2.0')),
            'api_timeout': int(os.getenv('API_TIMEOUT', '30')),
            
            # Collection limits
            'collection_limits': {
                'twitter': int(os.getenv('TWITTER_LIMIT', '50')),
                'github': int(os.getenv('GITHUB_LIMIT', '30')),
                'reddit': int(os.getenv('REDDIT_LIMIT', '30')),
                'hackernews': int(os.getenv('HACKERNEWS_LIMIT', '20')),
            },
            
            # Publishing configuration
            'daily_post_limit': int(os.getenv('DAILY_POST_LIMIT', '3')),
            'min_post_interval': int(os.getenv('MIN_POST_INTERVAL', '300')),  # 5 minutes
            
            # Scheduler configuration
            'collection_interval_hours': int(os.getenv('COLLECTION_INTERVAL_HOURS', '2')),
            'analysis_interval_hours': int(os.getenv('ANALYSIS_INTERVAL_HOURS', '12')),
            'publishing_interval_hours': int(os.getenv('PUBLISHING_INTERVAL_HOURS', '8')),
            'cleanup_interval_days': int(os.getenv('CLEANUP_INTERVAL_DAYS', '1')),
            
            # Publishing times
            'publish_times': [
                os.getenv('PUBLISH_TIME_1', '09:00'),
                os.getenv('PUBLISH_TIME_2', '15:00'),
                os.getenv('PUBLISH_TIME_3', '21:00')
            ],
            
            # Visualization configuration
            'viz_output_dir': os.getenv('VIZ_OUTPUT_DIR', 'visualizations'),
            'viz_cleanup_days': int(os.getenv('VIZ_CLEANUP_DAYS', '7')),
            
            # Health check configuration
            'health_check_interval': int(os.getenv('HEALTH_CHECK_INTERVAL', '300')),  # 5 minutes
            'max_memory_mb': int(os.getenv('MAX_MEMORY_MB', '1024')),  # 1GB
            
            # OpenAI configuration
            'openai_model': os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo'),
            'openai_max_tokens': int(os.getenv('OPENAI_MAX_TOKENS', '2000')),
            'openai_temperature': float(os.getenv('OPENAI_TEMPERATURE', '0.7')),
            'openai_timeout': int(os.getenv('OPENAI_TIMEOUT', '60')),
        }
    
    def _validate_environment(self):
        """Validate required environment variables."""
        required_vars = {
            'OPENAI_API_KEY': 'OpenAI API key for analysis',
            'TWITTER_BEARER_TOKEN': 'Twitter Bearer Token',
            'TWITTER_CONSUMER_KEY': 'Twitter Consumer Key',
            'TWITTER_CONSUMER_SECRET': 'Twitter Consumer Secret',
            'TWITTER_ACCESS_TOKEN': 'Twitter Access Token',
            'TWITTER_ACCESS_TOKEN_SECRET': 'Twitter Access Token Secret',
        }
        
        optional_vars = {
            'REDDIT_CLIENT_ID': 'Reddit Client ID (optional for Reddit data)',
            'REDDIT_CLIENT_SECRET': 'Reddit Client Secret (optional for Reddit data)',
            'GITHUB_TOKEN': 'GitHub Token (optional for higher rate limits)',
        }
        
        missing_required = []
        missing_optional = []
        
        for var, description in required_vars.items():
            if not os.getenv(var):
                missing_required.append(f"{var}: {description}")
        
        for var, description in optional_vars.items():
            if not os.getenv(var):
                missing_optional.append(f"{var}: {description}")
        
        if missing_required:
            raise EnvironmentError(
                f"Missing required environment variables:\n" + 
                "\n".join(f"  - {var}" for var in missing_required) +
                "\n\nPlease check your .env file and ensure all required variables are set."
            )
        
        if missing_optional:
            print("Warning: Missing optional environment variables:")
            for var in missing_optional:
                print(f"  - {var}")
            print("Some features may be limited.\n")
    
    def _setup_logging(self):
        """Setup centralized logging configuration."""
        # Create logs directory
        log_dir = Path(self.config['log_dir'])
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Configure root logger
        logging.getLogger().handlers.clear()
        
        # Create formatters
        detailed_formatter = logging.Formatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        simple_formatter = logging.Formatter(
            fmt='%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(simple_formatter)
        
        # Main application log (rotating file)
        main_log_file = log_dir / 'trendbot.log'
        main_handler = logging.handlers.RotatingFileHandler(
            filename=main_log_file,
            maxBytes=self.config['max_log_size'],
            backupCount=self.config['backup_count'],
            encoding='utf-8'
        )
        main_handler.setLevel(logging.DEBUG)
        main_handler.setFormatter(detailed_formatter)
        
        # Error log (rotating file)
        error_log_file = log_dir / 'errors.log'
        error_handler = logging.handlers.RotatingFileHandler(
            filename=error_log_file,
            maxBytes=self.config['max_log_size'],
            backupCount=self.config['backup_count'],
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(detailed_formatter)
        
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, self.config['log_level']))
        root_logger.addHandler(console_handler)
        root_logger.addHandler(main_handler)
        root_logger.addHandler(error_handler)
        
        # Configure component-specific loggers
        self._setup_component_loggers(log_dir, detailed_formatter)
        
        # Reduce noise from external libraries
        logging.getLogger('apscheduler').setLevel(logging.WARNING)
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        logging.getLogger('requests').setLevel(logging.WARNING)
        logging.getLogger('tweepy').setLevel(logging.WARNING)
        logging.getLogger('openai').setLevel(logging.WARNING)
        
        logging.info(f"Logging configured with level: {self.config['log_level']}")
        logging.info(f"Log files location: {log_dir}")
    
    def _setup_component_loggers(self, log_dir: Path, formatter: logging.Formatter):
        """Setup individual component loggers."""
        components = [
            'collector', 'analyzer', 'publisher', 'scheduler', 
            'database', 'visualizer'
        ]
        
        for component in components:
            logger = logging.getLogger(component)
            
            # Component-specific log file
            component_log_file = log_dir / f'{component}.log'
            component_handler = logging.handlers.RotatingFileHandler(
                filename=component_log_file,
                maxBytes=self.config['max_log_size'],
                backupCount=self.config['backup_count'],
                encoding='utf-8'
            )
            component_handler.setLevel(logging.DEBUG)
            component_handler.setFormatter(formatter)
            
            logger.addHandler(component_handler)
            logger.setLevel(logging.DEBUG)
            # Prevent duplicate logs in root logger
            logger.propagate = True
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        return self.config.get(key, default)
    
    def set(self, key: str, value: Any):
        """Set configuration value."""
        self.config[key] = value
    
    def get_api_config(self) -> Dict[str, Any]:
        """Get API-related configuration."""
        return {
            'retry_attempts': self.config['api_retry_attempts'],
            'retry_delay': self.config['api_retry_delay'],
            'backoff_factor': self.config['api_backoff_factor'],
            'timeout': self.config['api_timeout'],
        }
    
    def get_database_config(self) -> Dict[str, Any]:
        """Get database-related configuration."""
        return {
            'database_path': self.config['database_path'],
            'timeout': self.config['db_timeout'],
            'check_same_thread': self.config['db_check_same_thread'],
        }
    
    def validate_disk_space(self, required_mb: int = 100) -> bool:
        """Check if sufficient disk space is available."""
        try:
            import shutil
            free_bytes = shutil.disk_usage('.').free
            free_mb = free_bytes / (1024 * 1024)
            return free_mb >= required_mb
        except Exception:
            return True  # Assume OK if we can't check
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get system health status using built-in modules."""
        try:
            import resource
            import platform
            import shutil
            
            # Memory usage using resource module
            memory_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            # On macOS ru_maxrss is in bytes, on Linux it's in KB
            if platform.system() == 'Darwin':
                memory_mb = memory_kb / (1024 * 1024)
            else:
                memory_mb = memory_kb / 1024
            
            # Disk usage
            disk_usage = shutil.disk_usage('.')
            free_gb = disk_usage.free / (1024 * 1024 * 1024)
            
            # Log file sizes
            log_dir = Path(self.config['log_dir'])
            log_sizes = {}
            if log_dir.exists():
                for log_file in log_dir.glob('*.log'):
                    size_mb = log_file.stat().st_size / (1024 * 1024)
                    log_sizes[log_file.name] = round(size_mb, 2)
            
            return {
                'status': 'healthy',
                'memory_mb': round(memory_mb, 2),
                'memory_limit_mb': self.config['max_memory_mb'],
                'disk_free_gb': round(free_gb, 2),
                'log_sizes_mb': log_sizes,
                'timestamp': logging.Formatter().formatTime(logging.LogRecord(
                    '', 0, '', 0, '', (), None
                ))
            }
        except Exception as e:
            return {
                'status': 'unknown',
                'message': f'Health monitoring error: {e}',
                'timestamp': logging.Formatter().formatTime(logging.LogRecord(
                    '', 0, '', 0, '', (), None
                ))
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e),
                'timestamp': logging.Formatter().formatTime(logging.LogRecord(
                    '', 0, '', 0, '', (), None
                ))
            }


class RetryConfig:
    """Configuration for retry logic with exponential backoff."""
    
    def __init__(self, config: TrendBotConfig):
        self.max_attempts = config.get('api_retry_attempts', 3)
        self.base_delay = config.get('api_retry_delay', 1.0)
        self.backoff_factor = config.get('api_backoff_factor', 2.0)
        self.max_delay = config.get('api_max_delay', 60.0)
    
    def get_delay(self, attempt: int) -> float:
        """Calculate delay for retry attempt."""
        delay = self.base_delay * (self.backoff_factor ** attempt)
        return min(delay, self.max_delay)


def setup_logging(config_file: Optional[str] = None) -> TrendBotConfig:
    """Setup logging and return configuration object."""
    try:
        config = TrendBotConfig(config_file)
        logging.info("TrendBot configuration and logging initialized successfully")
        return config
    except Exception as e:
        # Fallback logging if configuration fails
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler('fallback.log')
            ]
        )
        logging.error(f"Failed to setup configuration: {e}")
        raise


def validate_environment_quick() -> bool:
    """Quick environment validation for health checks."""
    required_vars = [
        'OPENAI_API_KEY', 'TWITTER_BEARER_TOKEN', 'TWITTER_CONSUMER_KEY',
        'TWITTER_CONSUMER_SECRET', 'TWITTER_ACCESS_TOKEN', 'TWITTER_ACCESS_TOKEN_SECRET'
    ]
    
    return all(os.getenv(var) for var in required_vars)


# Global configuration instance
_config_instance: Optional[TrendBotConfig] = None

def get_config() -> TrendBotConfig:
    """Get the global configuration instance."""
    global _config_instance
    if _config_instance is None:
        _config_instance = setup_logging()
    return _config_instance


def get_logger(name: str) -> logging.Logger:
    """Get a logger for a specific component."""
    # Ensure configuration is loaded
    get_config()
    return logging.getLogger(name)