# APEX Society — Qwen Cloud AI Hackathon | Track 3: Agent Society

> A production-grade multi-agent system where 7 specialized AI agents collaborate, negotiate, and self-correct to build full-stack applications — powered entirely by Qwen Cloud.

**[Global AI Hackathon Series with Qwen Cloud](https://qwencloud-hackathon.devpost.com/) — Track 3: Agent Society**

---

## What It Does

APEX Society orchestrates 7 specialized Qwen-powered agents that work together to build production-ready code from a single sentence. Each agent has a distinct role, communicates structured outputs to the next, and the system self-corrects automatically when issues arise.

The key insight: **a society of specialized agents consistently outperforms a single generalist agent** — both in code quality and security.

---

## Benchmark Results

| Metric | Single Agent | Agent Society |
|---|---|---|
| Time | 69.3s | 182.9s |
| Files generated | 5 | **11** |
| Quality score | 91/100 | **100/100** |
| Security checks passed | 9/10 | **10/10** |
| CVEs shipped to production | **1 critical** | **0** |
| Agents coordinating | 1 | **7** |

**The critical finding:** The single agent shipped a hardcoded JWT secret fallback (`SECRET_KEY = os.getenv("SECRET_KEY", "09d25e094faa...")`) — a CVE-level vulnerability. The Reviewer agent caught it at t=185s. The SelfHealer patched it automatically at t=192s. Zero secrets in production.

```
Track 3 requirement: "measurable efficiency gain over single-agent baselines"
Result: +9 files, +9 quality points, 1 critical CVE eliminated
```

---

## Agent Society Architecture

```
User Input (task description)
        │
        ▼
┌─────────────────────────────────────────┐
│           FastAPI WebSocket Server       │
│              (server.py)                 │
└─────────────────┬───────────────────────┘
                  │  real-time events
                  ▼
┌─────────────────────────────────────────┐
│          APEX Orchestrator               │
│         (core/orchestrator.py)           │
└──┬──────────────────────────────────────┘
   │
   ├─▶ 🗺  Planner      → JSON plan (tech stack, files, API routes, DB schema)
   │         │
   ├─▶ 🏛  Architect   → Architecture decisions, security notes
   │         │
   ├─▶ 👨‍💻 Coder       → Production code generation
   │         │
   ├─▶ 🔍 Reviewer    → Security audit, quality scoring, CVE detection
   │         │  (sends feedback back to Coder if issues found)
   ├─▶ 🔧 SelfHealer  → Auto-patches vulnerabilities and bugs
   │         │
   ├─▶ 🐛 Debugger    → Runtime error detection
   │         │
   └─▶ 📝 DocWriter   → Professional README generation
              │
              ▼
┌─────────────────────────────────────────┐
│    Qwen Cloud API (dashscope-intl)       │
│    Model: qwen-plus / qwen-turbo         │
│    Endpoint: dashscope-intl.aliyuncs.com │
└─────────────────────────────────────────┘
              │
              ▼
    Generated Project (12 files avg)
    Quality Score: 100/100
    CVEs: 0
```

---

## Track 3 Requirements Met

| Requirement | Implementation |
|---|---|
| Multiple agents with distinct capabilities | 7 agents: Planner, Architect, Coder, Reviewer, SelfHealer, Debugger, DocWriter |
| Task decomposition and role assignment | Planner outputs structured JSON plan distributed to all agents |
| Resolving disagreements and execution conflicts | Reviewer sends quality feedback; SelfHealer patches conflicts automatically |
| Measurable efficiency gain over single-agent | +9 files, +9 quality score, -1 CVE vs single agent (see benchmark) |

---

## Live Dashboard

Real-time visualization of the agent society at work — built with SVG `animateMotion`, force-directed graph, and WebSocket streaming.

```bash
# Start the server
uvicorn server:app --reload --port 8000

# Open dashboard
http://127.0.0.1:8000
```

Features:
- **Animated agent graph** — nodes light up when active, dots travel along edges showing agent-to-agent communication
- **Live execution log** — every agent event streams in real time
- **Security panel** — CVE detection shown live during Reviewer phase
- **Benchmark view** — side-by-side comparison vs single agent
- **Keyboard navigation** — press 1-3 to switch views

---

## Alibaba Cloud Integration

All inference runs through Alibaba Cloud's DashScope service:

```python
# core/ai/provider.py — all 7 agents route through here
ALIBABA_CLOUD_ENDPOINT = (
    "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions"
)
```

Verify the connection:
```bash
python alibaba_cloud_proof.py
# Output: ✓ ALIBABA CLOUD CONNECTION VERIFIED
```

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/mahak867/ai-dev-engine
cd ai-dev-engine

# 2. Install
pip install -r requirements.txt

# 3. Set API keys
cp .env.example .env
# Add: QWEN_API_KEY=your_key (from home.qwencloud.com/api-keys)

# 4. Start the server
uvicorn server:app --reload --port 8000

# 5. Open dashboard at http://127.0.0.1:8000
# Click RUN — watch 7 agents collaborate live

# Or use CLI directly
python cli.py generate "build a REST API with auth" --name myapp
```

---

## Run the Benchmark

```bash
python benchmark.py
# Runs single agent vs agent society on identical task
# Shows quality scores, files generated, CVE detection
```

---

## Project Structure

```
apex-society/
├── server.py                 # FastAPI WebSocket backend
├── dashboard.html            # Live agent visualization UI
├── benchmark.py              # Single vs society comparison
├── alibaba_cloud_proof.py    # Alibaba Cloud connection verification
├── cli.py                    # CLI interface
├── core/
│   ├── orchestrator.py       # Agent pipeline coordinator
│   ├── agents/
│   │   └── base.py           # All 7 agent implementations
│   ├── ai/
│   │   └── provider.py       # Qwen Cloud API router
│   └── memory/
│       └── store.py          # Persistent session memory
└── tests/
    └── test_apex.py          # Test suite (32 passing)
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `QWEN_API_KEY` | ✅ Required | From home.qwencloud.com/api-keys |
| `GROQ_API_KEY` | Optional | Fallback provider |

---

## Built With

- **Qwen Cloud** — qwen-plus / qwen-turbo via DashScope API
- **FastAPI + WebSockets** — real-time agent event streaming
- **SVG animateMotion** — live agent graph animations
- **Python** — orchestration, agents, benchmark

---

*Built for the Global AI Hackathon Series with Qwen Cloud — Track 3: Agent Society*
*Submission by Mahak Fahad — June 2026*
