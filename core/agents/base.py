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

    SYSTEM = """You are a senior software architect and project planner.
Given a project idea, output a precise JSON plan with:
- "tech_stack": {frontend, backend, database, deployment}
- "files": ["list", "of", "all", "files", "to", "create"]
- "features": ["feature1", ...]
- "api_routes": [{"method": "GET", "path": "/api/x", "desc": "..."}]
- "db_schema": ["table: fields..."]
- "steps": ["step1", "step2", ...]
- "complexity": "low|medium|high"
Output ONLY valid JSON, no prose."""

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
Rules:
- Write complete, working files — no placeholders, no TODOs
- Use modern patterns: async/await, TypeScript strict mode, proper error handling
- Include proper imports and exports
- Add type annotations everywhere
- Format code blocks as:
  ```language
  # file: path/to/file.ext
  <complete file content>
  ```
- Generate ALL files listed in the plan
- Use environment variables for secrets (never hardcode)
- Include error boundaries and loading states in UI
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


# ── Reviewer Agent ─────────────────────────────────────────────────────────────
class ReviewerAgent(Agent):
    name = "Reviewer"
    emoji = "🔍"
    model_profile = "coding"

    SYSTEM = """You are a senior code reviewer. Analyze code for:
1. Bugs and logic errors
2. Security vulnerabilities (XSS, SQLi, secrets in code, etc.)
3. Performance issues
4. Missing error handling
5. Type safety issues
6. Missing edge cases

Output a JSON report:
{
  "score": 0-100,
  "critical": ["issue1", ...],
  "warnings": ["warn1", ...],
  "suggestions": ["tip1", ...],
  "security_issues": ["sec1", ...],
  "fixed_files": {"path": "fixed content"}
}"""

    def run(self, context: dict) -> AgentResult:
        t0 = time.time()
        code = context.get("code", "")
        if not code:
            return AgentResult(agent=self.name, output='{"score":100}', duration=0)
        msgs = self._messages(self.SYSTEM, f"Review this code:\n\n{code}")
        try:
            raw = self.llm.complete(msgs, max_tokens=4096)
            raw = re.sub(r"^```json\s*|\s*```$", "", raw.strip())
            report = json.loads(raw)
            return AgentResult(
                agent=self.name, output=json.dumps(report, indent=2),
                files=report.get("fixed_files", {}), duration=time.time()-t0
            )
        except Exception as e:
            return AgentResult(agent=self.name, output='{"score":75}', success=False, error=str(e))


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
