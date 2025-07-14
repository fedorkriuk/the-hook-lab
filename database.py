import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Union
import json
import os
import threading
from contextlib import contextmanager
from pathlib import Path

from config import get_logger
from utils import RetryWithBackoff, PerformanceMonitor

class TrendDatabase:
    """Enhanced database manager with transaction safety and comprehensive error handling."""
    
    def __init__(self, db_path: str = "trends.db", config=None):
        self.config = config
        self.db_path = Path(db_path)
        self.logger = get_logger('database')
        
        # Database configuration
        self.timeout = config.get('db_timeout', 30) if config else 30
        self.check_same_thread = config.get('db_check_same_thread', False) if config else False
        
        # Connection pool and thread safety
        self._local = threading.local()
        self._connection_count = 0
        self._max_connections = 10
        
        # Performance tracking
        self.query_count = 0
        self.error_count = 0
        self.total_query_time = 0.0
        
        # Initialize database
        self._init_database()
        
        self.logger.info(f"TrendDatabase initialized at: {self.db_path}")
    
    def _init_database(self):
        """Initialize the database with required tables and comprehensive schema."""
        try:
            # Ensure database directory exists
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            
            with self._get_connection() as conn:
                # Enable WAL mode for better concurrency
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")
                conn.execute("PRAGMA temp_store=MEMORY")
                conn.execute("PRAGMA mmap_size=268435456")  # 256MB
                
                # Create tables with enhanced schema
                self._create_tables(conn)
                self._create_indexes(conn)
                self._create_triggers(conn)
                
                conn.commit()
                self.logger.info("Database initialized successfully")
                
                # Verify schema integrity
                self._verify_schema(conn)
                
        except sqlite3.Error as e:
            self.logger.error(f"Error initializing database: {e}", exc_info=True)
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error initializing database: {e}", exc_info=True)
            raise
    
    def _create_tables(self, conn: sqlite3.Connection):
        """Create database tables with enhanced schema."""
        # Enhanced trend_data table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trend_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                source TEXT NOT NULL,
                topic TEXT NOT NULL,
                content TEXT,
                url TEXT,
                engagement_score REAL DEFAULT 0,
                metadata TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_processed BOOLEAN DEFAULT FALSE,
                hash_value TEXT,
                CONSTRAINT check_engagement_score CHECK (engagement_score >= 0),
                CONSTRAINT check_source_not_empty CHECK (LENGTH(source) > 0),
                CONSTRAINT check_topic_not_empty CHECK (LENGTH(topic) > 0)
            )
        """)
        
        # Enhanced trend_analysis table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trend_analysis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                trends_summary TEXT NOT NULL,
                sentiment_score REAL,
                insights TEXT,
                visualization_path TEXT,
                data_points_count INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                analysis_version TEXT DEFAULT '1.0',
                quality_score REAL DEFAULT 0.0,
                processing_time_ms INTEGER DEFAULT 0,
                CONSTRAINT check_sentiment_range CHECK (sentiment_score BETWEEN -1 AND 1),
                CONSTRAINT check_data_points CHECK (data_points_count >= 0)
            )
        """)
        
        # Enhanced published_content table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS published_content (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                platform TEXT NOT NULL,
                content TEXT NOT NULL,
                analysis_id INTEGER,
                post_id TEXT,
                success BOOLEAN DEFAULT FALSE,
                error_message TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                retry_count INTEGER DEFAULT 0,
                scheduled_time DATETIME,
                FOREIGN KEY (analysis_id) REFERENCES trend_analysis (id)
            )
        """)
        
        # Database metadata table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS db_metadata (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Insert schema version
        conn.execute("""
            INSERT OR REPLACE INTO db_metadata (key, value) 
            VALUES ('schema_version', '2.0')
        """)
    
    def _create_indexes(self, conn: sqlite3.Connection):
        """Create database indexes for performance."""
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_trend_data_timestamp ON trend_data(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_trend_data_source ON trend_data(source)",
            "CREATE INDEX IF NOT EXISTS idx_trend_data_engagement ON trend_data(engagement_score DESC)",
            "CREATE INDEX IF NOT EXISTS idx_trend_data_processed ON trend_data(is_processed)",
            "CREATE INDEX IF NOT EXISTS idx_trend_data_hash ON trend_data(hash_value)",
            "CREATE INDEX IF NOT EXISTS idx_trend_analysis_timestamp ON trend_analysis(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_trend_analysis_sentiment ON trend_analysis(sentiment_score)",
            "CREATE INDEX IF NOT EXISTS idx_published_content_platform_date ON published_content(platform, date(timestamp))",
            "CREATE INDEX IF NOT EXISTS idx_published_content_success ON published_content(success)",
        ]
        
        for index_sql in indexes:
            conn.execute(index_sql)
    
    def _create_triggers(self, conn: sqlite3.Connection):
        """Create database triggers for data integrity."""
        # Update timestamp triggers
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS update_trend_data_timestamp 
            AFTER UPDATE ON trend_data
            FOR EACH ROW
            BEGIN
                UPDATE trend_data SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
            END
        """)
        
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS update_trend_analysis_timestamp 
            AFTER UPDATE ON trend_analysis
            FOR EACH ROW
            BEGIN
                UPDATE trend_analysis SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
            END
        """)
    
    def _verify_schema(self, conn: sqlite3.Connection):
        """Verify database schema integrity."""
        try:
            # Check if all required tables exist
            required_tables = ['trend_data', 'trend_analysis', 'published_content', 'db_metadata']
            
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name IN ({})".format(
                    ','.join('?' * len(required_tables))
                ), required_tables
            )
            
            existing_tables = [row[0] for row in cursor.fetchall()]
            missing_tables = set(required_tables) - set(existing_tables)
            
            if missing_tables:
                raise sqlite3.Error(f"Missing required tables: {missing_tables}")
            
            self.logger.debug("Database schema verification passed")
            
        except Exception as e:
            self.logger.error(f"Schema verification failed: {e}")
            raise
    
    @contextmanager
    def _get_connection(self):
        """Get database connection with proper resource management."""
        conn = None
        try:
            conn = sqlite3.connect(
                self.db_path,
                timeout=self.timeout,
                check_same_thread=self.check_same_thread
            )
            conn.row_factory = sqlite3.Row
            self._connection_count += 1
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            self.error_count += 1
            self.logger.error(f"Database connection error: {e}")
            raise
        finally:
            if conn:
                conn.close()
                self._connection_count -= 1
    
    @RetryWithBackoff(max_attempts=3, base_delay=0.5, exceptions=(sqlite3.OperationalError, sqlite3.DatabaseError))
    def insert_trend_data(self, source: str, topic: str, content: str = None, 
                         url: str = None, engagement_score: float = 0.0, 
                         metadata: Dict = None) -> int:
        """Insert trend data into the database with enhanced error handling and deduplication."""
        operation_id = f"insert_trend_{int(datetime.now().timestamp()*1000)}"
        
        with PerformanceMonitor(f"insert_trend_data_{operation_id}"):
            try:
                # Validate input data
                self._validate_trend_input(source, topic, engagement_score)
                
                # Create content hash for deduplication
                content_hash = self._generate_content_hash(source, topic, content)
                
                # Check for duplicate
                if self._is_duplicate_trend(content_hash):
                    self.logger.debug(f"[{operation_id}] Duplicate trend detected, skipping")
                    return -1
                
                metadata_json = json.dumps(metadata) if metadata else None
                
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    
                    start_time = datetime.now()
                    cursor.execute("""
                        INSERT INTO trend_data 
                        (source, topic, content, url, engagement_score, metadata, hash_value)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (source, topic, content, url, engagement_score, metadata_json, content_hash))
                    
                    trend_id = cursor.lastrowid
                    conn.commit()
                    
                    query_time = (datetime.now() - start_time).total_seconds()
                    self.total_query_time += query_time
                    self.query_count += 1
                    
                    self.logger.debug(f"[{operation_id}] Inserted trend data with ID: {trend_id}")
                    return trend_id
                    
            except sqlite3.IntegrityError as e:
                self.logger.warning(f"[{operation_id}] Data integrity error: {e}")
                self.error_count += 1
                raise
            except sqlite3.Error as e:
                self.logger.error(f"[{operation_id}] Database error inserting trend: {e}", exc_info=True)
                self.error_count += 1
                raise
            except Exception as e:
                self.logger.error(f"[{operation_id}] Unexpected error inserting trend: {e}", exc_info=True)
                self.error_count += 1
                raise
    
    def _validate_trend_input(self, source: str, topic: str, engagement_score: float):
        """Validate trend input data."""
        if not source or len(source.strip()) == 0:
            raise ValueError("Source cannot be empty")
        
        if not topic or len(topic.strip()) == 0:
            raise ValueError("Topic cannot be empty")
        
        if engagement_score < 0:
            raise ValueError("Engagement score must be non-negative")
        
        if len(source) > 50:
            raise ValueError("Source too long (max 50 characters)")
        
        if len(topic) > 200:
            raise ValueError("Topic too long (max 200 characters)")
    
    def _generate_content_hash(self, source: str, topic: str, content: str) -> str:
        """Generate hash for content deduplication."""
        import hashlib
        
        content_str = f"{source}:{topic}:{content or ''}"
        return hashlib.md5(content_str.encode('utf-8')).hexdigest()
    
    def _is_duplicate_trend(self, content_hash: str) -> bool:
        """Check if trend is duplicate based on hash."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id FROM trend_data WHERE hash_value = ? AND timestamp > datetime('now', '-1 day')",
                    (content_hash,)
                )
                return cursor.fetchone() is not None
        except Exception as e:
            self.logger.debug(f"Duplicate check failed: {e}")
            return False  # Assume not duplicate if check fails
    
    def insert_trend_analysis(self, trends_summary: str, sentiment_score: float,
                             insights: str, visualization_path: str = None,
                             data_points_count: int = 0) -> int:
        """Insert trend analysis into the database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO trend_analysis 
                    (trends_summary, sentiment_score, insights, visualization_path, data_points_count)
                    VALUES (?, ?, ?, ?, ?)
                """, (trends_summary, sentiment_score, insights, visualization_path, data_points_count))
                
                analysis_id = cursor.lastrowid
                conn.commit()
                self.logger.debug(f"Inserted trend analysis with ID: {analysis_id}")
                return analysis_id
                
        except sqlite3.Error as e:
            self.logger.error(f"Error inserting trend analysis: {e}", exc_info=True)
            self.error_count += 1
            raise
    
    def insert_published_content(self, platform: str, content: str, 
                                analysis_id: int = None, post_id: str = None,
                                success: bool = False, error_message: str = None) -> int:
        """Insert published content record into the database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO published_content 
                    (platform, content, analysis_id, post_id, success, error_message)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (platform, content, analysis_id, post_id, success, error_message))
                
                content_id = cursor.lastrowid
                conn.commit()
                self.logger.debug(f"Inserted published content with ID: {content_id}")
                return content_id
                
        except sqlite3.Error as e:
            self.logger.error(f"Error inserting published content: {e}", exc_info=True)
            self.error_count += 1
            raise
    
    @RetryWithBackoff(max_attempts=2, base_delay=0.5, exceptions=(sqlite3.OperationalError,))
    def get_recent_trend_data(self, hours: int = 24, source: str = None, limit: int = None) -> List[Dict]:
        """Get recent trend data from the database with enhanced filtering and caching."""
        operation_id = f"get_recent_{int(datetime.now().timestamp()*1000)}"
        
        with PerformanceMonitor(f"get_recent_trend_data_{operation_id}"):
            try:
                self.logger.debug(f"[{operation_id}] Fetching recent trends: hours={hours}, source={source}, limit={limit}")
                
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    
                    start_time = datetime.now()
                    
                    # Build dynamic query
                    base_query = """
                        SELECT id, timestamp, source, topic, content, url, 
                               engagement_score, metadata, created_at, is_processed
                        FROM trend_data 
                        WHERE timestamp >= datetime('now', '-{} hours')
                    """.format(hours)
                    
                    params = []
                    
                    if source:
                        base_query += " AND source = ?"
                        params.append(source)
                    
                    # Add ordering and limit
                    base_query += " ORDER BY engagement_score DESC, timestamp DESC"
                    
                    if limit:
                        base_query += " LIMIT ?"
                        params.append(limit)
                    
                    cursor.execute(base_query, params)
                    rows = cursor.fetchall()
                    
                    query_time = (datetime.now() - start_time).total_seconds()
                    self.total_query_time += query_time
                    self.query_count += 1
                    
                    # Convert to list of dictionaries with metadata parsing
                    result = []
                    for row in rows:
                        try:
                            row_dict = dict(row)
                            # Parse metadata JSON
                            if row_dict.get('metadata'):
                                row_dict['metadata'] = json.loads(row_dict['metadata'])
                            result.append(row_dict)
                        except json.JSONDecodeError as e:
                            self.logger.warning(f"[{operation_id}] Failed to parse metadata for row {row['id']}: {e}")
                            row_dict = dict(row)
                            row_dict['metadata'] = {}
                            result.append(row_dict)
                    
                    self.logger.debug(f"[{operation_id}] Retrieved {len(result)} trends in {query_time:.3f}s")
                    return result
                    
            except sqlite3.Error as e:
                self.logger.error(f"[{operation_id}] Database error getting recent trends: {e}", exc_info=True)
                self.error_count += 1
                raise
            except Exception as e:
                self.logger.error(f"[{operation_id}] Unexpected error getting recent trends: {e}", exc_info=True)
                self.error_count += 1
                raise
    
    def get_latest_analysis(self) -> Optional[Dict]:
        """Get the latest trend analysis."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM trend_analysis 
                    ORDER BY timestamp DESC 
                    LIMIT 1
                """)
                
                row = cursor.fetchone()
                return dict(row) if row else None
                
        except sqlite3.Error as e:
            self.logger.error(f"Error getting latest analysis: {e}", exc_info=True)
            self.error_count += 1
            raise
    
    def get_today_published_count(self, platform: str = "twitter") -> int:
        """Get count of successful posts published today."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT COUNT(*) FROM published_content 
                    WHERE platform = ? 
                    AND success = TRUE
                    AND date(timestamp) = date('now')
                """, (platform,))
                
                count = cursor.fetchone()[0]
                return count
                
        except sqlite3.Error as e:
            self.logger.error(f"Error getting today's published count: {e}", exc_info=True)
            self.error_count += 1
            raise
    
    def get_engagement_stats(self, hours: int = 24) -> Dict[str, Any]:
        """Get engagement statistics for recent data."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT 
                        source,
                        COUNT(*) as count,
                        AVG(engagement_score) as avg_engagement,
                        MAX(engagement_score) as max_engagement
                    FROM trend_data 
                    WHERE timestamp >= datetime('now', '-{} hours')
                    GROUP BY source
                """.format(hours))
                
                rows = cursor.fetchall()
                stats = {}
                for row in rows:
                    stats[row[0]] = {
                        'count': row[1],
                        'avg_engagement': round(row[2], 2) if row[2] else 0,
                        'max_engagement': row[3] if row[3] else 0
                    }
                return stats
                
        except sqlite3.Error as e:
            self.logger.error(f"Error getting engagement stats: {e}", exc_info=True)
            self.error_count += 1
            raise
    
    def cleanup_old_data(self, days: int = 30) -> Dict[str, int]:
        """Clean up data older than specified days with detailed reporting."""
        operation_id = f"cleanup_{int(datetime.now().timestamp()*1000)}"
        
        with PerformanceMonitor(f"cleanup_old_data_{operation_id}"):
            try:
                self.logger.info(f"[{operation_id}] Starting cleanup of data older than {days} days")
                
                cleanup_stats = {
                    'trend_data_deleted': 0,
                    'trend_analysis_deleted': 0,
                    'published_content_deleted': 0
                }
                
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    
                    # Clean trend_data
                    cursor.execute(
                        "SELECT COUNT(*) FROM trend_data WHERE timestamp < datetime('now', '-{} days')".format(days)
                    )
                    trend_data_count = cursor.fetchone()[0]
                    
                    if trend_data_count > 0:
                        cursor.execute(
                            "DELETE FROM trend_data WHERE timestamp < datetime('now', '-{} days')".format(days)
                        )
                        cleanup_stats['trend_data_deleted'] = trend_data_count
                    
                    # Clean trend_analysis (keep longer - 2x days)
                    analysis_retention_days = days * 2
                    cursor.execute(
                        "SELECT COUNT(*) FROM trend_analysis WHERE timestamp < datetime('now', '-{} days')".format(analysis_retention_days)
                    )
                    analysis_count = cursor.fetchone()[0]
                    
                    if analysis_count > 0:
                        cursor.execute(
                            "DELETE FROM trend_analysis WHERE timestamp < datetime('now', '-{} days')".format(analysis_retention_days)
                        )
                        cleanup_stats['trend_analysis_deleted'] = analysis_count
                    
                    # Clean published_content
                    cursor.execute(
                        "SELECT COUNT(*) FROM published_content WHERE timestamp < datetime('now', '-{} days')".format(days)
                    )
                    published_count = cursor.fetchone()[0]
                    
                    if published_count > 0:
                        cursor.execute(
                            "DELETE FROM published_content WHERE timestamp < datetime('now', '-{} days')".format(days)
                        )
                        cleanup_stats['published_content_deleted'] = published_count
                    
                    # Vacuum database to reclaim space
                    cursor.execute("VACUUM")
                    
                    conn.commit()
                    
                    total_deleted = sum(cleanup_stats.values())
                    self.logger.info(f"[{operation_id}] Cleanup completed: {total_deleted} total records deleted")
                    
                    for table, count in cleanup_stats.items():
                        if count > 0:
                            self.logger.info(f"[{operation_id}] {table}: {count} records deleted")
                    
                    return cleanup_stats
                    
            except sqlite3.Error as e:
                self.logger.error(f"[{operation_id}] Database error during cleanup: {e}", exc_info=True)
                self.error_count += 1
                raise
            except Exception as e:
                self.logger.error(f"[{operation_id}] Unexpected error during cleanup: {e}", exc_info=True)
                self.error_count += 1
                raise
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Get comprehensive database statistics."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                stats = {
                    'connection_count': self._connection_count,
                    'query_count': self.query_count,
                    'error_count': self.error_count,
                    'avg_query_time': round(self.total_query_time / max(self.query_count, 1), 4),
                    'database_size_mb': round(self.db_path.stat().st_size / (1024 * 1024), 2) if self.db_path.exists() else 0
                }
                
                # Table counts
                for table in ['trend_data', 'trend_analysis', 'published_content']:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    stats[f'{table}_count'] = cursor.fetchone()[0]
                
                # Recent data counts (last 24 hours)
                cursor.execute(
                    "SELECT COUNT(*) FROM trend_data WHERE timestamp >= datetime('now', '-24 hours')"
                )
                stats['recent_trends_24h'] = cursor.fetchone()[0]
                
                # Engagement statistics
                cursor.execute(
                    "SELECT AVG(engagement_score), MAX(engagement_score) FROM trend_data WHERE timestamp >= datetime('now', '-24 hours')"
                )
                engagement_stats = cursor.fetchone()
                stats['avg_engagement_24h'] = round(engagement_stats[0] or 0, 2)
                stats['max_engagement_24h'] = engagement_stats[1] or 0
                
                return stats
                
        except Exception as e:
            self.logger.error(f"Error getting database stats: {e}")
            return {'error': str(e)}
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get database health status."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Test basic operations
                cursor.execute("SELECT 1")
                
                # Check WAL mode
                cursor.execute("PRAGMA journal_mode")
                journal_mode = cursor.fetchone()[0]
                
                # Check integrity
                cursor.execute("PRAGMA integrity_check(1)")
                integrity_result = cursor.fetchone()[0]
                
                return {
                    'status': 'healthy' if integrity_result == 'ok' else 'degraded',
                    'journal_mode': journal_mode,
                    'integrity_check': integrity_result,
                    'database_exists': self.db_path.exists(),
                    'last_query_time': round(self.total_query_time / max(self.query_count, 1), 4),
                    'error_rate': round(self.error_count / max(self.query_count, 1), 4)
                }
                
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e)
            }
    
    def optimize_database(self) -> Dict[str, Any]:
        """Optimize database performance."""
        operation_id = f"optimize_{int(datetime.now().timestamp()*1000)}"
        
        try:
            self.logger.info(f"[{operation_id}] Starting database optimization")
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Analyze tables for query optimization
                cursor.execute("ANALYZE")
                
                # Reindex for performance
                cursor.execute("REINDEX")
                
                # Update table statistics
                cursor.execute("PRAGMA optimize")
                
                conn.commit()
                
                self.logger.info(f"[{operation_id}] Database optimization completed")
                
                return {
                    'success': True,
                    'operation_id': operation_id,
                    'timestamp': datetime.now().isoformat()
                }
                
        except Exception as e:
            self.logger.error(f"[{operation_id}] Database optimization failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'operation_id': operation_id
            }
    
    def close(self):
        """Close database connections and cleanup resources."""
        try:
            # Log final statistics
            if self.query_count > 0:
                avg_time = self.total_query_time / self.query_count
                self.logger.info(f"Database session completed: {self.query_count} queries, avg time: {avg_time:.4f}s")
            
            # Clear any cached connections
            if hasattr(self, '_local'):
                delattr(self, '_local')
                
        except Exception as e:
            self.logger.warning(f"Error during database cleanup: {e}")