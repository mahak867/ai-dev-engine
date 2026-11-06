"""
APEX Society — real MCP server (official Model Context Protocol Python SDK).

Exposes the 9-agent society to any MCP client (Claude Desktop, Claude Code,
Cursor, VS Code…):

  * 7 single-agent tools  — plan_project, design_architecture, generate_code,
    review_code, heal_code, debug_error, write_documentation (text in, text out;
    no file writes, no shell)
  * generate_project      — the full 9-agent pipeline (Planner ∥ Architect →
    Coder ⇄ Reviewer → SelfHealer → Debugger → Executor → DocWriter, with
    Memory), written under APEX_MCP_OUTPUT_DIR with path containment
  * apex://agents         — resource describing the agents

Transports:
  apex-mcp                      # stdio (what Claude Desktop launches)
  apex-mcp --http               # Streamable HTTP on 127.0.0.1:8002/mcp
  APEX_API_TOKEN=... apex-mcp --http --host 0.0.0.0   # bearer token required

HTTP mode uses the SDK's DNS-rebinding protection (Host/Origin allowlists) and
refuses non-loopback binds without APEX_API_TOKEN.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from core.agent_tools import adapt_inputs

AGENTS = [
    {"name": "Planner", "kind": "llm", "role": "turns the request into a JSON plan (stack, files, routes, schema, security notes)"},
    {"name": "Architect", "kind": "llm", "role": "designs structure and patterns; runs in parallel with Planner"},
    {"name": "Coder", "kind": "llm", "role": "writes every file; revises when the Reviewer rejects"},
    {"name": "Reviewer", "kind": "llm", "role": "scores 0-100 and rejects on critical/security issues (up to 3 rounds)"},
    {"name": "SelfHealer", "kind": "llm", "role": "patches code from reviewer leftovers and real sandbox failures"},
    {"name": "Debugger", "kind": "llm", "role": "checks for runtime errors (imports, undefined names, startup crashes)"},
    {"name": "Executor", "kind": "tool", "role": "syntax-checks, then runs the project in a network-less Docker sandbox"},
    {"name": "DocWriter", "kind": "llm", "role": "writes the README"},
    {"name": "Memory", "kind": "tool", "role": "stores lessons from past runs and injects them into new ones"},
]

MAX_TEXT = int(os.environ.get("APEX_MAX_TOOL_INPUT_CHARS", "20000"))
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


def _clip(s: str, limit: int = MAX_TEXT) -> str:
    s = s or ""
    if len(s) > limit:
        raise ValueError(f"input exceeds {limit} characters")
    return s


# ── agent plumbing (shared with mcp_server.py's REST adapter) ────────────────
_lock = threading.Lock()
_agents: dict[str, Any] | None = None


def agents() -> dict[str, Any]:
    global _agents
    with _lock:
        if _agents is None:
            from core.agents.base import (ArchitectAgent, CoderAgent, DebuggerAgent, DocWriterAgent,
                                          PlannerAgent, ReviewerAgent, SelfHealerAgent)
            from core.ai.provider import LLMProvider
            llm, coding = LLMProvider("auto"), LLMProvider("coding")
            _agents = {
                "plan_project": PlannerAgent(LLMProvider("reasoning")),
                "design_architecture": ArchitectAgent(llm),
                "generate_code": CoderAgent(coding),
                "review_code": ReviewerAgent(coding),
                "heal_code": SelfHealerAgent(coding),
                "debug_error": DebuggerAgent(coding),
                "write_documentation": DocWriterAgent(llm),
            }
        return _agents


def call_agent(tool: str, inputs: dict) -> dict:
    from core import telemetry
    tracker = telemetry.UsageTracker()
    with telemetry.track(tracker):
        result = agents()[tool].run(adapt_inputs(tool, inputs))
    out = {"agent": result.agent, "success": result.success, "output": result.output,
           "files": result.files, "usage": tracker.summary()}
    if result.error:
        out["error"] = result.error
    if tool == "review_code":
        out.update(verdict=result.verdict, score=result.score, critical=result.critical)
    return out


# ── server ────────────────────────────────────────────────────────────────────
def build_server(host: str = "127.0.0.1", port: int = 8002) -> FastMCP:
    allowed_hosts = [h.strip() for h in os.environ.get(
        "APEX_ALLOWED_HOSTS", f"localhost:{port},127.0.0.1:{port},[::1]:{port}").split(",") if h.strip()]
    allowed_origins = [o.strip() for o in os.environ.get(
        "APEX_ALLOWED_ORIGINS", f"http://localhost:{port},http://127.0.0.1:{port}").split(",") if o.strip()]
    mcp = FastMCP(
        "apex-society",
        instructions=("APEX Society: a 9-agent software team. Use generate_project to build a whole "
                      "project end to end, or the single-agent tools (plan_project, generate_code, "
                      "review_code, …) to use one specialist."),
        host=host, port=port,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=allowed_hosts, allowed_origins=allowed_origins),
    )

    async def _run(tool: str, **inputs) -> dict:
        import anyio
        return await anyio.to_thread.run_sync(lambda: call_agent(tool, inputs))

    @mcp.tool()
    async def plan_project(request: str, name: str = "app") -> dict:
        """Planner agent: turn a project request into a JSON plan (tech stack, files, API routes, DB schema, security notes)."""
        return await _run("plan_project", request=_clip(request), name=name[:64])

    @mcp.tool()
    async def design_architecture(plan: str, request: str) -> dict:
        """Architect agent: design the system architecture for a plan."""
        return await _run("design_architecture", plan=_clip(plan), request=_clip(request))

    @mcp.tool()
    async def generate_code(request: str, plan: str = "", architecture: str = "", name: str = "app") -> dict:
        """Coder agent: generate every file for the project. Returns {path: content}; nothing is written to disk."""
        return await _run("generate_code", request=_clip(request), plan=_clip(plan),
                          architecture=_clip(architecture), name=name[:64])

    @mcp.tool()
    async def review_code(code: str) -> dict:
        """Reviewer agent: security/quality review. Returns score 0-100, verdict approved/rejected and critical issues."""
        return await _run("review_code", code=_clip(code))

    @mcp.tool()
    async def heal_code(files: dict[str, str], issues: list[str]) -> dict:
        """SelfHealer agent: fix the listed issues in the given files. Returns patched files."""
        if len(json.dumps(files)) > MAX_TEXT * 2:
            raise ValueError("files too large")
        return await _run("heal_code", files=files, issues=[_clip(str(x), 2000) for x in issues[:50]])

    @mcp.tool()
    async def debug_error(code: str, error: str, traceback: str = "") -> dict:
        """Debugger agent: find and fix the cause of an error."""
        return await _run("debug_error", code=_clip(code), error=_clip(error, 5000), traceback=_clip(traceback, 10000))

    @mcp.tool()
    async def write_documentation(name: str, code: str, plan: str = "", request: str = "") -> dict:
        """DocWriter agent: write a README for the project."""
        return await _run("write_documentation", name=name[:64], code=_clip(code), plan=_clip(plan),
                          request=_clip(request) or name)

    @mcp.tool()
    async def generate_project(request: str, name: str, ctx: Context) -> dict:
        """
        Run the full 9-agent pipeline and write the project to disk under
        APEX_MCP_OUTPUT_DIR (default ~/apex-projects). Returns the path, file list,
        reviewer score, sandbox result (if APEX_SANDBOX=docker) and per-agent token usage.
        """
        import anyio
        if not _NAME_RE.match(name or ""):
            raise ValueError("name must be 1-64 chars: letters, digits, '-', '_'")
        request = _clip(request, 4000)
        out_root = Path(os.environ.get("APEX_MCP_OUTPUT_DIR", "~/apex-projects")).expanduser()
        out_root.mkdir(parents=True, exist_ok=True)
        events: list[str] = []

        def work() -> dict:
            from core import telemetry
            from core.orchestrator import Orchestrator
            tracker = telemetry.UsageTracker()
            final: dict = {}

            def on_event(agent, status, msg, extra=None):
                events.append(f"[{agent}] {status}: {msg}"[:300])
                if extra and "quality_score" in extra:
                    final.update(extra)

            with telemetry.track(tracker):
                orch = Orchestrator(model="auto", on_event=on_event)
                path = orch.generate_fullstack(name=name, request=request, output_dir=str(out_root))
            files = sorted(str(p.relative_to(path)) for p in Path(path).rglob("*") if p.is_file())
            return {"path": path, "files": files, "quality_score": final.get("quality_score"),
                    "sandbox": orch.last_sandbox, "usage": tracker.summary(), "log": events[-40:]}

        await ctx.info(f"Starting 9-agent pipeline for {name!r}")
        result = await anyio.to_thread.run_sync(work)
        await ctx.info(f"Done: {len(result['files'])} files at {result['path']}")
        return result

    @mcp.resource("apex://agents")
    def agent_roster() -> str:
        """The 9 agents and what each one does."""
        return json.dumps({"agents": AGENTS, "count": len(AGENTS)}, indent=2)

    return mcp


def _bearer_wrap(app, token: str):
    """Minimal ASGI bearer-token gate for HTTP mode."""
    import hmac

    async def wrapped(scope, receive, send):
        if scope["type"] == "http":
            hdrs = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
            auth = hdrs.get("authorization", "")
            given = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
            if not (given and hmac.compare_digest(given.encode(), token.encode())):
                from starlette.responses import JSONResponse
                return await JSONResponse({"error": "authentication required"}, status_code=401,
                                          headers={"WWW-Authenticate": "Bearer"})(scope, receive, send)
        return await app(scope, receive, send)
    return wrapped


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="apex-mcp", description="APEX Society MCP server")
    ap.add_argument("--http", action="store_true", help="serve Streamable HTTP instead of stdio")
    ap.add_argument("--host", default=os.environ.get("APEX_HOST", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("APEX_MCP_PORT", "8002")))
    args = ap.parse_args(argv)
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    mcp = build_server(args.host, args.port)
    if not args.http:
        mcp.run("stdio")
        return 0

    from core.web_security import is_loopback_host
    token = os.environ.get("APEX_API_TOKEN", "").strip()
    if not is_loopback_host(args.host) and not token:
        print(f"Refusing to bind {args.host!r} without APEX_API_TOKEN.", file=sys.stderr)
        return 2
    import uvicorn
    app = mcp.streamable_http_app()
    if token:
        app = _bearer_wrap(app, token)
    print(f"APEX MCP (Streamable HTTP) on http://{args.host}:{args.port}/mcp", file=sys.stderr)
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
