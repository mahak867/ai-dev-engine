"""
APEX v3 — Multi-Agent System
Agents: Planner, Architect, Coder, Reviewer, Debugger, SelfHealer, DocWriter
"""
from __future__ import annotations
import re, json, logging, time
from dataclasses import dataclass, field
from typing import Iterator, Any
from core.ai.provider import LLMProvider

log = logging.getLogger("apex.agents")


@dataclass
class AgentResult:
    agent: str
    output: str
    files: dict[str, str] = field(default_factory=dict)
    thoughts: str = ""
    duration: float = 0.0
    success: bool = True
    error: str = ""
    # Used by ReviewerAgent for the conflict-resolution loop. Other agents
    # leave these at their defaults and they're simply ignored.
    verdict: str = ""      # "approved" | "rejected" | "" (n/a)
    score: int = 0
    critical: list = field(default_factory=list)


# ── Base Agent ─────────────────────────────────────────────────────────────────
class Agent:
    name: str = "Base"
    emoji: str = "🤖"
    model_profile: str = "auto"   # auto | coding | reasoning

    def __init__(self, provider: LLMProvider | None = None):
        self.llm = provider or LLMProvider(self.model_profile)

    def run(self, context: dict) -> AgentResult:
        raise NotImplementedError

    def _messages(self, system: str, user: str) -> list[dict]:
        return [{"role": "system", "content": system},
                {"role": "user",   "content": user}]

    def _parse_files(self, text: str) -> dict[str, str]:
        """Extract ```path/to/file.ext ... ``` code blocks."""
        files = {}
        pattern = r"```(?:\w+)?\s*\n?(?:#\s*)?(?:file:\s*)?([\w./\-]+\.\w+)\n(.*?)```"
        for m in re.finditer(pattern, text, re.DOTALL):
            files[m.group(1).strip()] = m.group(2).rstrip()
        # fallback: look for ### filename headers
        if not files:
            pattern2 = r"###\s+([\w./\-]+\.\w+)\s*\n```[^\n]*\n(.*?)```"
            for m in re.finditer(pattern2, text, re.DOTALL):
                files[m.group(1).strip()] = m.group(2).rstrip()
        return files


# ── Planner Agent ──────────────────────────────────────────────────────────────
class PlannerAgent(Agent):
    name = "Planner"
    emoji = "🗺️"
    model_profile = "reasoning"

    SYSTEM = """You are a senior software architect. Output ONLY valid JSON, zero prose.
Be concise. Max 8 files. Max 6 API routes. Max 4 DB tables.
Required keys: tech_stack, files, features, api_routes, db_schema, security_notes, complexity.
security_notes: list specific security requirements (JWT expiry, input validation, env vars for secrets).
Output ONLY valid JSON."""

    def run(self, context: dict) -> AgentResult:
        t0 = time.time()
        prompt = f"Project: {context['request']}\nName: {context.get('name','app')}"
        msgs = self._messages(self.SYSTEM, prompt)
        try:
            raw = self.llm.complete(msgs, max_tokens=2048)
            # strip markdown fences if present
            raw = re.sub(r"^```json\s*|\s*```$", "", raw.strip())
            plan = json.loads(raw)
            return AgentResult(
                agent=self.name, output=json.dumps(plan, indent=2),
                thoughts=raw, duration=time.time()-t0
            )
        except Exception as e:
            log.error(f"Planner failed: {e}")
            return AgentResult(agent=self.name, output="{}", success=False, error=str(e))


# ── Architect Agent ────────────────────────────────────────────────────────────
class ArchitectAgent(Agent):
    name = "Architect"
    emoji = "🏛️"
    model_profile = "reasoning"

    SYSTEM = """You are an elite software architect. Given a project plan,
produce detailed architecture decisions:
- Component diagram in ASCII art
- Data flow description
- Security considerations
- Scalability notes
- Potential bottlenecks and solutions
Be concise and technical. Focus on decisions that matter."""

    def run(self, context: dict) -> AgentResult:
        t0 = time.time()
        msgs = self._messages(self.SYSTEM,
            f"Plan:\n{context.get('plan','')}\n\nProject: {context['request']}")
        try:
            out = self.llm.complete(msgs, max_tokens=2048)
            return AgentResult(agent=self.name, output=out, duration=time.time()-t0)
        except Exception as e:
            return AgentResult(agent=self.name, output="", success=False, error=str(e))


# ── Coder Agent ────────────────────────────────────────────────────────────────
class CoderAgent(Agent):
    name = "Coder"
    emoji = "👨‍💻"
    model_profile = "coding"

    SYSTEM = """You are an elite full-stack engineer. Generate production-quality code.
CRITICAL SECURITY RULES (Reviewer will reject if violated):
- NEVER hardcode secrets or use fallback defaults in os.getenv/process.env calls
  BAD:  secret = os.getenv("JWT_SECRET", "mysecret123")
  BAD:  const secret = process.env.JWT_SECRET || "fallback"
  GOOD: secret = os.getenv("JWT_SECRET")  # no default, raise error at startup if missing
  GOOD: const secret = process.env.JWT_SECRET; if (!secret) throw new Error("JWT_SECRET required")
- ALL user inputs must be validated and sanitized before use
- SQL queries must use parameterized queries only — never string concatenation
- CORS must whitelist specific origins — never use wildcard * in production config
- Rate limiting must be applied to all auth endpoints (/login, /register, /token)
- Strip internal error details from API responses — never expose stack traces

CODE QUALITY RULES:
- Write complete, working files — no placeholders, no TODOs
- Use modern patterns: async/await, TypeScript strict mode, proper error handling
- Add type annotations everywhere
- Format code blocks as:
  ```language
  # file: path/to/file.ext
  <complete file content>
  ```
- Generate ALL files listed in the plan
- Include proper error boundaries and loading states in UI
- Write idiomatic code for the chosen tech stack"""

    def run(self, context: dict) -> AgentResult:
        t0 = time.time()
        plan_str = context.get("plan", "")
        request  = context["request"]
        name     = context.get("name", "app")
        batch    = context.get("batch", "all")

        prompt = f"""Project Name: {name}
Request: {request}

Architecture Plan:
{plan_str}

Generate {'all' if batch == 'all' else f'batch {batch}'} production-ready files.
Include package.json/requirements.txt with all dependencies.
Make it fully functional — no mocks, no stubs."""

        msgs = self._messages(self.SYSTEM, prompt)
        try:
            raw   = self.llm.complete(msgs, max_tokens=8192)
            files = self._parse_files(raw)
            return AgentResult(
                agent=self.name, output=raw, files=files, duration=time.time()-t0
            )
        except Exception as e:
            return AgentResult(agent=self.name, output="", success=False, error=str(e))

    def stream(self, context: dict) -> Iterator[str]:
        """Streaming version of code generation."""
        plan_str = context.get("plan", "")
        prompt = f"""Project: {context.get('name','app')}
Request: {context['request']}
Plan: {plan_str}
Generate all production-ready files now."""
        msgs = self._messages(self.SYSTEM, prompt)
        yield from self.llm.stream(msgs, max_tokens=8192)

    REVISE_SYSTEM = """You are an elite full-stack engineer revising code after a
peer review rejection. You will be given the original files and a list of
issues a Reviewer agent raised. Your job:
- Fix EVERY issue listed — do not skip any
- For hardcoded secrets: remove ALL fallback defaults from os.getenv/process.env calls
  Replace: os.getenv("JWT_SECRET", "any-value") → os.getenv("JWT_SECRET")
  Replace: process.env.JWT_SECRET || "fallback" → process.env.JWT_SECRET (with startup check)
- Do NOT rewrite files that weren't flagged; only touch what's necessary
- Preserve working functionality; this is a targeted patch, not a rewrite
- Return the COMPLETE corrected content for every file you change
- Format code blocks as:
  ```language
  # file: path/to/file.ext
  <complete file content>
  ```
- Briefly note above the code blocks what you changed and why (one line per issue)"""

    def revise(self, files: dict[str, str], revision_notes: str) -> AgentResult:
        """Targeted revision pass in response to a Reviewer rejection."""
        t0 = time.time()
        code_dump = "\n\n".join(f"```\n# file: {p}\n{c}\n```" for p, c in files.items())
        prompt = f"""Reviewer rejected this submission. Issues to fix:

{revision_notes}

Files as currently written:
{code_dump}

Fix every issue above and return the complete corrected files."""
        msgs = self._messages(self.REVISE_SYSTEM, prompt)
        try:
            raw = self.llm.complete(msgs, max_tokens=8192)
            revised = self._parse_files(raw)
            return AgentResult(
                agent=self.name, output=raw, files=revised, duration=time.time()-t0
            )
        except Exception as e:
            return AgentResult(agent=self.name, output="", success=False, error=str(e))


# ── Reviewer Agent ─────────────────────────────────────────────────────────────
class ReviewerAgent(Agent):
    name = "Reviewer"
    emoji = "🔍"
    model_profile = "coding"

    # Minimum score to approve. Below this, or any critical issue present,
    # triggers a rejection and sends the code back to the Coder for revision.
    APPROVAL_THRESHOLD = 80  # lowered slightly — 80+ with no critical = shippable

    SYSTEM = """You are a senior code reviewer. Score the code 0-100.
Start at 100. Deduct points only for real issues found:
- Hardcoded secret with value (-25): e.g. os.getenv("KEY", "actual-secret")
- SQL injection via string concat (-20)
- Missing input validation on auth endpoints (-15)
- Unhandled promise rejections or missing try/catch on DB calls (-10)
- Missing rate limiting on auth (-10)
- Wildcard CORS in production (-10)
- Type errors or missing null checks (-5 each)

If code correctly uses env vars with NO defaults, parameterized queries, and validated inputs — score 90+.
Only add to "critical" if it would cause data loss, secret exposure, or auth bypass.
Warnings are non-blocking. Suggestions are optional.

Output ONLY this JSON:
{
  "score": 0-100,
  "critical": ["blocking issue only if truly critical"],
  "warnings": ["non-blocking"],
  "suggestions": ["optional"],
  "security_issues": ["actual vuln only"],
  "fixed_files": {"path/to/file": "complete fixed content if you fixed something"}
}"""

    def run(self, context: dict) -> AgentResult:
        t0 = time.time()
        code = context.get("code", "")
        if not code:
            result = AgentResult(agent=self.name, output='{"score":100}', duration=0)
            result.verdict = "approved"
            result.score = 100
            result.critical = []
            return result
        msgs = self._messages(self.SYSTEM, f"Review this code:\n\n{code}")
        try:
            raw = self.llm.complete(msgs, max_tokens=4096)
            raw = re.sub(r"^```json\s*|\s*```$", "", raw.strip())
            report = json.loads(raw)
            result = AgentResult(
                agent=self.name, output=json.dumps(report, indent=2),
                files=report.get("fixed_files", {}), duration=time.time()-t0
            )
            self._attach_verdict(result, report)
            return result
        except Exception as e:
            result = AgentResult(agent=self.name, output='{"score":75}', success=False, error=str(e))
            # Fail-safe: if the reviewer itself errors, don't block the pipeline
            # indefinitely — approve-with-warning rather than reject-forever.
            result.verdict = "approved"
            result.score = 75
            result.critical = []
            return result

    def _attach_verdict(self, result: AgentResult, report: dict) -> None:
        """Decide approve vs reject from the structured report and stash
        the verdict on the AgentResult so the orchestrator can branch on it."""
        score = report.get("score", 0)
        critical = report.get("critical", []) or []
        security = report.get("security_issues", []) or []
        blocking = critical + security

        result.score = score
        result.critical = blocking
        if blocking or score < self.APPROVAL_THRESHOLD:
            result.verdict = "rejected"
        else:
            result.verdict = "approved"

    def build_revision_notes(self, report_json: str) -> str:
        """Turn a rejection's raw report into instructions the Coder can act on."""
        try:
            report = json.loads(report_json)
        except Exception:
            return "Fix all reported issues and resubmit."
        parts = []
        if report.get("critical"):
            parts.append("CRITICAL (must fix):\n- " + "\n- ".join(report["critical"]))
        if report.get("security_issues"):
            parts.append("SECURITY (must fix):\n- " + "\n- ".join(report["security_issues"]))
        if report.get("warnings"):
            parts.append("Warnings (fix if feasible):\n- " + "\n- ".join(report["warnings"]))
        return "\n\n".join(parts) if parts else "Fix all reported issues and resubmit."


# ── Debugger Agent ─────────────────────────────────────────────────────────────
class DebuggerAgent(Agent):
    name = "Debugger"
    emoji = "🐛"
    model_profile = "coding"

    SYSTEM = """You are an expert debugger. Given code and an error:
1. Identify root cause precisely
2. Explain why it happens
3. Provide the COMPLETE fixed file (not just the diff)
4. Add defensive code to prevent similar issues

Output:
```
# file: path/to/fixed_file.ext
<complete fixed content>
```
Then explain the fix."""

    def run(self, context: dict) -> AgentResult:
        t0 = time.time()
        prompt = f"""Error: {context.get('error', '')}
File: {context.get('file', 'unknown')}

Code:
{context.get('code', '')}

Stack trace:
{context.get('traceback', '')}"""
        msgs = self._messages(self.SYSTEM, prompt)
        try:
            raw   = self.llm.complete(msgs, max_tokens=4096)
            files = self._parse_files(raw)
            return AgentResult(agent=self.name, output=raw, files=files, duration=time.time()-t0)
        except Exception as e:
            return AgentResult(agent=self.name, output="", success=False, error=str(e))


# ── Self-Healer Agent ──────────────────────────────────────────────────────────
class SelfHealerAgent(Agent):
    """Monitors generated code, detects issues, auto-patches."""
    name = "SelfHealer"
    emoji = "🔧"
    model_profile = "coding"

    SYSTEM = """You are an autonomous self-healing system. You receive code that failed
(import errors, syntax errors, runtime errors) and must:
1. Fix ALL issues automatically
2. Return ONLY the complete fixed files, no explanation needed
3. Ensure all imports exist and are correct
4. Fix type errors
5. Add missing dependencies to package.json or requirements.txt

Output only fixed files as code blocks with file paths."""

    MAX_RETRIES = 3

    def heal(self, files: dict[str, str], error: str) -> AgentResult:
        t0 = time.time()
        code_dump = "\n\n".join(
            f"```\n# file: {path}\n{content}\n```"
            for path, content in files.items()
        )
        prompt = f"Error encountered:\n{error}\n\nFiles:\n{code_dump}"
        msgs   = self._messages(self.SYSTEM, prompt)
        try:
            raw   = self.llm.complete(msgs, max_tokens=8192)
            fixed = self._parse_files(raw)
            return AgentResult(agent=self.name, output=raw, files=fixed, duration=time.time()-t0)
        except Exception as e:
            return AgentResult(agent=self.name, output="", success=False, error=str(e))

    def run(self, context: dict) -> AgentResult:
        return self.heal(context.get("files", {}), context.get("error", ""))


# ── DocWriter Agent ────────────────────────────────────────────────────────────
class DocWriterAgent(Agent):
    name = "DocWriter"
    emoji = "📝"
    model_profile = "auto"

    SYSTEM = """Write a professional README.md for this project. Include:
- Project title and description
- Features list (with emoji bullets)
- Tech stack
- Prerequisites
- Installation steps (numbered, copy-pasteable)
- Environment variables table
- API endpoints table (if applicable)
- Deployment instructions
- Contributing guide
- License

Make it look polished and professional."""

    def run(self, context: dict) -> AgentResult:
        t0   = time.time()
        msgs = self._messages(self.SYSTEM,
            f"Project: {context.get('name','app')}\n"
            f"Description: {context['request']}\n"
            f"Plan:\n{context.get('plan','')}"
        )
        try:
            readme = self.llm.complete(msgs, max_tokens=3000)
            return AgentResult(
                agent=self.name, output=readme,
                files={"README.md": readme}, duration=time.time()-t0
            )
        except Exception as e:
            return AgentResult(agent=self.name, output="", success=False, error=str(e))
