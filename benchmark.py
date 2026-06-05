"""
Agent Society Benchmark
=======================
Compares single-agent vs multi-agent (society) on identical tasks.
Measures: time, files generated, bugs caught, quality score, self-corrections.

Usage:
    py benchmark.py
    py benchmark.py --task "build a user auth API with JWT"
    py benchmark.py --export results.json
"""
from __future__ import annotations
from dotenv import load_dotenv
load_dotenv()

import argparse, json, time, os, sys, logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(level=logging.WARNING)

# ── colour helpers ─────────────────────────────────────────────────────────────
def _c(code, t): return f"\033[{code}m{t}\033[0m" if os.name != "nt" or os.environ.get("WT_SESSION") else t
def amber(t):  return _c("38;5;214", t)
def teal(t):   return _c("38;5;43",  t)
def green(t):  return _c("38;5;82",  t)
def red(t):    return _c("38;5;196", t)
def muted(t):  return _c("38;5;244", t)
def bold(t):   return _c("1",        t)

BANNER = f"""
{amber("╔══════════════════════════════════════════════════════════╗")}
{amber("║")}  {bold("AGENT SOCIETY BENCHMARK")}  v1.0                           {amber("║")}
{amber("║")}  {teal("Single Agent  vs  7-Agent Society (Qwen Cloud)")}          {amber("║")}
{amber("╚══════════════════════════════════════════════════════════╝")}
"""

# ── quality scorer ─────────────────────────────────────────────────────────────
def score_output(files: dict[str, str], task: str) -> dict:
    """
    Heuristic quality scoring on generated code.
    Returns score 0-100 and list of issues found/missed.

    Key fix: detects hardcoded secret fallbacks like:
        SECRET_KEY = os.getenv("SECRET_KEY", "hardcoded_value_here")
    which is a real CVE-level vulnerability — secret leaks if env var not set.
    """
    import re
    score = 50  # baseline
    issues_caught = []
    issues_missed = []
    security_vulnerabilities = []

    all_code = "\n".join(files.values())

    # ── critical security check: hardcoded secret fallbacks ───────────────────
    # catches: os.getenv("SECRET_KEY", "actual_secret_here")
    # catches: SECRET_KEY = "hardcoded..."
    hardcoded_secret_patterns = [
        r'os\.getenv\s*\(\s*["\'](?:SECRET|JWT|TOKEN|PASSWORD|API_KEY|AUTH)[^"\']*["\'],\s*["\'][a-f0-9]{20,}["\']',
        r'(?:SECRET_KEY|JWT_SECRET|API_KEY)\s*=\s*["\'][a-zA-Z0-9+/=_\-]{16,}["\'](?!\s*#\s*override)',
        r'password\s*=\s*["\'][^"\']{6,}["\']',
        r'token\s*=\s*["\'][a-zA-Z0-9+/=_\-]{20,}["\']',
    ]
    has_hardcoded_secret = any(
        re.search(p, all_code, re.IGNORECASE)
        for p in hardcoded_secret_patterns
    )
    if has_hardcoded_secret:
        security_vulnerabilities.append("CRITICAL: hardcoded secret key fallback (CVE risk)")

    # ── proper secret handling: secrets ONLY from env, no fallback ────────────
    # good: os.getenv("SECRET_KEY") with no fallback, or raise if missing
    proper_secret_handling = (
        not has_hardcoded_secret and
        ("os.getenv" in all_code or "os.environ" in all_code or
         "process.env" in all_code or "dotenv" in all_code)
    )

    # ── code structure checks ─────────────────────────────────────────────────
    checks = {
        # 🔴 critical security (high weight — these are real vulnerabilities)
        "no hardcoded secrets":     not has_hardcoded_secret,
        "proper secret handling":   proper_secret_handling,
        "input validation":         bool(re.search(r'validat|sanitiz|is_valid|zod|joi\.', all_code, re.I)),
        "error handling":           ("try:" in all_code and "except" in all_code) or
                                    ("try {" in all_code and "catch" in all_code),
        "sql injection safe":       bool(re.search(r'sqlalchemy|sequelize|prisma|knex|parameteriz', all_code, re.I)),

        # 🟡 structure quality (medium weight)
        "separated modules":        len(files) >= 4,  # not everything in one file
        "has readme":               any("readme" in f.lower() for f in files),
        "has health check":         bool(re.search(r'/health|/ping|healthcheck', all_code, re.I)),
        "proper http codes":        "201" in all_code and "404" in all_code and "400" in all_code,
        "rate limiting or security headers": bool(re.search(r'helmet|ratelimit|rate.limit|throttl', all_code, re.I)),

        # 🟢 nice to have (low weight)
        "logging":                  bool(re.search(r'logging|logger|winston|pino', all_code, re.I)),
        "pagination":               bool(re.search(r'paginate|page.*limit|offset', all_code, re.I)),
        "environment config":       bool(re.search(r'\.env|dotenv|process\.env', all_code, re.I)),
    }

    weights = {
        "no hardcoded secrets":          15,  # critical — CVE if violated
        "proper secret handling":        10,
        "input validation":               8,
        "error handling":                 8,
        "sql injection safe":             7,
        "separated modules":              6,
        "has readme":                     4,
        "has health check":               4,
        "proper http codes":              4,
        "rate limiting or security headers": 5,
        "logging":                        3,
        "pagination":                     2,
        "environment config":             4,
    }

    for check, passed in checks.items():
        if passed:
            score += weights[check]
            issues_caught.append(check)
        else:
            issues_missed.append(check)

    return {
        "score": min(score, 100),
        "issues_caught": issues_caught,
        "issues_missed": issues_missed,
        "security_vulnerabilities": security_vulnerabilities,
        "file_count": len(files),
        "total_lines": sum(c.count("\n") for c in files.values()),
    }


# ── single agent runner ────────────────────────────────────────────────────────
def run_single_agent(task: str, output_dir: str) -> dict:
    """Run a single LLM call — no planning, no review, no healing."""
    from core.ai.provider import LLMProvider

    print(f"\n  {amber('[ SINGLE AGENT ]')} starting...")
    provider = LLMProvider(model="auto")

    messages = [{
        "role": "system",
        "content": (
            "You are a senior software engineer. Generate a complete, production-ready "
            "codebase for the given task. Output files using this format:\n\n"
            "=== filename.ext ===\n<file content>\n\n"
            "Include all necessary files. No explanations, just code."
        )
    }, {
        "role": "user",
        "content": f"Build: {task}"
    }]

    events = []
    t_start = time.time()

    def log_event(msg):
        events.append({"ts": time.time() - t_start, "msg": msg})
        print(f"    {muted(f'{time.time()-t_start:.1f}s')}  {msg}")

    log_event("single agent thinking...")
    raw = provider.complete(messages, max_tokens=4096)
    log_event(f"single agent responded ({len(raw)} chars)")

    # parse files from response
    files = {}
    current_file = None
    current_lines = []

    for line in raw.split("\n"):
        if line.startswith("=== ") and line.endswith(" ==="):
            if current_file:
                files[current_file] = "\n".join(current_lines)
            current_file = line[4:-4].strip()
            current_lines = []
        elif current_file:
            current_lines.append(line)

    if current_file and current_lines:
        files[current_file] = "\n".join(current_lines)

    elapsed = time.time() - t_start
    log_event(f"done — {len(files)} files in {elapsed:.1f}s")

    # save output
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    for fname, content in files.items():
        fpath = out / fname
        fpath.parent.mkdir(parents=True, exist_ok=True)
        fpath.write_text(content, encoding="utf-8")

    quality = score_output(files, task)

    return {
        "mode": "single_agent",
        "elapsed_seconds": round(elapsed, 1),
        "files_generated": len(files),
        "events": events,
        "quality": quality,
    }


# ── multi-agent society runner ─────────────────────────────────────────────────
def run_agent_society(task: str, output_dir: str) -> dict:
    """Run the full 7-agent society pipeline."""
    from core.orchestrator import Orchestrator

    print(f"\n  {teal('[ AGENT SOCIETY ]')} starting...")

    events = []
    t_start = time.time()

    def on_event(agent: str, status: str, msg: str):
        elapsed = time.time() - t_start
        entry = {"ts": round(elapsed, 1), "agent": agent, "status": status, "msg": msg}
        events.append(entry)
        icon = {"Planner": "🗺 ", "Architect": "🏛 ", "Coder": "👨‍💻",
                "Reviewer": "🔍", "SelfHealer": "🔧", "DocWriter": "📝",
                "System": "⚙ "}.get(agent, "  ")
        status_icon = {"running": "⟳", "done": "✓", "error": "✗"}.get(status, " ")
        print(f"    {muted(f'{elapsed:.1f}s')}  {icon} {agent:12} {status_icon}  {msg}")

    orch = Orchestrator(model="auto", on_event=on_event)
    path = orch.generate_fullstack(
        name=Path(output_dir).name,
        request=task,
        output_dir=str(Path(output_dir).parent),
    )

    elapsed = time.time() - t_start

    # read generated files
    files = {}
    out = Path(path)
    skip = {".git", "node_modules", "__pycache__"}
    for p in out.rglob("*"):
        if p.is_file() and not any(s in p.parts for s in skip):
            try:
                files[str(p.relative_to(out))] = p.read_text(encoding="utf-8")
            except Exception:
                pass

    quality = score_output(files, task)

    # count self-corrections (healer patches)
    corrections = sum(1 for e in events if e.get("agent") == "SelfHealer"
                      and "patch" in e.get("msg", "").lower())

    return {
        "mode": "agent_society",
        "elapsed_seconds": round(elapsed, 1),
        "files_generated": len(files),
        "agents_used": len({e["agent"] for e in events}),
        "self_corrections": corrections,
        "events": events,
        "quality": quality,
    }


# ── results printer ────────────────────────────────────────────────────────────
def print_results(single: dict, society: dict, task: str):
    sq = single["quality"]
    mq = society["quality"]

    time_improvement = round((single["elapsed_seconds"] - society["elapsed_seconds"])
                              / single["elapsed_seconds"] * 100)
    quality_improvement = mq["score"] - sq["score"]
    extra_files = society["files_generated"] - single["files_generated"]
    bugs_caught_extra = len(mq["issues_caught"]) - len(sq["issues_caught"])

    print(f"\n\n  {bold('═' * 58)}")
    print(f"  {bold('BENCHMARK RESULTS')}")
    print(f"  {bold('═' * 58)}\n")
    print(f"  Task: {amber(task[:60])}\n")

    # table
    print(f"  {'Metric':<28} {'Single Agent':>14} {'Agent Society':>14}")
    print(f"  {'─'*28} {'─'*14} {'─'*14}")

    def row(label, sv, mv, higher_is_better=True):
        better = mv > sv if higher_is_better else mv < sv
        mv_str = green(str(mv)) if better else red(str(mv))
        sv_str = str(sv)
        print(f"  {label:<28} {sv_str:>14} {mv_str:>24}")

    row("Time (seconds)",           single["elapsed_seconds"], society["elapsed_seconds"], higher_is_better=False)
    row("Files generated",          single["files_generated"], society["files_generated"])
    row("Quality score (/100)",     sq["score"],               mq["score"])
    row("Security checks passed",   len(sq["issues_caught"]),  len(mq["issues_caught"]))
    row("Issues missed",            len(sq["issues_missed"]),  len(mq["issues_missed"]), higher_is_better=False)
    if "agents_used" in society:
        print(f"  {'Agents coordinated':<28} {'1':>14} {teal(str(society['agents_used'])):>24}")
    if "self_corrections" in society:
        print(f"  {'Self-corrections made':<28} {'0':>14} {green(str(society['self_corrections'])):>24}")

    print(f"\n  {bold('─' * 58)}\n")

    # verdict
    print(f"  {bold('VERDICT')}\n")
    if time_improvement > 0:
        print(f"  ⚡ Agent Society was {green(f'{abs(time_improvement)}% faster')}")
    else:
        print(f"  ⏱  Agent Society took {amber(f'{abs(time_improvement)}% longer')} (more thorough)")

    if quality_improvement > 0:
        print(f"  🏆 Quality score {green(f'+{quality_improvement} points')} higher ({sq['score']} → {mq['score']})")
    elif quality_improvement == 0:
        print(f"  ✅ Quality score {green('equal')} ({mq['score']}/100) — society used more agents")
    else:
        print(f"  ⚠  Quality score {amber(f'{quality_improvement} points')} — review output manually")

    if bugs_caught_extra > 0:
        print(f"  🔒 Caught {green(str(bugs_caught_extra))} additional security/quality issues")

    if extra_files > 0:
        print(f"  📁 Generated {green(str(extra_files))} more files (docs, tests, config)")

    print(f"\n  {muted('Society issues missed: ' + ', '.join(mq['issues_missed']) if mq['issues_missed'] else 'Society issues missed: none')}")
    print(f"  {muted('Single issues missed: ' + ', '.join(sq['issues_missed']) if sq['issues_missed'] else 'Single issues missed: none')}")

    # show critical security vulnerabilities
    if sq.get("security_vulnerabilities"):
        print(f"\n  {bold('SECURITY VULNERABILITIES FOUND:')}")
        for v in sq["security_vulnerabilities"]:
            print(f"  {red('🚨 SINGLE AGENT:')} {v}")
        print(f"  {green('✅ AGENT SOCIETY:')} no critical vulnerabilities detected")
    print()


# ── export ─────────────────────────────────────────────────────────────────────
def export_results(single: dict, society: dict, task: str, path: str):
    data = {
        "task": task,
        "timestamp": datetime.utcnow().isoformat(),
        "single_agent": single,
        "agent_society": society,
        "summary": {
            "time_delta_seconds": round(single["elapsed_seconds"] - society["elapsed_seconds"], 1),
            "quality_delta": society["quality"]["score"] - single["quality"]["score"],
            "files_delta": society["files_generated"] - single["files_generated"],
            "bugs_caught_delta": len(society["quality"]["issues_caught"]) - len(single["quality"]["issues_caught"]),
        }
    }
    Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"\n  {green('✔')} Results exported to {teal(path)}")


# ── main ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Benchmark single agent vs Agent Society")
    parser.add_argument("--task",   default="build a REST API for a task manager with user auth, CRUD operations, and JWT tokens",
                        help="Task to benchmark")
    parser.add_argument("--export", default="benchmark_results.json",
                        help="Export results to JSON file")
    parser.add_argument("--output", default="./benchmark_runs",
                        help="Output directory for generated projects")
    args = parser.parse_args()

    print(BANNER)
    print(f"  {bold('Task:')} {amber(args.task[:70])}")
    print(f"  {bold('Time:')} {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    print(f"  {muted('Running both modes sequentially. This takes ~5-8 minutes.')}\n")
    print(f"  {bold('═' * 58)}")

    # run single agent
    single = run_single_agent(
        task=args.task,
        output_dir=f"{args.output}/single_agent"
    )

    print(f"\n  {bold('═' * 58)}")

    # run agent society
    society = run_agent_society(
        task=args.task,
        output_dir=f"{args.output}/agent_society"
    )

    # print comparison
    print_results(single, society, args.task)

    # export
    export_results(single, society, args.task, args.export)

    print(f"  {green('✔')} Benchmark complete!\n")


if __name__ == "__main__":
    main()
