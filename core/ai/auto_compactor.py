# core/ai/auto_compactor.py
# Auto-compaction engine - prevents context overflow
# Pattern from claw-code compact.rs:
# "200,000 token threshold, summarises previous turns to preserve long-term intent"
# Adapted for APEX: 80k char threshold, compacts architecture/schema outputs

import re
from typing import Optional


class AutoCompactor:
    """
    Automatically compacts large context blocks to stay under token limits.
    Unlike simple truncation, extracts and preserves KEY information.
    """

    # Thresholds (chars)
    HARD_LIMIT = 80000       # Groq 413 limit
    COMPACT_AT = 60000       # Start compacting when context reaches this
    TARGET_SIZE = 40000      # Compact down to this size

    def __init__(self):
        self._compaction_count = 0

    def should_compact(self, ctx: dict) -> bool:
        """Check if context is large enough to need compaction."""
        total = sum(len(str(v)) for v in ctx.values() if isinstance(v, str))
        return total > self.COMPACT_AT

    def compact_context(self, ctx: dict) -> dict:
        """
        Intelligently compact the context dictionary.
        Preserves: API endpoints, model names, key decisions
        Removes: verbose descriptions, repeated text, markdown formatting
        """
        if not self.should_compact(ctx):
            return ctx

        compacted = dict(ctx)
        self._compaction_count += 1

        # Compact architecture output (usually the largest)
        if "api_contract" in compacted and len(compacted["api_contract"]) > 2000:
            compacted["api_contract"] = self._compact_architecture(
                compacted["api_contract"]
            )

        # Compact schema output
        if "db_schema" in compacted and len(compacted["db_schema"]) > 1500:
            compacted["db_schema"] = self._compact_schema(compacted["db_schema"])

        # Clear raw file outputs (too large, not needed downstream)
        for key in ("backend_files", "frontend_files", "config_files"):
            if key in compacted and len(compacted.get(key, "")) > 5000:
                compacted[key] = compacted[key][:3000] + "\n... [compacted]"

        total_after = sum(len(str(v)) for v in compacted.values() if isinstance(v, str))
        print(f"  [AutoCompact] #{self._compaction_count}: context {total_after:,} chars")
        return compacted

    def _compact_architecture(self, text: str) -> str:
        """Extract only the essential facts from architecture output."""
        if len(text) <= 1500:
            return text

        lines = text.split("\n")
        essential = []
        capture = False

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            # Always keep API endpoints
            if any(method in stripped for method in ["GET ", "POST ", "PUT ", "DELETE ", "PATCH "]):
                essential.append(stripped)
                continue

            # Keep model/table definitions
            if any(kw in stripped.lower() for kw in [
                "class ", "model:", "table:", "schema:", "endpoint:",
                "blueprint", "route", "auth", "role", "permission"
            ]):
                essential.append(stripped[:150])
                continue

            # Keep section headers
            if stripped.startswith("#") or stripped.startswith("##"):
                essential.append(stripped[:80])

        result = "\n".join(essential[:60])
        return result if result else text[:1500]

    def _compact_schema(self, text: str) -> str:
        """Extract model definitions from schema output."""
        if len(text) <= 800:
            return text

        lines = text.split("\n")
        essential = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            # Keep class definitions and key fields
            if (stripped.startswith("class ") or
                "db.Column" in stripped or
                "db.relationship" in stripped or
                "primary_key=True" in stripped):
                essential.append(stripped[:120])

        result = "\n".join(essential[:40])
        return result if result else text[:800]

    def compact_prompt(self, prompt: str, max_size: int = None) -> str:
        """Compact a single prompt string."""
        limit = max_size or self.HARD_LIMIT
        if len(prompt) <= limit:
            return prompt

        # Try intelligent compaction first
        compacted = self._remove_redundancy(prompt)
        if len(compacted) <= limit:
            return compacted

        # Hard trim as fallback
        print(f"  [AutoCompact] Hard trimming prompt {len(prompt)} -> {limit} chars")
        return prompt[:limit]

    def _remove_redundancy(self, text: str) -> str:
        """Remove redundant patterns from prompt text."""
        # Remove repeated blank lines
        text = re.sub(r"\n{3,}", "\n\n", text)
        # Remove repeated dashes/equals
        text = re.sub(r"[-=]{10,}", "---", text)
        # Remove markdown bold/italic markers
        text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
        return text

    def stats(self) -> dict:
        return {"compaction_count": self._compaction_count}


# Global instance
_compactor = AutoCompactor()


def compact(ctx: dict) -> dict:
    return _compactor.compact_context(ctx)


def compact_prompt(prompt: str, max_size: int = None) -> str:
    return _compactor.compact_prompt(prompt, max_size)


def should_compact(ctx: dict) -> bool:
    return _compactor.should_compact(ctx)
