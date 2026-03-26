# core/ai/fullstack_pipeline.py
# APEX AI Dev Engine — Competition & Investor Grade
# Generates production-ready, deployable full-stack applications.

import json
from typing import Dict, Any
from core.ai.pipeline import Pipeline, PipelineStep
from core.ai.project_classifier import ProjectClassifier
from core.ai.public_apis import get_api_hint
from core.ai.integrations import get_integration_prompt, get_extra_packages


# ─────────────────────────────────────────────────────────────────
# STEP 1 — ARCHITECTURE (Kimi K2)
# ─────────────────────────────────────────────────────────────────

def _architecture_prompt(ctx: dict) -> str:
    spec = ctx.get("spec", {})
    request = ctx.get("request", "")
    api_hints = get_api_hint(request)
    integrations = get_integration_prompt(request, spec)
    return f"""You are a CTO-level principal engineer. You have shipped production systems at Stripe, Linear, Notion, and Vercel.
You think in systems. You never cut corners. Every decision is deliberate and documented.

PROJECT: {request}
SPEC: {json.dumps(spec, indent=2)}
{api_hints}

━━━ PRODUCE A COMPLETE TECHNICAL BLUEPRINT ━━━

## 1. PRODUCT VISION & SCOPE
- What this does in one sharp sentence
- Who uses it (personas)
- Core value proposition
- MVP scope vs future features

## 2. COMPLETE FILE TREE
List EVERY file that will be generated. No exceptions. Use this format:
backend/
  app.py, config.py, extensions.py, models.py
  routes/auth.py, routes/[resource].py, routes/[resource2].py
  utils/helpers.py, utils/validators.py
frontend/src/
  App.jsx, main.jsx, index.css
  pages/Dashboard.jsx, pages/[Page].jsx (one per route)
  components/Navbar.jsx, components/[Component].jsx
  services/api.js
  hooks/useToast.js, hooks/use[Feature].js

## 3. DATABASE SCHEMA (complete)
For EVERY table:
  - All fields with types, constraints, indexes
  - Foreign key relationships
  - Many-to-many junction tables
  - Enum values for status fields
  - Which fields are indexed for performance

## 4. ROLE-BASED ACCESS CONTROL
Define all user roles and permissions:
  - admin: full access
  - [role]: specific permissions
  - [role]: specific permissions
  For each API endpoint: which roles can access it

## 5. COMPLETE API CONTRACT
For EVERY endpoint (exhaustive):
  METHOD + PATH
  Auth required + allowed roles
  Request body with field types
  Success response 200
  Error responses with codes

## 6. FRONTEND ROUTES & STATE
For EVERY page:
  - Route path
  - Auth required?
  - What data it fetches (API calls)
  - Loading state behavior
  - Empty state behavior
  - Error state behavior
  - Key user interactions

## 7. COMPLEX BUSINESS LOGIC
Describe any non-trivial logic:
  - Multi-step workflows
  - Calculations / algorithms
  - State machines
  - Background jobs
  - Data aggregations

## 8. RELATIONSHIPS & DATA FLOW
How data flows through the system:
  - User creates X → what happens
  - X changes state → what updates
  - Cascade deletes
  - Denormalization decisions

## 9. SECURITY CONSIDERATIONS
  - Input validation rules per endpoint
  - Authorization checks needed
  - Rate limiting requirements
  - Data sanitization

## 10. DEPLOYMENT ARCHITECTURE
  - Environment variables (all of them)
  - Docker services
  - Database migration strategy
  - Health check endpoints

Be exhaustive. A senior team should be able to implement from this blueprint alone.
{integrations}
"""

def _db_schema_prompt(ctx: dict) -> str:
    spec = ctx.get("spec", {})
    api = ctx.get("api_contract", "")
    request = ctx.get("request", "")
    return f"""You are a senior database architect with 15 years experience designing schemas for apps with millions of users.

PROJECT: {request}
ARCHITECTURE: {api[:4000]}

Write COMPLETE, PRODUCTION-GRADE SQLAlchemy models. Every model must be fully implemented.

━━━ MANDATORY RULES ━━━
1. ALWAYS import from extensions: from extensions import db
2. Every model has: id (Integer PK), created_at, updated_at
3. Every to_dict() returns ALL fields as JSON-serializable types (use .isoformat() for dates, .value for enums)
4. Use proper SQLAlchemy relationships with back_populates (not backref)
5. Add __table_args__ with composite indexes on frequently queried fields
6. Use db.Enum for status/type fields
7. Add cascade="all, delete-orphan" on child relationships
8. Use db.Text for long content, db.String(N) for bounded strings

━━━ REQUIRED PATTERNS ━━━

MANY-TO-MANY (use association table):
user_projects = db.Table('user_projects',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('project_id', db.Integer, db.ForeignKey('projects.id'), primary_key=True),
    db.Column('role', db.String(50), default='member'),
    db.Column('joined_at', db.DateTime, default=datetime.utcnow)
)

ENUM FIELDS:
import enum
class TaskStatus(enum.Enum):
    TODO = 'todo'
    IN_PROGRESS = 'in_progress'
    DONE = 'done'
    ARCHIVED = 'archived'
status = db.Column(db.Enum(TaskStatus), default=TaskStatus.TODO, nullable=False)

SOFT DELETE:
deleted_at = db.Column(db.DateTime, nullable=True)
def soft_delete(self): self.deleted_at = datetime.utcnow(); db.session.commit()
@classmethod
def active(cls): return cls.query.filter_by(deleted_at=None)

AUDIT TRAIL:
created_by = db.Column(db.String(255))  # Clerk user ID
updated_by = db.Column(db.String(255))

COMPUTED PROPERTIES:
@property
def is_overdue(self): return self.due_date and self.due_date < datetime.utcnow() and self.status != TaskStatus.DONE

FULL to_dict() EXAMPLE:
def to_dict(self, include_relations=False):
    d = {{
        'id': self.id,
        'name': self.name,
        'status': self.status.value if self.status else None,
        'created_at': self.created_at.isoformat() if self.created_at else None,
        'updated_at': self.updated_at.isoformat() if self.updated_at else None,
    }}
    if include_relations:
        d['items'] = [i.to_dict() for i in self.items]
    return d

━━━ GENERATE ALL MODELS FOR THIS PROJECT ━━━
Include ALL models needed, with complete fields, relationships, and methods.
Return ONLY Python code. No JSON wrapper. No markdown fences.
"""

def _backend_prompt(ctx: dict) -> str:
    spec = ctx.get("spec", {})
    api = ctx.get("api_contract", "")
    schema = ctx.get("db_schema", "")
    request = ctx.get("request", "")
    needs_auth = spec.get("needs_auth", False)
    integrations = get_integration_prompt(request, spec)

    auth_helpers = """
def get_user_id():
    \"\"\"Extract Clerk user ID from JWT token.\"\"\"
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return None
    try:
        import base64, json as _json
        parts = auth.split(' ')[1].split('.')
        payload = parts[1] + '=' * (4 - len(parts[1]) % 4)
        return _json.loads(base64.b64decode(payload)).get('sub')
    except Exception:
        return None

def require_auth(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        user_id = get_user_id()
        if not user_id:
            return jsonify({{'success': False, 'error': 'Authentication required', 'code': 'UNAUTHORIZED'}}), 401
        return f(*args, **kwargs)
    return decorated

def require_role(role):
    from functools import wraps
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            user_id = get_user_id()
            if not user_id:
                return jsonify({{'success': False, 'error': 'Authentication required', 'code': 'UNAUTHORIZED'}}), 401
            user = User.query.filter_by(clerk_id=user_id).first()
            if not user or user.role not in ([role] if isinstance(role, str) else role):
                return jsonify({{'success': False, 'error': 'Insufficient permissions', 'code': 'FORBIDDEN'}}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator
""" if needs_auth else ""

    return f"""You are a senior backend engineer who has built APIs used by millions of users.
You write clean, secure, production-grade Flask code with zero shortcuts.

PROJECT: {request}
ARCHITECTURE: {api[:2500]}
DATABASE SCHEMA: {schema[:2000]}
{integrations}

━━━ GENERATE ALL THESE FILES (complete, no truncation) ━━━

FILE 1: backend/extensions.py
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
db = SQLAlchemy()
bcrypt = Bcrypt()

FILE 2: backend/config.py
import os
class Config:
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {{'pool_recycle': 300, 'pool_pre_ping': True}}
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-change-in-production')
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', 'http://localhost:5173,http://localhost:3000').split(',')
    # Fix Render/Railway postgres:// -> postgresql://
    if SQLALCHEMY_DATABASE_URI and SQLALCHEMY_DATABASE_URI.startswith('postgres://'):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace('postgres://', 'postgresql://', 1)

FILE 3: backend/app.py (EXACT pattern - fill in your blueprints)
import os
from flask import Flask, jsonify
from flask_cors import CORS
from extensions import db, bcrypt
from config import Config

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    bcrypt.init_app(app)
    CORS(app, origins=app.config['CORS_ORIGINS'], supports_credentials=True)
    from routes.main import main_bp
    app.register_blueprint(main_bp, url_prefix='/api/v1')
    @app.errorhandler(404)
    def not_found(e): return jsonify({{'success': False, 'error': 'Not found', 'code': 'NOT_FOUND'}}), 404
    @app.errorhandler(500)
    def server_error(e): return jsonify({{'success': False, 'error': 'Server error', 'code': 'SERVER_ERROR'}}), 500
    @app.route('/health')
    def health(): return jsonify({{'status': 'ok', 'version': '1.0.0'}})
    with app.app_context():
        db.create_all()
    return app
app = create_app()
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

FILE 4: backend/utils/helpers.py (auth helpers)
{auth_helpers}

def paginate_query(query, page=1, per_page=20):
    result = query.paginate(page=page, per_page=per_page, error_out=False)
    return {{
        'data': [item.to_dict() for item in result.items],
        'total': result.total,
        'pages': result.pages,
        'page': page,
        'per_page': per_page,
        'has_next': result.has_next,
        'has_prev': result.has_prev,
    }}

def validate_required(data, fields):
    missing = [f for f in fields if not data.get(f)]
    if missing:
        return {{'error': f'Missing required fields: {{", ".join(missing)}}', 'code': 'VALIDATION_ERROR'}}, 400
    return None, None

FILE 5+: backend/routes/ (one file per resource)
━━━ ROUTE IMPLEMENTATION RULES ━━━
1. ALWAYS wrap in try/except, rollback on error
2. ALWAYS validate inputs before DB operations
3. Use paginate_query() for all list endpoints
4. Consistent response format:
   Success: {{'success': True, 'data': ..., 'message': '...'}}
   List:    {{'success': True, **paginate_query(query)}}
   Error:   {{'success': False, 'error': '...', 'code': 'ERROR_CODE'}}
5. Use get_user_id() for user context, require_auth decorator for protected routes
6. Add @require_auth on POST/PUT/DELETE endpoints
7. Input sanitization: .strip() on strings, validate email format, check lengths
8. Never return raw SQLAlchemy exceptions to client

COMPLEX ROUTE PATTERNS:

Nested resources:
  GET /projects/:id/tasks - get all tasks for a project
  POST /projects/:id/tasks - create task in project

Bulk operations:
  POST /tasks/bulk-update - update multiple tasks
  DELETE /tasks/bulk-delete - delete multiple tasks

Filtering & sorting:
  GET /tasks?status=todo&assigned_to=user123&sort=due_date&order=asc

Search:
  GET /search?q=query&type=task&page=1

Statistics/aggregations:
  GET /dashboard/stats - return counts, averages, trends

FILE 6: backend/requirements.txt
flask==3.0.0
flask-cors==4.0.0
flask-sqlalchemy==3.1.1
flask-bcrypt==1.0.1
python-dotenv==1.0.0
gunicorn==21.2.0
stripe==8.0.0

Return ONLY valid JSON: {{"files":[{{"path":"backend/extensions.py","content":"..."}},{{"path":"backend/config.py","content":"..."}},{{"path":"backend/app.py","content":"..."}},{{"path":"backend/routes/main.py","content":"..."}}]}}
"""

def _frontend_prompt(ctx: dict) -> str:
    spec       = ctx.get("spec", {})
    api        = ctx.get("api_contract", "")
    request    = ctx.get("request", "")
    needs_auth = spec.get("needs_auth", False)
    use_clerk  = spec.get("use_clerk", True)

    clerk_ui = """
CLERK AUTH (Core 3 - latest):
PACKAGES: "@clerk/clerk-react": "^5.0.0", "@clerk/ui": "^1.0.0"

main.jsx - ClerkProvider with dark theme:
import { dark } from "@clerk/ui/themes"
const clerkAppearance = {
  theme: dark,
  variables: {
    colorPrimary: "#f0c040",
    colorBackground: "#080808",
    colorInputBackground: "#161616",
    colorInputText: "#f0ede8",
    colorText: "#f0ede8",
    colorTextSecondary: "#909090",
    borderRadius: "8px",
    fontFamily: "DM Sans, sans-serif",
    colorDanger: "#f87171",
    colorSuccess: "#34d399",
  },
  elements: {
    card: "background:#111;border:1px solid #222;box-shadow:0 16px 48px rgba(0,0,0,0.8)",
    formButtonPrimary: "background:#f0c040;color:#080808;font-weight:600",
    footerActionLink: "color:#f0c040",
    identityPreviewText: "color:#f0ede8",
    userButtonAvatarBox: "width:32px;height:32px",
    userButtonPopoverCard: "background:#111;border:1px solid #222",
    userButtonPopoverActionButton: "color:#f0ede8",
  }
}
ReactDOM.createRoot(document.getElementById("root")).render(
  <ClerkProvider publishableKey={KEY} appearance={clerkAppearance}>
    <App />
  </ClerkProvider>
)

App.jsx routes:
- /sign-in/* → <SignIn routing="path" path="/sign-in" afterSignInUrl="/" fallbackRedirectUrl="/" />
- /sign-up/* → <SignUp routing="path" path="/sign-up" afterSignUpUrl="/" fallbackRedirectUrl="/" />
- Protected: <SignedIn>{children}</SignedIn><SignedOut><RedirectToSignIn /></SignedOut>

Navbar with Clerk Core 3:
import { SignedIn, SignedOut, UserButton, SignInButton } from "@clerk/clerk-react"
<SignedIn><UserButton appearance={{ elements: { avatarBox: "width:32px;height:32px" } }} /></SignedIn>
<SignedOut><SignInButton mode="modal"><button className="btn btn-primary btn-sm">Sign In</button></SignInButton></SignedOut>

Get token for API calls:
const { getToken } = useAuth()
const token = await getToken()
headers: { Authorization: `Bearer ${token}` }

Get user info:
const { user } = useUser()
user.firstName, user.lastName, user.emailAddresses[0].emailAddress, user.imageUrl
""" if (needs_auth and use_clerk) else ""

    css = """@import url('https://fonts.googleapis.com/css2?family=Fraunces:wght@700;900&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500&display=swap');
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#050505;--surface:#0c0c0c;--surface-2:#141414;--surface-3:#1c1c1c;--border:rgba(255,255,255,0.06);--border-hover:rgba(255,255,255,0.12);--glass:rgba(255,255,255,0.04);--glass-hover:rgba(255,255,255,0.07);--glass-border:rgba(255,255,255,0.08);--accent:#f0c040;--accent-2:#e8a020;--accent-dim:rgba(240,192,64,0.08);--accent-glow:0 0 40px rgba(240,192,64,0.15);--text:#f0ede8;--text-2:#888;--text-3:#444;--green:#34d399;--green-dim:rgba(52,211,153,0.08);--red:#f87171;--red-dim:rgba(248,113,113,0.08);--blue:#60a5fa;--r:10px;--r-lg:16px;--r-xl:22px;--t:0.18s cubic-bezier(0.4,0,0.2,1);--shadow-lg:0 20px 60px rgba(0,0,0,0.8);--font-display:"Fraunces",serif;--font-body:"DM Sans",sans-serif}
html{scroll-behavior:smooth}body{background:var(--bg);color:var(--text);font-family:var(--font-body);font-weight:300;min-height:100vh;-webkit-font-smoothing:antialiased}
body::before{content:"";position:fixed;inset:0;background:radial-gradient(ellipse 80% 60% at 50% -20%,rgba(240,192,64,0.04),transparent);pointer-events:none;z-index:0}
#root{position:relative;z-index:1}
::selection{background:var(--accent-dim);color:var(--accent)}::-webkit-scrollbar{width:4px}::-webkit-scrollbar-thumb{background:rgba(255,255,255,0.1);border-radius:2px}
.navbar{position:fixed;top:0;left:0;right:0;z-index:200;height:58px;display:flex;align-items:center;justify-content:space-between;padding:0 24px;background:rgba(5,5,5,0.7);backdrop-filter:blur(32px) saturate(180%);-webkit-backdrop-filter:blur(32px) saturate(180%);border-bottom:1px solid var(--border)}
.navbar-logo{font-family:var(--font-display);font-size:1.15rem;font-weight:700;color:var(--accent);letter-spacing:-0.02em;display:flex;align-items:center;gap:8px}
.navbar-links{display:flex;align-items:center;gap:2px}.navbar-right{display:flex;align-items:center;gap:8px}
.nav-link{color:var(--text-2);font-size:0.85rem;padding:6px 13px;border-radius:var(--r);transition:var(--t)}.nav-link:hover{color:var(--text);background:var(--glass-hover)}.nav-link.active{color:var(--text);background:var(--glass)}
.page{min-height:100vh;padding:78px 24px 80px;max-width:1240px;margin:0 auto}.page-sm{max-width:680px;margin:0 auto}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;border-radius:var(--r);font-family:var(--font-body);font-weight:500;cursor:pointer;transition:var(--t);white-space:nowrap;border:none;font-size:0.875rem}
.btn:active{transform:scale(0.97)}.btn-primary{background:var(--accent);color:#050505;padding:10px 22px;font-weight:600}.btn-primary:hover{background:var(--accent-2);box-shadow:var(--accent-glow)}
.btn-secondary{background:var(--glass);color:var(--text);padding:10px 22px;border:1px solid var(--glass-border)}.btn-secondary:hover{background:var(--glass-hover)}
.btn-ghost{background:transparent;color:var(--text-2);padding:8px 14px}.btn-ghost:hover{color:var(--text);background:var(--glass)}
.btn-danger{background:var(--red-dim);color:var(--red);border:1px solid rgba(248,113,113,0.2);padding:8px 16px}
.btn-sm{padding:6px 14px;font-size:0.8rem}.btn-lg{padding:13px 28px;font-size:0.95rem}.btn:disabled{opacity:0.35;cursor:not-allowed}.w-full{width:100%}
.form-group{display:flex;flex-direction:column;gap:8px;margin-bottom:20px}
.form-label{font-size:0.72rem;font-weight:600;color:var(--text-2);text-transform:uppercase;letter-spacing:0.08em}
.input,.textarea{width:100%;background:var(--surface-2);border:1px solid var(--border);border-radius:var(--r);padding:10px 14px;color:var(--text);font-family:var(--font-body);font-size:0.875rem;outline:none;transition:var(--t)}
.input:focus,.textarea:focus{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-dim)}.input::placeholder{color:var(--text-3)}
.card{background:var(--glass);border:1px solid var(--glass-border);border-radius:var(--r-lg);padding:24px;backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);transition:var(--t);position:relative;overflow:hidden}
.card::before{content:"";position:absolute;inset:0;background:linear-gradient(135deg,rgba(255,255,255,0.04),transparent 60%);pointer-events:none;border-radius:inherit}
.card:hover{border-color:var(--border-hover)}.card-solid{background:var(--surface);backdrop-filter:none}.card-interactive{cursor:pointer}.card-interactive:hover{transform:translateY(-2px);box-shadow:var(--shadow-lg)}
.card-selected{border-color:var(--accent);background:var(--accent-dim)}.card-header{display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:20px;gap:12px}.card-title{font-family:var(--font-display);font-size:1.1rem;font-weight:700}
.grid{display:grid;gap:16px}.grid-2{grid-template-columns:repeat(2,1fr)}.grid-3{grid-template-columns:repeat(3,1fr)}.grid-4{grid-template-columns:repeat(4,1fr)}.grid-auto{grid-template-columns:repeat(auto-fill,minmax(280px,1fr))}
.bento{display:grid;gap:16px}.bento-2{grid-template-columns:repeat(2,1fr)}.bento-3{grid-template-columns:repeat(3,1fr)}.bento-4{grid-template-columns:repeat(4,1fr)}.bento-span-2{grid-column:span 2}
.stat-card{background:var(--glass);border:1px solid var(--glass-border);border-radius:var(--r-lg);padding:24px;backdrop-filter:blur(16px);position:relative;overflow:hidden;transition:var(--t)}
.stat-card::after{content:"";position:absolute;top:0;left:0;right:0;height:1px;background:linear-gradient(90deg,transparent,var(--accent),transparent)}
.stat-icon{width:36px;height:36px;border-radius:var(--r);background:var(--accent-dim);display:flex;align-items:center;justify-content:center;margin-bottom:14px}
.stat-value{font-family:var(--font-display);font-size:2.4rem;font-weight:700;color:var(--accent);line-height:1;margin-bottom:4px}.stat-label{font-size:0.7rem;color:var(--text-3);text-transform:uppercase;letter-spacing:0.1em}
.stat-change{font-size:0.78rem;margin-top:10px;font-weight:500;display:flex;align-items:center;gap:5px}.stat-change.up{color:var(--green)}.stat-change.down{color:var(--red)}
.badge{display:inline-flex;align-items:center;gap:4px;padding:3px 10px;border-radius:100px;font-size:0.68rem;font-weight:600}
.badge-accent{background:var(--accent-dim);color:var(--accent)}.badge-green{background:var(--green-dim);color:var(--green)}.badge-red{background:var(--red-dim);color:var(--red)}.badge-gray{background:var(--surface-2);color:var(--text-2)}
.table-wrap{border:1px solid var(--border);border-radius:var(--r-lg);overflow:hidden;background:var(--surface)}
table{width:100%;border-collapse:collapse}th{padding:11px 16px;text-align:left;font-size:0.68rem;font-weight:600;color:var(--text-3);text-transform:uppercase;letter-spacing:0.1em;border-bottom:1px solid var(--border);background:var(--surface-2)}
td{padding:13px 16px;font-size:0.875rem;border-bottom:1px solid var(--border)}tr:last-child td{border-bottom:none}tbody tr:hover{background:var(--glass)}
.spinner{width:24px;height:24px;border:2px solid var(--border);border-top-color:var(--accent);border-radius:50%;animation:spin 0.65s linear infinite}
.skeleton{background:linear-gradient(90deg,var(--surface-2) 25%,var(--surface-3) 50%,var(--surface-2) 75%);background-size:200% 100%;animation:shimmer 1.6s infinite;border-radius:var(--r)}
.empty-state{text-align:center;padding:80px 24px;color:var(--text-3)}.empty-icon{width:64px;height:64px;border-radius:var(--r-xl);background:var(--surface-2);display:flex;align-items:center;justify-content:center;margin:0 auto 20px}
.alert{padding:14px 16px;border-radius:var(--r);font-size:0.875rem}.alert-error{background:var(--red-dim);border:1px solid rgba(248,113,113,0.25);color:var(--red)}.alert-success{background:var(--green-dim);border:1px solid rgba(52,211,153,0.25);color:var(--green)}
.modal-overlay{position:fixed;inset:0;background:rgba(0,0,0,0.65);backdrop-filter:blur(12px);z-index:300;display:flex;align-items:center;justify-content:center;padding:20px;animation:fadeIn 0.18s ease}
.modal{background:rgba(12,12,12,0.92);border:1px solid var(--glass-border);border-radius:22px;width:100%;max-width:480px;animation:scaleIn 0.22s cubic-bezier(0.34,1.3,0.64,1);backdrop-filter:blur(40px)}
.modal-header{padding:24px 28px 0;display:flex;align-items:center;justify-content:space-between}.modal-title{font-family:var(--font-display);font-size:1.3rem;font-weight:700}.modal-body{padding:20px 28px}.modal-footer{padding:16px 28px 24px;display:flex;justify-content:flex-end;gap:10px;border-top:1px solid var(--border);margin-top:4px}
.toast-container{position:fixed;bottom:24px;right:24px;z-index:400;display:flex;flex-direction:column;gap:10px;pointer-events:none;max-width:380px}
.toast{background:rgba(20,20,20,0.92);border:1px solid var(--glass-border);border-radius:var(--r-lg);padding:14px 18px;font-size:0.875rem;box-shadow:var(--shadow-lg);animation:slideUp 0.28s ease;pointer-events:all;display:flex;align-items:center;gap:12px;backdrop-filter:blur(20px)}
.sidebar{width:240px;min-height:100vh;background:rgba(8,8,8,0.9);border-right:1px solid var(--border);display:flex;flex-direction:column;position:fixed;top:0;left:0;z-index:100;backdrop-filter:blur(20px)}
.sidebar-logo{font-family:var(--font-display);font-size:1.1rem;font-weight:700;color:var(--accent);padding:18px 16px;display:flex;align-items:center;gap:8px;border-bottom:1px solid var(--border)}
.sidebar-body{padding:10px 8px;flex:1}.sidebar-link{display:flex;align-items:center;gap:10px;padding:9px 12px;border-radius:var(--r);color:var(--text-2);font-size:0.84rem;transition:var(--t);margin-bottom:1px;cursor:pointer}
.sidebar-link:hover{color:var(--text);background:var(--glass)}.sidebar-link.active{color:var(--text);background:var(--glass-hover);font-weight:500}.main-content{margin-left:240px;flex:1;padding:32px}
.divider{height:1px;background:var(--border);margin:24px 0}.error-box{background:var(--red-dim);border:1px solid rgba(248,113,113,0.25);border-radius:var(--r);padding:12px 16px;margin-bottom:16px;font-size:0.875rem;color:var(--red)}
.flex{display:flex}.flex-col{flex-direction:column}.items-center{align-items:center}.justify-between{justify-content:space-between}.justify-center{justify-content:center}.gap-2{gap:8px}.gap-3{gap:12px}.gap-4{gap:16px}.gap-6{gap:24px}.flex-1{flex:1}.text-center{text-align:center}.text-muted{color:var(--text-2)}.text-dim{color:var(--text-3)}.text-accent{color:var(--accent)}.text-sm{font-size:0.82rem}.text-xs{font-size:0.72rem}.font-bold{font-weight:700}.font-medium{font-weight:500}.font-display{font-family:var(--font-display)}.truncate{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.w-full{width:100%}.cursor-pointer{cursor:pointer}.relative{position:relative}.overflow-hidden{overflow:hidden}
.mt-4{margin-top:16px}.mt-6{margin-top:24px}.mb-4{margin-bottom:16px}.mb-6{margin-bottom:24px}.p-4{padding:16px}.p-6{padding:24px}
@keyframes fadeIn{from{opacity:0}to{opacity:1}}@keyframes fadeUp{from{opacity:0;transform:translateY(18px)}to{opacity:1;transform:translateY(0)}}@keyframes scaleIn{from{opacity:0;transform:scale(0.94)}to{opacity:1;transform:scale(1)}}@keyframes slideUp{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:translateY(0)}}@keyframes spin{to{transform:rotate(360deg)}}@keyframes shimmer{0%{background-position:200% 0}100%{background-position:-200% 0}}
.animate-fade-up{animation:fadeUp 0.35s ease forwards}.animate-fade-in{animation:fadeIn 0.25s ease forwards}.stagger-1{animation-delay:0.06s;opacity:0}.stagger-2{animation-delay:0.12s;opacity:0}.stagger-3{animation-delay:0.18s;opacity:0}.stagger-4{animation-delay:0.24s;opacity:0}
@media(max-width:768px){.navbar{padding:0 16px}.page{padding:68px 16px 60px}.grid-2,.grid-3,.grid-4,.bento-2,.bento-3,.bento-4{grid-template-columns:1fr}.sidebar{display:none}.main-content{margin-left:0;padding:20px}.bento-span-2{grid-column:span 1}}
@media(prefers-reduced-motion:reduce){*{animation-duration:0.01ms!important;transition-duration:0.01ms!important}}"""


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

{get_integration_prompt(request, spec)}

QUALITY BAR — EVERY GENERATED APP MUST MEET THIS STANDARD:

━━━ COMPLEXITY REQUIREMENTS ━━━
1. REAL DATA FLOWS: Every page fetches real data from the backend. No hardcoded mock data in production pages.
2. FULL CRUD: Every resource has Create, Read, Update, Delete — all wired up with working API calls.
3. OPTIMISTIC UPDATES: When user creates/updates/deletes, update UI immediately before server confirms.
4. ERROR RECOVERY: Every API call has error handling. Show specific error messages, not just "something went wrong".
5. LOADING SKELETONS: Every data-fetching page shows skeleton loaders while fetching.
6. EMPTY STATES: Every list page has a meaningful empty state with a CTA to create the first item.
7. CONFIRMATION DIALOGS: Destructive actions (delete) show a confirmation modal.
8. FORM VALIDATION: Every form validates inputs client-side before submitting. Show inline errors.
9. TOAST NOTIFICATIONS: Every action (create/update/delete/error) shows a toast notification.
10. RESPONSIVE: Every page works on mobile. Use the responsive classes.

━━━ ADVANCED PATTERNS TO USE ━━━

OPTIMISTIC UPDATE PATTERN:
const deleteItem = async (id) => {{
  setItems(prev => prev.filter(i => i.id !== id)) // optimistic
  try {{
    await api.del(`/items/${{id}}`, token)
    toast('Deleted successfully', 'success')
  }} catch (err) {{
    setItems(prev => [...prev, deletedItem]) // rollback
    toast(err.message, 'error')
  }}
}}

FORM WITH VALIDATION:
const [errors, setErrors] = useState({{}})
const validate = (data) => {{
  const errs = {{}}
  if (!data.name?.trim()) errs.name = 'Name is required'
  if (data.name?.length > 100) errs.name = 'Name must be under 100 characters'
  if (data.email && !/^[^@]+@[^@]+[.][^@]+$/.test(data.email)) errs.email = 'Invalid email'
  return errs
}}
const handleSubmit = async (e) => {{
  e.preventDefault()
  const errs = validate(formData)
  if (Object.keys(errs).length) {{ setErrors(errs); return }}
  // submit...
}}
// Render: {{errors.name && <span className="form-error">{{errors.name}}</span>}}

INFINITE SCROLL:
const [page, setPage] = useState(1)
const [hasMore, setHasMore] = useState(true)
const loadMore = async () => {{
  const res = await api.get(`/items?page=${{page+1}}`, token)
  setItems(prev => [...prev, ...res.data.data])
  setHasMore(res.data.has_next)
  setPage(p => p+1)
}}

REAL-TIME SEARCH WITH DEBOUNCE:
const [query, setQuery] = useState('')
useEffect(() => {{
  const timer = setTimeout(async () => {{
    if (!query.trim()) {{ setResults([]); return }}
    const res = await api.get(`/search?q=${{encodeURIComponent(query)}}`, token)
    setResults(res.data.data)
  }}, 300)
  return () => clearTimeout(timer)
}}, [query])

ROLE-BASED UI:
const {{user}} = useUser()
const isAdmin = user?.publicMetadata?.role === 'admin'
{{isAdmin && <button className="btn btn-danger btn-sm">Admin Action</button>}}

MULTI-STEP FORM:
const [step, setStep] = useState(1)
const steps = ['Basic Info', 'Details', 'Review']
// Progress bar + step navigation

DRAG TO REORDER (with API persistence):
const handleDragEnd = async ({{active, over}}) => {{
  if (!over || active.id === over.id) return
  const newOrder = arrayMove(items, oldIdx, newIdx)
  setItems(newOrder) // optimistic
  await api.post('/items/reorder', {{ids: newOrder.map(i => i.id)}}, token)
}}

DATA TABLE WITH SORT + FILTER + BULK SELECT:
const [selected, setSelected] = useState(new Set())
const [sortField, setSortField] = useState('created_at')
const [sortDir, setSortDir] = useState('desc')
const toggleSelect = (id) => setSelected(prev => {{
  const next = new Set(prev)
  next.has(id) ? next.delete(id) : next.add(id)
  return next
}})
// Bulk actions bar appears when selected.size > 0

━━━ PAGE-LEVEL REQUIREMENTS ━━━
Dashboard: Real stats from /dashboard/stats, activity feed, charts with real data
List pages: Searchable, sortable, filterable, paginated table or card grid
Detail pages: Full item info, edit inline or via modal, related items
Settings: Form with save/cancel, success feedback
Auth pages: Clerk SignIn/SignUp with custom appearance matching theme

━━━ REFERENCE QUALITY ━━━
Every page should look and function like: Linear.app, Vercel dashboard, Stripe dashboard, Notion, Loom.
No lorem ipsum. No placeholder content. Real, context-aware copy throughout.
Production-ready from day 1.

UI COMPONENT PATTERNS (use these exact patterns in generated code):

1. Icons — use lucide-react for all icons:
   import {{ Plus, Trash2, Edit, Check, X, ChevronRight, Home, Settings, Bell }} from 'lucide-react'

2. Conditional classes — use clsx:
   import clsx from 'clsx'
   className={{clsx('btn', isActive && 'btn-primary', isDisabled && 'btn-disabled')}}

3. Clerk UserButton appearance — match our dark theme:
   <UserButton appearance={{{{
     elements: {{{{
       avatarBox: "width:32px;height:32px",
       userButtonPopoverCard: "background:#111;border:1px solid #222",
     }}}}
   }}}} afterSignOutUrl="/sign-in" />

4. Loading skeleton pattern:
   <div className="skeleton" style={{{{height:20,borderRadius:6,marginBottom:8}}}} />

5. Empty state pattern:
   <div className="empty-state">
     <span className="empty-icon"><Icon /></span>
     <h3>No items yet</h3>
     <p>Create your first item to get started</p>
     <button className="btn btn-primary">+ Add Item</button>
   </div>

6. Toast notification hook usage:
   const {{ toast }} = useToast()
   toast('Saved successfully', 'success')
   toast('Something went wrong', 'error')

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

    # Tech lead reviews architecture before code review
    complexity = spec.get("complexity", "moderate")
    if complexity in ("complex", "advanced") and ctx.get("api_contract"):
        print("\n  🏗️  Tech Lead reviewing architecture...")
        try:
            from core.ai.senior_team import tech_lead_review
            improved_contract = tech_lead_review(spec, ctx["api_contract"])
            if improved_contract and improved_contract != ctx["api_contract"]:
                ctx["api_contract"] = improved_contract
                print("     Architecture improved by Tech Lead")
        except Exception as e:
            print(f"     ⚠️  Tech lead review skipped: {e}")

    return ctx
