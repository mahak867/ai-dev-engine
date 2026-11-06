"""Map public tool arguments (REST + MCP) onto each agent's context keys."""
from __future__ import annotations


def adapt_inputs(tool: str, inputs: dict) -> dict:
    """Map public tool arguments onto each agent's context keys."""
    i = dict(inputs)
    if tool == "generate_code" and i.get("architecture"):
        i["plan"] = f"{i.get('plan', '')}\n\nArchitecture:\n{i['architecture']}"
    if tool == "heal_code":
        files = i.get("files") or {"code.txt": i.get("code", "")}
        issues = i.get("issues") or []
        return {"files": files, "error": "\n".join(map(str, issues)) or i.get("error", "")}
    if tool == "write_documentation":
        i.setdefault("request", i.get("plan", "") or i.get("name", "app"))
        i["plan"] = f"{i.get('plan', '')}\n\nCode:\n{i.get('code', '')[:8000]}"
    return i
