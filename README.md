# ⚡ APEX AI Dev Engine v3

> **Multi-Agent • Multi-Model • Self-Healing • Persistent Memory**
> Build full-stack apps from a single sentence. No Claude API required.

---

## 🔥 What Makes This Better

| Feature | v2 (old) | v3 (this) |
|---|---|---|
| Providers | Groq only | Groq + OpenRouter + Together + Ollama + Mistral |
| Models | 1 | 18+ (Kimi K2, Gemini 2.5, DeepSeek R1, QwQ, Codestral…) |
| Agents | 1 (coder) | 7 (Planner, Architect, Coder, Reviewer, Debugger, Healer, DocWriter) |
| Fallback | None | Cascade: tries next model if one fails |
| Memory | None | Persistent JSON store with search |
| Self-healing | Stub | Real: runs code, detects errors, patches automatically |
| UI | CLI only | CLI + Web UI at localhost:7331 |
| Streaming | No | Yes (token-by-token) |
| Code Review | No | Auto-review + security audit |
| Tests | None | Full pytest suite |

---

## 🚀 Quick Start

```bash
# 1. Clone & install
git clone https://github.com/mahak867/ai-dev-engine
cd ai-dev-engine
pip install -r requirements.txt

# 2. Set at least ONE API key
cp .env.example .env
# Edit .env — add GROQ_API_KEY (free at console.groq.com)

# 3. Generate your first project
python cli.py generate "SaaS todo app with Next.js, FastAPI, PostgreSQL and auth" --name taskmaster

# 4. Or use the Web UI
python web_ui.py   # → open http://localhost:7331
```

---

## 🤖 Providers & Models

### Free / Fast
| Model | Provider | Context | Speed |
|---|---|---|---|
| `groq/llama-3.3-70b` | Groq | 128k | ⚡⚡⚡ |
| `groq/qwen-qwq-32b` | Groq | 128k | ⚡⚡⚡ |
| `ollama/qwen2.5-coder:32b` | Local | 128k | ⚡ |

### Premium (via OpenRouter)
| Model | Context | Strength |
|---|---|---|
| `or/kimi-k2` | 131k | Coding |
| `or/gemini-2.5-pro` | 1M | Reasoning |
| `or/deepseek-r1` | 163k | Reasoning |

### Code Specialists
| Model | Provider | Context |
|---|---|---|
| `mistral/codestral` | Mistral | 256k |
| `together/deepseek-r1` | Together | 163k |

---

## 🧠 Agent Pipeline

```
Request
  │
  ▼
🗺️  Planner      → JSON plan (tech stack, files, API routes, DB schema)
  │
  ▼
🏛️  Architect    → Architecture decisions, component diagram, security notes
  │
  ▼
👨‍💻 Coder        → Complete production-ready files (no placeholders)
  │
  ▼
🔍 Reviewer     → Quality score, security audit, auto-fixes
  │
  ▼
🔧 Self-Healer  → Runs code, catches errors, patches automatically
  │
  ▼
📝 DocWriter    → Professional README.md
  │
  ▼
✅ Output directory with all files
```

---

## 💻 CLI Reference

```bash
# Generate full-stack project
python cli.py generate "your idea" --name myapp

# Use specific model
python cli.py generate "REST API" --name api --model groq/qwen-qwq-32b

# Stream output token-by-token
python cli.py generate "chat app" --name chat --stream

# Use reasoning cascade (DeepSeek R1, QwQ)
python cli.py generate "complex fintech app" --model reasoning

# Edit existing project
python cli.py edit --path ./myapp --edit "add dark mode toggle"

# Debug an error
python cli.py edit --path ./myapp/server.py --debug "AttributeError: NoneType"

# Audit code quality
python cli.py audit --path ./myapp

# List all generated projects
python cli.py list

# Show available models
python cli.py models
```

---

## 🌐 Web UI

```bash
python web_ui.py
# → http://localhost:7331
```

Features:
- Live agent status indicators
- Real-time streaming output
- Project history sidebar
- File tree viewer
- Model selector with all 18+ models

---

## 🔧 Smart Cascades

Instead of specifying a model, use smart cascades:

- **`auto`** — tries Groq → Ollama → Together (best availability)
- **`coding`** — QwQ → Llama → Codestral → DeepSeek (code-optimized)
- **`reasoning`** — QwQ → DeepSeek R1 → Gemini 2.5 (complex problems)

---

## 🛠️ Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | ⭐ Recommended | Free at console.groq.com |
| `OPENROUTER_API_KEY` | Optional | Access Kimi K2, Gemini 2.5 |
| `TOGETHER_API_KEY` | Optional | DeepSeek R1, Qwen 2.5 |
| `MISTRAL_API_KEY` | Optional | Codestral (best for code) |
| `OLLAMA_HOST` | Optional | Default: localhost:11434 |

---

## 🧪 Tests

```bash
pip install pytest
python -m pytest tests/ -v
```

---

## 📁 Project Structure

```
apex-v3/
├── cli.py                    # Main CLI entry point
├── web_ui.py                 # Flask web interface
├── requirements.txt
├── .env.example
├── core/
│   ├── orchestrator.py       # Master pipeline coordinator
│   ├── ai/
│   │   └── provider.py       # Multi-provider router (18+ models)
│   ├── agents/
│   │   └── base.py           # All 7 agents
│   ├── execution/
│   │   ├── runner.py         # Safe subprocess executor
│   │   └── auto_heal.py      # Install → typecheck → test → heal loop
│   └── memory/
│       └── store.py          # Persistent project memory
└── tests/
    └── test_apex.py          # Full pytest suite
```

---

## 📜 License

MIT — built by Mahak Fahad
