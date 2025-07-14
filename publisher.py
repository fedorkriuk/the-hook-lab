import tweepy
import logging
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import os
import re
# Environment variables are loaded via config.py

class TwitterPublisher:
    def __init__(self, config=None, daily_limit: int = 3):
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.daily_limit = daily_limit
        self.client = None
        self._setup_twitter_api()
        
        # Rate limiting
        self.last_post_time = 0
        self.min_post_interval = 300  # 5 minutes between posts
        
        # Content validation patterns
        self.bot_identifiers = [
            "🤖", "bot", "automated", "generated", "#bot", "[bot]"
        ]
        
    def _setup_twitter_api(self):
        """Initialize Twitter API client with v2."""
        try:
            # Twitter API v2 client
            self.client = tweepy.Client(
                bearer_token=os.getenv('TWITTER_BEARER_TOKEN'),
                consumer_key=os.getenv('TWITTER_CONSUMER_KEY'),
                consumer_secret=os.getenv('TWITTER_CONSUMER_SECRET'),
                access_token=os.getenv('TWITTER_ACCESS_TOKEN'),
                access_token_secret=os.getenv('TWITTER_ACCESS_TOKEN_SECRET'),
                wait_on_rate_limit=True
            )
            
            # Test authentication
            try:
                me = self.client.get_me()
                if me.data:
                    self.logger.info(f"Twitter API authenticated successfully for user: {me.data.username}")
                else:
                    self.logger.warning("Twitter API authentication succeeded but no user data returned")
            except Exception as e:
                self.logger.error(f"Twitter API authentication test failed: {e}")
                
        except Exception as e:
            self.logger.error(f"Error setting up Twitter API: {e}")
            self.client = None
    
    def _validate_tweet_content(self, content: str) -> Tuple[bool, str]:
        """Validate tweet content for compliance and quality."""
        issues = []
        
        # Check length
        if len(content) > 280:
            issues.append(f"Tweet too long: {len(content)} characters (max 280)")
        
        if len(content.strip()) == 0:
            issues.append("Empty tweet content")
        
        # Check for bot identification (required for automation compliance)
        has_bot_identifier = any(identifier.lower() in content.lower() 
                               for identifier in self.bot_identifiers)
        if not has_bot_identifier:
            issues.append("Missing bot identification")
        
        # Check for spam patterns
        if content.count('#') > 5:
            issues.append("Too many hashtags (max 5 recommended)")
        
        # Check for repeated characters (spam indicator)
        if re.search(r'(.)\1{4,}', content):
            issues.append("Contains repeated characters (potential spam)")
        
        # Check for excessive capitalization
        caps_ratio = sum(1 for c in content if c.isupper()) / len(content) if content else 0
        if caps_ratio > 0.3:
            issues.append("Excessive capitalization")
        
        # Check for inappropriate content patterns
        inappropriate_patterns = [
            r'\b(buy|sell|invest|money|crypto|bitcoin)\b.*\b(now|today|urgent)\b',
            r'\b(click|link|dm|message)\b.*\b(below|here|bio)\b',
            r'\b(free|prize|winner|giveaway)\b.*\b(claim|click|enter)\b'
        ]
        
        for pattern in inappropriate_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                issues.append("Contains potentially promotional/spam content")
                break
        
        is_valid = len(issues) == 0
        return is_valid, "; ".join(issues) if issues else "Content validated"
    
    def _check_daily_limit(self, database) -> Tuple[bool, int]:
        """Check if daily posting limit has been reached."""
        try:
            today_count = database.get_today_published_count("twitter")
            can_post = today_count < self.daily_limit
            remaining = max(0, self.daily_limit - today_count)
            
            return can_post, remaining
            
        except Exception as e:
            self.logger.error(f"Error checking daily limit: {e}")
            return False, 0
    
    def _check_rate_limit(self) -> Tuple[bool, int]:
        """Check if enough time has passed since last post."""
        current_time = time.time()
        time_since_last = current_time - self.last_post_time
        
        if time_since_last < self.min_post_interval:
            wait_time = int(self.min_post_interval - time_since_last)
            return False, wait_time
        
        return True, 0
    
    def post_tweet(self, content: str, database=None) -> Tuple[bool, str, Optional[str]]:
        """Post a single tweet with validation and compliance checks."""
        try:
            if not self.client:
                return False, "Twitter API not initialized", None
            
            # Validate content
            is_valid, validation_msg = self._validate_tweet_content(content)
            if not is_valid:
                self.logger.warning(f"Tweet validation failed: {validation_msg}")
                return False, f"Validation failed: {validation_msg}", None
            
            # Check daily limit
            if database:
                can_post, remaining = self._check_daily_limit(database)
                if not can_post:
                    return False, f"Daily limit reached ({self.daily_limit} tweets/day)", None
            
            # Check rate limiting
            can_post_now, wait_time = self._check_rate_limit()
            if not can_post_now:
                return False, f"Rate limited: wait {wait_time} seconds", None
            
            # Post the tweet
            response = self.client.create_tweet(text=content)
            
            if response.data:
                tweet_id = response.data['id']
                self.last_post_time = time.time()
                
                # Log to database if available
                if database:
                    database.insert_published_content(
                        platform="twitter",
                        content=content,
                        post_id=tweet_id,
                        success=True
                    )
                
                self.logger.info(f"Tweet posted successfully: {tweet_id}")
                return True, "Tweet posted successfully", tweet_id
            else:
                error_msg = "Tweet creation failed: no response data"
                self.logger.error(error_msg)
                
                if database:
                    database.insert_published_content(
                        platform="twitter",
                        content=content,
                        success=False,
                        error_message=error_msg
                    )
                
                return False, error_msg, None
                
        except tweepy.Forbidden as e:
            error_msg = f"Twitter API access forbidden: {e}"
            self.logger.error(error_msg)
            
            if database:
                database.insert_published_content(
                    platform="twitter",
                    content=content,
                    success=False,
                    error_message=error_msg
                )
            
            return False, error_msg, None
            
        except tweepy.TooManyRequests as e:
            error_msg = f"Twitter API rate limit exceeded: {e}"
            self.logger.error(error_msg)
            return False, error_msg, None
            
        except Exception as e:
            error_msg = f"Error posting tweet: {e}"
            self.logger.error(error_msg)
            
            if database:
                database.insert_published_content(
                    platform="twitter",
                    content=content,
                    success=False,
                    error_message=error_msg
                )
            
            return False, error_msg, None
    
    def post_thread(self, tweets: List[str], database=None) -> Tuple[bool, str, List[str]]:
        """Post a Twitter thread with proper threading."""
        try:
            if not self.client:
                return False, "Twitter API not initialized", []
            
            if not tweets:
                return False, "No tweets provided", []
            
            # Validate all tweets first
            for i, tweet in enumerate(tweets):
                is_valid, validation_msg = self._validate_tweet_content(tweet)
                if not is_valid:
                    return False, f"Tweet {i+1} validation failed: {validation_msg}", []
            
            # Check daily limit for entire thread
            if database:
                can_post, remaining = self._check_daily_limit(database)
                if remaining < len(tweets):
                    return False, f"Daily limit insufficient: need {len(tweets)}, have {remaining}", []
            
            posted_tweet_ids = []
            previous_tweet_id = None
            
            for i, tweet_content in enumerate(tweets):
                # Check rate limiting between tweets
                if i > 0:  # No need to wait for the first tweet
                    can_post_now, wait_time = self._check_rate_limit()
                    if not can_post_now:
                        self.logger.info(f"Waiting {wait_time} seconds before posting tweet {i+1}")
                        time.sleep(wait_time)
                
                try:
                    # Create tweet with reply to previous tweet (for threading)
                    if previous_tweet_id:
                        response = self.client.create_tweet(
                            text=tweet_content,
                            in_reply_to_tweet_id=previous_tweet_id
                        )
                    else:
                        response = self.client.create_tweet(text=tweet_content)
                    
                    if response.data:
                        tweet_id = response.data['id']
                        posted_tweet_ids.append(tweet_id)
                        previous_tweet_id = tweet_id
                        self.last_post_time = time.time()
                        
                        # Log to database
                        if database:
                            database.insert_published_content(
                                platform="twitter",
                                content=tweet_content,
                                post_id=tweet_id,
                                success=True
                            )
                        
                        self.logger.info(f"Thread tweet {i+1}/{len(tweets)} posted: {tweet_id}")
                        
                        # Brief pause between thread tweets (Twitter best practice)
                        if i < len(tweets) - 1:
                            time.sleep(2)
                    else:
                        error_msg = f"Failed to post tweet {i+1} in thread"
                        self.logger.error(error_msg)
                        
                        if database:
                            database.insert_published_content(
                                platform="twitter",
                                content=tweet_content,
                                success=False,
                                error_message=error_msg
                            )
                        
                        return False, error_msg, posted_tweet_ids
                        
                except Exception as e:
                    error_msg = f"Error posting tweet {i+1} in thread: {e}"
                    self.logger.error(error_msg)
                    
                    if database:
                        database.insert_published_content(
                            platform="twitter",
                            content=tweet_content,
                            success=False,
                            error_message=error_msg
                        )
                    
                    return False, error_msg, posted_tweet_ids
            
            success_msg = f"Thread posted successfully: {len(posted_tweet_ids)} tweets"
            self.logger.info(success_msg)
            return True, success_msg, posted_tweet_ids
            
        except Exception as e:
            error_msg = f"Error posting thread: {e}"
            self.logger.error(error_msg)
            return False, error_msg, []
    
    def ensure_bot_identification(self, content: str) -> str:
        """Ensure tweet content includes bot identification."""
        # Check if bot identifier already exists
        has_identifier = any(identifier.lower() in content.lower() 
                           for identifier in self.bot_identifiers)
        
        if not has_identifier:
            # Add bot identifier if there's space
            bot_tag = " 🤖"
            if len(content) + len(bot_tag) <= 280:
                content += bot_tag
            else:
                # Replace some content to make room for bot identifier
                available_space = 280 - len(bot_tag)
                content = content[:available_space-3] + "..." + bot_tag
        
        return content
    
    def get_posting_status(self, database=None) -> Dict[str, Any]:
        """Get current posting status and limits."""
        try:
            status = {
                'api_available': self.client is not None,
                'daily_limit': self.daily_limit,
                'min_interval_seconds': self.min_post_interval
            }
            
            if database:
                can_post, remaining = self._check_daily_limit(database)
                today_count = self.daily_limit - remaining
                
                status.update({
                    'can_post_today': can_post,
                    'posts_today': today_count,
                    'remaining_today': remaining
                })
            
            # Rate limiting status
            can_post_now, wait_time = self._check_rate_limit()
            status.update({
                'can_post_now': can_post_now,
                'wait_time_seconds': wait_time
            })
            
            return status
            
        except Exception as e:
            self.logger.error(f"Error getting posting status: {e}")
            return {'error': str(e)}
    
    def create_compliant_thread(self, analysis: Dict[str, Any]) -> List[str]:
        """Create a compliant Twitter thread from analysis data."""
        try:
            from analyzer import TrendAnalyzer
            analyzer = TrendAnalyzer()
            
            # Generate thread using analyzer
            thread = analyzer.create_twitter_thread(analysis)
            
            # Ensure each tweet has bot identification
            compliant_thread = []
            for tweet in thread:
                compliant_tweet = self.ensure_bot_identification(tweet)
                compliant_thread.append(compliant_tweet)
            
            return compliant_thread
            
        except Exception as e:
            self.logger.error(f"Error creating compliant thread: {e}")
            # Fallback to simple compliant tweet
            fallback_tweet = "🔍 Tech trends analysis in progress. Stay tuned for updates! #TechTrends #AI 🤖"
            return [fallback_tweet]
    
    def schedule_post(self, content: str, delay_minutes: int = 0) -> bool:
        """Schedule a post for later (simple delay-based scheduling)."""
        try:
            if delay_minutes > 0:
                self.logger.info(f"Scheduling tweet for {delay_minutes} minutes from now")
                time.sleep(delay_minutes * 60)
            
            success, message, tweet_id = self.post_tweet(content)
            return success
            
        except Exception as e:
            self.logger.error(f"Error in scheduled post: {e}")
            return False
    
    def get_recent_tweets(self, count: int = 10) -> List[Dict]:
        """Get recent tweets from the authenticated user."""
        try:
            if not self.client:
                return []
            
            # Get authenticated user info
            me = self.client.get_me()
            if not me.data:
                return []
            
            user_id = me.data.id
            
            # Get recent tweets
            tweets = self.client.get_users_tweets(
                id=user_id,
                max_results=min(count, 100),  # API limit
                tweet_fields=['created_at', 'public_metrics', 'text']
            )
            
            if tweets.data:
                recent_tweets = []
                for tweet in tweets.data:
                    recent_tweets.append({
                        'id': tweet.id,
                        'text': tweet.text,
                        'created_at': tweet.created_at.isoformat() if tweet.created_at else None,
                        'metrics': tweet.public_metrics
                    })
                return recent_tweets
            
            return []
            
        except Exception as e:
            self.logger.error(f"Error getting recent tweets: {e}")
            return []