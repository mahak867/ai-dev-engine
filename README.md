# APEX Society — Qwen Cloud AI Hackathon | Track 3: Agent Society

> A production-grade multi-agent system where 9 specialized Qwen 3.7 agents collaborate, negotiate, and self-correct to build full-stack applications — with a real conflict resolution loop that rejects, revises, and approves code before it ships.

**[Global AI Hackathon Series with Qwen Cloud](https://qwencloud-hackathon.devpost.com/) — Track 3: Agent Society**

🔴 **Live Demo:** http://47.84.135.232:8000 — Deployed on Alibaba Cloud ECS Singapore

---

## Demo Video

> 📹 **[APEX Society Demo — 9-Agent Qwen AI System](https://youtu.be/XBzURya6XAk)**

---

## What It Does

APEX Society takes a single sentence — "build a REST API with JWT auth" — and runs it through a society of 9 specialized Qwen 3.7 agents. Each agent has a distinct role and communicates structured outputs to the next via a real-time WebSocket dialogue system.

The core innovation: **agents can disagree**. The Reviewer can reject the Coder's output, send structured feedback, and force a revision cycle — up to 3 rounds — before approving. This is real agent negotiation, not a scripted pipeline.

---

## Benchmark: Society vs Single Agent

| Metric | Single Agent | APEX Society |
|---|---|---|
| Files generated | 5 | **17–22** |
| Quality score | 91/100 | **96–100/100** |
| Security checks passed | 9/10 | **10/10** |
| CVEs shipped to production | **1 critical** | **0** |
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
| **Measurable efficiency gain over single-agent** | +12–17 files, +5–9 quality score, 1 critical CVE eliminated, 0 secrets in production |

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

All 9 agents route through Alibaba Cloud DashScope:

```python
# core/ai/provider.py
ENDPOINT = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions"
PRIMARY   = "qwen3.7-max"   # 1M context, agent-tuned
VISION    = "qwen3.7-plus"  # multimodal wireframe input
```

**Deployment:** Alibaba Cloud ECS, ap-southeast-1 (Singapore) — `47.84.135.232:8000`

```bash
python alibaba_cloud_proof.py
# ✓ ALIBABA CLOUD CONNECTION VERIFIED
# ✓ APEX SOCIETY IS RUNNING ON ALIBABA CLOUD
```

---

## MCP Integration

```bash
curl http://47.84.135.232:8000/mcp/tools          # list tools
curl http://47.84.135.232:8000/mcp/schema         # full schema
curl -X POST http://47.84.135.232:8000/mcp/tools/plan_project \
  -H "Content-Type: application/json" \
  -d '{"request":"build a todo API","name":"myapp"}'
```

---

## Quick Start

```bash
git clone https://github.com/mahak867/ai-dev-engine
cd ai-dev-engine
pip install -r requirements.txt
cp .env.example .env          # add QWEN_API_KEY
uvicorn server:app --host 0.0.0.0 --port 8000
# open http://localhost:8000
```

---

## Run the Benchmark

```bash
python benchmark.py
# Single agent vs 9-agent society — files, quality, CVE comparison
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
│   ├── agents/base.py        # All 9 agent implementations
│   ├── ai/provider.py        # Qwen Cloud router + retry logic
│   └── memory/store.py       # Persistent session memory
└── tests/test_apex.py        # 35 tests passing
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `QWEN_API_KEY` | ✅ | From home.qwencloud.com/api-keys |
| `GROQ_API_KEY` | Optional | Free fallback |

---

*Built for the Global AI Hackathon Series with Qwen Cloud — Track 3: Agent Society*
*Submitted by Mahak Fahad — June 2026 | [github.com/mahak867/ai-dev-engine](https://github.com/mahak867/ai-dev-engine)*
