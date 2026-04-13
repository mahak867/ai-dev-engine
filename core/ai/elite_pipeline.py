import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from core.ai.cloud_router import generate_cloud_text
from core.ai.doctor import doctor_markdown, run_doctor
from core.ai.integrations import INTEGRATIONS, detect_integrations, get_extra_packages
from core.ai.skills_library import SKILLS, get_all_skills_for_complexity


def _fallback_plan(mode: str, prompt: str) -> str:
    return f"""# Elite Execution Plan

## Mode
{mode}

## Prompt
{prompt}

## Phases
1. Discovery and architecture
2. Core implementation vertical slice
3. Quality loop (tests, lint, security)
4. Release prep and rollback plan

## Parallel Workers
- Worker A: Frontend UX and command surface
- Worker B: Backend/data contracts and reliability
- Worker C: Quality gates and regression tests
"""


def _fallback_review(project_name: str) -> str:
    return f"""# Quality Review ({project_name})

## Required Gates
- Architecture documented
- API contracts listed
- Error handling and rollback path
- Test strategy documented
- Security basics validated

## Risks
- Scope creep under parallel execution
- Missing validation on mutable endpoints
- Unclear deployment ownership
"""


def _fallback_release(project_name: str) -> str:
    return f"""# Release Checklist ({project_name})

1. Run doctor report and confirm health score above 80
2. Run syntax checks and automated tests
3. Verify environment variables and secrets policy
4. Verify build and startup scripts
5. Create rollback steps
6. Final smoke test on local environment
"""


def _task_board(prompt: str) -> Dict[str, object]:
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "prompt": prompt,
        "lanes": {
            "todo": [
                "Define architecture boundaries",
                "Implement core command loop",
                "Add integration scaffolding",
                "Add quality checks",
            ],
            "doing": [],
            "done": [],
        },
    }


def run_elite_pipeline(
    project_path: Path,
    mode: str,
    prompt: str,
    cloud_provider: str,
    cloud_profile: str,
    openrouter_key: str,
    groq_key: str,
) -> Dict[str, str]:
    detected = detect_integrations(prompt, {"project_type": mode.lower()})
    extra = get_extra_packages(prompt, {"project_type": mode.lower()})
    skills_prompt = get_all_skills_for_complexity("complex", {"needs_auth": "auth" in prompt.lower()})

    plan_prompt = f"""Create an elite implementation plan for this project.
Mode: {mode}
Prompt: {prompt}
Detected integrations: {detected}
Available integrations count: {len(INTEGRATIONS)}
Available skills count: {len(SKILLS)}

Output sections:
1. Architecture
2. Parallel worker breakdown
3. Milestone sequence
4. Quality gates
5. Risks and mitigations
"""
    plan_result = generate_cloud_text(
        prompt=plan_prompt,
        profile=cloud_profile,
        provider_preference=cloud_provider,
        openrouter_key=openrouter_key,
        groq_key=groq_key,
        system_prompt="You are an elite software architect. Be concrete and operational.",
    )
    plan_text = plan_result["text"] if plan_result.get("ok") == "1" else _fallback_plan(mode, prompt)

    review_prompt = f"""Review this project plan for quality and risks.
Project: {project_path.name}
Plan:
{plan_text}

Produce:
1. Quality findings
2. Missing tests
3. Security and reliability checks
4. Recommended fixes
"""
    review_result = generate_cloud_text(
        prompt=review_prompt,
        profile=cloud_profile,
        provider_preference=cloud_provider,
        openrouter_key=openrouter_key,
        groq_key=groq_key,
        system_prompt="You are a principal engineer and release reviewer.",
    )
    review_text = review_result["text"] if review_result.get("ok") == "1" else _fallback_review(project_path.name)

    release_prompt = f"""Create a ship-ready release checklist for this project.
Project: {project_path.name}
Mode: {mode}
Prompt: {prompt}
"""
    release_result = generate_cloud_text(
        prompt=release_prompt,
        profile=cloud_profile,
        provider_preference=cloud_provider,
        openrouter_key=openrouter_key,
        groq_key=groq_key,
        system_prompt="You are a release manager. Be concise and strict.",
    )
    release_text = release_result["text"] if release_result.get("ok") == "1" else _fallback_release(project_path.name)

    doctor = run_doctor(project_path, openrouter_key, groq_key)
    board = _task_board(prompt)
    meta = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "project": project_path.name,
        "mode": mode,
        "prompt": prompt,
        "cloud": {
            "provider_preference": cloud_provider,
            "profile": cloud_profile,
            "plan_provider": plan_result.get("provider", ""),
            "plan_model": plan_result.get("model", ""),
            "review_provider": review_result.get("provider", ""),
            "review_model": review_result.get("model", ""),
            "release_provider": release_result.get("provider", ""),
            "release_model": release_result.get("model", ""),
        },
        "integrations": {
            "detected": detected,
            "packages": extra,
        },
        "skills_summary": {
            "total_available": len(SKILLS),
            "hinted_bundle_characters": len(skills_prompt),
        },
    }

    runbook = f"""# Elite Runbook

## Project
{project_path.name}

## Fast Commands
1. `scripts\\start_elite.bat` - start workspace web UI
2. `scripts\\doctor.bat` - quick local health checks
3. `scripts\\run_agent.bat` - run autonomous elite runtime pass
4. `scripts\\ship_check.bat` - verify release documents

## Workflow
1. Open `docs/elite/plan.md`
2. Execute tasks from `docs/elite/task-board.json`
3. Review findings in `docs/elite/review.md`
4. Validate readiness with `docs/elite/release-checklist.md`
"""

    command_center = {
        "commands": [
            {"name": "/plan", "action": "open docs/elite/plan.md"},
            {"name": "/review", "action": "open docs/elite/review.md"},
            {"name": "/doctor", "action": "open docs/elite/doctor.md"},
            {"name": "/ship", "action": "open docs/elite/release-checklist.md"},
        ],
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }

    return {
        "docs/elite/plan.md": plan_text + "\n",
        "docs/elite/review.md": review_text + "\n",
        "docs/elite/release-checklist.md": release_text + "\n",
        "docs/elite/doctor.md": doctor_markdown(doctor),
        "docs/elite/task-board.json": json.dumps(board, indent=2),
        "docs/elite/meta.json": json.dumps(meta, indent=2),
        "docs/elite/runbook.md": runbook,
        "docs/elite/command-center.json": json.dumps(command_center, indent=2),
    }
