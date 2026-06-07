# APEX Society — Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        USER                                  │
│              (types task in dashboard)                       │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP / WebSocket
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              LIVE DASHBOARD (dashboard.html)                 │
│   SVG force graph · animateMotion dots · ghost characters    │
│   Real-time log · Benchmark view · Security panel           │
└──────────────────────┬──────────────────────────────────────┘
                       │ WebSocket ws://localhost:8000/ws
                       ▼
┌─────────────────────────────────────────────────────────────┐
│            FASTAPI WEBSOCKET SERVER (server.py)              │
│   Session management · Event broadcasting · REST API        │
│   /ws · /api/health · /api/sessions · /api/sessions/{id}   │
└──────────────────────┬──────────────────────────────────────┘
                       │ Python function calls
                       ▼
┌─────────────────────────────────────────────────────────────┐
│          APEX ORCHESTRATOR (core/orchestrator.py)            │
│   Coordinates 7 agents · Routes context · Emits events     │
└──┬───────────────────────────────────────────────────────┬──┘
   │                                                       │
   │ Sequential pipeline with feedback loops               │
   ▼                                                       ▼
┌──────────────────────────────────────────────────────────────┐
│                    7 SPECIALIZED AGENTS                       │
│                  (core/agents/base.py)                        │
│                                                               │
│  🗺 Planner    → JSON plan (stack, files, routes, schema)     │
│       ↓                                                       │
│  🏛 Architect  → Architecture decisions + security notes      │
│       ↓                                                       │
│  👨‍💻 Coder      → Production code generation (all files)      │
│       ↓                                                       │
│  🔍 Reviewer   → Security audit · CVE detection · scoring    │
│       ↓ (sends issues back if found)                         │
│  🔧 SelfHealer → Auto-patches vulnerabilities + bugs         │
│       ↓                                                       │
│  🐛 Debugger   → Runtime error detection + fixes             │
│       ↓                                                       │
│  📝 DocWriter  → Professional README generation              │
└──────────────────────┬───────────────────────────────────────┘
                       │ HTTPS API calls
                       ▼
┌─────────────────────────────────────────────────────────────┐
│         ALIBABA CLOUD — DASHSCOPE API                        │
│   Endpoint: dashscope-intl.aliyuncs.com                     │
│   Region: Singapore (ap-southeast-1)                         │
│   Models: qwen-plus · qwen-turbo                            │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│               GENERATED OUTPUT                               │
│   12 production files · Quality 100/100 · 0 CVEs           │
│   Saved to runs/{session_id}/                               │
└─────────────────────────────────────────────────────────────┘

SECURITY BOUNDARY
─────────────────
Prompt-based:  Agents instructed not to modify original inputs
Architectural: Output written only to runs/ directory
MCP layer:     8 typed tool functions — no raw shell execution exposed
Evidence:      alibaba_cloud_proof.py verifies live connection

AGENT COMMUNICATION PROTOCOL
──────────────────────────────
Each agent receives structured context dict:
  {request, name, plan, architecture, code, review_notes}
Each agent returns AgentResult:
  {output: str, files: dict[str,str], success: bool, agent: str}
Reviewer can flag issues → SelfHealer receives issue list → patches code
This constitutes agent-to-agent negotiation on code quality
```
