"""
Pytest configuration and shared fixtures for TrendBot tests.

This module provides:
- Test configuration setup
- Shared fixtures for all test modules
- Mock data and API responses
- Test database setup
"""

import pytest
import tempfile
import os
import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, MagicMock
import sqlite3

# Import TrendBot components for testing
import sys
sys.path.append(str(Path(__file__).parent.parent))

from config import TrendBotConfig
from database import TrendDatabase
from collectors import DataCollector
from analyzer import TrendAnalyzer
from visualizer import TrendVisualizer
from publisher import TwitterPublisher
from scheduler import TrendBotScheduler


@pytest.fixture(scope="session")
def test_config():
    """Create test configuration."""
    return {
        'log_level': 'DEBUG',
        'database_path': ':memory:',  # Use in-memory database for tests
        'max_memory_mb': 512,
        'api_retry_attempts': 1,
        'api_retry_delay': 0.1,
        'collection_limits': {
            'twitter': 5,
            'github': 5,
            'reddit': 5,
            'hackernews': 5
        },
        'openai_model': 'gpt-3.5-turbo',
        'openai_max_tokens': 100,
        'openai_temperature': 0.0,  # Deterministic for testing
        'daily_post_limit': 1,
        'viz_output_dir': 'test_visualizations'
    }


@pytest.fixture
def temp_db():
    """Create temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    yield db_path
    
    # Cleanup
    try:
        os.unlink(db_path)
    except FileNotFoundError:
        pass


@pytest.fixture
def test_database(temp_db, test_config):
    """Create test database instance."""
    config = test_config.copy()
    config['database_path'] = temp_db
    
    db = TrendDatabase(config=config)
    yield db
    db.close()


@pytest.fixture
def sample_trends_data():
    """Sample trend data for testing."""
    return [
        {
            'source': 'twitter',
            'topic': 'AI breakthrough',
            'content': 'New AI model shows amazing results in language understanding',
            'url': 'https://twitter.com/user/status/123',
            'engagement_score': 150.0,
            'metadata': {
                'tweet_id': '123',
                'author_id': 'user123',
                'created_at': '2024-01-01T12:00:00Z',
                'metrics': {'likes': 100, 'retweets': 50}
            }
        },
        {
            'source': 'github',
            'topic': 'awesome-ml-lib',
            'content': 'Repository: user/awesome-ml-lib - Advanced machine learning library',
            'url': 'https://github.com/user/awesome-ml-lib',
            'engagement_score': 200.0,
            'metadata': {
                'repo_id': 456,
                'full_name': 'user/awesome-ml-lib',
                'language': 'Python',
                'stars': 150,
                'forks': 25
            }
        },
        {
            'source': 'reddit',
            'topic': 'r/MachineLearning',
            'content': 'Discussion about latest ML techniques and research papers',
            'url': 'https://reddit.com/r/MachineLearning/post/789',
            'engagement_score': 75.0,
            'metadata': {
                'post_id': '789',
                'subreddit': 'MachineLearning',
                'author': 'ml_researcher',
                'score': 50,
                'num_comments': 25
            }
        },
        {
            'source': 'hackernews',
            'topic': 'Hacker News',
            'content': 'Show HN: I built a neural network that can predict stock prices',
            'url': 'https://news.ycombinator.com/item?id=987',
            'engagement_score': 120.0,
            'metadata': {
                'story_id': 987,
                'author': 'startup_founder',
                'score': 80,
                'comments': 40
            }
        }
    ]


@pytest.fixture
def sample_analysis_result():
    """Sample analysis result for testing."""
    return {
        'sentiment_score': 0.3,
        'insights': 'The trends show positive sentiment towards AI and machine learning technologies. Key developments include new breakthrough models and increased community engagement.',
        'summary': 'Analyzed 4 trends with positive sentiment (score: 0.30). Average engagement: 136.2. Sources: twitter(1), github(1), reddit(1), hackernews(1).',
        'top_topics': [
            {
                'topic': 'awesome-ml-lib',
                'source': 'github',
                'engagement_score': 200.0,
                'content_preview': 'Repository: user/awesome-ml-lib - Advanced machine learning library'
            },
            {
                'topic': 'AI breakthrough',
                'source': 'twitter',
                'engagement_score': 150.0,
                'content_preview': 'New AI model shows amazing results in language understanding'
            }
        ],
        'source_breakdown': {
            'twitter': {'count': 1, 'total_engagement': 150.0, 'avg_engagement': 150.0},
            'github': {'count': 1, 'total_engagement': 200.0, 'avg_engagement': 200.0},
            'reddit': {'count': 1, 'total_engagement': 75.0, 'avg_engagement': 75.0},
            'hackernews': {'count': 1, 'total_engagement': 120.0, 'avg_engagement': 120.0}
        },
        'total_trends': 4,
        'timestamp': '2024-01-01T12:00:00Z'
    }


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for testing."""
    mock_client = Mock()
    
    # Mock sentiment response
    sentiment_response = Mock()
    sentiment_response.choices = [Mock()]
    sentiment_response.choices[0].message = Mock()
    sentiment_response.choices[0].message.content = "0.3"
    
    # Mock insights response
    insights_response = Mock()
    insights_response.choices = [Mock()]
    insights_response.choices[0].message = Mock()
    insights_response.choices[0].message.content = "The trends show positive sentiment towards AI technologies."
    
    # Configure the mock to return appropriate responses
    mock_client.chat.completions.create.side_effect = [sentiment_response, insights_response]
    
    return mock_client


@pytest.fixture
def mock_twitter_client():
    """Mock Twitter client for testing."""
    mock_client = Mock()
    
    # Mock user info
    mock_user = Mock()
    mock_user.data = Mock()
    mock_user.data.id = "123456789"
    mock_user.data.username = "testbot"
    
    mock_client.get_me.return_value = mock_user
    
    # Mock tweet creation
    mock_tweet_response = Mock()
    mock_tweet_response.data = {'id': '987654321'}
    mock_client.create_tweet.return_value = mock_tweet_response
    
    # Mock search results
    mock_search_response = Mock()
    mock_tweet = Mock()
    mock_tweet.id = '111222333'
    mock_tweet.text = 'Test tweet about AI trends'
    mock_tweet.author_id = '123456789'
    mock_tweet.created_at = datetime.now()
    mock_tweet.public_metrics = {
        'like_count': 10,
        'retweet_count': 5,
        'reply_count': 2
    }
    
    mock_search_response.data = [mock_tweet]
    mock_client.search_recent_tweets.return_value = mock_search_response
    
    return mock_client


@pytest.fixture
def mock_reddit_client():
    """Mock Reddit client for testing."""
    mock_reddit = Mock()
    
    # Mock subreddit
    mock_subreddit = Mock()
    
    # Mock post
    mock_post = Mock()
    mock_post.id = 'test_post_id'
    mock_post.title = 'Test Reddit Post About ML'
    mock_post.selftext = 'This is a test post content'
    mock_post.score = 50
    mock_post.num_comments = 10
    mock_post.author = Mock()
    mock_post.author.__str__ = lambda: 'test_user'
    mock_post.permalink = '/r/test/comments/test_post_id/'
    mock_post.created_utc = datetime.now().timestamp()
    mock_post.upvote_ratio = 0.85
    mock_post.stickied = False
    
    mock_subreddit.hot.return_value = [mock_post]
    mock_subreddit.top.return_value = [mock_post]
    
    mock_reddit.subreddit.return_value = mock_subreddit
    
    return mock_reddit


@pytest.fixture
def mock_requests_session():
    """Mock requests session for testing."""
    mock_session = Mock()
    
    # Mock GitHub API response
    github_response = Mock()
    github_response.status_code = 200
    github_response.json.return_value = {
        'items': [
            {
                'id': 123456,
                'name': 'test-repo',
                'full_name': 'user/test-repo',
                'description': 'A test repository',
                'html_url': 'https://github.com/user/test-repo',
                'stargazers_count': 100,
                'forks_count': 20,
                'language': 'Python',
                'created_at': '2024-01-01T00:00:00Z',
                'updated_at': '2024-01-01T12:00:00Z'
            }
        ]
    }
    
    # Mock HackerNews API responses
    hn_stories_response = Mock()
    hn_stories_response.status_code = 200
    hn_stories_response.json.return_value = [1, 2, 3, 4, 5]
    
    hn_story_response = Mock()
    hn_story_response.status_code = 200
    hn_story_response.json.return_value = {
        'id': 1,
        'type': 'story',
        'title': 'Test HN Story',
        'url': 'https://example.com',
        'score': 100,
        'descendants': 50,
        'by': 'test_user',
        'time': int(datetime.now().timestamp())
    }
    
    # Configure mock responses
    def mock_get(url, **kwargs):
        if 'github.com' in url:
            return github_response
        elif 'topstories.json' in url:
            return hn_stories_response
        elif 'item/' in url:
            return hn_story_response
        else:
            response = Mock()
            response.status_code = 200
            response.json.return_value = {}
            return response
    
    mock_session.get.side_effect = mock_get
    
    return mock_session


@pytest.fixture
def mock_environment_vars(monkeypatch):
    """Set up mock environment variables for testing."""
    env_vars = {
        'OPENAI_API_KEY': 'test-openai-key',
        'TWITTER_BEARER_TOKEN': 'test-bearer-token',
        'TWITTER_CONSUMER_KEY': 'test-consumer-key',
        'TWITTER_CONSUMER_SECRET': 'test-consumer-secret',
        'TWITTER_ACCESS_TOKEN': 'test-access-token',
        'TWITTER_ACCESS_TOKEN_SECRET': 'test-access-secret',
        'REDDIT_CLIENT_ID': 'test-reddit-id',
        'REDDIT_CLIENT_SECRET': 'test-reddit-secret',
        'REDDIT_USER_AGENT': 'TrendBot/Test',
        'GITHUB_TOKEN': 'test-github-token',
        'LOG_LEVEL': 'DEBUG'
    }
    
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)


@pytest.fixture
def temp_viz_dir(tmp_path):
    """Create temporary directory for visualization tests."""
    viz_dir = tmp_path / "test_visualizations"
    viz_dir.mkdir(exist_ok=True)
    return viz_dir


@pytest.fixture(scope="function")
def clean_cache():
    """Clean up any caches between tests."""
    yield
    # Clean up any global state or caches if needed


# Test markers for categorizing tests
pytest_plugins = []


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "api: mark test as requiring API access"
    )


# Custom test utilities
class MockResponse:
    """Mock HTTP response for testing."""
    
    def __init__(self, json_data, status_code=200):
        self.json_data = json_data
        self.status_code = status_code
        self.headers = {}
    
    def json(self):
        return self.json_data
    
    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


def create_mock_trend(source="test", topic="test topic", engagement_score=100.0, **kwargs):
    """Helper function to create mock trend data."""
    trend = {
        'source': source,
        'topic': topic,
        'content': kwargs.get('content', f'Test content for {topic}'),
        'url': kwargs.get('url', f'https://example.com/{source}/test'),
        'engagement_score': engagement_score,
        'metadata': kwargs.get('metadata', {})
    }
    trend.update(kwargs)
    return trend


def assert_valid_trend_data(trend_data):
    """Assert that trend data has required fields."""
    required_fields = ['source', 'topic', 'engagement_score']
    for field in required_fields:
        assert field in trend_data, f"Missing required field: {field}"
    
    assert isinstance(trend_data['engagement_score'], (int, float))
    assert trend_data['engagement_score'] >= 0


def assert_valid_analysis_result(analysis_result):
    """Assert that analysis result has required structure."""
    required_fields = ['sentiment_score', 'insights', 'summary', 'top_topics', 'source_breakdown']
    for field in required_fields:
        assert field in analysis_result, f"Missing required field: {field}"
    
    assert isinstance(analysis_result['sentiment_score'], (int, float))
    assert -1 <= analysis_result['sentiment_score'] <= 1
    assert isinstance(analysis_result['insights'], str)
    assert len(analysis_result['insights']) > 0