# ⬡ APEX AI Dev Engine

> **Competition-grade full-stack app generator powered by Kimi K2 + Qwen3-32B + Llama 3.3 70B on Groq**

[![Python](https://img.shields.io/badge/Python-3.10+-f0c040?style=flat-square&logo=python&logoColor=black)](https://python.org)
[![Groq](https://img.shields.io/badge/Powered%20by-Groq-f0c040?style=flat-square)](https://groq.com)
[![React](https://img.shields.io/badge/Generates-React%20+%20Flask-61dafb?style=flat-square&logo=react&logoColor=black)](https://react.dev)
[![Clerk](https://img.shields.io/badge/Auth-Clerk-6c47ff?style=flat-square)](https://clerk.com)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

APEX is a personal AI development engine that generates **investor-ready, deployable full-stack applications** from a single prompt. Built for hackathons, CTF competitions, and rapid product development.

---

## What it does

Type an idea. Get a complete, production-quality application in under 5 minutes.

```
"Build a SaaS project management platform with teams and analytics"
         ↓  5 minutes  ↓
  ✅ Flask REST API with auth
  ✅ React frontend with dark theme UI
  ✅ SQLite database with migrations
  ✅ Clerk authentication (Google/GitHub login)
  ✅ Dockerfile + docker-compose
  ✅ Professional README
  ✅ Deployable to Railway/Render in one click
```

---

## Features

- **5-step AI pipeline** — Architecture → Schema → Backend → Frontend → Deployment
- **3 specialized models** — Kimi K2 for system design, Qwen3-32B for code, Llama 3.3 70B for config
- **Desktop launcher** — Dark GUI, no terminal needed
- **Telegram bot** — Generate apps remotely from your phone
- **Clerk auth** — Google/GitHub/email login auto-integrated
- **Auto post-fixer** — Automatically repairs 15+ common generation errors
- **Public APIs library** — 20 free APIs auto-detected and integrated
- **Production ready** — Dockerfile, .env, docker-compose included every time

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Reasoning | Kimi K2 (MoE, best-in-class planning) |
| Code Generation | Qwen3-32B (purpose-built for code) |
| Config/Formatting | Llama 3.3 70B Versatile |
| Inference | Groq LPU (1800+ tokens/sec) |
| Backend | Flask + SQLAlchemy + Flask-CORS |
| Frontend | React 18 + Vite + React Router |
| Auth | Clerk (Google, GitHub, email) |
| Deployment | Docker + Gunicorn |

---

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- Free [Groq API key](https://console.groq.com)
- Free [Clerk key](https://clerk.com) (for auth apps)

### Install

```bash
git clone https://github.com/mahak867/ai-dev-engine
cd ai-dev-engine
pip install -r requirements.txt
```

### Set your Groq key

```bash
# Windows
setx GROQ_API_KEY "your_key_here"

# Mac/Linux
export GROQ_API_KEY="your_key_here"
```

### Launch the Desktop UI

```bash
py launcher.py
```

### Or use the CLI

```bash
py cli.py --fullstack "Build a todo app with React and Flask" --name todo --provider groq
```

### Or use Telegram

```bash
setx TELEGRAM_BOT_TOKEN "your_bot_token"
py telegram_bot.py
```

---

## Generated App Structure

```
my_app/
├── backend/
│   ├── app.py              # Flask factory
│   ├── config.py           # Configuration
│   ├── extensions.py       # SQLAlchemy, Bcrypt
│   ├── models.py           # Database models
│   └── routes/             # API blueprints
├── frontend/
│   ├── src/
│   │   ├── App.jsx         # Router + layout
│   │   ├── index.css       # Complete design system
│   │   ├── components/     # Navbar, Card, Modal, etc.
│   │   ├── pages/          # One per route
│   │   └── services/api.js
│   ├── index.html
│   ├── vite.config.js
│   └── package.json
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

## Running Generated Apps

**Backend** (Terminal 1):
```bash
cd my_app/backend
py app.py
```

**Frontend** (Terminal 2):
```bash
cd my_app/frontend
npm install
npm run dev
```

---

## CLI Options

```bash
py cli.py --fullstack "app idea" --name my_app --provider groq

  --fullstack    Full-stack app idea
  --name         Project folder name
  --provider     groq or ollama
  --chat         Quick chat
  --check        Verify Groq connection
```

---

## Model Pipeline

```
User Prompt
    ↓
[Llama 3.3 70B]  Classify project type
    ↓
[Kimi K2]        Architecture & API design
    ↓
[Qwen3-32B]      Database schema & models
    ↓
[Qwen3-32B]      Flask backend
    ↓
[Qwen3-32B]      React frontend
    ↓
[Llama 3.3 70B]  Deployment config
    ↓
[Post-Fixer]     Auto-repair errors
    ↓
Production app ✅
```

---

## Performance

| Metric | Value |
|--------|-------|
| Full app generation | 3-5 minutes |
| Token speed | 1,800+ tokens/sec |
| Daily free generations | ~40 full apps |
| Files per app | 15-25 files |

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `GROQ_API_KEY` | Groq cloud API key (required) |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token (optional) |
| `PYTHONUTF8` | Set to `1` on Windows |

---

## Repository Structure

```
ai-dev-engine/
├── cli.py                          # CLI entry point
├── launcher.py                     # Desktop GUI
├── telegram_bot.py                 # Telegram bot
├── core/
│   ├── ai/
│   │   ├── fullstack_pipeline.py   # Generation pipeline
│   │   ├── groq_provider.py        # Groq API client
│   │   ├── post_fixer.py           # Auto-repair engine
│   │   ├── project_classifier.py   # Project detection
│   │   └── public_apis.py          # Free API library
│   └── orchestrator.py
└── requirements.txt
```

---

## License

MIT

---

<div align="center">
  <strong>Built by Mahak</strong><br/>
  <sub>Powered by Groq · Kimi K2 · Qwen3-32B · Llama 3.3 70B</sub>
</div>
