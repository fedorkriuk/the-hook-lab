# 🚀 TrendBot – Tech Trend Analysis MVP

[![Python](https://img.shields.io/badge/Python-3.10+-blue)](https://www.python.org)
[![Status](https://img.shields.io/badge/Build-Active-green)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> 🧠 **AI-powered bot** that collects, analyzes, visualizes, and publishes **technology trends** from Twitter, GitHub, Reddit, and Hacker News — in real time.

---

## 🌐 Overview

<div align="center">
  <img src="https://github.com/fedorkriuk/the-hook-lab/assets/placeholder-bot-preview.gif" alt="TrendBot Animation" width="600"/>
</div>

---

## ⚙️ What It Does

TrendBot is a modular pipeline that:
- 📡 **Collects** real-time trends from Twitter, GitHub, Reddit, Hacker News
- 🧠 **Analyzes** trends using OpenAI's GPT-3.5-turbo
- 📊 **Visualizes** insights via interactive dashboards
- 🐦 **Publishes** Twitter threads with automated content validation

---

## 🎯 Architecture

```
+-----------------+      +------------------+      +-------------------+
|  Data Sources   | ---> |   Data Collector | ---> |   SQLite Database |
| (Twitter, etc.) |      +------------------+      +-------------------+
        |                                              |
        v                                              v
+------------------+      +------------------+      +-------------------+
|   AI Analyzer    | ---> |   Visualizer     | ---> |    Publisher      |
| (OpenAI + Rules) |      | (Plotly Charts)  |      |  (Twitter Bot)    |
+------------------+      +------------------+      +-------------------+
```

---

## 🧪 Features

### 📡 Data Collection
- Multi-source integration (Twitter, GitHub, Reddit, Hacker News)
- Real-time monitoring with rate-limiting & fallback logic
- Engagement scoring & topic ranking

### 🧠 AI-Powered Analysis
- GPT-3.5-turbo for trend insights and sentiment scoring
- PII and NSFW content filtering
- Contextual summaries & relevance scoring

### 📊 Visualization
- **Interactive charts** powered by Plotly
- Timelines, source breakdowns, topic maps
- HTML export for dashboards

<div align="center">
  <img src="https://github.com/fedorkriuk/the-hook-lab/assets/sample-dashboard-preview.png" width="600" alt="Dashboard Preview">
</div>

### 🐦 Auto Publishing
- Twitter thread creation with safety validation
- Rate-limited, policy-compliant automation
- Scheduled publishing at multiple times daily

---

## ⚡ Quickstart

### 📥 Clone & Install
```bash
git clone https://github.com/fedorkriuk/the-hook-lab.git
cd the-hook-lab
pip install -r requirements.txt
```

### ⚙️ Setup `.env`
Create a `.env` file and configure your keys:
```env
TWITTER_BEARER_TOKEN=your_token
OPENAI_API_KEY=your_openai_key
REDDIT_CLIENT_ID=your_client_id
...
```

---

## ▶️ Run the Bot

### 🔁 Full Cycle Mode
```bash
python main.py --mode single
```

### ⏱️ Scheduled Mode
```bash
python main.py --mode scheduled
```

### ⚙️ Other Modes
```bash
python main.py --mode collect    # Only collect
python main.py --mode analyze    # Analyze trends
python main.py --mode publish    # Tweet analysis
python main.py --mode status     # Bot status
```

---

## 📁 File Structure

```
the-hook-lab/
├── main.py               # Entrypoint
├── collectors/           # API scrapers
├── analyzer/             # GPT integration
├── visualizer/           # Plotly dashboards
├── publisher/            # Twitter logic
├── scheduler.py          # Job manager
├── .env.example          # Sample config
└── requirements.txt
```

---

## 💻 Developer API

```python
from main import TrendBot

bot = TrendBot()
bot.collect_trends()
bot.analyze_trends(hours_back=24)
bot.generate_visualizations()
bot.publish_analysis()
```

---

## 🧰 Tech Stack

- 🐍 Python 3.10+
- 🤖 OpenAI GPT-3.5
- 📊 Plotly + Kaleido
- 🗃️ SQLite
- 🌐 Tweepy, Reddit (PRAW), GitHub API
- 🕒 APScheduler

---

## 🧼 Clean & Compliant

- ✅ Twitter automation policy compliance
- ✅ Rate limit awareness
- ✅ PII detection & filtering
- ✅ Local storage only

---

## 📄 License

MIT License • [See LICENSE](LICENSE)

---

## 🤝 Contribute

PRs welcome! Fork, create a branch, and submit changes with docs/tests:
```bash
pip install -r requirements-dev.txt
black *.py
python -m pytest
```

---

## ✨ Coming Soon

- Slack/Discord integration
- Streamlit dashboard mode
- Multi-language support
- ML model comparison engine

---

> 🧪 MVP build by [@fedorkriuk](https://github.com/fedorkriuk) — designed for experimentation and insight, not production scale (yet).
