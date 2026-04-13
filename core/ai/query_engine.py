# core/ai/query_engine.py
# Query engine with session management, compaction, and streaming events
# Architecture pattern from claw-code public docs (claw-code.codes/architecture.html)
# Fully original implementation for APEX engine

import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Generator, Optional


# ── EVENT TYPES ───────────────────────────────────────────────────────────────

class EventType(Enum):
    MESSAGE_START   = "message_start"
    COMMAND_MATCH   = "command_match"
    TOOL_MATCH      = "tool_match"
    PERMISSION_DENY = "permission_denial"
    MESSAGE_DELTA   = "message_delta"
    MESSAGE_STOP    = "message_stop"
    STEP_START      = "step_start"
    STEP_DONE       = "step_done"
    ERROR           = "error"


@dataclass
class StreamEvent:
    type: EventType
    data: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


# ── MESSAGE SCHEMA ─────────────────────────────────────────────────────────────

class MessageRole(Enum):
    SYSTEM    = "system"
    USER      = "user"
    ASSISTANT = "assistant"
    TOOL      = "tool"


@dataclass
class ContentBlock:
    type: str        # "text" | "tool_use" | "tool_result"
    text: str = ""
    tool_name: str = ""
    tool_input: dict = field(default_factory=dict)
    tool_result: str = ""


@dataclass
class Message:
    role: MessageRole
    content: list[ContentBlock]
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "role": self.role.value,
            "content": [{"type": c.type, "text": c.text} for c in self.content if c.text],
            "timestamp": self.timestamp,
        }


# ── TRANSCRIPT ────────────────────────────────────────────────────────────────

class Transcript:
    """
    Rolling in-memory transcript with compaction.
    Pattern: compact_after_turns=12, keep_last=10
    """

    COMPACT_AFTER_TURNS = 12
    KEEP_LAST = 10
    MAX_CHARS_PER_MESSAGE = 2000

    def __init__(self):
        self._messages: list[Message] = []
        self._turn_count = 0
        self._compacted_summary = ""

    def add(self, role: MessageRole, text: str):
        content = [ContentBlock(type="text", text=text[:self.MAX_CHARS_PER_MESSAGE])]
        self._messages.append(Message(role=role, content=content))
        if role == MessageRole.ASSISTANT:
            self._turn_count += 1
            if self._turn_count >= self.COMPACT_AFTER_TURNS:
                self._compact()

    def _compact(self):
        """Retain last N messages, summarise the rest."""
        if len(self._messages) <= self.KEEP_LAST:
            return
        old = self._messages[:-self.KEEP_LAST]
        # Build summary of old messages
        summary_parts = []
        for msg in old:
            role = msg.role.value
            text = " ".join(c.text[:100] for c in msg.content if c.text)
            summary_parts.append(f"[{role}]: {text}")
        self._compacted_summary = "Previous context: " + " | ".join(summary_parts[-5:])
        self._messages = self._messages[-self.KEEP_LAST:]
        self._turn_count = 0
        print(f"  [Transcript] Compacted to {self.KEEP_LAST} messages")

    def to_api_messages(self, system_prompt: str = "") -> list[dict]:
        """Format for LLM API."""
        result = []
        if system_prompt:
            result.append({"role": "system", "content": system_prompt})
        if self._compacted_summary:
            result.append({
                "role": "user",
                "content": f"[Session context: {self._compacted_summary}]"
            })
        for msg in self._messages:
            result.append(msg.to_dict())
        return result

    def token_estimate(self) -> int:
        total = sum(len(c.text) for m in self._messages for c in m.content)
        return total // 4


# ── TURN RESULT ───────────────────────────────────────────────────────────────

@dataclass
class TurnResult:
    success: bool
    output: str
    tokens_used: int = 0
    tool_calls: list = field(default_factory=list)
    error: Optional[str] = None
    duration: float = 0.0


# ── QUERY ENGINE ──────────────────────────────────────────────────────────────

class QueryEngine:
    """
    Core query engine. Manages session, transcript, tool calls.
    Pattern from claw-code: run_turn recursive loop with tool execution.
    """

    MAX_BUDGET_TOKENS = 100000
    MAX_TOOL_ITERATIONS = 5

    def __init__(self, session_id: Optional[str] = None):
        self.session_id = session_id or uuid.uuid4().hex
        self.transcript = Transcript()
        self._tools: dict = {}
        self._permissions: set = set()
        self._token_budget_used = 0

    def register_tool(self, name: str, fn, requires_permission: bool = False):
        """Register a callable tool."""
        self._tools[name] = {"fn": fn, "requires_permission": requires_permission}

    def grant_permission(self, permission: str):
        self._permissions.add(permission)

    def run_turn(self, prompt: str, generate_fn,
                 system_prompt: str = "") -> Generator[StreamEvent, None, TurnResult]:
        """
        Single turn: prompt -> LLM -> tool calls -> result.
        Yields StreamEvents for live output. Returns TurnResult.
        """
        start = time.time()
        yield StreamEvent(EventType.MESSAGE_START, {"prompt_len": len(prompt)})

        # Add user message to transcript
        self.transcript.add(MessageRole.USER, prompt)

        # Check budget
        if self._token_budget_used > self.MAX_BUDGET_TOKENS:
            yield StreamEvent(EventType.ERROR, {"error": "Token budget exceeded"})
            return TurnResult(success=False, output="", error="Budget exceeded")

        try:
            # Build messages
            messages = self.transcript.to_api_messages(system_prompt)

            # Generate
            response = generate_fn(prompt)
            tokens = len(response) // 4
            self._token_budget_used += tokens

            # Add assistant response to transcript
            self.transcript.add(MessageRole.ASSISTANT, response)

            # Yield delta events (simulate streaming for UI)
            chunk_size = 200
            for i in range(0, len(response), chunk_size):
                chunk = response[i:i+chunk_size]
                yield StreamEvent(EventType.MESSAGE_DELTA, {"text": chunk})

            yield StreamEvent(EventType.MESSAGE_STOP, {
                "tokens": tokens,
                "total_tokens": self._token_budget_used,
            })

            duration = time.time() - start
            return TurnResult(
                success=True,
                output=response,
                tokens_used=tokens,
                duration=duration,
            )

        except Exception as e:
            yield StreamEvent(EventType.ERROR, {"error": str(e)})
            return TurnResult(success=False, output="", error=str(e))

    def compact(self):
        """Force compact the transcript."""
        self.transcript._compact()

    def status(self) -> dict:
        return {
            "session_id": self.session_id,
            "turns": self.transcript._turn_count,
            "messages": len(self.transcript._messages),
            "tokens_used": self._token_budget_used,
            "budget_remaining": self.MAX_BUDGET_TOKENS - self._token_budget_used,
        }
