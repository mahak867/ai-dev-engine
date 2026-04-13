# core/ai/agent_runtime.py
# Agent runtime - routes prompts to commands/tools, manages execution loop
# Pattern from claw-code: PortRuntime with route_prompt and run_session

import time
import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from core.ai.query_engine import QueryEngine, StreamEvent, EventType, TurnResult
from core.ai.tool_registry import ToolRegistry


# ── SLASH COMMANDS ─────────────────────────────────────────────────────────────

SLASH_COMMANDS = {
    "/help":        "Show available commands",
    "/compact":     "Compact the conversation transcript",
    "/model":       "Show or change the current model",
    "/permissions": "Show granted permissions",
    "/cost":        "Show token usage and estimated cost",
    "/session":     "Show session info",
    "/tools":       "List available tools",
    "/memory":      "Show memory stats",
    "/status":      "Show engine status",
    "/clear":       "Clear the transcript",
    "/edit":        "Edit an existing app file",
    "/test":        "Run tests on the project",
    "/deploy":      "Deploy the project",
    "/history":     "Show generation history",
}


@dataclass
class RoutedMatch:
    kind: str       # "command" | "tool" | "generate"
    name: str
    source_hint: str
    score: float
    args: dict = field(default_factory=dict)


class AgentRuntime:
    """
    Routes user input to commands, tools, or generation.
    Manages session persistence and execution loop.
    Pattern: route_prompt + execute_session from claw-code PortRuntime.
    """

    def __init__(self, project_path: str = ".",
                 permissions: Optional[set] = None,
                 session_id: Optional[str] = None):
        self.project_path = Path(project_path)
        self.session_id = session_id or uuid.uuid4().hex
        self.query_engine = QueryEngine(self.session_id)
        self.tools = ToolRegistry(
            str(project_path),
            permissions or {"file.read", "git", "web"}
        )
        self._model = "moonshotai/kimi-k2-instruct"
        self._session_start = time.time()
        self._turn_count = 0

    def route_prompt(self, text: str) -> RoutedMatch:
        """
        Tokenize input and score against commands and tools.
        Returns the best match.
        """
        text = text.strip()

        # Slash command
        if text.startswith("/"):
            cmd = text.split()[0].lower()
            if cmd in SLASH_COMMANDS:
                args = {}
                parts = text.split(maxsplit=1)
                if len(parts) > 1:
                    args["args"] = parts[1]
                return RoutedMatch(
                    kind="command", name=cmd,
                    source_hint="slash_commands", score=1.0,
                    args=args
                )

        # Tool call detection (e.g. "read file app.py", "run tests")
        text_lower = text.lower()
        tool_patterns = {
            "read_file":    ["read file", "show file", "cat ", "open file"],
            "list_dir":     ["list files", "ls ", "show directory", "list directory"],
            "bash":         ["run command", "execute", "bash "],
            "git_status":   ["git status", "what changed"],
            "git_commit":   ["commit changes", "git commit"],
            "syntax_check": ["check syntax", "syntax error"],
            "run_tests":    ["run tests", "test the"],
            "find_todos":   ["find todos", "show todos"],
        }
        for tool_name, patterns in tool_patterns.items():
            for pattern in patterns:
                if pattern in text_lower:
                    if tool_name in self.tools.available_tools():
                        return RoutedMatch(
                            kind="tool", name=tool_name,
                            source_hint="pattern_match", score=0.8,
                            args={"query": text}
                        )

        # Default: generate
        return RoutedMatch(
            kind="generate", name="llm_generate",
            source_hint="default", score=0.5
        )

    def execute_command(self, match: RoutedMatch) -> str:
        """Execute a slash command."""
        cmd = match.name
        args = match.args.get("args", "")

        if cmd == "/help":
            lines = ["Available commands:"]
            for name, desc in SLASH_COMMANDS.items():
                lines.append(f"  {name:20s} {desc}")
            return "\n".join(lines)

        elif cmd == "/compact":
            self.query_engine.compact()
            return "Transcript compacted."

        elif cmd == "/model":
            if args:
                self._model = args.strip()
                return f"Model set to: {self._model}"
            return f"Current model: {self._model}"

        elif cmd == "/permissions":
            return f"Granted permissions: {', '.join(sorted(self.tools.permissions))}"

        elif cmd == "/cost":
            status = self.query_engine.status()
            tokens = status["tokens_used"]
            # Rough cost estimate (Groq Qwen3-32b: ~$0.29/1M tokens)
            cost = tokens * 0.00000029
            return f"Tokens used: {tokens:,} | Est. cost: ${cost:.4f}"

        elif cmd == "/session":
            status = self.query_engine.status()
            elapsed = time.time() - self._session_start
            return (
                f"Session: {self.session_id[:8]}...\n"
                f"Turns: {self._turn_count}\n"
                f"Messages: {status['messages']}\n"
                f"Tokens: {status['tokens_used']:,}\n"
                f"Elapsed: {elapsed:.0f}s"
            )

        elif cmd == "/tools":
            available = self.tools.available_tools()
            lines = [f"Available tools ({len(available)}):"]
            for t in available:
                desc = self.tools.TOOLS[t]["desc"]
                lines.append(f"  {t:20s} {desc}")
            return "\n".join(lines)

        elif cmd == "/memory":
            try:
                from core.ai.memory_system import get_stats, get_recent_projects
                stats = get_stats()
                recent = get_recent_projects(3)
                lines = [
                    f"Total generated: {stats.get('total_generated', 0)}",
                    f"Recent: {', '.join(p['name'] for p in recent)}",
                ]
                return "\n".join(lines)
            except Exception as e:
                return f"Memory error: {e}"

        elif cmd == "/status":
            status = self.query_engine.status()
            return json.dumps(status, indent=2)

        elif cmd == "/clear":
            self.query_engine.transcript._messages.clear()
            return "Transcript cleared."

        elif cmd == "/test":
            path = args.strip() or str(self.project_path / "backend")
            return self.tools.call("run_tests", path=path)

        elif cmd == "/deploy":
            try:
                from core.ai.deployer import print_deploy_guide
                print_deploy_guide(str(self.project_path), self.project_path.name)
                return "Deploy guide printed above."
            except Exception as e:
                return f"Deploy error: {e}"

        elif cmd == "/history":
            try:
                from core.ai.memory_system import get_recent_projects
                projects = get_recent_projects(10)
                lines = ["Recent projects:"]
                for p in reversed(projects):
                    lines.append(f"  {p['name']:20s} {p.get('type','')}")
                return "\n".join(lines)
            except Exception as e:
                return f"History error: {e}"

        return f"Unknown command: {cmd}"

    def run_session(self, prompt: str, generate_fn) -> str:
        """
        Full session turn: route -> execute -> return result.
        Handles commands, tool calls, and generation.
        """
        self._turn_count += 1
        match = self.route_prompt(prompt)

        if match.kind == "command":
            return self.execute_command(match)

        elif match.kind == "tool":
            # Extract args from prompt for tool call
            result = self.tools.call(match.name, path=prompt.split()[-1]
                                     if len(prompt.split()) > 1 else ".")
            return result

        else:
            # LLM generation
            result = ""
            for event in self.query_engine.run_turn(prompt, generate_fn):
                if event.type == EventType.MESSAGE_DELTA:
                    result += event.data.get("text", "")
                elif event.type == EventType.ERROR:
                    return f"Error: {event.data.get('error')}"
            return result

    def save_session(self, sessions_dir: str = ".apex_sessions"):
        """Persist session state."""
        path = Path(sessions_dir)
        path.mkdir(exist_ok=True)
        session_file = path / f"{self.session_id}.json"
        data = {
            "session_id": self.session_id,
            "turn_count": self._turn_count,
            "model": self._model,
            "status": self.query_engine.status(),
        }
        session_file.write_text(json.dumps(data, indent=2))
        return str(session_file)

    def resume_session(self, session_id: str, sessions_dir: str = ".apex_sessions") -> bool:
        """Resume a previous session."""
        path = Path(sessions_dir) / f"{session_id}.json"
        if not path.exists():
            return False
        data = json.loads(path.read_text())
        self.session_id = data["session_id"]
        self._turn_count = data.get("turn_count", 0)
        self._model = data.get("model", self._model)
        return True
