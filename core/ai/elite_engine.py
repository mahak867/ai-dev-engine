import json
import platform
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from core.ai.integrations import INTEGRATIONS, detect_integrations, get_extra_packages
from core.ai.skills_library import SKILLS, SKILL_CATEGORIES, get_skills_for_task


MODE_TO_TASK = {
    "Agent Builder": "planning",
    "Hackathon Pack": "planning",
    "CTF Lab": "security",
}


def _task_for_mode(mode: str) -> str:
    return MODE_TO_TASK.get(mode, "planning")


def _select_skills(mode: str, prompt: str, limit: int = 16) -> List[str]:
    task = _task_for_mode(mode)
    preferred = get_skills_for_task(task)
    text = prompt.lower()
    keyword_boost = []
    if "react" in text or "ui" in text or "frontend" in text:
        keyword_boost.extend(SKILL_CATEGORIES.get("frontend", []))
    if "api" in text or "backend" in text or "database" in text:
        keyword_boost.extend(SKILL_CATEGORIES.get("backend", []))
    if "deploy" in text or "devops" in text:
        keyword_boost.extend(SKILL_CATEGORIES.get("devops", []))
    if "test" in text or "quality" in text:
        keyword_boost.extend(SKILL_CATEGORIES.get("testing", []))
    if "performance" in text:
        keyword_boost.extend(SKILL_CATEGORIES.get("performance", []))
    if "security" in text or "ctf" in text:
        keyword_boost.extend(SKILL_CATEGORIES.get("security", []))

    merged = []
    for name in preferred + keyword_boost:
        if name in SKILLS and name not in merged:
            merged.append(name)
    if len(merged) < limit:
        for name in SKILLS.keys():
            if name not in merged:
                merged.append(name)
            if len(merged) >= limit:
                break
    return merged[:limit]


def _doctor_lines(project_path: Path, cloud_provider: str, cloud_profile: str) -> List[str]:
    lines = []
    lines.append(f"- Timestamp: {datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"- OS: {platform.system()} {platform.release()}")
    lines.append(f"- Python: {sys.version.split()[0]}")
    lines.append(f"- Workspace: {project_path}")
    lines.append(f"- Cloud provider preference: {cloud_provider}")
    lines.append(f"- Cloud profile: {cloud_profile}")
    lines.append(f"- Project path exists: {'yes' if project_path.exists() else 'no'}")
    lines.append(f"- Write access check: {'yes' if _check_write(project_path) else 'no'}")
    lines.append("- Runtime doctor style inspired by claw-code diagnostics workflows.")
    return lines


def _check_write(project_path: Path) -> bool:
    try:
        test_file = project_path / ".write_check.tmp"
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def generate_elite_artifacts(
    project_path: Path,
    mode: str,
    prompt: str,
    cloud_provider: str,
    cloud_profile: str,
) -> Dict[str, str]:
    task = _task_for_mode(mode)
    spec = {"project_type": task}
    detected_integrations = detect_integrations(prompt, spec)
    packages = get_extra_packages(prompt, spec)
    selected_skills = _select_skills(mode, prompt)

    manifest = {
        "name": project_path.name,
        "mode": mode,
        "task": task,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "prompt": prompt,
        "cloud": {
            "provider_preference": cloud_provider,
            "profile": cloud_profile,
        },
        "counts": {
            "all_integrations_available": len(INTEGRATIONS),
            "all_skills_available": len(SKILLS),
            "detected_integrations": len(detected_integrations),
            "selected_skills": len(selected_skills),
        },
        "detected_integrations": detected_integrations,
        "selected_skills": selected_skills,
        "packages": packages,
        "sources": {
            "runtime_inspiration": "https://github.com/instructkr/claw-code",
            "skills_catalog_inspiration": "https://github.com/sickn33/antigravity-awesome-skills",
        },
    }

    integration_lines = [
        "# Integration Matrix",
        "",
        f"Detected integrations ({len(detected_integrations)}): {', '.join(detected_integrations) if detected_integrations else 'none'}",
        f"Total integrations available in engine: {len(INTEGRATIONS)}",
        "",
        "## Suggested packages",
        f"- Frontend: {', '.join(packages.get('frontend', [])) if packages.get('frontend') else 'none'}",
        f"- Backend: {', '.join(packages.get('backend', [])) if packages.get('backend') else 'none'}",
        "",
        "## Notes",
        "- This matrix is auto-detected from your prompt and mode.",
        "- You can force additional integrations by adding explicit keywords in the prompt.",
    ]

    skills_lines = [
        "# Skill Bundle",
        "",
        f"Selected skills ({len(selected_skills)} of {len(SKILLS)} available):",
        "",
    ]
    for name in selected_skills:
        first_line = SKILLS.get(name, "").strip().splitlines()[0] if SKILLS.get(name) else ""
        skills_lines.append(f"- `{name}`: {first_line}")
    skills_lines.extend(
        [
            "",
            "## Source Alignment",
            "- Workflow bundling pattern inspired by antigravity-awesome-skills.",
            "- Agent discipline pattern inspired by claw-code.",
        ]
    )

    doctor = ["# Doctor Report", ""] + _doctor_lines(project_path, cloud_provider, cloud_profile)

    all_integrations_lines = [
        "# Full Integrations Catalog",
        "",
        f"Total integrations available: {len(INTEGRATIONS)}",
        "",
    ]
    for name, info in sorted(INTEGRATIONS.items(), key=lambda item: item[0]):
        keywords = ", ".join(info.get("keywords", [])[:8])
        all_integrations_lines.append(f"- `{name}` | keywords: {keywords}")

    all_skills_lines = [
        "# Full Skills Catalog",
        "",
        f"Total skills available: {len(SKILLS)}",
        "",
    ]
    for name in sorted(SKILLS.keys()):
        first_line = SKILLS[name].strip().splitlines()[0] if SKILLS[name].strip() else ""
        all_skills_lines.append(f"- `{name}`: {first_line}")

    return {
        "docs/elite-manifest.json": json.dumps(manifest, indent=2),
        "docs/integration-matrix.md": "\n".join(integration_lines) + "\n",
        "docs/skill-bundle.md": "\n".join(skills_lines) + "\n",
        "docs/doctor-report.md": "\n".join(doctor) + "\n",
        "docs/catalog-integrations.md": "\n".join(all_integrations_lines) + "\n",
        "docs/catalog-skills.md": "\n".join(all_skills_lines) + "\n",
    }
