"""Generate a project from Python and print what happened.

    pip install apex-ai-dev-engine
    export GROQ_API_KEY=gsk_...        # free tier works
    python examples/generate_project.py
"""
import apex


def progress(agent, status, message, extra=None):
    print(f"[{agent:10}] {status:9} {message[:90]}")


result = apex.generate(
    "URL shortener API with SQLite storage and pytest tests",
    name="shortener",
    output_dir="out",
    sandbox=None,          # True = run it in Docker and heal failures; None = follow APEX_SANDBOX
    on_event=progress,
)

print(f"\nProject:        {result.path}")
print(f"Files:          {len(result.files)}")
print(f"Reviewer score: {result.quality_score}/100 after {result.review_rounds} round(s)")
if result.sandbox:
    print(f"Sandbox:        {'passed' if result.passed_sandbox else 'failed'} "
          f"after {result.sandbox['attempts']} attempt(s)")
print(f"Tokens:         {result.usage['total_tokens']:,} across {result.usage['calls']} calls")
for agent, u in sorted(result.usage["by_agent"].items(), key=lambda kv: -kv[1]["total_tokens"]):
    print(f"  {agent:10} {u['total_tokens']:>8,} tokens  {u['seconds']:>6}s")
