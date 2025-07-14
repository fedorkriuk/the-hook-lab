"""
Unit tests for DataCollector class.

Tests cover:
- API client initialization
- Data collection from different sources
- Rate limiting
- Error handling and retry logic
- Data validation and cleaning
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from collectors import DataCollector
from conftest import MockResponse, create_mock_trend


class TestDataCollector:
    """Test cases for DataCollector class."""
    
    def test_collector_initialization(self, test_config, mock_environment_vars):
        """Test DataCollector initialization with proper configuration."""
        collector = DataCollector(config=test_config)
        
        assert collector.config == test_config
        assert collector.collection_limits == test_config['collection_limits']
        assert len(collector.api_status) == 4
        
        # Check that status tracking is initialized
        for api in ['twitter', 'github', 'reddit', 'hackernews']:
            assert api in collector.api_status
            assert 'available' in collector.api_status[api]
            assert 'error_count' in collector.api_status[api]
    
    @patch('collectors.tweepy.Client')
    def test_twitter_api_setup_success(self, mock_tweepy_client, test_config, mock_environment_vars):
        """Test successful Twitter API setup."""
        # Mock successful authentication
        mock_client_instance = Mock()
        mock_user = Mock()
        mock_user.data = Mock()
        mock_user.data.username = "testbot"
        mock_client_instance.get_me.return_value = mock_user
        mock_tweepy_client.return_value = mock_client_instance
        
        collector = DataCollector(config=test_config)
        
        assert collector.api_status['twitter']['available'] is True
        assert collector.twitter_client is not None
    
    @patch('collectors.tweepy.Client')
    def test_twitter_api_setup_failure(self, mock_tweepy_client, test_config, mock_environment_vars):
        """Test Twitter API setup failure handling."""
        # Mock failed authentication
        mock_tweepy_client.side_effect = Exception("Authentication failed")
        
        collector = DataCollector(config=test_config)
        
        assert collector.api_status['twitter']['available'] is False
        assert 'Authentication failed' in collector.api_status['twitter']['last_error']
        assert collector.twitter_client is None
    
    @patch('collectors.praw.Reddit')
    def test_reddit_api_setup_success(self, mock_praw_reddit, test_config, mock_environment_vars):
        """Test successful Reddit API setup."""
        # Mock successful Reddit connection
        mock_reddit_instance = Mock()
        mock_subreddit = Mock()
        mock_post = Mock()
        mock_subreddit.hot.return_value = [mock_post]
        mock_reddit_instance.subreddit.return_value = mock_subreddit
        mock_praw_reddit.return_value = mock_reddit_instance
        
        collector = DataCollector(config=test_config)
        
        assert collector.api_status['reddit']['available'] is True
        assert collector.reddit is not None
    
    def test_reddit_api_missing_credentials(self, test_config, monkeypatch):
        """Test Reddit API setup with missing credentials."""
        # Remove Reddit credentials
        monkeypatch.delenv('REDDIT_CLIENT_ID', raising=False)
        monkeypatch.delenv('REDDIT_CLIENT_SECRET', raising=False)
        
        collector = DataCollector(config=test_config)
        
        assert collector.api_status['reddit']['available'] is False
        assert collector.reddit is None
    
    @patch('collectors.requests.get')
    def test_github_api_setup_success(self, mock_requests_get, test_config, mock_environment_vars):
        """Test successful GitHub API setup."""
        # Mock successful GitHub API response
        mock_response = MockResponse({
            'rate': {'remaining': 5000}
        })
        mock_requests_get.return_value = mock_response
        
        collector = DataCollector(config=test_config)
        
        assert collector.api_status['github']['available'] is True
        assert collector.github_token is not None
    
    @patch('collectors.requests.get')
    def test_github_api_setup_failure(self, mock_requests_get, test_config, mock_environment_vars):
        """Test GitHub API setup failure handling."""
        # Mock failed GitHub API response
        mock_requests_get.side_effect = Exception("API request failed")
        
        collector = DataCollector(config=test_config)
        
        assert collector.api_status['github']['available'] is False
        assert 'API request failed' in collector.api_status['github']['last_error']
    
    def test_rate_limiting(self, test_config, mock_environment_vars):
        """Test rate limiting functionality."""
        collector = DataCollector(config=test_config)
        
        # Record start time
        start_time = time.time()
        
        # Make two rapid requests
        collector._rate_limit_check('test_source')
        collector._rate_limit_check('test_source')
        
        # Second call should be delayed
        elapsed = time.time() - start_time
        assert elapsed >= collector.min_request_intervals.get('test_source', 1)
    
    def test_rate_limiting_with_errors(self, test_config, mock_environment_vars):
        """Test adaptive rate limiting with error tracking."""
        collector = DataCollector(config=test_config)
        
        # Simulate errors to trigger adaptive delay
        collector.api_status['test_source'] = {'error_count': 3}
        
        start_time = time.time()
        collector._rate_limit_check('test_source')
        elapsed = time.time() - start_time
        
        # Should have additional delay due to errors
        expected_delay = collector.min_request_intervals.get('test_source', 1) + 1.5  # 3 * 0.5
        assert elapsed >= expected_delay * 0.9  # Allow small tolerance
    
    @patch('collectors.DataCollector.collect_twitter_trends')
    @patch('collectors.DataCollector.collect_github_trends')
    @patch('collectors.DataCollector.collect_reddit_trends')
    @patch('collectors.DataCollector.collect_hackernews_trends')
    def test_collect_all_trends_success(self, mock_hn, mock_reddit, mock_github, mock_twitter, 
                                      test_config, mock_environment_vars):
        """Test successful collection from all sources."""
        # Setup mocks to return sample data
        mock_twitter.return_value = [create_mock_trend('twitter', 'AI news')]
        mock_github.return_value = [create_mock_trend('github', 'ml-library')]
        mock_reddit.return_value = [create_mock_trend('reddit', 'r/MachineLearning')]
        mock_hn.return_value = [create_mock_trend('hackernews', 'Show HN')]
        
        collector = DataCollector(config=test_config)
        # Set all APIs as available
        for api in collector.api_status:
            collector.api_status[api]['available'] = True
        
        trends = collector.collect_all_trends()
        
        assert len(trends) == 4
        assert all('source' in trend for trend in trends)
        assert all('engagement_score' in trend for trend in trends)
        
        # Should be sorted by engagement score
        for i in range(len(trends) - 1):
            assert trends[i]['engagement_score'] >= trends[i + 1]['engagement_score']
    
    @patch('collectors.DataCollector.collect_twitter_trends')
    def test_collect_all_trends_partial_failure(self, mock_twitter, test_config, mock_environment_vars):
        """Test collection with some sources failing."""
        # Twitter succeeds
        mock_twitter.return_value = [create_mock_trend('twitter', 'AI news')]
        
        collector = DataCollector(config=test_config)
        # Only Twitter API available
        collector.api_status['twitter']['available'] = True
        collector.api_status['github']['available'] = False
        collector.api_status['reddit']['available'] = False
        collector.api_status['hackernews']['available'] = True  # HN doesn't need auth
        
        with patch.object(collector, 'collect_hackernews_trends', side_effect=Exception("HN failed")):
            trends = collector.collect_all_trends()
        
        assert len(trends) == 1  # Only Twitter succeeded
        assert trends[0]['source'] == 'twitter'
    
    def test_collect_all_trends_timeout(self, test_config, mock_environment_vars):
        """Test collection timeout handling."""
        collector = DataCollector(config=test_config)
        collector.collection_timeout = 1  # Very short timeout
        
        # Mock a slow collection method
        def slow_collect():
            time.sleep(2)  # Longer than timeout
            return []
        
        with patch.object(collector, '_collect_twitter_safe', slow_collect):
            collector.api_status['twitter']['available'] = True
            trends = collector.collect_all_trends()
            
        # Should return empty due to timeout
        assert len(trends) == 0
    
    @patch('collectors.tweepy.Client')
    def test_twitter_trends_collection(self, mock_tweepy_client, test_config, mock_environment_vars):
        """Test Twitter trends collection with mocked API."""
        # Setup mock responses
        mock_client = Mock()
        mock_tweet = Mock()
        mock_tweet.id = '123456789'
        mock_tweet.text = 'Test tweet about #AI trends'
        mock_tweet.author_id = '987654321'
        mock_tweet.created_at = datetime.now()
        mock_tweet.public_metrics = {
            'like_count': 10,
            'retweet_count': 5,
            'reply_count': 2
        }
        
        mock_response = Mock()
        mock_response.data = [mock_tweet]
        mock_client.search_recent_tweets.return_value = mock_response
        
        # Setup authentication mock
        mock_user = Mock()
        mock_user.data = Mock()
        mock_user.data.username = "testbot"
        mock_client.get_me.return_value = mock_user
        
        mock_tweepy_client.return_value = mock_client
        
        collector = DataCollector(config=test_config)
        trends = collector.collect_twitter_trends(limit=5)
        
        assert len(trends) > 0
        
        for trend in trends:
            assert trend['source'] == 'twitter'
            assert 'topic' in trend
            assert 'engagement_score' in trend
            assert trend['engagement_score'] >= 0
    
    @patch('collectors.requests.Session.get')
    def test_github_trends_collection(self, mock_get, test_config, mock_environment_vars):
        """Test GitHub trends collection with mocked API."""
        # Mock GitHub API response
        mock_response = MockResponse({
            'items': [
                {
                    'id': 123456,
                    'name': 'awesome-ai-lib',
                    'full_name': 'user/awesome-ai-lib',
                    'description': 'An awesome AI library',
                    'html_url': 'https://github.com/user/awesome-ai-lib',
                    'stargazers_count': 1000,
                    'forks_count': 200,
                    'language': 'Python',
                    'created_at': '2024-01-01T00:00:00Z',
                    'updated_at': '2024-01-01T12:00:00Z',
                    'topics': ['machine-learning', 'ai']
                }
            ]
        })
        mock_get.return_value = mock_response
        
        collector = DataCollector(config=test_config)
        collector.api_status['github']['available'] = True
        
        trends = collector.collect_github_trends(limit=5)
        
        assert len(trends) > 0
        
        for trend in trends:
            assert trend['source'] == 'github'
            assert 'metadata' in trend
            assert 'repo_id' in trend['metadata']
            assert 'language' in trend['metadata']
    
    @patch('collectors.praw.Reddit')
    def test_reddit_trends_collection(self, mock_praw, test_config, mock_environment_vars):
        """Test Reddit trends collection with mocked API."""
        # Setup mock Reddit posts
        mock_post = Mock()
        mock_post.id = 'test_post'
        mock_post.title = 'Interesting ML research paper'
        mock_post.selftext = 'This paper discusses novel approaches to machine learning'
        mock_post.score = 150
        mock_post.num_comments = 25
        mock_post.author = Mock()
        mock_post.author.__str__ = lambda: 'researcher123'
        mock_post.permalink = '/r/MachineLearning/comments/test_post/'
        mock_post.created_utc = datetime.now().timestamp()
        mock_post.upvote_ratio = 0.89
        mock_post.stickied = False
        
        mock_subreddit = Mock()
        mock_subreddit.hot.return_value = [mock_post]
        mock_subreddit.top.return_value = [mock_post]
        
        mock_reddit = Mock()
        mock_reddit.subreddit.return_value = mock_subreddit
        mock_praw.return_value = mock_reddit
        
        collector = DataCollector(config=test_config)
        collector.api_status['reddit']['available'] = True
        
        trends = collector.collect_reddit_trends(limit=5)
        
        assert len(trends) > 0
        
        for trend in trends:
            assert trend['source'] == 'reddit'
            assert 'r/' in trend['topic']
            assert 'metadata' in trend
            assert 'subreddit' in trend['metadata']
    
    @patch('collectors.requests.Session.get')
    def test_hackernews_trends_collection(self, mock_get, test_config, mock_environment_vars):
        """Test HackerNews trends collection with mocked API."""
        # Mock HN API responses
        def mock_get_response(url, **kwargs):
            if 'topstories.json' in url:
                return MockResponse([1, 2, 3, 4, 5])
            elif 'item/' in url:
                return MockResponse({
                    'id': 1,
                    'type': 'story',
                    'title': 'Show HN: My AI startup',
                    'url': 'https://example.com',
                    'score': 250,
                    'descendants': 100,
                    'by': 'startup_founder',
                    'time': int(datetime.now().timestamp())
                })
            else:
                return MockResponse({})
        
        mock_get.side_effect = mock_get_response
        
        collector = DataCollector(config=test_config)
        trends = collector.collect_hackernews_trends(limit=5)
        
        assert len(trends) > 0
        
        for trend in trends:
            assert trend['source'] == 'hackernews'
            assert trend['topic'] == 'Hacker News'
            assert 'metadata' in trend
            assert 'story_id' in trend['metadata']
    
    def test_validate_and_clean_trends(self, test_config, mock_environment_vars):
        """Test trend data validation and cleaning."""
        collector = DataCollector(config=test_config)
        
        # Create test data with various issues
        raw_trends = [
            # Valid trend
            {
                'source': 'test',
                'topic': 'Valid trend',
                'content': 'This is valid content',
                'url': 'https://example.com',
                'engagement_score': 100.0,
                'metadata': {'key': 'value'}
            },
            # Missing source (should be filtered out)
            {
                'topic': 'No source',
                'content': 'Missing source field'
            },
            # Empty topic (should be filtered out)
            {
                'source': 'test',
                'topic': '',
                'content': 'Empty topic'
            },
            # Very long content (should be truncated)
            {
                'source': 'test',
                'topic': 'Long content',
                'content': 'x' * 2000,  # Very long content
                'engagement_score': 50.0
            },
            # Negative engagement (should be fixed)
            {
                'source': 'test',
                'topic': 'Negative engagement',
                'content': 'This has negative engagement',
                'engagement_score': -10.0
            }
        ]
        
        validated = collector._validate_and_clean_trends(raw_trends)
        
        assert len(validated) == 3  # Only 3 valid trends
        
        # Check that long content was truncated
        long_content_trend = next(t for t in validated if t['topic'] == 'Long content')
        assert len(long_content_trend['content']) <= 1000
        
        # Check that negative engagement was fixed
        negative_trend = next(t for t in validated if t['topic'] == 'Negative engagement')
        assert negative_trend['engagement_score'] == 0.0  # Should be 0, not negative
        
        # Check that collection_time was added
        for trend in validated:
            assert 'collection_time' in trend
    
    def test_content_hash_generation(self, test_config, mock_environment_vars):
        """Test content hash generation for deduplication."""
        collector = DataCollector(config=test_config)
        
        hash1 = collector._generate_content_hash('twitter', 'AI news', 'Content about AI')
        hash2 = collector._generate_content_hash('twitter', 'AI news', 'Content about AI')
        hash3 = collector._generate_content_hash('twitter', 'Different news', 'Content about AI')
        
        # Same content should produce same hash
        assert hash1 == hash2
        
        # Different content should produce different hash
        assert hash1 != hash3
        
        # Hash should be MD5 hex string
        assert len(hash1) == 32
        assert all(c in '0123456789abcdef' for c in hash1)
    
    def test_api_status_tracking(self, test_config, mock_environment_vars):
        """Test API status tracking and error counting."""
        collector = DataCollector(config=test_config)
        
        # Initially no errors
        assert collector.api_status['test']['error_count'] == 0
        
        # Update status with error
        collector._update_api_status('test', False, 'Connection failed')
        
        assert collector.api_status['test']['available'] is False
        assert collector.api_status['test']['last_error'] == 'Connection failed'
        assert collector.api_status['test']['error_count'] == 1
    
    def test_get_api_status(self, test_config, mock_environment_vars):
        """Test API status reporting."""
        collector = DataCollector(config=test_config)
        
        status = collector.get_api_status()
        
        assert isinstance(status, dict)
        assert 'timestamp' in status
        assert 'apis' in status
        assert 'collection_limits' in status
        assert 'last_request_times' in status
        
        # Check that all expected APIs are tracked
        for api in ['twitter', 'github', 'reddit', 'hackernews']:
            assert api in status['apis']
    
    @pytest.mark.slow
    def test_concurrent_collection(self, test_config, mock_environment_vars):
        """Test concurrent data collection doesn't cause issues."""
        import threading
        import time
        
        collector = DataCollector(config=test_config)
        results = []
        errors = []
        
        def collect_data(thread_id):
            try:
                # Mock successful collection
                with patch.object(collector, '_collect_twitter_safe', 
                                return_value=[create_mock_trend('twitter', f'Thread {thread_id}')]):
                    collector.api_status['twitter']['available'] = True
                    trends = collector.collect_all_trends()
                    results.append(trends)
            except Exception as e:
                errors.append(e)
        
        # Start multiple collection threads
        threads = []
        for i in range(3):
            thread = threading.Thread(target=collect_data, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        assert len(errors) == 0, f"Concurrent collection errors: {errors}"
        assert len(results) == 3
        assert all(len(result) > 0 for result in results)
    
    def test_retry_decorator_functionality(self, test_config, mock_environment_vars):
        """Test that retry decorators work correctly."""
        collector = DataCollector(config=test_config)
        
        # Mock a method that fails twice then succeeds
        call_count = 0
        def failing_method():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception(f"Attempt {call_count} failed")
            return "success"
        
        # Apply retry decorator
        from utils import RetryWithBackoff
        retried_method = RetryWithBackoff(max_attempts=3, base_delay=0.1)(failing_method)
        
        result = retried_method()
        assert result == "success"
        assert call_count == 3  # Should have been called 3 times
    
    def test_collection_with_no_available_apis(self, test_config, mock_environment_vars):
        """Test collection behavior when no APIs are available."""
        collector = DataCollector(config=test_config)
        
        # Set all APIs as unavailable
        for api in collector.api_status:
            collector.api_status[api]['available'] = False
        
        trends = collector.collect_all_trends()
        
        # Should return empty list but not crash
        assert trends == []