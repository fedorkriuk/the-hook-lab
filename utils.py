"""
Utility classes and functions for TrendBot.

This module provides:
- Memory monitoring utilities
- Retry decorators with exponential backoff
- Health check utilities
- Performance monitoring
"""

import time
import functools
import logging
import resource
import platform
from typing import Callable, Any, Dict, Optional
from datetime import datetime, timedelta


class MemoryMonitor:
    """Monitor memory usage and prevent memory leaks."""
    
    def __init__(self, max_memory_mb: int = 1024):
        """Initialize memory monitor with maximum memory threshold."""
        self.max_memory_mb = max_memory_mb
        self.logger = logging.getLogger('memory_monitor')
        self.start_memory = self.get_current_memory()
        
    def get_current_memory(self) -> float:
        """Get current memory usage in MB using resource module."""
        try:
            memory_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            # On macOS ru_maxrss is in bytes, on Linux it's in KB
            if platform.system() == 'Darwin':
                return memory_kb / (1024 * 1024)
            else:
                return memory_kb / 1024
        except Exception:
            return 0.0
    
    def check_memory(self) -> bool:
        """Check if memory usage is within limits."""
        current_memory = self.get_current_memory()
        
        if current_memory > self.max_memory_mb:
            self.logger.warning(
                f"Memory usage ({current_memory:.2f} MB) exceeds limit ({self.max_memory_mb} MB)"
            )
            return False
        
        return True
    
    def log_memory_usage(self, context: str = ""):
        """Log current memory usage."""
        current_memory = self.get_current_memory()
        memory_growth = current_memory - self.start_memory
        
        self.logger.info(
            f"Memory usage{' (' + context + ')' if context else ''}: "
            f"{current_memory:.2f} MB (growth: {memory_growth:+.2f} MB)"
        )


class RetryWithBackoff:
    """Decorator for retry logic with exponential backoff."""
    
    def __init__(self, max_attempts: int = 3, base_delay: float = 1.0, 
                 backoff_factor: float = 2.0, max_delay: float = 60.0,
                 exceptions: tuple = (Exception,)):
        """Initialize retry decorator."""
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.backoff_factor = backoff_factor
        self.max_delay = max_delay
        self.exceptions = exceptions
        
    def __call__(self, func: Callable) -> Callable:
        """Apply retry logic to function."""
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            logger = logging.getLogger(f'retry.{func.__name__}')
            
            for attempt in range(self.max_attempts):
                try:
                    return func(*args, **kwargs)
                    
                except self.exceptions as e:
                    if attempt == self.max_attempts - 1:  # Last attempt
                        logger.error(f"Function {func.__name__} failed after {self.max_attempts} attempts: {e}")
                        raise
                    
                    delay = min(
                        self.base_delay * (self.backoff_factor ** attempt),
                        self.max_delay
                    )
                    
                    logger.warning(
                        f"Attempt {attempt + 1}/{self.max_attempts} failed for {func.__name__}: {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    
                    time.sleep(delay)
            
            return None  # Should never reach here
        
        return wrapper


class PerformanceMonitor:
    """Monitor performance metrics for operations."""
    
    def __init__(self, operation_name: str):
        """Initialize performance monitor."""
        self.operation_name = operation_name
        self.logger = logging.getLogger('performance')
        self.start_time = None
        self.end_time = None
        self.memory_start = None
        self.memory_end = None
        
    def __enter__(self):
        """Start monitoring."""
        self.start_time = datetime.now()
        try:
            memory_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            if platform.system() == 'Darwin':
                self.memory_start = memory_kb / (1024 * 1024)
            else:
                self.memory_start = memory_kb / 1024
        except Exception:
            self.memory_start = 0
            
        self.logger.debug(f"Starting operation: {self.operation_name}")
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop monitoring and log results."""
        self.end_time = datetime.now()
        
        try:
            memory_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            if platform.system() == 'Darwin':
                self.memory_end = memory_kb / (1024 * 1024)
            else:
                self.memory_end = memory_kb / 1024
        except Exception:
            self.memory_end = self.memory_start or 0
            
        duration = (self.end_time - self.start_time).total_seconds()
        memory_delta = self.memory_end - (self.memory_start or 0)
        
        if exc_type is None:
            self.logger.info(
                f"Operation '{self.operation_name}' completed in {duration:.2f}s "
                f"(memory change: {memory_delta:+.2f} MB)"
            )
        else:
            self.logger.error(
                f"Operation '{self.operation_name}' failed after {duration:.2f}s "
                f"with {exc_type.__name__}: {exc_val}"
            )


class HealthChecker:
    """Perform health checks on system components."""
    
    def __init__(self, config):
        """Initialize health checker."""
        self.config = config
        self.logger = logging.getLogger('health_check')
        
    def check_database_health(self, database) -> Dict[str, Any]:
        """Check database health."""
        try:
            # Simple query to test database
            recent_trends = database.get_recent_trend_data(hours=1)
            return {
                'status': 'healthy',
                'recent_data_count': len(recent_trends) if recent_trends else 0,
                'message': 'Database accessible'
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'message': f'Database error: {e}'
            }
    
    def check_api_health(self, collector) -> Dict[str, Any]:
        """Check API connectivity health."""
        try:
            # This would need to be implemented in collector
            # For now, just check if collector exists
            if hasattr(collector, '_setup_apis'):
                return {
                    'status': 'healthy',
                    'message': 'API collector available'
                }
            else:
                return {
                    'status': 'unhealthy',
                    'message': 'API collector not properly initialized'
                }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'message': f'API check error: {e}'
            }
    
    def check_disk_space(self) -> Dict[str, Any]:
        """Check available disk space."""
        try:
            import shutil
            usage = shutil.disk_usage('.')
            free_gb = usage.free / (1024**3)
            total_gb = usage.total / (1024**3)
            used_percent = ((usage.total - usage.free) / usage.total) * 100
            
            status = 'healthy'
            if free_gb < 1:  # Less than 1GB free
                status = 'critical'
            elif used_percent > 90:  # More than 90% used
                status = 'warning'
            
            return {
                'status': status,
                'free_gb': round(free_gb, 2),
                'total_gb': round(total_gb, 2),
                'used_percent': round(used_percent, 1),
                'message': f'{free_gb:.1f}GB free ({used_percent:.1f}% used)'
            }
        except Exception as e:
            return {
                'status': 'unknown',
                'message': f'Disk check error: {e}'
            }
    
    def check_memory_usage(self) -> Dict[str, Any]:
        """Check memory usage using resource module."""
        try:
            memory_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            # On macOS ru_maxrss is in bytes, on Linux it's in KB
            if platform.system() == 'Darwin':
                memory_mb = memory_kb / (1024 * 1024)
            else:
                memory_mb = memory_kb / 1024
                
            max_memory = self.config.get('max_memory_mb', 1024)
            memory_percent = (memory_mb / max_memory) * 100
            
            status = 'healthy'
            if memory_mb > max_memory:
                status = 'critical'
            elif memory_percent > 80:
                status = 'warning'
            
            return {
                'status': status,
                'memory_mb': round(memory_mb, 2),
                'max_memory_mb': max_memory,
                'memory_percent': round(memory_percent, 1),
                'message': f'{memory_mb:.1f}MB used ({memory_percent:.1f}% of limit)'
            }
        except Exception as e:
            return {
                'status': 'unknown',
                'message': f'Memory check error: {e}'
            }
    
    def perform_full_health_check(self, trendbot) -> Dict[str, Any]:
        """Perform comprehensive health check."""
        checks = {}
        overall_status = 'healthy'
        
        # Database check
        if hasattr(trendbot, 'database'):
            checks['database'] = self.check_database_health(trendbot.database)
        else:
            checks['database'] = {'status': 'unavailable', 'message': 'Database not initialized'}
        
        # API check
        if hasattr(trendbot, 'collector'):
            checks['apis'] = self.check_api_health(trendbot.collector)
        else:
            checks['apis'] = {'status': 'unavailable', 'message': 'Collector not initialized'}
        
        # System checks
        checks['disk_space'] = self.check_disk_space()
        checks['memory'] = self.check_memory_usage()
        
        # Determine overall status
        statuses = [check['status'] for check in checks.values()]
        if 'critical' in statuses:
            overall_status = 'critical'
        elif 'unhealthy' in statuses:
            overall_status = 'unhealthy'
        elif 'warning' in statuses:
            overall_status = 'warning'
        
        return {
            'overall_status': overall_status,
            'timestamp': datetime.now().isoformat(),
            'checks': checks,
            'uptime_hours': self._get_uptime_hours(trendbot)
        }
    
    def _get_uptime_hours(self, trendbot) -> float:
        """Get uptime in hours."""
        try:
            if hasattr(trendbot, 'initialization_time'):
                uptime = datetime.now() - trendbot.initialization_time
                return round(uptime.total_seconds() / 3600, 2)
            return 0.0
        except Exception:
            return 0.0


def format_duration(seconds: float) -> str:
    """Format duration in human-readable format."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


def validate_data_structure(data: Dict[str, Any], required_fields: list) -> bool:
    """Validate that data contains required fields."""
    try:
        for field in required_fields:
            if field not in data:
                return False
            if data[field] is None:
                return False
        return True
    except Exception:
        return False


def safe_json_serialize(obj: Any) -> str:
    """Safely serialize object to JSON."""
    import json
    
    try:
        return json.dumps(obj, default=str, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"<Serialization error: {e}>"