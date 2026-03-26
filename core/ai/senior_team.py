# core/ai/senior_team.py
# Simulates a team of senior developers reviewing and improving generated code
# Each "developer" has a specialty and reviews from their perspective

import json
from core.ai.provider import generate
from core.ai.model_router import get_model


SENIOR_ROLES = {
    "tech_lead": {
        "model": "reasoner",
        "name": "Tech Lead (Kimi K2)",
        "focus": "architecture, patterns, scalability, security",
    },
    "backend_lead": {
        "model": "coder",
        "name": "Backend Lead (Qwen3)",
        "focus": "API design, database queries, error handling, performance",
    },
    "frontend_lead": {
        "model": "coder",
        "name": "Frontend Lead (Qwen3)",
        "focus": "UX, component design, state management, accessibility",
    },
    "reviewer": {
        "model": "decoder",
        "name": "Code Reviewer (Llama)",
        "focus": "bugs, edge cases, missing error handling, security holes",
    },
}


def tech_lead_review(spec: dict, api_contract: str) -> str:
    """Tech lead reviews architecture before code is written."""
    model = get_model("reasoner")
    prompt = f"""You are the tech lead on this project. Review the architecture and identify issues BEFORE coding begins.

PROJECT SPEC:
{json.dumps(spec, indent=2)}

API CONTRACT:
{api_contract[:3000]}

As tech lead, identify:
1. MISSING ENDPOINTS — what API routes are needed but not listed?
2. MISSING MODELS — what database tables are needed but not mentioned?
3. SECURITY GAPS — what auth/validation is missing?
4. RELATIONSHIP ERRORS — any wrong or missing FK relationships?
5. SCALABILITY CONCERNS — what will break at 10,000 users?
6. MISSING FEATURES — what would users expect that isn't spec'd?

For each issue, provide the EXACT fix needed.

Then write a CORRECTED and COMPLETE API contract that addresses all issues.
Be exhaustive. A senior team will implement from this.

Return JSON: {{
    "issues_found": ["issue 1", "issue 2"],
    "corrected_api_contract": "complete corrected spec here",
    "additional_models": ["Model1", "Model2"],
    "security_requirements": ["requirement 1", "requirement 2"],
    "approved": true
}}"""
    
    try:
        response = generate(model, prompt)
        cleaned = response.strip()
        if cleaned.startswith("```"):
            cleaned = "\n".join(cleaned.split("\n")[1:]).rstrip("`").strip()
        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1
        result = json.loads(cleaned[start:end])
        issues = result.get("issues_found", [])
        if issues:
            print(f"\n  🔍 Tech Lead found {len(issues)} improvements:")
            for issue in issues[:5]:
                print(f"     → {issue[:80]}")
        return result.get("corrected_api_contract", api_contract)
    except Exception as e:
        print(f"  ⚠️  Tech lead review skipped: {e}")
        return api_contract


def backend_review(files_json: str, spec: dict) -> str:
    """Backend lead reviews generated backend code."""
    model = get_model("coder")
    prompt = f"""You are a senior backend engineer doing a code review.

SPEC: {json.dumps(spec, indent=2)}

GENERATED BACKEND CODE:
{files_json[:4000]}

Review for these SPECIFIC issues:
1. Missing try/except blocks
2. Missing input validation
3. SQL injection vulnerabilities (raw queries without parameterization)
4. Missing db.session.rollback() in except blocks
5. Circular imports (importing from app.py inside routes)
6. Missing relationships in models
7. Missing indexes on foreign keys
8. Endpoints returning wrong HTTP status codes
9. Missing pagination on list endpoints
10. Hardcoded values that should be config

For EACH issue found, provide the EXACT corrected code.

Return JSON: {{
    "critical_bugs": ["bug description with fix"],
    "improvements": ["improvement description"],
    "corrected_files": [{{"path": "backend/routes/main.py", "content": "...full corrected content..."}}]
}}

Only include files in corrected_files if they have actual corrections needed."""

    try:
        response = generate(model, prompt)
        cleaned = response.strip()
        if cleaned.startswith("```"):
            cleaned = "\n".join(cleaned.split("\n")[1:]).rstrip("`").strip()
        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1
        result = json.loads(cleaned[start:end])
        bugs = result.get("critical_bugs", [])
        if bugs:
            print(f"\n  🔧 Backend Lead fixed {len(bugs)} bugs:")
            for bug in bugs[:3]:
                print(f"     → {str(bug)[:80]}")
        return result.get("corrected_files", [])
    except Exception as e:
        print(f"  ⚠️  Backend review skipped: {e}")
        return []


def frontend_review(files_json: str, spec: dict) -> str:
    """Frontend lead reviews generated frontend code."""
    model = get_model("coder")
    prompt = f"""You are a senior frontend engineer and UX expert doing a code review.

SPEC: {json.dumps(spec, indent=2)}

GENERATED FRONTEND CODE:
{files_json[:4000]}

Review for these SPECIFIC issues:
1. Missing loading states (data fetched without skeleton/spinner)
2. Missing error states (API errors not shown to user)
3. Missing empty states (empty lists with no message)
4. Form submissions without loading state (double-submit possible)
5. Missing key props in .map() calls
6. Direct DOM manipulation instead of React state
7. API calls in wrong lifecycle (missing useEffect dependencies)
8. No optimistic updates on mutations
9. No form validation before API call
10. Hardcoded API URLs not using the api.js service

For EACH issue, provide the EXACT corrected component code.

Return JSON: {{
    "ux_issues": ["issue description"],
    "bug_fixes": ["fix description"],
    "corrected_files": [{{"path": "frontend/src/pages/X.jsx", "content": "...full corrected content..."}}]
}}"""

    try:
        response = generate(model, prompt)
        cleaned = response.strip()
        if cleaned.startswith("```"):
            cleaned = "\n".join(cleaned.split("\n")[1:]).rstrip("`").strip()
        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1
        result = json.loads(cleaned[start:end])
        issues = result.get("ux_issues", [])
        if issues:
            print(f"\n  🎨 Frontend Lead fixed {len(issues)} UX issues:")
            for issue in issues[:3]:
                print(f"     → {str(issue)[:80]}")
        return result.get("corrected_files", [])
    except Exception as e:
        print(f"  ⚠️  Frontend review skipped: {e}")
        return []


def final_review(all_files: list, spec: dict) -> list:
    """Final code reviewer checks for bugs and security issues."""
    model = get_model("decoder")
    
    # Summarize files for review
    file_summary = []
    for f in all_files[:8]:
        path = f.get("path", "")
        content = f.get("content", "")[:500]
        file_summary.append(f"FILE: {path}\n{content}\n---")
    
    prompt = f"""You are a senior security engineer and code reviewer doing a final pass.

SPEC: {json.dumps(spec, indent=2)}

FILES SUMMARY:
{"".join(file_summary)}

Do a FINAL check for:
1. Any hardcoded secrets or API keys
2. SQL injection risks
3. XSS vulnerabilities in frontend
4. CORS misconfiguration
5. Missing authentication on sensitive endpoints
6. Any import errors (importing non-existent modules)
7. Any syntax errors you can spot
8. Missing error boundaries in React
9. Exposed internal error messages to frontend

Return JSON: {{
    "security_issues": ["issue"],
    "import_errors": ["file: issue"],
    "syntax_issues": ["file: issue"],
    "approved": true,
    "confidence_score": 85
}}"""

    try:
        response = generate(model, prompt)
        cleaned = response.strip()
        if cleaned.startswith("```"):
            cleaned = "\n".join(cleaned.split("\n")[1:]).rstrip("`").strip()
        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1
        result = json.loads(cleaned[start:end])
        score = result.get("confidence_score", 0)
        approved = result.get("approved", False)
        security = result.get("security_issues", [])
        imports = result.get("import_errors", [])
        print(f"\n  ✅ Final Review: {'APPROVED' if approved else 'NEEDS WORK'} | Confidence: {score}%")
        if security:
            print(f"     Security: {security[0][:80] if security else 'None'}")
        if imports:
            print(f"     Import fixes: {len(imports)}")
        return result
    except Exception as e:
        print(f"  ⚠️  Final review skipped: {e}")
        return {"approved": True, "confidence_score": 75}


def apply_corrections(original_files: list, corrections: list) -> list:
    """Apply corrected files from review back into the file list."""
    if not corrections:
        return original_files
    
    corrected_paths = {f["path"]: f["content"] for f in corrections if f.get("path") and f.get("content")}
    result = []
    for f in original_files:
        if f.get("path") in corrected_paths:
            result.append({"path": f["path"], "content": corrected_paths[f["path"]]})
        else:
            result.append(f)
    
    # Add any new files from corrections not in original
    original_paths = {f.get("path") for f in original_files}
    for path, content in corrected_paths.items():
        if path not in original_paths:
            result.append({"path": path, "content": content})
            print(f"  [SeniorTeam] Added missing file: {path}")
    
    return result
