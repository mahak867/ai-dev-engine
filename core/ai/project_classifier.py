# core/ai/project_classifier.py
# Elite project classifier - detects type, complexity, integrations, and special modes

import json
from core.ai.model_router import get_model
from core.ai.provider import generate

PROJECT_TYPES = {
    "fullstack_react":   "Full-stack — Flask backend + React frontend",
    "saas_platform":     "SaaS platform with subscriptions, dashboard, and teams",
    "marketplace":       "Two-sided marketplace with buyers and sellers",
    "social_app":        "Social platform with feeds, follows, and interactions",
    "ecommerce":         "E-commerce store with products, cart, and payments",
    "dashboard":         "Analytics or admin dashboard with charts and metrics",
    "project_management":"Project management tool with tasks, teams, and workflows",
    "crm":               "Customer relationship management system",
    "cms":               "Content management system with editor and publishing",
    "booking_platform":  "Booking/scheduling platform with calendar and payments",
    "learning_platform": "Learning management system with courses and progress",
    "community_platform":"Community platform with forums, posts, and moderation",
    "api_platform":      "API-first platform with developer dashboard",
    "fintech_app":       "Financial technology app with transactions and analytics",
    "health_app":        "Health/fitness tracking app with metrics and goals",
    "real_estate":       "Real estate platform with listings and search",
    "job_board":         "Job board with listings, applications, and profiles",
    "event_platform":    "Event management and ticketing platform",
    "food_delivery":     "Food ordering and delivery platform",
    "ctf_tool":          "CTF/security tool for competitions and research",
    "devtool":           "Developer tool or productivity application",
    "landing_page":      "Marketing landing page with conversion focus",
    "portfolio":         "Portfolio or personal branding site",
    "blog_platform":     "Blog/content platform with markdown and SEO",
    "chat_app":          "Real-time chat application with rooms and users",
    "ai_app":            "AI-powered application with LLM integration",
    "iot_dashboard":     "IoT device monitoring and control dashboard",
    "inventory_system":  "Inventory management and tracking system",
    "hr_platform":       "HR management system with employees and payroll",
    "document_platform": "Document management and collaboration platform",
}

COMPLEXITY_LEVELS = {
    "simple":   "1-3 models, basic CRUD, single user type",
    "moderate": "4-6 models, multiple resources, auth, basic workflows",
    "complex":  "7-12 models, RBAC, complex relationships, multi-step workflows",
    "advanced": "12+ models, microservice-ready, real-time, payments, AI, analytics",
}



def _detect_design(request: str) -> dict:
    """Detect accent color and design style from request. (from apex-pro design_engine)"""
    p = request.lower()
    # Accent color detection
    if any(w in p for w in ["bold", "vibrant", "energetic", "pink", "red"]):
        accent = "#ec4899"
    elif any(w in p for w in ["minimal", "clean", "simple", "white"]):
        accent = "#18181b"
    elif any(w in p for w in ["blue", "professional", "corporate", "saas"]):
        accent = "#3b82f6"
    elif any(w in p for w in ["green", "health", "finance", "money"]):
        accent = "#10b981"
    elif any(w in p for w in ["purple", "creative", "ai", "tech"]):
        accent = "#8b5cf6"
    else:
        accent = "#f0c040"  # APEX gold default

    # Hero style
    if any(w in p for w in ["landing", "marketing", "saas", "startup"]):
        hero = "animated-gradient"
    elif any(w in p for w in ["dashboard", "admin", "analytics"]):
        hero = "stats-hero"
    else:
        hero = "glass-card"

    return {
        "accent_color": accent,
        "hero_style": hero,
        "dark_mode": True,
        "glassmorphism": True,
    }


class ProjectClassifier:
    def classify(self, request: str) -> dict:
        model = get_model("general")
        prompt = f"""You are an expert software architect. Classify this project request.

Valid project_type values:
{json.dumps(PROJECT_TYPES, indent=2)}

Complexity levels:
{json.dumps(COMPLEXITY_LEVELS, indent=2)}

Return ONLY valid JSON with this EXACT structure (no extra fields, no markdown):
{{
  "project_type": "<type from list above>",
  "app_name": "<descriptive_snake_case_name>",
  "description": "<one clear sentence>",
  "complexity": "<simple|moderate|complex|advanced>",
  "backend_framework": "flask",
  "frontend_framework": "react",
  "needs_database": true,
  "database_type": "sqlite",
  "needs_auth": true,
  "use_clerk": true,
  "needs_payments": false,
  "payment_type": "none",
  "needs_realtime": false,
  "needs_ai": false,
  "needs_file_upload": false,
  "needs_email": false,
  "needs_charts": false,
  "needs_search": false,
  "needs_rbac": false,
  "user_roles": ["user", "admin"],
  "core_models": ["Model1", "Model2", "Model3"],
  "core_features": ["feature 1", "feature 2", "feature 3", "feature 4", "feature 5"],
  "tech_stack": ["Flask", "React", "SQLite", "Clerk"],
  "target_users": "<who uses this>",
  "competition_ready": false,
  "suggested_name": "<AppName>"
}}

Classification rules:
- use_clerk = true whenever needs_auth = true
- needs_payments = true for: SaaS, e-commerce, marketplace, booking, events
- needs_realtime = true for: chat, collaboration, live dashboards, notifications
- needs_ai = true for: AI assistants, content generation, smart features
- needs_charts = true for: dashboards, analytics, metrics, reporting
- needs_rbac = true for: admin panels, teams, multi-role systems
- complexity = advanced for: marketplace, social, food delivery, booking
- complexity = complex for: SaaS, CRM, PM tool, LMS
- complexity = moderate for: dashboard, blog, job board, portfolio
- core_models: list 3-6 main database models needed
- user_roles: always include "user", add "admin" if needs_rbac

Project request: {request}"""

        response = generate(model, prompt)
        cleaned = response.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:])
            cleaned = cleaned.rstrip("`").strip()
        try:
            result = json.loads(cleaned)
            # Ensure required fields exist
            result.setdefault('complexity', 'moderate')
            result.setdefault('needs_realtime', False)
            result.setdefault('needs_ai', False)
            result.setdefault('needs_charts', False)
            result.setdefault('needs_rbac', False)
            result.setdefault('needs_search', False)
            result.setdefault('needs_file_upload', False)
            result.setdefault('needs_email', False)
            result.setdefault('core_models', [])
            result.setdefault('user_roles', ['user', 'admin'])
            return result
        except Exception:
            start = cleaned.find("{")
            end = cleaned.rfind("}") + 1
            result = json.loads(cleaned[start:end])
            result.setdefault('complexity', 'moderate')
            result.setdefault('needs_rbac', False)
            result.setdefault('core_models', [])
            result.update(_detect_design(request))
            return result
