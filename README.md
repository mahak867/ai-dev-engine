# ai-dev-engine

Local autonomous full-stack AI developer engine powered by a **4-model Ollama stack**.

## Model Stack

| Role | Model | Used For |
|------|-------|----------|
| General / Chat | `qwen3:9b` | Conversation, coordination |
| Code Generation | `qwen2.5-coder:14b` | Backend, frontend, tests, DB schema |
| Output Formatting | `decoder:14b` | JSON cleanup, config files, .env |
| Reasoning / Planning | `deepseek-r1:14b` | Architecture, API contracts, code review, error analysis |

## Full-Stack Pipeline (8 Steps)

```
User Request
     │
     ▼
[R1]     1. Classify project type + detect stack
     │
     ▼
[R1]     2. Architecture + API contract design
     │
     ▼
[Coder]  3. Database schema + SQLAlchemy models
     │
     ▼
[Coder]  4. Backend code (Flask/FastAPI + routes + auth)
     │
     ▼
[Coder]  5. Frontend code (React / Vue / HTML+JS)
     │
     ▼
[Coder]  6. Test suite (pytest + API tests)
     │
     ▼
[Decoder] 7. Config files (.env.example, docker-compose, package.json, README)
     │
     ▼
[Decoder] 8. Merge + format all files into final output
```

## Setup

```bash
pip install -r requirements.txt

ollama pull qwen3:9b
ollama pull qwen2.5-coder:14b
ollama pull decoder:14b
ollama pull deepseek-r1:14b
ollama serve
```

## Usage

```bash
# Full-stack app (recommended)
python cli.py --fullstack "Build a task manager with React frontend and Flask REST API with SQLite" --name task_manager

# Classify first to see what will be built
python cli.py --classify "Build a blog with Vue frontend and FastAPI backend"

# 4-model pipeline
python cli.py --pipeline "Build a REST API for a bookstore" --name bookstore_api

# Single-model (fast)
python cli.py --generate "Build a Flask REST API" --name my_api

# Single model calls
python cli.py --chat  "What is JWT authentication?"
python cli.py --plan  "Design a microservices e-commerce system"
python cli.py --code  "Write a React login component"
```

## Supported Project Types

| Type | Description |
|------|-------------|
| `fullstack_react` | Flask/FastAPI + React |
| `fullstack_vue` | Flask/FastAPI + Vue |
| `fullstack_html` | Flask/FastAPI + Plain HTML/JS |
| `frontend_react` | React SPA only |
| `frontend_vue` | Vue SPA only |
| `frontend_html` | Static HTML/CSS/JS |
| `backend_api` | REST API only |
| `cli_tool` | Python CLI tool |
| `python_script` | Python script |
| `data_pipeline` | Data processing |

## Smart Execution Engine

Automatically detects and runs the right command:
- Python server → `python app.py`
- Python script → `python main.py`
- React/Vue → `npm install && npm run dev`
- Static HTML → opens `index.html`
- Full-stack → runs backend + frontend together
