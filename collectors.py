import tweepy
import requests
import praw
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FutureTimeoutError
import signal
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import get_logger, RetryConfig
from utils import RetryWithBackoff, PerformanceMonitor

class DataCollector:
    """Enhanced data collector with comprehensive error handling and retry logic."""
    
    def __init__(self, config=None):
        self.config = config
        self.logger = get_logger('collector')
        self.retry_config = RetryConfig(config) if config else None
        
        # Initialize API clients with error handling
        self.api_status = {
            'twitter': {'available': False, 'last_error': None, 'error_count': 0},
            'github': {'available': False, 'last_error': None, 'error_count': 0},
            'reddit': {'available': False, 'last_error': None, 'error_count': 0},
            'hackernews': {'available': False, 'last_error': None, 'error_count': 0}
        }
        
        # Rate limiting with enhanced tracking
        self.last_request_times = {
            'twitter': 0,
            'github': 0,
            'reddit': 0,
            'hackernews': 0
        }
        
        # Configuration-driven intervals
        self.min_request_intervals = {
            'twitter': config.get('twitter_interval', 1) if config else 1,
            'github': config.get('github_interval', 0.5) if config else 0.5,
            'reddit': config.get('reddit_interval', 2) if config else 2,
            'hackernews': config.get('hackernews_interval', 1) if config else 1
        }
        
        # Collection limits
        self.collection_limits = {
            'twitter': config.get('collection_limits', {}).get('twitter', 50) if config else 50,
            'github': config.get('collection_limits', {}).get('github', 30) if config else 30,
            'reddit': config.get('collection_limits', {}).get('reddit', 30) if config else 30,
            'hackernews': config.get('collection_limits', {}).get('hackernews', 20) if config else 20
        }
        
        # Setup timeout for collection operations
        self.collection_timeout = config.get('collection_timeout', 300) if config else 300  # 5 minutes
        
        # Initialize APIs
        self._setup_apis()
        
        # Setup requests session with retry strategy
        self._setup_requests_session()
        
        self.logger.info("DataCollector initialized with enhanced error handling")
    
    def _setup_apis(self):
        """Initialize API clients with comprehensive error handling."""
        self.logger.info("Initializing API clients...")
        
        # Twitter API setup
        self._setup_twitter_api()
        
        # Reddit API setup
        self._setup_reddit_api()
        
        # GitHub API setup
        self._setup_github_api()
        
        # Log API availability summary
        available_apis = [api for api, status in self.api_status.items() if status['available']]
        self.logger.info(f"APIs initialized. Available: {available_apis}")
        
        if not available_apis:
            self.logger.warning("No APIs are available - collection will be limited")
    
    def _setup_twitter_api(self):
        """Setup Twitter API with error handling."""
        try:
            required_vars = [
                'TWITTER_BEARER_TOKEN', 'TWITTER_CONSUMER_KEY', 'TWITTER_CONSUMER_SECRET',
                'TWITTER_ACCESS_TOKEN', 'TWITTER_ACCESS_TOKEN_SECRET'
            ]
            
            missing_vars = [var for var in required_vars if not os.getenv(var)]
            if missing_vars:
                raise EnvironmentError(f"Missing Twitter API variables: {missing_vars}")
            
            self.twitter_client = tweepy.Client(
                bearer_token=os.getenv('TWITTER_BEARER_TOKEN'),
                consumer_key=os.getenv('TWITTER_CONSUMER_KEY'),
                consumer_secret=os.getenv('TWITTER_CONSUMER_SECRET'),
                access_token=os.getenv('TWITTER_ACCESS_TOKEN'),
                access_token_secret=os.getenv('TWITTER_ACCESS_TOKEN_SECRET'),
                wait_on_rate_limit=True
            )
            
            # Test API connection
            try:
                me = self.twitter_client.get_me()
                if me.data:
                    self.api_status['twitter']['available'] = True
                    self.logger.info(f"Twitter API connected as: {me.data.username}")
                else:
                    raise Exception("No user data returned")
            except Exception as test_error:
                self.logger.warning(f"Twitter API test failed: {test_error}")
                self.api_status['twitter']['last_error'] = str(test_error)
                
        except Exception as e:
            self.logger.error(f"Twitter API setup failed: {e}")
            self.api_status['twitter']['last_error'] = str(e)
            self.twitter_client = None
    
    def _setup_reddit_api(self):
        """Setup Reddit API with error handling."""
        try:
            required_vars = ['REDDIT_CLIENT_ID', 'REDDIT_CLIENT_SECRET']
            missing_vars = [var for var in required_vars if not os.getenv(var)]
            
            if missing_vars:
                self.logger.warning(f"Reddit API variables missing: {missing_vars} - Reddit collection will be skipped")
                return
            
            self.reddit = praw.Reddit(
                client_id=os.getenv('REDDIT_CLIENT_ID'),
                client_secret=os.getenv('REDDIT_CLIENT_SECRET'),
                user_agent=os.getenv('REDDIT_USER_AGENT', 'TrendBot/1.0')
            )
            
            # Test Reddit API
            try:
                # Try to access a public subreddit
                test_sub = self.reddit.subreddit('test')
                test_post = next(test_sub.hot(limit=1))
                if test_post:
                    self.api_status['reddit']['available'] = True
                    self.logger.info("Reddit API connected successfully")
            except Exception as test_error:
                self.logger.warning(f"Reddit API test failed: {test_error}")
                self.api_status['reddit']['last_error'] = str(test_error)
                
        except Exception as e:
            self.logger.error(f"Reddit API setup failed: {e}")
            self.api_status['reddit']['last_error'] = str(e)
            self.reddit = None
    
    def _setup_github_api(self):
        """Setup GitHub API with error handling."""
        try:
            self.github_token = os.getenv('GITHUB_TOKEN')
            
            if not self.github_token:
                self.logger.warning("GitHub token not provided - using unauthenticated requests (lower rate limits)")
            
            # Test GitHub API
            headers = {
                'Accept': 'application/vnd.github.v3+json',
                'User-Agent': 'TrendBot/1.0'
            }
            
            if self.github_token:
                headers['Authorization'] = f'token {self.github_token}'
            
            response = requests.get('https://api.github.com/rate_limit', headers=headers, timeout=10)
            
            if response.status_code == 200:
                rate_limit_info = response.json()
                remaining = rate_limit_info.get('rate', {}).get('remaining', 0)
                self.api_status['github']['available'] = True
                self.logger.info(f"GitHub API connected. Rate limit remaining: {remaining}")
            else:
                raise Exception(f"GitHub API test failed: {response.status_code}")
                
        except Exception as e:
            self.logger.error(f"GitHub API setup failed: {e}")
            self.api_status['github']['last_error'] = str(e)
    
    def _setup_requests_session(self):
        """Setup requests session with retry strategy."""
        self.session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Set default timeout
        self.session.timeout = (10, 30)  # (connection timeout, read timeout)
    
    def _rate_limit_check(self, source: str):
        """Enhanced rate limiting with logging and adaptive delays."""
        current_time = time.time()
        last_request = self.last_request_times.get(source, 0)
        min_interval = self.min_request_intervals.get(source, 1)
        
        time_since_last = current_time - last_request
        if time_since_last < min_interval:
            sleep_time = min_interval - time_since_last
            
            # Add adaptive delay if there have been recent errors
            error_count = self.api_status.get(source, {}).get('error_count', 0)
            if error_count > 0:
                adaptive_delay = min(error_count * 0.5, 5.0)  # Max 5 seconds additional delay
                sleep_time += adaptive_delay
                self.logger.debug(f"Rate limiting {source}: {sleep_time:.2f}s (adaptive: {adaptive_delay:.2f}s)")
            else:
                self.logger.debug(f"Rate limiting {source}: {sleep_time:.2f}s")
            
            time.sleep(sleep_time)
        
        self.last_request_times[source] = time.time()
    
    @RetryWithBackoff(max_attempts=3, base_delay=2.0, exceptions=(tweepy.TooManyRequests, tweepy.Unauthorized, Exception))
    def collect_twitter_trends(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Collect trending topics and tweets from Twitter."""
        trends = []
        
        try:
            self._rate_limit_check('twitter')
            
            # Get trending topics (requires location, using worldwide - WOEID 1)
            try:
                # Note: Twitter API v2 doesn't have trends endpoint in basic access
                # Using search for popular tech-related terms instead
                search_terms = [
                    "#AI", "#TechNews", "#Programming", "#Development", 
                    "#OpenSource", "#WebDev", "#DataScience", "#MachineLearning"
                ]
                
                for term in search_terms[:5]:  # Limit to avoid rate limits
                    self._rate_limit_check('twitter')
                    
                    tweets = self.twitter_client.search_recent_tweets(
                        query=f"{term} -is:retweet lang:en",
                        max_results=10,
                        tweet_fields=['created_at', 'public_metrics', 'author_id', 'text']
                    )
                    
                    if tweets.data:
                        for tweet in tweets.data:
                            engagement_score = (
                                tweet.public_metrics['like_count'] +
                                tweet.public_metrics['retweet_count'] * 2 +
                                tweet.public_metrics['reply_count']
                            )
                            
                            trends.append({
                                'source': 'twitter',
                                'topic': term,
                                'content': tweet.text,
                                'url': f"https://twitter.com/user/status/{tweet.id}",
                                'engagement_score': engagement_score,
                                'metadata': {
                                    'tweet_id': tweet.id,
                                    'author_id': str(tweet.author_id),
                                    'created_at': tweet.created_at.isoformat() if tweet.created_at else None,
                                    'metrics': tweet.public_metrics
                                }
                            })
                
            except Exception as e:
                self.logger.warning(f"Could not get Twitter trends: {e}")
                
        except Exception as e:
            self.logger.error(f"Error collecting Twitter trends: {e}")
        
        self.logger.info(f"Collected {len(trends)} Twitter trends")
        return trends
    
    @RetryWithBackoff(max_attempts=3, base_delay=1.5, exceptions=(requests.RequestException, requests.HTTPError))
    def collect_github_trends(self, limit: int = 30) -> List[Dict[str, Any]]:
        """Collect trending repositories from GitHub with enhanced error handling."""
        trends = []
        operation_id = f"github_{int(datetime.now().timestamp())}"
        
        try:
            self.logger.debug(f"[{operation_id}] Starting GitHub trends collection (limit: {limit})")
            self._rate_limit_check('github')
            
            headers = {
                'Accept': 'application/vnd.github.v3+json',
                'User-Agent': 'TrendBot/1.0'
            }
            
            if self.github_token:
                headers['Authorization'] = f'token {self.github_token}'
            
            # Try multiple search strategies
            search_strategies = [
                self._get_today_trending_repos,
                self._get_weekly_trending_repos,
                self._get_popular_recent_repos
            ]
            
            for strategy_idx, strategy in enumerate(search_strategies):
                try:
                    self.logger.debug(f"[{operation_id}] Trying GitHub strategy {strategy_idx + 1}")
                    strategy_trends = strategy(headers, limit)
                    if strategy_trends:
                        trends.extend(strategy_trends)
                        break
                except Exception as e:
                    self.logger.warning(f"[{operation_id}] GitHub strategy {strategy_idx + 1} failed: {e}")
                    if strategy_idx == len(search_strategies) - 1:  # Last strategy
                        raise
                    continue
            
            # Remove duplicates by repository ID
            seen_repos = set()
            unique_trends = []
            for trend in trends:
                repo_id = trend.get('metadata', {}).get('repo_id')
                if repo_id and repo_id not in seen_repos:
                    seen_repos.add(repo_id)
                    unique_trends.append(trend)
            
            final_trends = unique_trends[:limit]
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"[{operation_id}] GitHub API request error: {e}")
            self._update_api_status('github', False, str(e))
            return []
        except Exception as e:
            self.logger.error(f"[{operation_id}] Error collecting GitHub trends: {e}", exc_info=True)
            self._update_api_status('github', False, str(e))
            return []
        
        self.logger.info(f"[{operation_id}] Collected {len(final_trends)} GitHub trends")
        return final_trends
    
    def _get_today_trending_repos(self, headers: dict, limit: int) -> List[Dict]:
        """Get repositories created today, sorted by stars."""
        today = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        url = f"https://api.github.com/search/repositories?q=created:>{today}&sort=stars&order=desc&per_page={min(limit, 100)}"
        
        response = self.session.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        return self._parse_github_response(response.json())
    
    def _get_weekly_trending_repos(self, headers: dict, limit: int) -> List[Dict]:
        """Get repositories from the past week, sorted by stars."""
        week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        url = f"https://api.github.com/search/repositories?q=created:>{week_ago}&sort=stars&order=desc&per_page={min(limit, 100)}"
        
        response = self.session.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        return self._parse_github_response(response.json())
    
    def _get_popular_recent_repos(self, headers: dict, limit: int) -> List[Dict]:
        """Get recently updated popular repositories."""
        week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        url = f"https://api.github.com/search/repositories?q=pushed:>{week_ago}&sort=stars&order=desc&per_page={min(limit, 100)}"
        
        response = self.session.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        return self._parse_github_response(response.json())
    
    def _parse_github_response(self, data: dict) -> List[Dict]:
        """Parse GitHub API response into trend format."""
        trends = []
        
        for repo in data.get('items', []):
            try:
                engagement_score = repo['stargazers_count'] + repo['forks_count'] * 2
                
                trends.append({
                    'source': 'github',
                    'topic': repo['name'],
                    'content': repo['description'] or f"Repository: {repo['full_name']}",
                    'url': repo['html_url'],
                    'engagement_score': engagement_score,
                    'metadata': {
                        'repo_id': repo['id'],
                        'full_name': repo['full_name'],
                        'language': repo.get('language'),
                        'stars': repo['stargazers_count'],
                        'forks': repo['forks_count'],
                        'created_at': repo.get('created_at'),
                        'updated_at': repo.get('updated_at'),
                        'topics': repo.get('topics', [])
                    }
                })
            except Exception as e:
                self.logger.debug(f"Failed to parse GitHub repo: {e}")
                continue
        
        return trends
    
    @RetryWithBackoff(max_attempts=2, base_delay=3.0, exceptions=(Exception,))
    def collect_reddit_trends(self, limit: int = 30) -> List[Dict[str, Any]]:
        """Collect trending posts from relevant subreddits with enhanced error handling."""
        trends = []
        operation_id = f"reddit_{int(datetime.now().timestamp())}"
        
        try:
            self.logger.debug(f"[{operation_id}] Starting Reddit trends collection (limit: {limit})")
            
            if not self.reddit:
                self.logger.warning(f"[{operation_id}] Reddit client not available")
                return []
            
            # Diverse subreddit list with fallbacks
            primary_subreddits = [
                'programming', 'technology', 'MachineLearning', 
                'artificial', 'webdev', 'datascience'
            ]
            
            fallback_subreddits = [
                'Python', 'javascript', 'reactjs', 'opensource',
                'compsci', 'ArtificialIntelligence'
            ]
            
            posts_per_subreddit = max(1, limit // len(primary_subreddits))
            collected_count = 0
            
            # Try primary subreddits first
            for subreddit_name in primary_subreddits:
                if collected_count >= limit:
                    break
                    
                try:
                    self._rate_limit_check('reddit')
                    
                    sub_trends = self._collect_from_subreddit(
                        subreddit_name, 
                        posts_per_subreddit, 
                        operation_id
                    )
                    
                    trends.extend(sub_trends)
                    collected_count += len(sub_trends)
                    
                except Exception as e:
                    self.logger.warning(f"[{operation_id}] Error collecting from r/{subreddit_name}: {e}")
                    continue
            
            # Use fallback subreddits if we didn't get enough
            if collected_count < limit // 2:
                self.logger.info(f"[{operation_id}] Using fallback subreddits (collected: {collected_count})")
                
                for subreddit_name in fallback_subreddits:
                    if collected_count >= limit:
                        break
                        
                    try:
                        self._rate_limit_check('reddit')
                        
                        sub_trends = self._collect_from_subreddit(
                            subreddit_name, 
                            min(3, limit - collected_count), 
                            operation_id
                        )
                        
                        trends.extend(sub_trends)
                        collected_count += len(sub_trends)
                        
                    except Exception as e:
                        self.logger.debug(f"[{operation_id}] Fallback subreddit r/{subreddit_name} failed: {e}")
                        continue
            
        except Exception as e:
            self.logger.error(f"[{operation_id}] Error collecting Reddit trends: {e}", exc_info=True)
            self._update_api_status('reddit', False, str(e))
            return []
        
        self.logger.info(f"[{operation_id}] Collected {len(trends)} Reddit trends")
        return trends
    
    def _collect_from_subreddit(self, subreddit_name: str, post_limit: int, operation_id: str) -> List[Dict]:
        """Collect trends from a specific subreddit."""
        trends = []
        
        try:
            subreddit = self.reddit.subreddit(subreddit_name)
            
            # Try multiple sorting methods
            sorting_methods = ['hot', 'top']
            
            for sort_method in sorting_methods:
                try:
                    if sort_method == 'hot':
                        posts = subreddit.hot(limit=post_limit * 2)  # Get more to filter
                    else:
                        posts = subreddit.top('day', limit=post_limit * 2)
                    
                    post_count = 0
                    for post in posts:
                        if post_count >= post_limit:
                            break
                            
                        if self._is_valid_reddit_post(post):
                            trend = self._parse_reddit_post(post, subreddit_name)
                            if trend:
                                trends.append(trend)
                                post_count += 1
                    
                    if trends:  # If we got posts, don't try other sorting methods
                        break
                        
                except Exception as e:
                    self.logger.debug(f"[{operation_id}] r/{subreddit_name} {sort_method} failed: {e}")
                    continue
            
        except Exception as e:
            self.logger.warning(f"[{operation_id}] Failed to access r/{subreddit_name}: {e}")
            raise
        
        return trends
    
    def _is_valid_reddit_post(self, post) -> bool:
        """Check if Reddit post is valid for collection."""
        try:
            # Skip stickied posts, deleted posts, and very low engagement
            if (post.stickied or 
                not post.title or 
                post.score < 10 or 
                str(post.author) in ['[deleted]', None]):
                return False
            
            # Skip posts that are too old (more than 7 days)
            post_age_days = (datetime.now().timestamp() - post.created_utc) / (24 * 3600)
            if post_age_days > 7:
                return False
            
            return True
            
        except Exception:
            return False
    
    def _parse_reddit_post(self, post, subreddit_name: str) -> Optional[Dict]:
        """Parse Reddit post into trend format."""
        try:
            engagement_score = post.score + post.num_comments * 2
            
            # Create content combining title and text
            content = post.title
            if hasattr(post, 'selftext') and post.selftext:
                content += f"\n{post.selftext[:200]}..."
            
            return {
                'source': 'reddit',
                'topic': f"r/{subreddit_name}",
                'content': content,
                'url': f"https://reddit.com{post.permalink}",
                'engagement_score': engagement_score,
                'metadata': {
                    'post_id': post.id,
                    'subreddit': subreddit_name,
                    'author': str(post.author) if post.author else '[deleted]',
                    'score': post.score,
                    'num_comments': post.num_comments,
                    'created_utc': post.created_utc,
                    'upvote_ratio': getattr(post, 'upvote_ratio', None),
                    'post_flair': getattr(post, 'link_flair_text', None)
                }
            }
            
        except Exception as e:
            self.logger.debug(f"Failed to parse Reddit post: {e}")
            return None
    
    @RetryWithBackoff(max_attempts=3, base_delay=1.0, exceptions=(requests.RequestException,))
    def collect_hackernews_trends(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Collect trending stories from Hacker News with enhanced error handling."""
        trends = []
        operation_id = f"hn_{int(datetime.now().timestamp())}"
        
        try:
            self.logger.debug(f"[{operation_id}] Starting Hacker News trends collection (limit: {limit})")
            self._rate_limit_check('hackernews')
            
            # Try multiple HN endpoints
            endpoints = [
                ('top', 'https://hacker-news.firebaseio.com/v0/topstories.json'),
                ('best', 'https://hacker-news.firebaseio.com/v0/beststories.json'),
                ('new', 'https://hacker-news.firebaseio.com/v0/newstories.json')
            ]
            
            for endpoint_name, endpoint_url in endpoints:
                try:
                    self.logger.debug(f"[{operation_id}] Trying HN {endpoint_name} endpoint")
                    
                    response = self.session.get(endpoint_url, timeout=15)
                    response.raise_for_status()
                    
                    story_ids = response.json()[:limit * 2]  # Get more IDs to account for failures
                    
                    if story_ids:
                        endpoint_trends = self._collect_hn_stories(story_ids[:limit], operation_id)
                        trends.extend(endpoint_trends)
                        
                        if len(trends) >= limit:
                            trends = trends[:limit]
                            break
                    
                except Exception as e:
                    self.logger.warning(f"[{operation_id}] HN {endpoint_name} endpoint failed: {e}")
                    continue
            
            if not trends:
                raise Exception("All HackerNews endpoints failed")
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"[{operation_id}] HackerNews API request error: {e}")
            return []
        except Exception as e:
            self.logger.error(f"[{operation_id}] Error collecting Hacker News trends: {e}", exc_info=True)
            return []
        
        self.logger.info(f"[{operation_id}] Collected {len(trends)} Hacker News trends")
        return trends
    
    def _collect_hn_stories(self, story_ids: List[int], operation_id: str) -> List[Dict]:
        """Collect individual HN stories with concurrent processing."""
        trends = []
        
        # Process stories concurrently but with rate limiting
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_to_id = {
                executor.submit(self._fetch_hn_story, story_id, operation_id): story_id 
                for story_id in story_ids
            }
            
            for future in as_completed(future_to_id, timeout=60):
                story_id = future_to_id[future]
                try:
                    story_trend = future.result()
                    if story_trend:
                        trends.append(story_trend)
                except Exception as e:
                    self.logger.debug(f"[{operation_id}] Failed to fetch HN story {story_id}: {e}")
                    continue
        
        return trends
    
    def _fetch_hn_story(self, story_id: int, operation_id: str) -> Optional[Dict]:
        """Fetch individual HN story with rate limiting."""
        try:
            self._rate_limit_check('hackernews')
            
            story_response = self.session.get(
                f'https://hacker-news.firebaseio.com/v0/item/{story_id}.json',
                timeout=10
            )
            story_response.raise_for_status()
            
            story = story_response.json()
            
            if not story or story.get('type') != 'story':
                return None
            
            # Filter out deleted or invalid stories
            if not story.get('title') or story.get('deleted', False):
                return None
            
            engagement_score = story.get('score', 0) + story.get('descendants', 0) * 2
            
            # Filter low-engagement stories
            if engagement_score < 5:
                return None
            
            return {
                'source': 'hackernews',
                'topic': 'Hacker News',
                'content': story.get('title', ''),
                'url': story.get('url', f"https://news.ycombinator.com/item?id={story_id}"),
                'engagement_score': engagement_score,
                'metadata': {
                    'story_id': story_id,
                    'author': story.get('by', ''),
                    'score': story.get('score', 0),
                    'comments': story.get('descendants', 0),
                    'time': story.get('time', 0),
                    'story_type': story.get('type', ''),
                    'hn_url': f"https://news.ycombinator.com/item?id={story_id}"
                }
            }
            
        except Exception as e:
            self.logger.debug(f"[{operation_id}] Error fetching HN story {story_id}: {e}")
            return None
    
    def _update_api_status(self, api_name: str, available: bool, error: str = None):
        """Update API status tracking."""
        if api_name in self.api_status:
            self.api_status[api_name]['available'] = available
            if error:
                self.api_status[api_name]['last_error'] = error
                self.api_status[api_name]['error_count'] += 1
    
    def collect_all_trends(self) -> List[Dict[str, Any]]:
        """Collect trends from all sources with enhanced error handling and concurrent processing."""
        with PerformanceMonitor("collect_all_trends"):
            all_trends = []
            collection_results = {}
            
            self.logger.info("Starting comprehensive trend collection...")
            
            # Define collection tasks
            collection_tasks = []
            
            if self.api_status['twitter']['available']:
                collection_tasks.append(('Twitter', self._collect_twitter_safe))
            
            if self.api_status['github']['available']:
                collection_tasks.append(('GitHub', self._collect_github_safe))
                
            if self.api_status['reddit']['available']:
                collection_tasks.append(('Reddit', self._collect_reddit_safe))
            
            # HackerNews doesn't require authentication
            collection_tasks.append(('HackerNews', self._collect_hackernews_safe))
            
            if not collection_tasks:
                self.logger.error("No available APIs for data collection")
                return []
            
            # Collect with concurrent processing and timeout
            try:
                with ThreadPoolExecutor(max_workers=4) as executor:
                    # Submit all tasks
                    future_to_source = {
                        executor.submit(self._collect_with_timeout, source_name, collect_func): source_name
                        for source_name, collect_func in collection_tasks
                    }
                    
                    # Collect results with overall timeout
                    for future in as_completed(future_to_source, timeout=self.collection_timeout):
                        source_name = future_to_source[future]
                        try:
                            trends = future.result()
                            if trends:
                                all_trends.extend(trends)
                                collection_results[source_name] = {
                                    'success': True,
                                    'count': len(trends)
                                }
                                self.logger.info(f"Collected {len(trends)} trends from {source_name}")
                            else:
                                collection_results[source_name] = {
                                    'success': True,
                                    'count': 0,
                                    'message': 'No trends found'
                                }
                                self.logger.warning(f"No trends collected from {source_name}")
                                
                        except Exception as e:
                            collection_results[source_name] = {
                                'success': False,
                                'error': str(e)
                            }
                            self.api_status[source_name.lower()]['error_count'] += 1
                            self.logger.error(f"Failed to collect from {source_name}: {e}", exc_info=True)
                            
            except FutureTimeoutError:
                self.logger.error(f"Collection timed out after {self.collection_timeout}s")
                # Cancel remaining futures
                for future in future_to_source:
                    future.cancel()
            
            # Post-process and validate collected trends
            validated_trends = self._validate_and_clean_trends(all_trends)
            
            # Sort by engagement score
            validated_trends.sort(key=lambda x: x.get('engagement_score', 0), reverse=True)
            
            # Log collection summary
            self._log_collection_summary(collection_results, len(validated_trends))
            
            return validated_trends
    
    def _collect_with_timeout(self, source_name: str, collect_func) -> List[Dict]:
        """Collect from a single source with timeout protection."""
        try:
            # Individual source timeout (shorter than overall timeout)
            source_timeout = min(60, self.collection_timeout // len(self.collection_tasks) if hasattr(self, 'collection_tasks') else 60)
            
            def timeout_handler(signum, frame):
                raise TimeoutError(f"{source_name} collection timed out")
            
            # Set up timeout for this collection
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(source_timeout)
            
            try:
                result = collect_func()
                signal.alarm(0)  # Cancel alarm
                return result
            finally:
                signal.signal(signal.SIGALRM, old_handler)
                
        except Exception as e:
            self.logger.error(f"Error in {source_name} collection with timeout: {e}")
            return []
    
    def _collect_twitter_safe(self) -> List[Dict]:
        """Safe wrapper for Twitter collection."""
        try:
            return self.collect_twitter_trends(self.collection_limits['twitter'])
        except Exception as e:
            self.logger.error(f"Twitter collection failed: {e}")
            return []
    
    def _collect_github_safe(self) -> List[Dict]:
        """Safe wrapper for GitHub collection."""
        try:
            return self.collect_github_trends(self.collection_limits['github'])
        except Exception as e:
            self.logger.error(f"GitHub collection failed: {e}")
            return []
    
    def _collect_reddit_safe(self) -> List[Dict]:
        """Safe wrapper for Reddit collection."""
        try:
            return self.collect_reddit_trends(self.collection_limits['reddit'])
        except Exception as e:
            self.logger.error(f"Reddit collection failed: {e}")
            return []
    
    def _collect_hackernews_safe(self) -> List[Dict]:
        """Safe wrapper for HackerNews collection."""
        try:
            return self.collect_hackernews_trends(self.collection_limits['hackernews'])
        except Exception as e:
            self.logger.error(f"HackerNews collection failed: {e}")
            return []
    
    def _validate_and_clean_trends(self, trends: List[Dict]) -> List[Dict]:
        """Validate and clean collected trends data."""
        validated_trends = []
        
        for trend in trends:
            try:
                # Required fields validation
                if not trend.get('source') or not trend.get('topic'):
                    continue
                
                # Clean and validate content
                cleaned_trend = {
                    'source': str(trend['source']).strip(),
                    'topic': str(trend['topic']).strip()[:200],  # Limit topic length
                    'content': str(trend.get('content', ''))[:1000] if trend.get('content') else '',  # Limit content
                    'url': str(trend.get('url', ''))[:500] if trend.get('url') else '',  # Limit URL length
                    'engagement_score': max(0, float(trend.get('engagement_score', 0))),  # Ensure non-negative
                    'metadata': trend.get('metadata', {}),
                    'collection_time': datetime.now().isoformat()
                }
                
                # Additional validation
                if len(cleaned_trend['topic']) >= 2:  # Minimum topic length
                    validated_trends.append(cleaned_trend)
                    
            except Exception as e:
                self.logger.debug(f"Failed to validate trend: {e}")
                continue
        
        self.logger.info(f"Validated {len(validated_trends)}/{len(trends)} collected trends")
        return validated_trends
    
    def _log_collection_summary(self, results: Dict, final_count: int):
        """Log detailed collection summary."""
        successful_sources = [source for source, result in results.items() if result.get('success')]
        failed_sources = [source for source, result in results.items() if not result.get('success')]
        
        self.logger.info(f"Collection completed. Final count: {final_count}")
        
        if successful_sources:
            self.logger.info(f"Successful sources: {successful_sources}")
            
        if failed_sources:
            self.logger.warning(f"Failed sources: {failed_sources}")
            for source in failed_sources:
                error = results[source].get('error', 'Unknown error')
                self.logger.warning(f"  {source}: {error}")
        
        # Log source-wise breakdown
        for source, result in results.items():
            if result.get('success'):
                count = result.get('count', 0)
                self.logger.debug(f"  {source}: {count} trends")
    
    def get_api_status(self) -> Dict[str, Any]:
        """Get current API status for monitoring."""
        return {
            'timestamp': datetime.now().isoformat(),
            'apis': self.api_status.copy(),
            'collection_limits': self.collection_limits.copy(),
            'last_request_times': self.last_request_times.copy()
        }
    
    def filter_trends_by_keywords(self, trends: List[Dict], keywords: List[str]) -> List[Dict]:
        """Filter trends by specific keywords."""
        if not keywords:
            return trends
        
        filtered_trends = []
        keywords_lower = [kw.lower() for kw in keywords]
        
        for trend in trends:
            content_lower = (trend.get('content', '') + ' ' + trend.get('topic', '')).lower()
            
            if any(keyword in content_lower for keyword in keywords_lower):
                filtered_trends.append(trend)
        
        self.logger.info(f"Filtered {len(filtered_trends)} trends matching keywords: {keywords}")
        return filtered_trends
    
    def get_content_summary(self, trends: List[Dict], max_trends: int = 50) -> str:
        """Get a summary of collected trends for analysis."""
        if not trends:
            return "No trends collected."
        
        summary_parts = []
        trends_by_source = {}
        
        # Group trends by source
        for trend in trends[:max_trends]:
            source = trend['source']
            if source not in trends_by_source:
                trends_by_source[source] = []
            trends_by_source[source].append(trend)
        
        # Create summary
        for source, source_trends in trends_by_source.items():
            summary_parts.append(f"\n{source.upper()} ({len(source_trends)} items):")
            for i, trend in enumerate(source_trends[:10], 1):  # Top 10 per source
                summary_parts.append(f"{i}. {trend['topic']}: {trend['content'][:100]}...")
        
        return '\n'.join(summary_parts)