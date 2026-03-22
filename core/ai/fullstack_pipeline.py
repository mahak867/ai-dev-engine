# core/ai/fullstack_pipeline.py
# APEX AI Dev Engine — Competition & Investor Grade
# Generates production-ready, deployable full-stack applications.

import json
from typing import Dict, Any
from core.ai.pipeline import Pipeline, PipelineStep
from core.ai.project_classifier import ProjectClassifier
from core.ai.public_apis import get_api_hint


# ─────────────────────────────────────────────────────────────────
# STEP 1 — ARCHITECTURE (Kimi K2)
# ─────────────────────────────────────────────────────────────────

def _architecture_prompt(ctx: dict) -> str:
    spec = ctx.get("spec", {})
    request = ctx.get("request", "")
    api_hint = get_api_hint(request)
    return f"""You are a principal engineer and CTO who has built products used by millions.
You design systems that are secure, scalable, and investor-ready.

PROJECT: {request}
SPEC: {json.dumps(spec, indent=2)}
{api_hint}

Produce a complete technical architecture document:

## PRODUCT VISION
One paragraph — what problem this solves, who uses it, why it matters.

## TECH STACK & DECISIONS
Every technology chosen and why. Trade-offs considered.

## COMPLETE FILE TREE
Every single file in backend/ and frontend/. No omissions.

## API CONTRACT
Every endpoint — method, path, auth required, request body (with types), 
success response, error responses, HTTP status codes.

## DATABASE SCHEMA  
Every table, every field with type/constraints/indexes.
SQLAlchemy model signatures. Relationships.

## AUTHENTICATION STRATEGY
Clerk handles all auth on frontend. Backend verifies requests are legitimate.
JWT optional for API-only routes. Social login (Google/GitHub) via Clerk.

## FRONTEND ROUTES & PAGES
Every React route, what it renders, what data it fetches, loading/error states.

## DEPLOYMENT CHECKLIST
Environment variables, Docker setup, production considerations.

## COMPETITIVE DIFFERENTIATORS  
What makes this app stand out. Features that would impress a judge or investor.

Be thorough. The code generation steps build directly from this.
"""


# ─────────────────────────────────────────────────────────────────
# STEP 2 — DATABASE SCHEMA (Qwen3-32B)
# ─────────────────────────────────────────────────────────────────

def _db_schema_prompt(ctx: dict) -> str:
    api = ctx.get("api_contract", "")
    request = ctx.get("request", "")
    return f"""You are a senior database architect.

PROJECT: {request}
ARCHITECTURE: {api}

Write complete SQLAlchemy models with:
- All fields: types, nullable, defaults, constraints
- Relationships with backref and lazy loading
- Indexes on all foreign keys and frequently queried fields  
- created_at / updated_at on every model using datetime.utcnow
- __repr__ method on every model
- to_dict() method returning JSON-serializable dict (no datetime objects — use .isoformat())
- Proper CASCADE delete rules

Start every file with:
from extensions import db
from datetime import datetime

Return as plain Python code only. No JSON wrapper.
"""


# ─────────────────────────────────────────────────────────────────
# STEP 3 — BACKEND (Qwen3-32B)
# ─────────────────────────────────────────────────────────────────

def _backend_prompt(ctx: dict) -> str:
    spec    = ctx.get("spec", {})
    api     = ctx.get("api_contract", "")
    schema  = ctx.get("db_schema", "")
    request = ctx.get("request", "")
    needs_auth = spec.get("needs_auth", False)

    auth_note = """
AUTH NOTE: This app uses Clerk on the frontend for authentication.
- DO NOT add @jwt_required() decorators — Clerk handles auth on frontend
- DO NOT import flask_jwt_extended in routes
- Routes should be open (no auth guards) OR check a simple header if needed
- Never import 'clerk' Python package — it does not exist
""" if needs_auth else ""

    return f"""You are a senior backend engineer. Write production-grade Flask code.

PROJECT: {request}
ARCHITECTURE: {api}
DATABASE SCHEMA: {schema}
{auth_note}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MANDATORY FILE TEMPLATES — COPY EXACTLY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

backend/extensions.py MUST BE:
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager
db = SQLAlchemy()
bcrypt = Bcrypt()
jwt = JWTManager()

backend/config.py MUST BE:
import os
class Config:
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'dev-secret-change-in-prod')
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-change-in-prod')
    CORS_ORIGINS = ['http://localhost:5173', 'http://localhost:3000']

backend/app.py MUST FOLLOW THIS PATTERN:
from flask import Flask, jsonify
from flask_cors import CORS
from config import Config
from extensions import db, bcrypt, jwt

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    bcrypt.init_app(app)
    jwt.init_app(app)
    CORS(app, origins=app.config['CORS_ORIGINS'], supports_credentials=True)
    
    # Import ALL models before create_all
    from models import User  # add all models here
    
    # Register blueprints
    from routes.auth import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/api/v1')
    # add more blueprints here
    
    # Health check
    @app.route('/health')
    def health():
        return jsonify({{'status': 'ok', 'version': '1.0.0'}})
    
    with app.app_context():
        db.create_all()
    
    return app

app = create_app()
if __name__ == '__main__':
    app.run(debug=True, port=5000)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CRITICAL RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. NEVER import from app.py in models.py or routes/ — circular import
2. ALWAYS import db, bcrypt, jwt from extensions.py
3. Database URI: sqlite:///app.db (no subdirectory)
4. Every route returns jsonify({{}}) — never plain strings
5. Validate all POST/PUT inputs — return 400 with message if invalid
6. Use try/except on all db operations — return 500 on failure
7. Enable CORS properly with flask-cors
8. requirements.txt: flask flask-cors flask-sqlalchemy flask-bcrypt flask-jwt-extended python-dotenv gunicorn

RESPONSE FORMAT (use consistently):
Success: {{"success": true, "data": {{}}, "message": "..."}}
List:    {{"success": true, "data": [], "total": N, "page": 1}}
Error:   {{"success": false, "error": "...", "code": "ERROR_CODE"}}

QUALITY BAR:
- Input validation on every POST/PUT
- Proper HTTP status codes (200, 201, 400, 401, 404, 500)
- No hardcoded secrets
- Pagination on list endpoints (page, per_page params)
- Search/filter on list endpoints where relevant

Generate ALL backend files completely. No truncation. No placeholders.

Return ONLY valid JSON:
{{"files":[{{"path":"backend/app.py","content":"..."}},{{"path":"backend/extensions.py","content":"..."}},{{"path":"backend/config.py","content":"..."}},{{"path":"backend/models.py","content":"..."}},{{"path":"backend/routes/__init__.py","content":""}},{{"path":"backend/routes/main.py","content":"..."}}]}}
"""


# ─────────────────────────────────────────────────────────────────
# STEP 4 — FRONTEND (Qwen3-32B)
# ─────────────────────────────────────────────────────────────────

def _frontend_prompt(ctx: dict) -> str:
    spec       = ctx.get("spec", {})
    api        = ctx.get("api_contract", "")
    request    = ctx.get("request", "")
    needs_auth = spec.get("needs_auth", False)
    use_clerk  = spec.get("use_clerk", True)

    clerk_ui = """
CLERK AUTH:
- Install @clerk/clerk-react in package.json
- main.jsx: wrap app in <ClerkProvider publishableKey={import.meta.env.VITE_CLERK_PUBLISHABLE_KEY}>
- App.jsx routes: /sign-in -> <SignIn routing="path" path="/sign-in" />, /sign-up -> <SignUp routing="path" path="/sign-up" />
- Protected routes: wrap in <SignedIn>...</SignedIn><SignedOut><Navigate to="/sign-in" /></SignedOut>
- Navbar: show <UserButton afterSignOutUrl="/sign-in" /> when signed in
- Get token: const { getToken } = useAuth(); const token = await getToken()
- API calls: Authorization: Bearer ${token}
""" if (needs_auth and use_clerk) else ""

    css = """@import url('https://fonts.googleapis.com/css2?family=Fraunces:wght@700;900&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500&display=swap');
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#080808;--surface:#0f0f0f;--surface-2:#161616;--border:#222;--border-hover:#333;--accent:#f0c040;--accent-dim:rgba(240,192,64,0.08);--text:#f0ede8;--text-2:#909090;--text-3:#505050;--green:#34d399;--red:#f87171;--r:8px;--r-lg:14px;--r-xl:20px;--t:0.15s cubic-bezier(0.4,0,0.2,1);--shadow-lg:0 16px 48px rgba(0,0,0,0.8);--font-display:"Fraunces",serif;--font-body:"DM Sans",sans-serif}
html{scroll-behavior:smooth}body{background:var(--bg);color:var(--text);font-family:var(--font-body);font-weight:300;min-height:100vh;-webkit-font-smoothing:antialiased}
::selection{background:var(--accent-dim);color:var(--accent)}::-webkit-scrollbar{width:5px}::-webkit-scrollbar-thumb{background:var(--border-hover);border-radius:3px}
.navbar{position:fixed;top:0;left:0;right:0;z-index:100;height:56px;display:flex;align-items:center;justify-content:space-between;padding:0 24px;background:rgba(8,8,8,0.8);backdrop-filter:blur(24px);border-bottom:1px solid var(--border)}
.navbar-logo{font-family:var(--font-display);font-size:1.1rem;font-weight:700;color:var(--accent)}.navbar-links{display:flex;align-items:center;gap:6px}.nav-link{color:var(--text-2);font-size:0.85rem;padding:6px 12px;border-radius:var(--r);transition:var(--t)}.nav-link:hover{color:var(--text);background:var(--surface-2)}
.page{min-height:100vh;padding:76px 24px 80px;max-width:1200px;margin:0 auto}.page-sm{max-width:680px}
.hero{padding:80px 0 64px;text-align:center}.hero h1{font-family:var(--font-display);font-size:clamp(2.5rem,6vw,4.5rem);font-weight:900;line-height:1.05;letter-spacing:-0.04em;margin-bottom:20px}.hero h1 em{font-style:normal;color:var(--accent)}.hero-sub{color:var(--text-2);font-size:1.1rem;max-width:520px;margin:0 auto 40px;line-height:1.75}.hero-cta{display:flex;gap:14px;justify-content:center;flex-wrap:wrap}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;border-radius:var(--r);font-family:var(--font-body);font-weight:500;cursor:pointer;transition:var(--t);white-space:nowrap;border:none;font-size:0.875rem}.btn-primary{background:var(--accent);color:#080808;padding:10px 22px;font-weight:600}.btn-primary:hover{filter:brightness(1.08)}.btn-secondary{background:var(--surface-2);color:var(--text);padding:10px 22px;border:1px solid var(--border)}.btn-secondary:hover{border-color:var(--border-hover)}.btn-ghost{background:transparent;color:var(--text-2);padding:8px 14px}.btn-ghost:hover{color:var(--text);background:var(--surface-2)}.btn-danger{background:rgba(248,113,113,0.1);color:var(--red);border:1px solid rgba(248,113,113,0.2);padding:8px 16px}.btn-sm{padding:6px 14px;font-size:0.8rem}.btn-lg{padding:13px 30px;font-size:0.95rem}.btn:disabled{opacity:0.35;cursor:not-allowed}
.form-group{display:flex;flex-direction:column;gap:7px;margin-bottom:20px}.form-label{font-size:0.75rem;font-weight:600;color:var(--text-2);text-transform:uppercase;letter-spacing:0.07em}.input,.textarea{width:100%;background:var(--surface-2);border:1px solid var(--border);border-radius:var(--r);padding:10px 14px;color:var(--text);font-family:var(--font-body);font-size:0.875rem;outline:none;transition:var(--t)}.input:focus,.textarea:focus{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-dim)}.input::placeholder{color:var(--text-3)}
.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--r-lg);padding:24px;transition:var(--t)}.card:hover{border-color:var(--border-hover)}.card-hover:hover{transform:translateY(-2px);box-shadow:var(--shadow-lg)}
.grid{display:grid;gap:16px}.grid-2{grid-template-columns:repeat(2,1fr)}.grid-3{grid-template-columns:repeat(3,1fr)}.grid-auto{grid-template-columns:repeat(auto-fill,minmax(280px,1fr))}
.stat-card{background:var(--surface);border:1px solid var(--border);border-radius:var(--r-lg);padding:24px}.stat-value{font-family:var(--font-display);font-size:2.2rem;font-weight:700;color:var(--accent);line-height:1;margin-bottom:4px}.stat-label{font-size:0.72rem;color:var(--text-3);text-transform:uppercase;letter-spacing:0.09em}
.badge{display:inline-flex;align-items:center;padding:3px 10px;border-radius:100px;font-size:0.7rem;font-weight:600}.badge-accent{background:var(--accent-dim);color:var(--accent)}.badge-green{background:rgba(52,211,153,0.1);color:var(--green)}.badge-red{background:rgba(248,113,113,0.1);color:var(--red)}
.table-container{border:1px solid var(--border);border-radius:var(--r-lg);overflow:hidden}table{width:100%;border-collapse:collapse}th{padding:11px 16px;text-align:left;font-size:0.7rem;font-weight:600;color:var(--text-3);text-transform:uppercase;letter-spacing:0.09em;border-bottom:1px solid var(--border);background:var(--surface-2)}td{padding:13px 16px;font-size:0.875rem;border-bottom:1px solid var(--border)}tbody tr:hover{background:var(--surface-2)}
.spinner{width:24px;height:24px;border:2px solid var(--border);border-top-color:var(--accent);border-radius:50%;animation:spin 0.6s linear infinite}.loading-center{display:flex;justify-content:center;padding:60px}@keyframes spin{to{transform:rotate(360deg)}}
.empty-state{text-align:center;padding:80px 24px;color:var(--text-3)}.empty-icon{font-size:3rem;opacity:0.15;margin-bottom:16px;display:block}
.alert-error{background:rgba(248,113,113,0.08);border:1px solid rgba(248,113,113,0.25);border-radius:var(--r);padding:12px 16px;color:var(--red);font-size:0.875rem}.alert-success{background:rgba(52,211,153,0.08);border:1px solid rgba(52,211,153,0.25);border-radius:var(--r);padding:12px 16px;color:var(--green);font-size:0.875rem}
.modal-overlay{position:fixed;inset:0;background:rgba(0,0,0,0.7);backdrop-filter:blur(8px);z-index:200;display:flex;align-items:center;justify-content:center;padding:20px}.modal{background:var(--surface);border:1px solid var(--border);border-radius:var(--r-xl);padding:28px;width:100%;max-width:480px;animation:scaleIn 0.2s ease}
.sidebar{width:240px;min-height:100vh;background:var(--surface);border-right:1px solid var(--border);position:fixed;top:0;left:0}.sidebar-logo{font-family:var(--font-display);font-size:1.1rem;font-weight:700;color:var(--accent);padding:20px 16px}.sidebar-link{display:flex;align-items:center;gap:10px;padding:9px 12px;border-radius:var(--r);color:var(--text-2);font-size:0.85rem;transition:var(--t);margin-bottom:2px}.sidebar-link:hover{color:var(--text);background:var(--surface-2)}.sidebar-link.active{color:var(--text);background:var(--surface-2);font-weight:500}.main-content{margin-left:240px;padding:32px}
.error-box{background:rgba(248,113,113,0.08);border:1px solid rgba(248,113,113,0.25);border-radius:var(--r);padding:12px 16px;margin-bottom:16px;font-size:0.875rem;color:var(--red)}
.flex{display:flex}.items-center{align-items:center}.justify-between{justify-content:space-between}.gap-3{gap:12px}.gap-4{gap:16px}.flex-1{flex:1}.w-full{width:100%}.text-center{text-align:center}.text-muted{color:var(--text-2)}.text-accent{color:var(--accent)}.text-sm{font-size:0.82rem}.font-bold{font-weight:700}.divider{height:1px;background:var(--border);margin:24px 0}
@keyframes fadeUp{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:translateY(0)}}@keyframes scaleIn{from{opacity:0;transform:scale(0.95)}to{opacity:1;transform:scale(1)}}
.animate-fade-up{animation:fadeUp 0.3s ease forwards}.stagger-1{animation-delay:0.06s;opacity:0}.stagger-2{animation-delay:0.12s;opacity:0}.stagger-3{animation-delay:0.18s;opacity:0}
@media(max-width:768px){.navbar{padding:0 16px}.page{padding:68px 16px 60px}.grid-2,.grid-3{grid-template-columns:1fr}.sidebar{width:100%;position:relative;border-right:none}.main-content{margin-left:0}}"""

    return f"""
You are a world-class product designer and React engineer. Build a stunning, investor-ready frontend.

PROJECT: {request}
API: {api[:1500]}
{clerk_ui}

REQUIRED FILES:
- frontend/index.html (exact boilerplate below)
- frontend/vite.config.js (exact boilerplate below)
- frontend/package.json (exact boilerplate below)
- frontend/src/main.jsx (exact boilerplate below)
- frontend/src/App.jsx (full router + all pages)
- frontend/src/index.css (use the CSS below + extend for app)
- frontend/src/services/api.js (all API calls)
- frontend/src/components/Navbar.jsx
- frontend/src/pages/ (one file per route)

EXACT BOILERPLATE:

index.html:
<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1.0"/><title>App</title></head><body><div id="root"></div><script type="module" src="/src/main.jsx"></script></body></html>

vite.config.js:
import {{defineConfig}} from 'vite'; import react from '@vitejs/plugin-react'; export default defineConfig({{plugins:[react()],server:{{proxy:{{'/api':'http://localhost:5000'}}}}}});

package.json:
{{"name":"app","version":"1.0.0","scripts":{{"dev":"vite","build":"vite build","preview":"vite preview"}},"dependencies":{{"react":"^18.3.0","react-dom":"^18.3.0","react-router-dom":"^6.24.0","@clerk/clerk-react":"^5.0.0"}},"devDependencies":{{"vite":"^5.3.0","@vitejs/plugin-react":"^4.3.0"}}}}

main.jsx:
import React from 'react'; import ReactDOM from 'react-dom/client'; import App from './App'; import './index.css'; ReactDOM.createRoot(document.getElementById('root')).render(<App/>);

App.jsx root route MUST be path="/" not path="/:".

CSS FOR index.css (copy exactly then add app-specific styles):
{css}

API.JS PATTERN:
const BASE = 'http://localhost:5000/api/v1';
async function req(method, path, body, token) {{
  const headers = {{'Content-Type':'application/json'}};
  if (token) headers['Authorization'] = 'Bearer ' + token;
  const res = await fetch(BASE + path, {{method, headers, body: body ? JSON.stringify(body) : undefined}});
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'Request failed');
  return data;
}}
export const api = {{
  get: (path, token) => req('GET', path, null, token),
  post: (path, body, token) => req('POST', path, body, token),
  put: (path, body, token) => req('PUT', path, body, token),
  del: (path, token) => req('DELETE', path, null, token),
}};

QUALITY: Every page needs loading state, empty state, error handling. No placeholder text. Looks like Linear.app or Vercel dashboard.

Return ONLY raw valid JSON: {{"files":[{{"path":"frontend/index.html","content":"..."}},{{"path":"frontend/src/index.css","content":"..."}}]}}
"""


def _config_prompt(ctx: dict) -> str:
    spec = ctx.get("spec", {})
    needs_auth = spec.get("needs_auth", False)
    return f"""
You are a senior DevOps engineer. Generate production-ready deployment files.

Spec: {json.dumps(spec, indent=2)}

Generate:
1. .env.example — all env vars with descriptions
2. requirements.txt — flask==3.0.0, flask-cors==4.0.0, flask-sqlalchemy==3.1.1, flask-bcrypt==1.0.1, python-dotenv==1.0.0, gunicorn==21.2.0{"\\nflask-jwt-extended==4.6.0" if needs_auth else ""}
3. Dockerfile — python:3.11-slim, non-root user, gunicorn
4. docker-compose.yml — backend service
5. .gitignore — python + node + env files
6. README.md — project title, features, tech stack, quick start, env vars table, API docs

Return ONLY valid JSON: {{"files":[{{"path":".env.example","content":"..."}}]}}
"""


def build_fullstack_pipeline(spec: dict) -> Pipeline:
    has_backend  = spec.get("backend_framework",  "none") != "none"
    has_frontend = spec.get("frontend_framework", "none") != "none"
    has_db       = spec.get("needs_database", False)
    steps = []

    steps.append(PipelineStep(
        name="Architecture & System Design",
        task_type="reasoner",
        prompt_fn=_architecture_prompt,
        output_key="api_contract",
    ))

    if has_db:
        steps.append(PipelineStep(
            name="Database Schema & Models",
            task_type="coder",
            prompt_fn=_db_schema_prompt,
            output_key="db_schema",
        ))
    else:
        steps.append(PipelineStep(
            name="DB Schema (skipped)",
            task_type="general",
            prompt_fn=lambda ctx: "NO_DB",
            output_key="db_schema",
        ))

    if has_backend:
        steps.append(PipelineStep(
            name="Backend API Generation",
            task_type="coder",
            prompt_fn=_backend_prompt,
            output_key="backend_files",
        ))
    else:
        steps.append(PipelineStep(
            name="Backend (skipped)",
            task_type="general",
            prompt_fn=lambda ctx: '{"files":[]}',
            output_key="backend_files",
        ))

    if has_frontend:
        steps.append(PipelineStep(
            name="Frontend UI Generation",
            task_type="coder",
            prompt_fn=_frontend_prompt,
            output_key="frontend_files",
        ))
    else:
        steps.append(PipelineStep(
            name="Frontend (skipped)",
            task_type="general",
            prompt_fn=lambda ctx: '{"files":[]}',
            output_key="frontend_files",
        ))

    steps.append(PipelineStep(
        name="Deployment & Config Files",
        task_type="decoder",
        prompt_fn=_config_prompt,
        output_key="config_files",
    ))

    return Pipeline(steps=steps, verbose=True)


def run_fullstack_generation(request: str):
    print("\n Classifying project...")
    classifier = ProjectClassifier()
    spec = classifier.classify(request)
    print(f"\n Detected: {spec.get('project_type')} -- {spec.get('description')}")
    print(f"   Stack: {spec.get('backend_framework')} + {spec.get('frontend_framework')} + {spec.get('database_type')}")
    print(f"   Auth: {'Clerk' if spec.get('needs_auth') else 'None'}\n")
    pipeline = build_fullstack_pipeline(spec)
    ctx = pipeline.run({"request": request, "spec": spec})
    ctx["spec"] = spec
    return ctx
