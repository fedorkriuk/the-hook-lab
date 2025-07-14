# TrendBot - Tech Trend Analysis Bot MVP

A comprehensive automated system for collecting, analyzing, visualizing, and publishing technology trends from multiple sources including Twitter, GitHub, Reddit, and Hacker News.

## 🚀 Features

### Data Collection
- **Multi-Source Integration**: Collects trends from Twitter, GitHub, Reddit, and Hacker News
- **Rate-Limited APIs**: Proper rate limiting and error handling for all data sources
- **Real-time Monitoring**: Continuous collection of trending topics and discussions
- **Engagement Scoring**: Automatic calculation of engagement metrics

### AI-Powered Analysis
- **OpenAI Integration**: Uses GPT-3.5-turbo for sentiment analysis and insight generation
- **Content Moderation**: Built-in safety checks for PII and inappropriate content
- **Trend Insights**: Automated generation of meaningful insights from collected data
- **Sentiment Scoring**: Real-time sentiment analysis of trending topics

### Visualization Dashboard
- **Interactive Charts**: Plotly-powered visualizations including:
  - Sentiment timeline
  - Source breakdown pie charts
  - Top topics bar charts
  - Engagement scatter plots
  - Comprehensive dashboards
- **Export Capabilities**: HTML export for easy sharing and embedding

### Automated Publishing
- **Twitter Integration**: Compliant Twitter thread creation and posting
- **Daily Limits**: Configurable posting limits with rate limiting
- **Bot Identification**: Automatic compliance with Twitter automation policies
- **Content Validation**: Pre-publication content validation and safety checks

### Scheduling & Automation
- **Background Scheduler**: APScheduler-based job management
- **Configurable Intervals**: Customizable collection, analysis, and publishing schedules
- **Graceful Error Handling**: Robust error handling and recovery mechanisms
- **Cleanup Jobs**: Automatic cleanup of old data and visualizations

## 📋 Requirements

### Dependencies
```
tweepy>=4.14.0
openai>=1.3.0
plotly>=5.17.0
pandas>=2.1.0
python-dotenv>=1.0.0
requests>=2.31.0
praw>=7.7.0
beautifulsoup4>=4.12.0
APScheduler>=3.10.0
kaleido>=0.2.1
sqlite3
```

### API Keys Required
- **Twitter API v2**: Bearer token, consumer keys, access tokens
- **OpenAI API**: API key for GPT analysis
- **Reddit API**: Client ID, secret, user agent
- **GitHub API**: Personal access token (optional, for higher rate limits)

## 🛠️ Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd the-hook-lab
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Environment Configuration**

Create a `.env` file based on `.env.example`:

```env
# Twitter API v2 Credentials
TWITTER_BEARER_TOKEN=your_bearer_token
TWITTER_CONSUMER_KEY=your_consumer_key
TWITTER_CONSUMER_SECRET=your_consumer_secret
TWITTER_ACCESS_TOKEN=your_access_token
TWITTER_ACCESS_TOKEN_SECRET=your_access_token_secret

# OpenAI API
OPENAI_API_KEY=your_openai_api_key

# Reddit API
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_CLIENT_SECRET=your_reddit_client_secret
REDDIT_USER_AGENT=TrendBot/1.0

# GitHub API (Optional)
GITHUB_TOKEN=your_github_token

# Database
DATABASE_PATH=trends.db

# Logging
LOG_LEVEL=INFO

# Scheduling (Optional)
COLLECTION_INTERVAL_HOURS=2
ANALYSIS_INTERVAL_HOURS=12
PUBLISHING_INTERVAL_HOURS=8
CLEANUP_INTERVAL_DAYS=1
PUBLISH_TIME_1=09:00
PUBLISH_TIME_2=15:00
PUBLISH_TIME_3=21:00
```

## 🚀 Usage

### Command Line Interface

TrendBot supports multiple operation modes:

#### Scheduled Mode (Default)
Run continuous automated operation:
```bash
python main.py --mode scheduled
```

#### Single Cycle
Run one complete cycle (collect → analyze → visualize → publish):
```bash
python main.py --mode single
```

#### Individual Operations
Run specific operations:

**Data Collection Only**
```bash
python main.py --mode collect
```

**Analysis Only**
```bash
python main.py --mode analyze --hours-back 24
```

**Publishing Only**
```bash
python main.py --mode publish
```

**Status Check**
```bash
python main.py --mode status
```

#### Configuration Options
```bash
python main.py --mode scheduled --log-level DEBUG --config config.json
```

### Programmatic Usage

```python
from main import TrendBot

# Initialize bot
bot = TrendBot()

# Run single operations
collection_result = bot.collect_trends()
analysis_result = bot.analyze_trends(hours_back=24)
viz_result = bot.generate_visualizations()
publish_result = bot.publish_analysis()

# Run full cycle
full_result = bot.run_full_cycle()

# Start scheduled operation
bot.start_scheduled_operation()

# Get status
status = bot.get_status()
```

## 📊 Architecture

### Core Components

1. **DataCollector** (`collectors.py`)
   - Multi-source data collection
   - Rate limiting and error handling
   - Content filtering and preprocessing

2. **TrendAnalyzer** (`analyzer.py`)
   - AI-powered sentiment analysis
   - Insight generation
   - Content moderation and safety

3. **TrendVisualizer** (`visualizer.py`)
   - Interactive chart generation
   - Dashboard creation
   - Export capabilities

4. **TwitterPublisher** (`publisher.py`)
   - Compliant Twitter posting
   - Thread management
   - Rate limiting and validation

5. **TrendDatabase** (`database.py`)
   - SQLite data storage
   - Query interfaces
   - Data cleanup utilities

6. **TrendBotScheduler** (`scheduler.py`)
   - Job scheduling and management
   - Error recovery
   - Status monitoring

### Data Flow

```
Data Sources → Collector → Database → Analyzer → Visualizer
                    ↓                      ↓
              Rate Limiting          AI Analysis
                    ↓                      ↓
              Content Filter        Publisher → Twitter
```

### Database Schema

**trend_data**
- Stores collected trend information
- Indexed by timestamp and source
- Includes engagement metrics and metadata

**trend_analysis**
- Stores analysis results and insights
- Links to visualization files
- Tracks sentiment scores

**published_content**
- Audit trail of published content
- Success/failure tracking
- Rate limiting compliance

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `COLLECTION_INTERVAL_HOURS` | Hours between data collection | 2 |
| `ANALYSIS_INTERVAL_HOURS` | Hours between analysis runs | 12 |
| `PUBLISHING_INTERVAL_HOURS` | Hours between publishing | 8 |
| `CLEANUP_INTERVAL_DAYS` | Days between cleanup jobs | 1 |
| `PUBLISH_TIME_1/2/3` | Daily publishing times | 09:00/15:00/21:00 |
| `DATABASE_PATH` | SQLite database location | trends.db |
| `LOG_LEVEL` | Logging verbosity | INFO |

### JSON Configuration

Create a `config.json` file for advanced configuration:

```json
{
  "log_level": "INFO",
  "database_path": "trends.db",
  "viz_output_dir": "visualizations",
  "daily_post_limit": 3,
  "collection_limits": {
    "twitter": 50,
    "github": 30,
    "reddit": 30,
    "hackernews": 20
  }
}
```

## 📈 Monitoring & Logging

### Log Files
- **trendbot.log**: Main application logs
- Console output with structured logging
- Error tracking and performance metrics

### Status Monitoring
```bash
# Check current status
python main.py --mode status

# View scheduled jobs
python -c "from scheduler import TrendBotScheduler; s = TrendBotScheduler(); print(s.get_job_status())"
```

### Metrics Tracked
- Collection success rates
- Analysis quality scores
- Publishing compliance
- API rate limit usage
- Database growth

## 🔒 Security & Compliance

### Content Safety
- PII detection and filtering
- Inappropriate content screening
- Content length validation
- Sentiment verification

### API Compliance
- Twitter automation policy compliance
- Rate limiting respect
- Bot identification in posts
- Error handling and retry logic

### Data Privacy
- No storage of personal information
- Automatic data cleanup
- Secure API key management
- Local database storage

## 🐛 Troubleshooting

### Common Issues

**API Authentication Errors**
```bash
# Verify credentials
python -c "from collectors import DataCollector; c = DataCollector()"
```

**Database Issues**
```bash
# Reset database
rm trends.db
python main.py --mode status  # Recreates tables
```

**Publishing Failures**
- Check Twitter API credentials
- Verify daily posting limits
- Review content validation errors

**Memory/Performance Issues**
- Adjust collection limits in config
- Increase cleanup frequency
- Monitor database size

### Debug Mode
```bash
python main.py --mode single --log-level DEBUG
```

### Error Recovery
- Automatic retry mechanisms
- Graceful degradation
- Job failure isolation
- Database transaction safety

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Implement changes with tests
4. Update documentation
5. Submit pull request

### Development Setup
```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
python -m pytest tests/

# Code formatting
black *.py
flake8 *.py
```

## 📄 License

MIT License - see LICENSE file for details.

## 🔗 Links

- **Documentation**: [Full API Documentation](docs/)
- **Issues**: [GitHub Issues](issues/)
- **Discussions**: [GitHub Discussions](discussions/)

## 📞 Support

For questions and support:
- Create an issue on GitHub
- Check the troubleshooting section
- Review the logs for error details

---

**Note**: This is an MVP (Minimum Viable Product) designed for educational and demonstration purposes. Production deployment requires additional security hardening and scalability considerations.