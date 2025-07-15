```
████████╗███████╗ ██████╗██╗  ██╗    ████████╗██████╗ ███████╗███╗   ██╗██████╗     ██████╗  ██████╗ ████████╗
╚══██╔══╝██╔════╝██╔════╝██║  ██╔╝   ╚══██╔══╝██╔══██╗██╔════╝████╗  ██║██╔══██╗    ██╔══██╗██╔═══██╗╚══██╔══╝
   ██║   █████╗  ██║     ███████╔╝      ██║   ██████╔╝█████╗  ██╔██╗ ██║██║  ██║    ██████╔╝██║   ██║   ██║   
   ██║   ██╔══╝  ██║     ██╔═ ██╗       ██║   ██╔═══╝ ██╔══╝  ██║╚██╗██║██║  ██║    ██╔═  █ ██║   ██║   ██║   
   ██║   ███████╗╚██████╗██║  ██╗       ██║   ██║  ██ ███████╗██║ ╚████║██████╔╝    ███ ██  ╚██████╔╝   ██║   
   ╚═╝   ╚══════╝ ╚═════╝╚═╝  ╚═╝       ╚═╝   ╚═╝   ╚═╚══════╝╚═╝  ╚═══╝╚═════╝     ╚═╝═══╝  ╚═════╝    ╚═╝   
```

---

# 🚀 TrendBot – Tech Trend Analysis Open-Source MVP

[![Python](https://img.shields.io/badge/Python-3.10+-blue)](https://www.python.org)
[![Status](https://img.shields.io/badge/Status-Active-green)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)


<div align="center">
  <img src="https://github.com/rajput2107/rajput2107/blob/master/Assets/Developer.gif?raw=true" width="600" alt="Working Dev Animation">
  <br/>
  <sub><strong>📡 Collect • 🧠 Analyze • 📊 Visualize • 🐦 Publish</strong></sub>
</div>

---

## 🌍 What is TrendBot?

> **TrendBot** is a full-stack, AI-powered automation tool that continuously tracks what's trending across dev platforms — turns it into intelligent insights — and shares it with the world.

Perfect for:
- 📰 Content creators
- 📈 Tech analysts
- 🤖 Automation geeks
- 🧪 AI/ML experimenters

---

> ⚠️ **Note:** This is an open-source MVP of TrendBot. In the future, advanced analysis components may become closed-source or proprietary as the project evolves.

---

## ⚡ Key Features

| ✅ Module       | 🔍 Description |
|----------------|----------------|
| 🌐 Multi-source | Collects data from Twitter, GitHub, Reddit, Hacker News |
| 🧠 AI Analyzer | Uses GPT-3.5 to summarize, score sentiment, moderate content |
| 📊 Visualizer  | Builds interactive Plotly dashboards |
| 🐦 Publisher   | Posts compliant, structured Twitter threads |
| 🕒 Scheduler   | APScheduler handles recurring jobs |
| 🔒 Secure      | Rate-limited, filtered, no PII stored |

---

## 🧠 Architecture

```
Data Sources → Collector → Database → Analyzer → Visualizer
                    ↓                      ↓
              Rate Limiting          AI Analysis
                    ↓                      ↓
              Content Filter        Publisher → Twitter

```

## 🚀 Quickstart

```bash
git clone https://github.com/fedorkriuk/the-hook-lab.git
cd the-hook-lab
pip install -r requirements.txt
cp .env.example .env  # fill in your API credentials
```

---

## ▶️ Run Modes

```bash
python main.py --mode single     # Full cycle (collect → analyze → publish)
python main.py --mode scheduled  # Background auto-run
python main.py --mode collect    # Just data collection
python main.py --mode analyze    # Just analysis
python main.py --mode publish    # Just publishing
python main.py --mode status     # View current status
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

## 📁 Folder Structure

```
the-hook-lab/
├── main.py               # Entrypoint & CLI
├── collectors/           # Twitter, GitHub, Reddit, HN modules
├── analyzer/             # GPT integration & filters
├── visualizer/           # Plotly dashboard builders
├── publisher/            # Twitter posting logic
├── scheduler.py          # Job manager
├── .env.example          # Config template
└── requirements.txt
```

---

## 📦 Tech Stack

- 🐍 Python 3.10+
- 🔍 OpenAI GPT-3.5
- 📊 Plotly & Kaleido
- 🕸️ Tweepy, Reddit API (PRAW), GitHub REST
- 🗄️ SQLite local storage
- 🕒 APScheduler

---

## 🔐 Security & Compliance

- ✅ No PII or private user data stored  
- ✅ All keys secured in `.env`  
- ✅ OpenAI moderation & filter layer  
- ✅ Twitter API automation-safe  

---

## 🧪 Development Tips

```bash
pip install -r requirements-dev.txt
black *.py
pytest
```

---

## 🧾 License

MIT License — Free to use, fork, modify.

---

<div align="center">
  <img src="https://user-images.githubusercontent.com/74038190/212744261-622b67cb-9151-43b8-9c70-ef7883ae8928.gif" width="400"/>
  <br/>
  <strong>TrendBot — Powered by AI, built with ❤️ and ☕ by <a href="https://github.com/fedorkriuk">@fedorkriuk</a></strong>
</div>

