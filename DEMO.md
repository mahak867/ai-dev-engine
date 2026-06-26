# APEX Society — Live Demo Transcript

> Real output from a live run on Alibaba Cloud ECS Singapore
> Task: `build a REST API with JWT authentication`
> Model: `qwen3.7-max` via Alibaba Cloud DashScope

---

## Run Log

```
0.1s   SYSTEM    starting agent society for: build a REST API with JWT authentication
0s     PLANNER   analyzing requirements...
43s    PLANNER   plan ready — Node.js, Express, PostgreSQL, Prisma, JWT
43.1s  PLANNER   Planner → Architect: plan complete, passing for system design
43s    ARCHITECT designing system architecture...
91.8s  ARCHITECT architecture ready — middleware order, JWT validation, env var names
91.9s  ARCHITECT Architect → Coder: architecture complete, implement all files per plan
91.8s  CODER     generating production code...
298s   CODER     21 files generated
298.6s CODER     Coder → Reviewer: code complete, requesting security audit
298.5s REVIEWER  reviewing code quality & security (round 1)...
442s   REVIEWER  round 1: score 68/100 — 2 blocking issue(s), sent back to Coder
442.7s REVIEWER  Reviewer → Coder: REJECTED (round 1, score 68/100)
                 CRITICAL: hardcoded JWT secret fallback in config.py
                 CRITICAL: missing input validation on /api/auth
442.6s CODER     revising per Reviewer feedback (round 1)...
596s   CODER     revised 2 file(s): auth.py, config.py
596.1s CODER     Coder → Reviewer: revision complete, resubmitting
596s   REVIEWER  reviewing code quality & security (round 2)...
742s   REVIEWER  approved — score 96/100 (round 2)
742.1s REVIEWER  Reviewer → SelfHealer: code APPROVED after 2 rounds, score 96/100
742s   SELFHEAL  running self-healing pass...
766s   SELFHEAL  no issues found
766.1s SELFHEAL  SelfHealer → Debugger: no patches needed, code is clean
766s   DEBUGGER  verifying no runtime errors...
798s   DEBUGGER  no runtime errors found
798.1s DEBUGGER  Debugger → DocWriter: runtime check passed
798s   DOCWRITE  writing documentation...
842s   DOCWRITE  README.md generated
842.1s DOCWRITE  DocWriter → System: documentation complete
842s   SYSTEM    project ready — 22 files generated
```

---

## Agent Dialogue (inter-agent messages)

| From | To | Type | Message |
|---|---|---|---|
| Planner | Architect | handoff | Plan complete. Tech stack: Node.js, Express, PostgreSQL, Prisma. Passing for system design. |
| Architect | Coder | handoff | Architecture complete. Middleware order: rate limiter → auth → handler. Use JWT_SECRET env var, no fallback. |
| Coder | Reviewer | handoff | Code generation complete. 21 files produced. Requesting security audit. |
| **Reviewer** | **Coder** | **request** | **REJECTED (round 1, score 68/100). CRITICAL: hardcoded JWT secret fallback `os.getenv("JWT_SECRET", "fallback")` — violates OWASP A3. CRITICAL: missing input validation on /api/auth.** |
| **Coder** | **Reviewer** | **patch** | **Revision complete for round 1. Patched 2 file(s): auth.py, config.py. Resubmitting for review.** |
| Reviewer | SelfHealer | feedback | Code APPROVED after 2 rounds. Score 96/100. No critical issues remain. |
| SelfHealer | Debugger | handoff | No patches needed. Code is clean. Debugger to verify no runtime errors. |
| Debugger | DocWriter | handoff | Runtime check passed. No startup errors detected. |
| DocWriter | System | complete | Documentation complete. README.md generated with full API docs. |

---

## Benchmark: Society vs Single Agent

| Metric | Single Agent | APEX Society |
|---|---|---|
| Files generated | 5 | **22** |
| Quality score | 91/100 | **96/100** |
| CVEs shipped | **1 critical** (hardcoded JWT secret) | **0** |
| Rounds to approval | n/a | 2 |

**The single agent shipped `SECRET_KEY = os.getenv("SECRET_KEY", "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7")` — a hardcoded secret in production code. APEX Society's Reviewer caught it, rejected the code, and verified the fix before anything shipped.**

---

## Live Server

```bash
curl http://47.84.135.232:8000/api/health
# {"status":"ok","sessions":0,"clients":0}

curl http://47.84.135.232:8000/mcp/tools
# lists all 7 agent tools available via MCP

python alibaba_cloud_proof.py
# ✓ ALIBABA CLOUD CONNECTION VERIFIED
# ✓ APEX SOCIETY IS RUNNING ON ALIBABA CLOUD
```
