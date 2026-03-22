# core/ai/project_classifier.py
# Apex project classifier — detects type, stack, and special modes.

import json
from core.ai.model_router import get_model
from core.ai.provider import generate

PROJECT_TYPES = {
    "fullstack_react":   "Full-stack — Flask backend + React frontend",
    "fullstack_vue":     "Full-stack — Flask backend + Vue frontend",
    "fullstack_html":    "Full-stack — Flask backend + HTML/CSS/JS frontend",
    "frontend_react":    "Frontend only — React SPA",
    "frontend_html":     "Frontend only — Static HTML/CSS/JS",
    "backend_api":       "Backend only — REST API",
    "saas_platform":     "SaaS platform with subscriptions and dashboard",
    "marketplace":       "Two-sided marketplace",
    "dashboard":         "Analytics or admin dashboard",
    "ecommerce":         "E-commerce store",
    "social_app":        "Social platform with feeds/follows",
    "ctf_tool":          "CTF/security tool (Python CLI or web)",
    "cli_tool":          "Command-line tool",
    "data_pipeline":     "Data processing / analysis",
    "landing_page":      "Marketing landing page",
}


class ProjectClassifier:
    def classify(self, request: str) -> dict:
        model = get_model("general")  # Use fast model for classification speed
        prompt = f"""Classify this project request and return a JSON spec.

Valid project_type values:
{json.dumps(PROJECT_TYPES, indent=2)}

Return ONLY valid JSON with this exact structure:
{{
  "project_type": "<type>",
  "app_name": "<snake_case_name>",
  "description": "<one sentence>",
  "backend_framework": "flask" | "fastapi" | "none",
  "frontend_framework": "react" | "vue" | "html" | "none",
  "needs_database": true | false,
  "database_type": "sqlite" | "postgresql" | "none",
  "needs_auth": true | false,
  "use_clerk": true | false,
  "tech_stack": ["list", "of", "technologies"],
  "key_features": ["feature 1", "feature 2", "feature 3"],
  "target_users": "<who uses this>",
  "competition_ready": true | false
}}

Rules:
- use_clerk should be true whenever needs_auth is true
- competition_ready is true for hackathon/CTF/demo projects
- prefer react over html for frontend
- prefer flask over fastapi unless explicitly requested

Project request: {request}
"""
        response = generate(model, prompt)
        cleaned = response.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:])
            cleaned = cleaned.rstrip("`").strip()
        try:
            return json.loads(cleaned)
        except Exception:
            start = cleaned.find("{")
            end   = cleaned.rfind("}") + 1
            return json.loads(cleaned[start:end])



