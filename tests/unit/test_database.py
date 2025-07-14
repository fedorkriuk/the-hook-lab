"""
Unit tests for TrendDatabase class.

Tests cover:
- Database initialization
- CRUD operations
- Data validation
- Error handling
- Performance monitoring
"""

import pytest
import sqlite3
import json
from datetime import datetime, timedelta
from unittest.mock import patch, Mock

from database import TrendDatabase


class TestTrendDatabase:
    """Test cases for TrendDatabase class."""
    
    def test_database_initialization(self, test_config, temp_db):
        """Test database initialization with proper schema."""
        db = TrendDatabase(db_path=temp_db, config=test_config)
        
        # Check if database file exists
        assert db.db_path.exists()
        
        # Verify tables exist
        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            tables = [row[0] for row in cursor.fetchall()]
            
            expected_tables = ['trend_data', 'trend_analysis', 'published_content', 'db_metadata']
            for table in expected_tables:
                assert table in tables, f"Missing table: {table}"
        
        db.close()
    
    def test_insert_trend_data_success(self, test_database, sample_trends_data):
        """Test successful trend data insertion."""
        trend = sample_trends_data[0]
        
        trend_id = test_database.insert_trend_data(
            source=trend['source'],
            topic=trend['topic'],
            content=trend['content'],
            url=trend['url'],
            engagement_score=trend['engagement_score'],
            metadata=trend['metadata']
        )
        
        assert trend_id > 0
        
        # Verify data was inserted correctly
        with test_database._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM trend_data WHERE id = ?", (trend_id,))
            row = cursor.fetchone()
            
            assert row is not None
            assert row['source'] == trend['source']
            assert row['topic'] == trend['topic']
            assert row['content'] == trend['content']
            assert row['engagement_score'] == trend['engagement_score']
            
            # Check metadata JSON parsing
            metadata = json.loads(row['metadata'])
            assert metadata == trend['metadata']
    
    def test_insert_trend_data_validation(self, test_database):
        """Test input validation for trend data insertion."""
        # Test empty source
        with pytest.raises(ValueError, match="Source cannot be empty"):
            test_database.insert_trend_data("", "topic", "content")
        
        # Test empty topic
        with pytest.raises(ValueError, match="Topic cannot be empty"):
            test_database.insert_trend_data("source", "", "content")
        
        # Test negative engagement score
        with pytest.raises(ValueError, match="Engagement score must be non-negative"):
            test_database.insert_trend_data("source", "topic", engagement_score=-1.0)
        
        # Test source too long
        long_source = "x" * 51
        with pytest.raises(ValueError, match="Source too long"):
            test_database.insert_trend_data(long_source, "topic")
        
        # Test topic too long
        long_topic = "x" * 201
        with pytest.raises(ValueError, match="Topic too long"):
            test_database.insert_trend_data("source", long_topic)
    
    def test_duplicate_detection(self, test_database):
        """Test duplicate trend detection."""
        # Insert first trend
        trend_id1 = test_database.insert_trend_data(
            source="test",
            topic="duplicate test",
            content="same content"
        )
        assert trend_id1 > 0
        
        # Try to insert identical trend
        trend_id2 = test_database.insert_trend_data(
            source="test",
            topic="duplicate test",
            content="same content"
        )
        assert trend_id2 == -1  # Should be detected as duplicate
    
    def test_get_recent_trend_data(self, test_database, sample_trends_data):
        """Test retrieving recent trend data."""
        # Insert sample data
        inserted_ids = []
        for trend in sample_trends_data:
            trend_id = test_database.insert_trend_data(
                source=trend['source'],
                topic=trend['topic'],
                content=trend['content'],
                url=trend['url'],
                engagement_score=trend['engagement_score'],
                metadata=trend['metadata']
            )
            inserted_ids.append(trend_id)
        
        # Retrieve recent data
        recent_trends = test_database.get_recent_trend_data(hours=24)
        
        assert len(recent_trends) == len(sample_trends_data)
        
        # Check data structure
        for trend in recent_trends:
            assert 'id' in trend
            assert 'source' in trend
            assert 'topic' in trend
            assert 'engagement_score' in trend
            assert 'metadata' in trend
            assert isinstance(trend['metadata'], dict)
    
    def test_get_recent_trend_data_with_filters(self, test_database, sample_trends_data):
        """Test retrieving recent trends with source filter and limit."""
        # Insert sample data
        for trend in sample_trends_data:
            test_database.insert_trend_data(
                source=trend['source'],
                topic=trend['topic'],
                content=trend['content'],
                url=trend['url'],
                engagement_score=trend['engagement_score'],
                metadata=trend['metadata']
            )
        
        # Test source filter
        twitter_trends = test_database.get_recent_trend_data(hours=24, source='twitter')
        assert len(twitter_trends) == 1
        assert twitter_trends[0]['source'] == 'twitter'
        
        # Test limit
        limited_trends = test_database.get_recent_trend_data(hours=24, limit=2)
        assert len(limited_trends) == 2
        
        # Should be ordered by engagement score DESC
        assert limited_trends[0]['engagement_score'] >= limited_trends[1]['engagement_score']
    
    def test_insert_trend_analysis(self, test_database, sample_analysis_result):
        """Test inserting trend analysis results."""
        analysis_id = test_database.insert_trend_analysis(
            trends_summary=sample_analysis_result['summary'],
            sentiment_score=sample_analysis_result['sentiment_score'],
            insights=sample_analysis_result['insights'],
            data_points_count=sample_analysis_result['total_trends']
        )
        
        assert analysis_id > 0
        
        # Verify insertion
        with test_database._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM trend_analysis WHERE id = ?", (analysis_id,))
            row = cursor.fetchone()
            
            assert row is not None
            assert row['sentiment_score'] == sample_analysis_result['sentiment_score']
            assert row['insights'] == sample_analysis_result['insights']
            assert row['data_points_count'] == sample_analysis_result['total_trends']
    
    def test_get_latest_analysis(self, test_database, sample_analysis_result):
        """Test retrieving latest analysis."""
        # Insert analysis
        analysis_id = test_database.insert_trend_analysis(
            trends_summary=sample_analysis_result['summary'],
            sentiment_score=sample_analysis_result['sentiment_score'],
            insights=sample_analysis_result['insights'],
            data_points_count=sample_analysis_result['total_trends']
        )
        
        # Retrieve latest
        latest = test_database.get_latest_analysis()
        
        assert latest is not None
        assert latest['id'] == analysis_id
        assert latest['sentiment_score'] == sample_analysis_result['sentiment_score']
    
    def test_published_content_tracking(self, test_database):
        """Test published content tracking."""
        content_id = test_database.insert_published_content(
            platform="twitter",
            content="Test tweet content",
            post_id="123456789",
            success=True
        )
        
        assert content_id > 0
        
        # Check daily count
        count = test_database.get_today_published_count("twitter")
        assert count == 1
    
    def test_cleanup_old_data(self, test_database):
        """Test cleaning up old data."""
        # Insert some test data
        test_database.insert_trend_data(
            source="test",
            topic="old data",
            content="This should be cleaned up"
        )
        
        # Manually set old timestamp
        with test_database._get_connection() as conn:
            cursor = conn.cursor()
            old_date = (datetime.now() - timedelta(days=35)).isoformat()
            cursor.execute(
                "UPDATE trend_data SET timestamp = ? WHERE topic = ?",
                (old_date, "old data")
            )
            conn.commit()
        
        # Run cleanup
        cleanup_stats = test_database.cleanup_old_data(days=30)
        
        assert isinstance(cleanup_stats, dict)
        assert 'trend_data_deleted' in cleanup_stats
        assert cleanup_stats['trend_data_deleted'] == 1
    
    def test_database_stats(self, test_database, sample_trends_data):
        """Test database statistics collection."""
        # Insert some data
        for trend in sample_trends_data:
            test_database.insert_trend_data(
                source=trend['source'],
                topic=trend['topic'],
                content=trend['content'],
                engagement_score=trend['engagement_score']
            )
        
        stats = test_database.get_database_stats()
        
        assert isinstance(stats, dict)
        assert 'trend_data_count' in stats
        assert 'query_count' in stats
        assert 'database_size_mb' in stats
        assert stats['trend_data_count'] == len(sample_trends_data)
    
    def test_health_status(self, test_database):
        """Test database health status check."""
        health = test_database.get_health_status()
        
        assert isinstance(health, dict)
        assert 'status' in health
        assert health['status'] in ['healthy', 'degraded', 'unhealthy']
        assert 'journal_mode' in health
        assert 'integrity_check' in health
    
    def test_optimize_database(self, test_database):
        """Test database optimization."""
        result = test_database.optimize_database()
        
        assert isinstance(result, dict)
        assert 'success' in result
        assert result['success'] is True
        assert 'operation_id' in result
    
    def test_error_handling_connection_failure(self, test_config):
        """Test error handling for connection failures."""
        # Try to initialize with invalid database path
        with pytest.raises(Exception):
            db = TrendDatabase(db_path="/invalid/path/db.sqlite", config=test_config)
    
    def test_performance_tracking(self, test_database):
        """Test that performance metrics are tracked."""
        initial_query_count = test_database.query_count
        
        # Perform some operations
        test_database.insert_trend_data("test", "performance test")
        test_database.get_recent_trend_data(hours=1)
        
        # Check that metrics were updated
        assert test_database.query_count > initial_query_count
        assert test_database.total_query_time > 0
    
    def test_concurrent_access(self, test_database):
        """Test database handling of concurrent access."""
        import threading
        import time
        
        results = []
        errors = []
        
        def insert_data(thread_id):
            try:
                trend_id = test_database.insert_trend_data(
                    source="test",
                    topic=f"concurrent test {thread_id}",
                    content=f"Thread {thread_id} data"
                )
                results.append(trend_id)
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=insert_data, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Check results
        assert len(errors) == 0, f"Concurrent access errors: {errors}"
        assert len(results) == 5
        assert all(tid > 0 for tid in results)  # All insertions successful
    
    def test_transaction_rollback(self, test_database):
        """Test transaction rollback on error."""
        with pytest.raises(sqlite3.IntegrityError):
            with test_database._get_connection() as conn:
                cursor = conn.cursor()
                # This should fail due to constraint violation
                cursor.execute(
                    "INSERT INTO trend_data (source, topic, engagement_score) VALUES (?, ?, ?)",
                    ("", "", -1.0)  # Invalid data
                )
                conn.commit()
        
        # Verify no partial data was inserted
        count = test_database.get_database_stats()['trend_data_count']
        assert count == 0
    
    @pytest.mark.slow
    def test_large_data_insertion(self, test_database):
        """Test handling of large data insertions."""
        import time
        
        start_time = time.time()
        
        # Insert many records
        for i in range(100):
            test_database.insert_trend_data(
                source="bulk_test",
                topic=f"Topic {i}",
                content=f"Content for item {i}",
                engagement_score=float(i)
            )
        
        end_time = time.time()
        
        # Verify all data was inserted
        recent_trends = test_database.get_recent_trend_data(hours=24, source="bulk_test")
        assert len(recent_trends) == 100
        
        # Check performance (should complete in reasonable time)
        total_time = end_time - start_time
        assert total_time < 10.0, f"Bulk insertion took too long: {total_time}s"
    
    def test_metadata_json_handling(self, test_database):
        """Test proper JSON handling for metadata."""
        complex_metadata = {
            'nested': {'key': 'value'},
            'list': [1, 2, 3],
            'unicode': 'café',
            'boolean': True,
            'null': None
        }
        
        trend_id = test_database.insert_trend_data(
            source="json_test",
            topic="metadata test",
            metadata=complex_metadata
        )
        
        # Retrieve and verify
        trends = test_database.get_recent_trend_data(hours=24, source="json_test")
        assert len(trends) == 1
        
        retrieved_metadata = trends[0]['metadata']
        assert retrieved_metadata == complex_metadata
    
    def test_database_migration_compatibility(self, test_database):
        """Test that database schema is compatible with expected version."""
        with test_database._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM db_metadata WHERE key = 'schema_version'")
            version = cursor.fetchone()
            
            assert version is not None
            assert version[0] == '2.0'