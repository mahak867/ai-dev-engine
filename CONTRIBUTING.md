# Contributing

Thanks for wanting to improve APEX Society.

## Setup

```bash
git clone https://github.com/mahak867/ai-dev-engine && cd ai-dev-engine
python -m venv .venv && source .venv/bin/activate
pip install -e ".[server,mcp,eval,dev]"
apex doctor
```

## Before you open a pull request

```bash
python -m ruff check .          # lint
python -m mypy                  # types
python -m pytest --cov          # tests; Docker sandbox tests run when Docker is up
```

CI runs the same checks on Python 3.10–3.13 and fails under 75% coverage.

No API key is needed for any test: they use the `fake/canned` model
(`apex/demo_llm.py`). `apex eval --self-test` checks the benchmark harness the same way.

## Where things live

| You want to… | Look at |
|---|---|
| Change what an agent does or its prompt | `apex/agents/base.py` |
| Add or reorder a pipeline stage | `apex/orchestrator.py` (one `_stage_*` method per stage) |
| Add an LLM provider | `apex/ai/provider.py` (most only need `_openai_compat`) |
| Change sandbox limits or steps | `apex/execution/sandbox.py` |
| Add an eval task or metric | `apex/evals/tasks.json`, `apex/evals/scoring.py` |
| Change the office dashboard | `apex/web/dashboard.html` (single file, no build step) |

## Ground rules

- Model output is untrusted. File paths go through `apex.security.safe_join`; generated
  code only runs inside the sandbox.
- New behaviour comes with a test. Security-relevant changes come with a test in
  `tests/test_security.py`.
- Keep the public API (`apex.generate`, `GenerationResult`, the CLI) backwards compatible,
  or call out the break in the PR description.
