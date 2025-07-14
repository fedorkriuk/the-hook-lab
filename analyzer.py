import openai
import logging
import re
import json
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import os
# Environment variables are loaded via config.py

class TrendAnalyzer:
    def __init__(self, config=None):
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.max_tokens = 2000
        self.temperature = 0.7
        
        # Content moderation patterns
        self.pii_patterns = [
            r'\b[\w._%+-]+@[\w.-]+\.[A-Z|a-z]{2,}\b',  # Email
            r'\b\d{3}-\d{2}-\d{4}\b',  # SSN
            r'\b\d{3}-\d{3}-\d{4}\b',  # Phone
            r'\b\d{16}\b',  # Credit card (basic)
        ]
        
        self.inappropriate_keywords = [
            'password', 'secret', 'token', 'api_key', 'private_key',
            'confidential', 'classified', 'restricted'
        ]
    
    def moderate_content(self, content: str) -> Tuple[bool, str]:
        """Check content for PII and inappropriate material."""
        issues = []
        
        # Check for PII patterns
        for pattern in self.pii_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                issues.append("Contains potential PII")
                break
        
        # Check for inappropriate keywords
        content_lower = content.lower()
        for keyword in self.inappropriate_keywords:
            if keyword in content_lower:
                issues.append(f"Contains sensitive keyword: {keyword}")
        
        # Check content length
        if len(content) > 10000:
            issues.append("Content too long")
        
        is_safe = len(issues) == 0
        return is_safe, "; ".join(issues) if issues else "Content approved"
    
    def analyze_sentiment(self, content: str) -> float:
        """Analyze sentiment of content using OpenAI."""
        try:
            # First check content safety
            is_safe, moderation_msg = self.moderate_content(content)
            if not is_safe:
                self.logger.warning(f"Content moderation failed: {moderation_msg}")
                return 0.0
            
            prompt = f"""
            Analyze the sentiment of the following text and return a sentiment score between -1 (very negative) and 1 (very positive), where 0 is neutral.
            
            Consider:
            - Overall tone and emotion
            - Context and implications
            - Technical vs emotional content
            
            Text: {content[:1000]}
            
            Return only a decimal number between -1 and 1.
            """
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=10,
                temperature=0.3
            )
            
            sentiment_text = response.choices[0].message.content.strip()
            
            # Extract numeric value
            try:
                sentiment_score = float(sentiment_text)
                # Clamp to valid range
                sentiment_score = max(-1.0, min(1.0, sentiment_score))
                return sentiment_score
            except ValueError:
                self.logger.warning(f"Could not parse sentiment score: {sentiment_text}")
                return 0.0
                
        except Exception as e:
            self.logger.error(f"Error analyzing sentiment: {e}")
            return 0.0
    
    def generate_insights(self, trends_data: List[Dict]) -> str:
        """Generate insights from trend data using OpenAI."""
        try:
            if not trends_data:
                return "No trend data available for analysis."
            
            # Prepare data summary
            summary = self._prepare_trends_summary(trends_data)
            
            # Check content safety
            is_safe, moderation_msg = self.moderate_content(summary)
            if not is_safe:
                self.logger.warning(f"Trends summary moderation failed: {moderation_msg}")
                return "Unable to analyze trends due to content safety concerns."
            
            prompt = f"""
            Analyze the following technology trends data and provide insights:

            {summary}

            Please provide:
            1. Top 3 emerging themes or patterns
            2. Notable technologies or topics gaining traction
            3. Sentiment overview (positive/negative/neutral trends)
            4. Potential implications for developers and tech community
            5. Recommendations for further monitoring

            Keep the analysis professional, factual, and suitable for a tech-focused audience.
            Limit response to 300 words.
            """
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )
            
            insights = response.choices[0].message.content.strip()
            
            # Additional content safety check on output
            is_output_safe, output_moderation = self.moderate_content(insights)
            if not is_output_safe:
                self.logger.warning(f"Generated insights failed moderation: {output_moderation}")
                return "Analysis completed but output filtered for safety."
            
            return insights
            
        except Exception as e:
            self.logger.error(f"Error generating insights: {e}")
            return f"Error generating insights: {str(e)}"
    
    def _prepare_trends_summary(self, trends_data: List[Dict], max_items: int = 30) -> str:
        """Prepare a concise summary of trends data for analysis."""
        if not trends_data:
            return "No trends data available."
        
        # Group by source and get top items
        summary_parts = []
        sources = {}
        
        for trend in trends_data[:max_items]:
            source = trend.get('source', 'unknown')
            if source not in sources:
                sources[source] = []
            sources[source].append(trend)
        
        for source, source_trends in sources.items():
            summary_parts.append(f"\n{source.upper()}:")
            for i, trend in enumerate(source_trends[:10], 1):  # Top 10 per source
                topic = trend.get('topic', 'Unknown')
                content = trend.get('content', '')[:100]  # Limit content length
                engagement = trend.get('engagement_score', 0)
                summary_parts.append(f"{i}. {topic} (Score: {engagement}): {content}...")
        
        return '\n'.join(summary_parts)
    
    def analyze_trends_batch(self, trends_data: List[Dict]) -> Dict[str, Any]:
        """Perform comprehensive analysis on a batch of trends."""
        try:
            if not trends_data:
                return {
                    'sentiment_score': 0.0,
                    'insights': 'No trend data available for analysis.',
                    'summary': 'No trends collected.',
                    'top_topics': [],
                    'source_breakdown': {},
                    'timestamp': datetime.now().isoformat()
                }
            
            # Calculate overall sentiment
            sentiments = []
            for trend in trends_data:
                content = f"{trend.get('topic', '')} {trend.get('content', '')}"
                if content.strip():
                    sentiment = self.analyze_sentiment(content)
                    sentiments.append(sentiment)
            
            avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0.0
            
            # Generate insights
            insights = self.generate_insights(trends_data)
            
            # Create summary
            summary = self._create_analysis_summary(trends_data, avg_sentiment)
            
            # Get top topics
            top_topics = self._get_top_topics(trends_data)
            
            # Source breakdown
            source_breakdown = self._get_source_breakdown(trends_data)
            
            return {
                'sentiment_score': round(avg_sentiment, 3),
                'insights': insights,
                'summary': summary,
                'top_topics': top_topics,
                'source_breakdown': source_breakdown,
                'total_trends': len(trends_data),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error in batch analysis: {e}")
            return {
                'sentiment_score': 0.0,
                'insights': f'Analysis error: {str(e)}',
                'summary': 'Analysis failed due to error.',
                'top_topics': [],
                'source_breakdown': {},
                'timestamp': datetime.now().isoformat()
            }
    
    def _create_analysis_summary(self, trends_data: List[Dict], sentiment: float) -> str:
        """Create a concise summary of the analysis."""
        total_trends = len(trends_data)
        
        # Count by source
        source_counts = {}
        total_engagement = 0
        
        for trend in trends_data:
            source = trend.get('source', 'unknown')
            source_counts[source] = source_counts.get(source, 0) + 1
            total_engagement += trend.get('engagement_score', 0)
        
        sentiment_desc = "positive" if sentiment > 0.1 else "negative" if sentiment < -0.1 else "neutral"
        avg_engagement = total_engagement / total_trends if total_trends > 0 else 0
        
        summary = f"Analyzed {total_trends} trends with {sentiment_desc} sentiment (score: {sentiment:.2f}). "
        summary += f"Average engagement: {avg_engagement:.1f}. "
        summary += f"Sources: {', '.join([f'{k}({v})' for k, v in source_counts.items()])}."
        
        return summary
    
    def _get_top_topics(self, trends_data: List[Dict], limit: int = 10) -> List[Dict]:
        """Get top topics by engagement score."""
        sorted_trends = sorted(trends_data, key=lambda x: x.get('engagement_score', 0), reverse=True)
        
        top_topics = []
        for trend in sorted_trends[:limit]:
            top_topics.append({
                'topic': trend.get('topic', 'Unknown'),
                'source': trend.get('source', 'unknown'),
                'engagement_score': trend.get('engagement_score', 0),
                'content_preview': trend.get('content', '')[:100] + '...' if trend.get('content') else ''
            })
        
        return top_topics
    
    def _get_source_breakdown(self, trends_data: List[Dict]) -> Dict[str, Any]:
        """Get breakdown of trends by source."""
        breakdown = {}
        
        for trend in trends_data:
            source = trend.get('source', 'unknown')
            if source not in breakdown:
                breakdown[source] = {
                    'count': 0,
                    'total_engagement': 0,
                    'avg_engagement': 0
                }
            
            breakdown[source]['count'] += 1
            breakdown[source]['total_engagement'] += trend.get('engagement_score', 0)
        
        # Calculate averages
        for source, data in breakdown.items():
            if data['count'] > 0:
                data['avg_engagement'] = round(data['total_engagement'] / data['count'], 2)
        
        return breakdown
    
    def create_twitter_thread(self, analysis: Dict[str, Any], max_tweets: int = 3) -> List[str]:
        """Create a Twitter thread from analysis results."""
        try:
            thread = []
            
            # First tweet - overview
            sentiment_emoji = "📈" if analysis['sentiment_score'] > 0.1 else "📉" if analysis['sentiment_score'] < -0.1 else "📊"
            
            first_tweet = f"🔍 Tech Trends Update {sentiment_emoji}\n\n"
            first_tweet += f"Analyzed {analysis['total_trends']} trends from {len(analysis['source_breakdown'])} sources.\n"
            first_tweet += f"Overall sentiment: {analysis['sentiment_score']:.2f}\n\n"
            first_tweet += "#TechTrends #AI #Programming"
            
            # Ensure first tweet is under 280 characters
            if len(first_tweet) <= 280:
                thread.append(first_tweet)
            
            # Second tweet - top topics
            if len(thread) < max_tweets and analysis['top_topics']:
                second_tweet = f"🚀 Top trending topics:\n\n"
                
                for i, topic in enumerate(analysis['top_topics'][:3], 1):
                    topic_line = f"{i}. {topic['topic']} ({topic['source']})\n"
                    if len(second_tweet + topic_line) < 250:  # Leave room for hashtags
                        second_tweet += topic_line
                
                second_tweet += "\n#Innovation #TechNews"
                
                if len(second_tweet) <= 280:
                    thread.append(second_tweet)
            
            # Third tweet - insights (if available and under max_tweets)
            if len(thread) < max_tweets and analysis['insights']:
                insights_short = analysis['insights'][:200] + "..." if len(analysis['insights']) > 200 else analysis['insights']
                third_tweet = f"💡 Key insights:\n\n{insights_short}\n\n🤖 Generated with AI analysis"
                
                if len(third_tweet) <= 280:
                    thread.append(third_tweet)
            
            # Ensure we have at least one tweet
            if not thread:
                thread.append("🔍 Tech trends analysis completed. Check back for updates! #TechTrends #AI")
            
            # Add bot identification to all tweets
            for i, tweet in enumerate(thread):
                if "🤖" not in tweet and i == len(thread) - 1:  # Add to last tweet if not already present
                    if len(tweet) + 20 <= 280:
                        thread[i] = tweet.rstrip() + "\n\n🤖 Automated analysis"
            
            return thread
            
        except Exception as e:
            self.logger.error(f"Error creating Twitter thread: {e}")
            return ["🔍 Tech trends analysis in progress. Stay tuned for updates! #TechTrends #AI 🤖"]
    
    def validate_analysis_quality(self, analysis: Dict[str, Any]) -> Tuple[bool, str]:
        """Validate the quality and safety of analysis results with enhanced checks."""
        issues = []
        
        # Check required fields
        required_fields = ['sentiment_score', 'insights', 'summary', 'top_topics']
        for field in required_fields:
            if field not in analysis:
                issues.append(f"Missing required field: {field}")
        
        # Check sentiment score range and validity
        sentiment = analysis.get('sentiment_score', 0)
        if not isinstance(sentiment, (int, float)) or sentiment < -1 or sentiment > 1:
            issues.append("Invalid sentiment score range")
        
        # Check insights content quality
        insights = analysis.get('insights', '')
        if insights:
            is_safe, moderation_msg = self.moderate_content(insights)
            if not is_safe:
                issues.append(f"Insights content issue: {moderation_msg}")
            
            # Check insights length and quality
            if len(insights.strip()) < 20:
                issues.append("Insights too short")
            elif "error" in insights.lower() or "failed" in insights.lower():
                issues.append("Insights indicate processing error")
        else:
            issues.append("Empty insights")
        
        # Check minimum data requirements
        total_trends = analysis.get('total_trends', 0)
        if total_trends == 0:
            issues.append("No trend data to analyze")
        elif total_trends < 5:
            issues.append("Insufficient trend data for reliable analysis")
        
        # Check for analysis errors
        if analysis.get('error', False):
            issues.append("Analysis marked as error")
        
        # Validate source breakdown
        source_breakdown = analysis.get('source_breakdown', {})
        if not source_breakdown or len(source_breakdown) == 0:
            issues.append("No source breakdown available")
        
        is_valid = len(issues) == 0
        return is_valid, "; ".join(issues) if issues else "Analysis passed validation"
    
    def get_analyzer_status(self) -> Dict[str, Any]:
        """Get analyzer performance and status metrics."""
        return {
            'client_available': self.client is not None,
            'model': self.model,
            'api_calls_made': self.api_call_count,
            'total_errors': self.error_count,
            'avg_processing_time': round(self.total_processing_time / max(self.api_call_count, 1), 3),
            'cache_size': len(self.cache),
            'cache_max_size': self.cache_max_size,
            'error_rate': round(self.error_count / max(self.api_call_count, 1), 3),
            'timestamp': datetime.now().isoformat()
        }
    
    def clear_cache(self):
        """Clear the sentiment analysis cache."""
        cache_size = len(self.cache)
        self.cache.clear()
        self.logger.info(f"Cleared analysis cache ({cache_size} items)")