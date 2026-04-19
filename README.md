# APEX AI Dev Engine

> **Competition & investor-grade full-stack app generator** powered by Kimi K2, Qwen3-32B, and Llama 3.3 70B.

[![CI](https://github.com/mahak867/ai-dev-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/mahak867/ai-dev-engine/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

APEX takes a plain-English description of an app and generates a complete, runnable full-stack project — Flask backend, React/Vite frontend, database schema, tests, config files, and auto-debug loop — in a single command.

---

## Features

| Feature | Details |
|---|---|
| 🏗️ Full-stack generation | Flask + React/Vite, SQLite/PostgreSQL, REST API |
| 🤖 Multi-model pipeline | Kimi K2 (architecture) → Qwen3-32B (code) → Llama 3.3 70B (format) |
| 🔧 Auto-debug loop | Runs the project, catches errors, feeds them back to the LLM |
| ✏️ In-place editing | `apex edit` surgically patches an existing project |
| 🔑 Integrations | Clerk auth, Stripe payments, public APIs |
| 💾 Response cache | SHA-256 cache avoids repeat API calls |
| 🧪 Test suite | 35 automated tests, runs offline with no API key |

---

## Installation

```bash
# 1. Clone
git clone https://github.com/mahak867/ai-dev-engine.git
cd ai-dev-engine

# 2. Install (creates the `apex` console script)
pip install -e .

# 3. Set your Groq API key
export GROQ_API_KEY=gsk_...          # Linux / macOS
# or
setx GROQ_API_KEY gsk_...            # Windows
```

Get a free Groq API key at <https://console.groq.com>.

---

## Quick start

### Generate a new app

```bash
apex generate "A task management app with user accounts and due-date reminders" \
  --name taskmaster \
  --clerk \
  --output ./projects
```

### Try it without an API key (dry-run)

```bash
apex generate "A blog with comments" --name myblog --dry-run
```

### Edit an existing generated app

```bash
# Apply an instruction to existing files
apex edit --path ./projects/taskmaster --edit "add dark mode toggle"

# Add a complete new feature
apex edit --path ./projects/taskmaster --add "Stripe subscription billing"
```

### Full option reference

```
apex generate <request> [options]

  <request>           Plain-English app description (required)
  --name NAME         Project folder name  [default: my_app]
  --output DIR        Parent directory for the project  [default: .]
  --provider NAME     AI provider  [default: groq]
  --clerk             Scaffold Clerk authentication
  --stripe            Scaffold Stripe payments
  --dry-run           Preview pipeline steps without calling the AI

apex edit [options]

  --path PATH         Path to an existing generated project (required)
  --edit INSTRUCTION  Instruction to apply to existing files
  --add FEATURE       New feature to generate and add
```

---

## Running the app after generation

After `apex generate` completes, follow the printed instructions:

```
  BACKEND (Terminal 1):
    cd taskmaster/backend
    python app.py
    -> http://127.0.0.1:5000

  FRONTEND (Terminal 2):
    cd taskmaster/frontend
    npm install
    npm run dev
    -> http://localhost:5173
```

---

## Development

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run the test suite (no API key required)
python -m pytest tests/ -v
```

Tests are located in `tests/` and cover:
- `tests/test_cli.py` — argument parsing and subcommand routing
- `tests/test_orchestrator.py` — core orchestrator logic (JSON parsing, file writing, merge, dry-run, edit/add)

All external AI calls are stubbed out, so the tests run fully offline.

---

## Project structure

```
ai-dev-engine/
├── cli.py                  # `apex` CLI entry point
├── core/
│   ├── orchestrator.py     # Central coordinator
│   ├── ai/
│   │   ├── fullstack_pipeline.py
│   │   ├── groq_provider.py
│   │   ├── editor.py
│   │   ├── post_fixer.py
│   │   ├── senior_team.py
│   │   └── ...
│   ├── execution/
│   │   ├── runner.py
│   │   └── debugger.py
│   └── tools/
│       └── dependency_installer.py
├── tests/
│   ├── fixtures/
│   │   └── sample_generation.json
│   ├── test_cli.py
│   └── test_orchestrator.py
├── pyproject.toml
├── requirements.txt
└── requirements-dev.txt
```

---

## License

MIT — see [LICENSE](LICENSE).
