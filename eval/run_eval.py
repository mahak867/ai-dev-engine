#!/usr/bin/env python3
"""
APEX eval harness — single agent vs the 9-agent society, scored independently.

    # real run (needs a provider key; pin one model so both modes are comparable)
    APEX_MODEL=groq/llama-3.3-70b GROQ_API_KEY=... python eval/run_eval.py --limit 30

    # add the Docker sandbox (install + import + pytest, network off)
    APEX_SANDBOX=docker python eval/run_eval.py --sandbox

    # prove the pipeline works with no key / no network (canned outputs)
    python eval/run_eval.py --self-test --limit 3

Results go to eval/results/<run-id>/: results.jsonl (one row per task×mode,
appended as it goes — re-running the same --run-id resumes), summary.json and
summary.md (means, paired differences with bootstrap 95% CIs, win/tie/loss).

Fairness rules baked in:
  * both modes get the identical task text and the same pinned model
  * the society gets a fresh, empty MemoryStore per task (no learning leakage
    between tasks unless --with-memory)
  * scoring never asks an LLM (see eval/scoring.py)
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import random
import statistics
import sys
import tempfile
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import telemetry  # noqa: E402
from core.security import write_files_contained  # noqa: E402
from eval.scoring import score_project, tool_versions  # noqa: E402

SINGLE_SYSTEM = (
    "You are a senior software engineer. Generate a complete, production-ready codebase for "
    "the given task. Output files using this format:\n\n=== filename.ext ===\n<file content>\n\n"
    "Include all necessary files (code, requirements.txt, tests). No explanations, just code."
)

# Metrics summarised in the report: (key, label, higher_is_better)
METRICS = [
    ("generated", "Generated any files", True),
    ("files", "Files", True),
    ("py_loc", "Python LOC", None),
    ("syntax_error_files", "Files with syntax errors", False),
    ("has_tests", "Has tests", True),
    ("bandit_high", "Bandit HIGH", False),
    ("bandit_medium", "Bandit MEDIUM", False),
    ("ruff_security", "Ruff S-rule findings", False),
    ("ruff_errors", "Ruff findings (E9,F,B,S)", False),
    ("secrets", "Hardcoded secrets", False),
    ("sandbox.ok", "Sandbox: all checks pass", True),
    ("sandbox.import_ok", "Sandbox: app imports", True),
    ("sandbox.test_pass_rate", "Sandbox: test pass rate", True),
    ("usage.total_tokens", "Tokens", False),
    ("usage.cost_usd", "Cost (USD)", False),
    ("usage.wall_seconds", "Wall time (s)", False),
]


# ── generation ────────────────────────────────────────────────────────────────
def parse_single(raw: str) -> dict[str, str]:
    files, cur, buf = {}, None, []
    for line in raw.split("\n"):
        s = line.strip()
        if s.startswith("=== ") and s.endswith(" ==="):
            if cur:
                files[cur] = "\n".join(buf).strip("\n") + "\n"
            cur, buf = s[4:-4].strip(), []
        elif cur:
            buf.append(line)
    if cur:
        files[cur] = "\n".join(buf).strip("\n") + "\n"
    if not files:  # model ignored the format — fall back to the agents' fenced-block parser
        from core.agents.base import Agent
        files = Agent.__new__(Agent)._parse_files(raw)
    return files


def run_single(task: str, out: Path) -> dict:
    from core.ai.provider import LLMProvider
    llm = LLMProvider("coding")
    with telemetry.agent_scope("SingleAgent"):
        raw = llm.complete([{"role": "system", "content": SINGLE_SYSTEM},
                            {"role": "user", "content": f"Build: {task}"}], max_tokens=16384)
    files = parse_single(raw)
    out.mkdir(parents=True, exist_ok=True)
    written, rejected = write_files_contained(out, files)
    return {"written": len(written), "rejected_paths": len(rejected)}


def run_society(task: str, out: Path, *, with_memory: bool, mem_dir: Path) -> dict:
    from core.memory.store import MemoryStore
    from core.orchestrator import Orchestrator
    store = MemoryStore(str(mem_dir)) if with_memory else MemoryStore(tempfile.mkdtemp(prefix="apex-eval-mem-"))
    orch = Orchestrator(model="auto", on_event=lambda *a, **k: None, memory_store=store)
    path = orch.generate_fullstack(name=out.name, request=task, output_dir=str(out.parent))
    return {"path": path, "sandbox_in_pipeline": orch.last_sandbox}


# ── stats ─────────────────────────────────────────────────────────────────────
def _get(row: dict, key: str):
    cur = row
    for part in key.split("."):
        if part == "test_pass_rate" and isinstance(cur, dict):
            f = cur.get("tests_found") or 0
            return (cur.get("tests_passed", 0) / f) if f else None
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    if isinstance(cur, bool):
        return 1.0 if cur else 0.0
    return cur if isinstance(cur, (int, float)) else None


def bootstrap_ci(diffs: list[float], n: int = 10_000, seed: int = 0) -> tuple[float, float]:
    if len(diffs) < 2:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    means = sorted(statistics.fmean(rng.choices(diffs, k=len(diffs))) for _ in range(n))
    return means[int(0.025 * n)], means[int(0.975 * n) - 1]


def summarize(rows: list[dict], meta: dict) -> dict:
    by_task: dict[str, dict] = {}
    for r in rows:
        by_task.setdefault(r["task_id"], {})[r["mode"]] = r
    modes = sorted({r["mode"] for r in rows})
    out = {"meta": meta, "n_tasks": len(by_task), "modes": modes, "metrics": {}}
    for key, label, higher in METRICS:
        m = {"label": label, "higher_is_better": higher}
        for mode in modes:
            vals = [v for v in (_get(t[mode], key) for t in by_task.values() if mode in t) if v is not None]
            m[mode] = {"n": len(vals),
                       "mean": round(statistics.fmean(vals), 4) if vals else None,
                       "median": round(statistics.median(vals), 4) if vals else None}
        if {"single", "society"} <= set(modes):
            pairs = [(_get(t["single"], key), _get(t["society"], key))
                     for t in by_task.values() if "single" in t and "society" in t]
            pairs = [(a, b) for a, b in pairs if a is not None and b is not None]
            diffs = [b - a for a, b in pairs]
            if diffs:
                lo, hi = bootstrap_ci(diffs)
                if higher is None:
                    w = t_ = l_ = None
                else:
                    better = (lambda d: d > 0) if higher else (lambda d: d < 0)
                    worse = (lambda d: d < 0) if higher else (lambda d: d > 0)
                    w = sum(better(d) for d in diffs)
                    l_ = sum(worse(d) for d in diffs)
                    t_ = len(diffs) - w - l_
                m["paired"] = {"n": len(diffs), "mean_diff": round(statistics.fmean(diffs), 4),
                               "ci95": [round(lo, 4), round(hi, 4)],
                               "society_wins": w, "ties": t_, "single_wins": l_}
        out["metrics"][key] = m
    # per-agent token share for the society
    agents: dict[str, dict] = {}
    for r in rows:
        if r["mode"] != "society":
            continue
        for a, d in (r.get("usage", {}).get("by_agent") or {}).items():
            acc = agents.setdefault(a, {"tokens": 0, "seconds": 0.0, "calls": 0})
            acc["tokens"] += d.get("total_tokens", 0)
            acc["seconds"] += d.get("seconds", 0.0)
            acc["calls"] += d.get("calls", 0)
    out["society_by_agent"] = agents
    out["errors"] = sum(1 for r in rows if r.get("error"))
    return out


def _fmt(v, key: str) -> str:
    if v is None:
        return "—"
    if "cost" in key:
        return f"${v:.4f}"
    if isinstance(v, float) and (key.endswith("ok") or "rate" in key or key in ("generated", "has_tests")):
        return f"{v * 100:.0f}%"
    return f"{v:.2f}" if isinstance(v, float) else str(v)


def render_md(s: dict) -> str:
    meta = s["meta"]
    lines = [f"# APEX eval — {meta['run_id']}", ""]
    if meta.get("self_test"):
        lines += ["> **SELF-TEST RUN** — canned fake-LLM outputs. Proves the harness works; "
                  "these numbers say nothing about model quality.", ""]
    lines += [f"- Tasks: **{s['n_tasks']}**  ·  modes: {', '.join(s['modes'])}  ·  errors: {s['errors']}",
              f"- Model: `{meta.get('model') or 'provider cascade (not pinned)'}`  ·  sandbox: {meta['sandbox']}  ·  "
              f"memory between tasks: {meta['with_memory']}",
              f"- Tools: {meta['tools']}  ·  Python {meta['python']}  ·  {meta['started']}", "",
              "| Metric | Single agent (mean) | Society (mean) | Δ society−single [95% CI] | W/T/L (society) |",
              "|---|---|---|---|---|"]
    for key, m in s["metrics"].items():
        a = (m.get("single") or {}).get("mean")
        b = (m.get("society") or {}).get("mean")
        if a is None and b is None:
            continue
        p = m.get("paired")
        delta = (f"{p['mean_diff']:+.3f} [{p['ci95'][0]:+.3f}, {p['ci95'][1]:+.3f}]" if p else "—")
        wtl = (f"{p['society_wins']}/{p['ties']}/{p['single_wins']}" if p and p["society_wins"] is not None else "—")
        lines.append(f"| {m['label']} | {_fmt(a, key)} | {_fmt(b, key)} | {delta} | {wtl} |")
    if s.get("society_by_agent"):
        total = sum(a["tokens"] for a in s["society_by_agent"].values()) or 1
        lines += ["", "## Society: where the tokens go", "", "| Agent | Calls | Tokens | Share | LLM/stage seconds |",
                  "|---|---|---|---|---|"]
        for name, a in sorted(s["society_by_agent"].items(), key=lambda kv: -kv[1]["tokens"]):
            lines.append(f"| {name} | {a['calls']} | {a['tokens']:,} | {a['tokens'] / total * 100:.0f}% | {a['seconds']:.1f} |")
    lines += ["", "Δ is paired per task. CIs are 10,000-sample bootstrap of the mean difference. "
              "W/T/L counts tasks where the society was better / equal / worse on that metric."]
    return "\n".join(lines) + "\n"


# ── main ──────────────────────────────────────────────────────────────────────
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tasks", default=str(ROOT / "eval" / "tasks.json"))
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--only", default="", help="comma-separated task ids")
    ap.add_argument("--modes", default="single,society")
    ap.add_argument("--run-id", default=time.strftime("%Y%m%d-%H%M%S"))
    ap.add_argument("--out", default=str(ROOT / "eval" / "results"))
    ap.add_argument("--sandbox", action="store_true", help="score with the Docker sandbox (install/import/pytest)")
    ap.add_argument("--with-memory", action="store_true", help="let the society learn across tasks")
    ap.add_argument("--self-test", action="store_true", help="fake LLM, no key/network needed")
    ap.add_argument("--summarize-only", action="store_true")
    args = ap.parse_args(argv)

    if args.self_test:
        from core.ai import provider
        from eval import fake_llm
        provider.set_fake_responder(fake_llm.respond)
        os.environ["APEX_MODEL"] = "fake/canned"

    tasks = json.loads(Path(args.tasks).read_text(encoding="utf-8"))
    if args.only:
        keep = set(args.only.split(","))
        tasks = [t for t in tasks if t["id"] in keep]
    if args.limit:
        tasks = tasks[: args.limit]
    modes = [m.strip() for m in args.modes.split(",") if m.strip()]

    run_dir = Path(args.out) / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    results_path = run_dir / "results.jsonl"
    done = set()
    rows: list[dict] = []
    if results_path.exists():
        for line in results_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                rows.append(r)
                done.add((r["task_id"], r["mode"]))

    meta = {
        "run_id": args.run_id, "self_test": args.self_test, "model": os.environ.get("APEX_MODEL"),
        "sandbox": args.sandbox, "with_memory": args.with_memory, "tools": tool_versions(),
        "python": platform.python_version(), "started": time.strftime("%Y-%m-%d %H:%M:%S"),
        "tasks_file": str(Path(args.tasks).name), "n_tasks_requested": len(tasks),
    }
    (run_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    if not args.summarize_only:
        gen_root = run_dir / "projects"
        mem_dir = run_dir / "memory"
        for i, t in enumerate(tasks, 1):
            for mode in modes:
                if (t["id"], mode) in done:
                    continue
                out = gen_root / mode / t["id"]
                tracker = telemetry.UsageTracker()
                row = {"task_id": t["id"], "mode": mode, "task": t["task"]}
                t0 = time.time()
                try:
                    with telemetry.track(tracker):
                        if mode == "single":
                            row["gen"] = run_single(t["task"], out)
                        elif mode == "society":
                            row["gen"] = run_society(t["task"], out, with_memory=args.with_memory, mem_dir=mem_dir)
                        else:
                            raise ValueError(f"unknown mode {mode}")
                except Exception as e:
                    row["error"] = f"{type(e).__name__}: {e}"
                    row["traceback"] = traceback.format_exc()[-2000:]
                row["gen_seconds"] = round(time.time() - t0, 2)
                row["usage"] = tracker.summary()
                row.update(score_project(out, sandbox=args.sandbox))
                with results_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(row) + "\n")
                rows.append(row)
                status = "ERR " + row["error"][:60] if row.get("error") else (
                    f"files={row.get('files')} bandit_hi={row.get('bandit_high')} "
                    f"secrets={row.get('secrets')} tokens={row['usage']['total_tokens']}")
                print(f"[{i}/{len(tasks)}] {mode:7s} {t['id']:20s} {status}", flush=True)

    summary = summarize(rows, meta)
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    md = render_md(summary)
    (run_dir / "summary.md").write_text(md, encoding="utf-8")
    print("\n" + md)
    print(f"Results: {run_dir}")
    return 1 if summary["errors"] == len(rows) and rows else 0


if __name__ == "__main__":
    raise SystemExit(main())
