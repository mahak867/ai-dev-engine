# APEX Society — Qwen Cloud AI Hackathon | Track 3: Agent Society

> A multi-agent system where 7 specialized LLM agents (plus a syntax-check Executor and persistent Memory — 9 pipeline roles) collaborate, negotiate, and self-correct to build full-stack applications — with a real conflict resolution loop that rejects, revises, and approves code before it ships.

**[Global AI Hackathon Series with Qwen Cloud](https://qwencloud-hackathon.devpost.com/) — Track 3: Agent Society**

**Hosted demo:** the hackathon instance on Alibaba Cloud ECS (Singapore) has been decommissioned. Run it locally with the Quick Start below.

---

## Demo Video

> 📹 **[APEX Society Demo — 9-Agent Qwen AI System](https://youtu.be/XBzURya6XAk)**

---

## What It Does

APEX Society takes a single sentence — "build a REST API with JWT auth" — and runs it through a society of 7 LLM agents plus an Executor and Memory. Each agent has a distinct role and communicates structured outputs to the next via a real-time WebSocket dialogue system.

The core innovation: **agents can disagree**. The Reviewer can reject the Coder's output, send structured feedback, and force a revision cycle — up to 3 rounds — before approving. This is real agent negotiation, not a scripted pipeline.

---

## Benchmark: Society vs Single Agent

> Recorded once during the hackathon on a single task (n=1). Quality scores are the Reviewer agent's own 0–100 assessment, not an independent security scan. Reproduce with `python benchmark.py`.

| Metric | Single Agent | APEX Society |
|---|---|---|
| Files generated | 5 | **17–22** |
| Quality score | 91/100 | **96–100/100** |
| Security checks passed | 9/10 | **10/10** |
| Critical issues flagged by Reviewer | **1** (hardcoded secret) | **0** |
| Agents coordinating | 1 | **7** |
| Conflict resolution rounds | 0 | **up to 3** |

**The critical finding:** The single agent shipped a hardcoded JWT secret fallback (`SECRET_KEY = os.getenv("SECRET_KEY", "09d25e094faa...")`) — a real CVE-level vulnerability. The Reviewer agent caught it, rejected the code, forced a revision, and verified the fix. Zero secrets shipped.

```
Track 3 requirement: "how they resolve disagreements and execution conflicts"
Result: Real Reviewer→Coder→Reviewer reject/revise/approve loop with structured dialogue
```

---

## Track 3 Requirements — Explicitly Met

| Requirement | How APEX Society meets it |
|---|---|
| **Agents decompose tasks and assign roles** | Planner outputs structured JSON (tech stack, files, API routes, DB schema) distributed to each agent |
| **Agents resolve disagreements and execution conflicts** | Reviewer scores code 0–100. Score <80 or any critical issue → REJECTED. Structured rejection notes sent to Coder. Coder revises targeted files only. Reviewer re-reviews. Up to 3 rounds. |
| **Measurable efficiency gain over single-agent** | +12–17 files, +5–9 Reviewer quality score, 1 Reviewer-flagged critical issue (hardcoded secret) fixed — single recorded run |

---

## Conflict Resolution Loop (Track 3 Core Feature)

```
Reviewer scores code → REJECTED (score 68/100, 2 blocking issues)
        ↓
Reviewer → Coder: "REJECTED. Fix: hardcoded JWT secret; missing input validation"
        ↓
Coder revises 2 files (targeted patch, not full rewrite)
        ↓
Coder → Reviewer: "Revision complete. Patched auth.py, config.py. Resubmitting."
        ↓
Reviewer re-reviews → APPROVED (score 96/100)
        ↓
Reviewer → SelfHealer: "Code approved after 2 rounds. No critical issues remain."
```

Visible in real time on the dashboard — Reviewer node pulses red on rejection, Agent Dialogue panel shows every message, quality score updates live after each round.

---

## Architecture

```
User Input → FastAPI WebSocket Server (server.py, port 8000)
                        │
                        ▼
              APEX Orchestrator (core/orchestrator.py)
                        │
    ┌───────────────────┼───────────────────┐
    ▼                   ▼                   ▼
🗺  Planner         🏛  Architect        📝 DocWriter
JSON plan           Security decisions   README.md
    │                   │
    └──────────┐        │
               ▼        ▼
           👨‍💻 Coder (production code, 17–22 files)
               │
               ▼ ◄──────────────────────────┐
           🔍 Reviewer (score 0–100)          │
           REJECTED → revision notes ─────────┘
           APPROVED → continue (up to 3 rounds)
               │
           🔧 SelfHealer (auto-patch CVEs)
               │
           🐛 Debugger (runtime error check)
               │
           ✅ Output

All inference: Alibaba Cloud DashScope (dashscope-intl.aliyuncs.com)
Primary model: qwen3.7-max  |  Vision: qwen3.7-plus
Fallback cascade: qwen-plus → qwen-turbo → groq/llama-3.3-70b
```

---

## Live Dashboard

Real-time visualization built with SVG `animateMotion`, force-directed graph physics, WebSocket streaming, and Octogent-style pixel art animated characters.

- **Animated ghost characters** — jog/bounce/sway/float per agent state; angry face on rejection
- **Agent Dialogue panel** — live `Reviewer → Coder` rejection and `Coder → Reviewer` patch messages
- **Quality score** — updates in header after each Reviewer round
- **Security panel** — auto-opens when CVEs are detected
- **Benchmark tab** — live Society vs Single Agent comparison

---

## Alibaba Cloud Integration

All LLM agents route through Alibaba Cloud DashScope by default:

```python
# core/ai/provider.py
ENDPOINT = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions"
PRIMARY   = "qwen3.7-max"   # 1M context, agent-tuned
VISION    = "qwen3.7-plus"  # multimodal wireframe input
```

**Deployment (hackathon, now decommissioned):** Alibaba Cloud ECS, ap-southeast-1 (Singapore).

```bash
python alibaba_cloud_proof.py
# ✓ ALIBABA CLOUD CONNECTION VERIFIED
# ✓ APEX SOCIETY IS RUNNING ON ALIBABA CLOUD
```

---

## MCP Integration

8 typed tools (7 agents + a static benchmark summary), served by `server.py` under `/mcp/*` or standalone by `mcp_server.py` (port 8001). This is a JSON-over-HTTP tool API in the spirit of MCP, not the JSON-RPC transport from the MCP spec.

```bash
curl http://127.0.0.1:8000/mcp/tools                 # list tools
curl -X POST http://127.0.0.1:8000/mcp/tools/plan_project \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $APEX_API_TOKEN" \
  -d '{"request":"build a todo API","name":"myapp"}'
```

---

## Quick Start

```bash
git clone https://github.com/mahak867/ai-dev-engine
cd ai-dev-engine
pip install -r requirements.txt
cp .env.example .env          # add QWEN_API_KEY
python server.py              # binds 127.0.0.1:8000
# open http://localhost:8000
```

CLI only (wheel install): `pip install .` then `apex generate "todo app" --name todo --dry-run`.
The web server and dashboard run from a source checkout (`pip install ".[server]"`).

---

## Security model

Generated code and model output are treated as untrusted (OWASP LLM05 / LLM06).

| Area | Default |
|---|---|
| Network | Binds `127.0.0.1`. Non-loopback binds are refused unless `APEX_API_TOKEN` is set. Put TLS in front for remote use. |
| Auth | With `APEX_API_TOKEN` set, every `/api/*`, `/mcp/*` route and the WebSocket require `Authorization: Bearer <token>` (or `?token=` for the WebSocket/downloads). Open the dashboard as `http://host:8000/#token=<token>`. |
| DNS rebinding / CSRF | `Host` header must be in `APEX_ALLOWED_HOSTS`; browser `Origin` must be in `APEX_ALLOWED_ORIGINS`. No wildcard CORS. |
| Sessions | Each WebSocket only receives events for sessions it started or subscribed to. Session IDs are validated; downloads never follow symlinks. |
| Cost | `APEX_MAX_CONCURRENT_JOBS` (default 2) and `APEX_MAX_TASK_CHARS` (default 500) bound spend; WebSocket messages are capped at 16 KB. |
| File writes | Every model-chosen path goes through `core.security.safe_join`: no `..`, absolute, drive/UNC paths, `.git/`, or symlink escapes. Writes are atomic. |
| Execution | Installing deps, running generated code, auto-starting apps and deploying are **off** unless `APEX_ALLOW_EXECUTION=1` or `approved=True`. No shell; children get a minimal env (no API keys); timeouts kill the whole process group; `npm install --ignore-scripts` by default. This is not an OS sandbox — use a container/VM for untrusted projects. |
| Agent tools | `python_eval` is literal-only; `web_fetch` blocks private, loopback and cloud-metadata addresses. |
| Memory | `~/.apex/memory` (override `APEX_MEMORY_DIR`), 0600 files, secrets redacted, file contents never stored, pruned to 500 records / 90 days. |

Run the security regression suite: `python -m pytest tests/test_security.py -v`.

---

## Run the Benchmark

```bash
python benchmark.py
# Single agent vs agent society — files, quality, Reviewer-flagged issues
```

---

## Project Structure

```
apex-society/
├── server.py                 # FastAPI + WebSocket backend
├── dashboard.html            # Live agent visualization (single file)
├── benchmark.py              # Single vs society comparison
├── alibaba_cloud_proof.py    # Alibaba Cloud connection proof
├── core/
│   ├── orchestrator.py       # Pipeline + conflict resolution loop
│   ├── agents/base.py        # 7 LLM agent implementations
│   ├── security.py           # Path containment, no-shell exec, env allowlist, SSRF guard, redaction
│   ├── web_security.py       # Host/Origin/token checks for the HTTP + WebSocket servers
│   ├── ai/provider.py        # Qwen Cloud router + retry logic
│   └── memory/store.py       # Persistent session memory
├── tests/test_apex.py        # Core unit tests
└── tests/test_security.py    # Security-boundary regression tests
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `QWEN_API_KEY` | ✅ | From home.qwencloud.com/api-keys |
| `GROQ_API_KEY` | Optional | Free fallback |
| `APEX_API_TOKEN` | For remote use | Bearer token for the server; required for non-loopback binds |
| `APEX_HOST` / `APEX_PORT` | Optional | Bind address (default `127.0.0.1:8000`) |
| `APEX_ALLOWED_HOSTS` / `APEX_ALLOWED_ORIGINS` | Optional | Comma lists for Host and browser Origin checks |
| `APEX_MAX_CONCURRENT_JOBS` / `APEX_MAX_TASK_CHARS` | Optional | Cost/abuse limits (defaults 2 / 500) |
| `APEX_ALLOW_EXECUTION` | Optional | `1` to let the engine install deps / run / deploy generated code |
| `APEX_MEMORY_DIR` | Optional | Memory location (default `~/.apex/memory`) |

---

*Built for the Global AI Hackathon Series with Qwen Cloud — Track 3: Agent Society*
*Submitted by Mahak Fahad — June 2026 | [github.com/mahak867/ai-dev-engine](https://github.com/mahak867/ai-dev-engine)*
