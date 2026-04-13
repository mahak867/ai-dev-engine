# core/ai/skills_library.py
# Complete skills library - all patterns from antigravity-awesome-skills
# Built from public catalog, documentation, and research
# Categories: frontend, backend, planning, security, devops, testing,
#             architecture, database, ai, mobile, performance, accessibility

SKILLS = {

# ── PLANNING & ARCHITECTURE ───────────────────────────────────────────────────

"brainstorming": """
BRAINSTORMING SKILL:
Before writing any code, answer these:
1. Core user stories (top 3 journeys)
2. MVP scope - what MUST exist day 1
3. What to cut - features for v2
4. Technical risks + mitigation
5. Success metrics
6. Dependencies (APIs, services, integrations)
Output: Structured plan with clear phases, not just a feature list.
""",

"architecture-planning": """
ARCHITECTURE PLANNING SKILL:
1. Define system boundaries (what's in/out of scope)
2. Choose architecture pattern: monolith / modular monolith / microservices
3. Data flow diagram: user -> frontend -> API -> DB
4. State management strategy
5. Auth strategy (JWT / session / OAuth)
6. Error handling strategy (global vs local)
7. Scaling considerations (where will bottlenecks be?)
Output: Architecture decision record (ADR) with rationale.
""",

"system-design": """
SYSTEM DESIGN SKILL:
Design for these qualities in order:
1. Correctness (it does what it should)
2. Reliability (handles errors gracefully)
3. Maintainability (easy to change)
4. Performance (fast enough)
5. Scalability (can grow)
Never optimise prematurely. Start simple, measure, then optimise.
Output: System design with explicit tradeoffs documented.
""",

"mvp-design": """
MVP DESIGN SKILL:
MVP = Minimum VALUABLE Product, not Minimum Viable.
Rules:
1. One core loop that works end-to-end
2. No admin panel in MVP (use DB directly)
3. No email in MVP (use console.log)
4. No payments in MVP (use Stripe test mode)
5. No mobile app in MVP (responsive web)
Cut scope until the team agrees it's too small. Then cut more.
Output: MVP feature list + explicit NOT IN SCOPE list.
""",

"senior-engineer": """
SENIOR ENGINEER MINDSET:
1. Read the full requirements before writing a line
2. Name things clearly (no abbreviations, no x/y/temp)
3. Write the simplest solution that works
4. Handle errors explicitly, never silently swallow them
5. Write code for the next person, not just to pass tests
6. Leave the codebase cleaner than you found it
7. When in doubt, do less and do it well
Output: Clean, readable, maintainable code.
""",

# ── FRONTEND ──────────────────────────────────────────────────────────────────

"react-best-practices": """
REACT BEST PRACTICES:
1. Functional components + hooks only (no class components)
2. TypeScript interfaces for ALL props
3. Error boundaries on every route
4. Loading + empty + error states on every data-fetch
5. React.memo on expensive pure components
6. useCallback for handlers passed to children
7. useMemo for expensive derived values
8. Colocate state as close to usage as possible
9. Custom hooks for reusable logic (useAuth, useToast, useDebounce)
10. Never put API calls directly in components - use hooks/services
""",

"frontend-design": """
FRONTEND DESIGN SKILL:
Typography: display font (Fraunces/Playfair) for headings, sans (DM Sans/Inter) for body
Spacing: consistent scale (4, 8, 12, 16, 24, 32, 48, 64px)
Color: one accent, semantic colors for states (green=success, red=error, amber=warning)
Motion: entrance animations (fadeUp 350ms ease), hover (150ms), never more than 300ms
Components: card > header > content > footer hierarchy always
Dark mode: CSS variables, not hardcoded colors
Glass: backdrop-filter: blur(16px) with rgba border, not flat surfaces
Output: Pixel-perfect, consistent, premium UI.
""",

"ui-polish": """
UI POLISH SKILL:
Details that separate good from great:
1. Hover states on every interactive element (cursor: pointer)
2. Focus states for keyboard navigation (outline: 2px solid accent)
3. Disabled states look clearly disabled (opacity 0.35)
4. Loading states prevent double-submit (disable button + show spinner)
5. Error messages are specific ("Email already exists", not "Error")
6. Success feedback is immediate (toast + optimistic update)
7. Empty states have an icon, message, and CTA button
8. Numbers are formatted (1,234 not 1234, $12.34 not 12.34)
9. Dates are human-readable ("2 hours ago", not ISO string)
10. Truncate long text with ellipsis, never overflow
""",

"component-library": """
COMPONENT LIBRARY SKILL:
Build these components before any pages:
- Button (primary, secondary, ghost, danger, sm, md, lg, disabled, loading)
- Input (text, email, password, textarea, with label, with error)
- Card (with header, body, footer variants)
- Badge (accent, green, red, gray)
- Modal (with header, body, footer, backdrop click to close)
- Toast (success, error, info - auto-dismiss 3.5s)
- Spinner + Skeleton loader
- Empty state (icon + message + CTA)
Each component must handle all its own states.
""",

"responsive-design": """
RESPONSIVE DESIGN SKILL:
Breakpoints: 480px (mobile), 768px (tablet), 1024px (desktop), 1440px (wide)
Mobile-first: start with mobile styles, add desktop with min-width media queries
Grid: CSS Grid for layout, Flexbox for component internals
Touch: minimum 44x44px tap targets
Navigation: hamburger menu on mobile, full nav on desktop
Tables: horizontal scroll on mobile or collapse to cards
Images: max-width: 100%, lazy loading
Never use px for font sizes (use rem), never use px for media queries (use em)
""",

"animation-patterns": """
ANIMATION PATTERNS SKILL:
Entrance: opacity 0->1 + translateY 20px->0, 350ms ease
Exit: opacity 1->0, 200ms ease
Hover: scale(1.02) or translateY(-2px), 150ms ease
Press: scale(0.97), 100ms
Loading: spin 650ms linear infinite
Skeleton: shimmer gradient 1.6s infinite
Page transition: fadeUp 350ms with stagger (60ms per item)
RULES:
- Always use transform (not position) for animations
- Add prefers-reduced-motion: reduce for accessibility
- Never animate width/height (use transform: scaleX/scaleY)
- Keep all transitions under 400ms
""",

"state-management": """
STATE MANAGEMENT SKILL:
Local state: useState for component-level (form values, toggles, UI state)
Server state: custom hooks with fetch + loading/error/data pattern
Derived state: useMemo - never store derived values in state
Global state: React Context for auth/theme only - NOT for server data
Patterns:
- Optimistic updates: update UI before API confirms, rollback on error
- Stale while revalidate: show cached data while refetching
- Pagination: page + per_page + total + has_next in response
- Infinite scroll: append to list, never replace
""",

"form-patterns": """
FORM PATTERNS SKILL:
1. Validate on blur (not on every keystroke)
2. Show error message BELOW the field, in red, with specific text
3. Disable submit button while loading
4. Show loading spinner inside button during submission
5. On success: reset form + show toast + redirect if needed
6. On error: show error message + keep form data
7. Use controlled inputs (value + onChange)
8. Required fields: validate before API call, not after
9. Email: regex check + lowercase trim
10. Password: min 8 chars, show/hide toggle
""",

"accessibility": """
ACCESSIBILITY SKILL (WCAG 2.1 AA):
1. All images need alt text (empty alt="" for decorative)
2. Color contrast ratio minimum 4.5:1 for text
3. All interactive elements keyboard accessible (Tab, Enter, Space)
4. Focus visible on all interactive elements
5. Form inputs have associated labels (not just placeholder)
6. Error messages linked to inputs via aria-describedby
7. Modals trap focus and close on Escape
8. Loading states announced to screen readers (aria-live)
9. Use semantic HTML (button not div, nav not div, main not div)
10. Skip to main content link for keyboard users
""",

"performance-frontend": """
FRONTEND PERFORMANCE SKILL:
1. Lazy load routes: const Page = React.lazy(() => import('./Page'))
2. Code splitting: separate chunks per route
3. Debounce search inputs (300ms)
4. Memoize filtered/sorted lists with useMemo
5. Virtualize long lists (100+ items)
6. Optimize images: WebP format, proper dimensions, lazy loading
7. Avoid layout thrash: read then write to DOM
8. Use CSS transforms not position changes for animations
9. Minimize re-renders: memo + useCallback + stable references
10. Bundle analysis: identify and eliminate dead code
""",

# ── BACKEND ───────────────────────────────────────────────────────────────────

"api-design": """
API DESIGN SKILL:
URL conventions:
- Plural nouns: /users, /projects, /tasks (not /getUser)
- Nested resources: /projects/:id/tasks
- Query params for filtering: ?status=todo&assigned_to=user123
- Query params for pagination: ?page=1&per_page=20
- Query params for sorting: ?sort=created_at&order=desc
HTTP methods: GET=read, POST=create(201), PUT=full update, PATCH=partial, DELETE=remove
Status codes: 200=ok, 201=created, 400=bad request, 401=unauth, 403=forbidden, 404=not found, 429=rate limit, 500=server error
Response format - ALWAYS consistent:
  Success: {success: true, data: {...}, message: "..."}
  List:    {success: true, data: [...], total: N, page: 1, pages: N, has_next: bool}
  Error:   {success: false, error: "Human message", code: "SNAKE_CASE_CODE"}
""",

"flask-patterns": """
FLASK PATTERNS SKILL:
Application factory (ALWAYS use this):
  def create_app():
      app = Flask(__name__)
      db.init_app(app)
      from routes.main import main_bp
      app.register_blueprint(main_bp, url_prefix='/api/v1')
      with app.app_context(): db.create_all()
      return app

Route pattern (ALWAYS follow this):
  @bp.route('/items', methods=['POST'])
  @require_auth
  def create_item():
      try:
          data = request.get_json() or {}
          name = data.get('name','').strip()
          if not name: return jsonify({'success':False,'error':'Name required','code':'VALIDATION_ERROR'}),400
          item = Item(name=name, user_id=get_user_id())
          db.session.add(item)
          db.session.commit()
          return jsonify({'success':True,'data':item.to_dict()}),201
      except Exception as e:
          db.session.rollback()
          return jsonify({'success':False,'error':'Server error','code':'SERVER_ERROR'}),500
""",

"error-handling": """
ERROR HANDLING SKILL:
Backend rules:
1. Every route wrapped in try/except
2. db.session.rollback() in EVERY except block
3. Never return raw exception messages to client
4. Log exceptions server-side for debugging
5. Return specific error codes: VALIDATION_ERROR, NOT_FOUND, UNAUTHORIZED, FORBIDDEN, SERVER_ERROR
6. 404 for missing resources, 403 for permission denied, 401 for missing auth
Frontend rules:
1. Every API call in try/catch
2. Show specific error message (not "Something went wrong")
3. Retry button for network errors
4. Rollback optimistic updates on error
5. Log errors to console in development
""",

"input-validation": """
INPUT VALIDATION SKILL:
Backend (always validate BEFORE DB operations):
  def validate(data, rules):
      errors = {}
      for field, constraints in rules.items():
          val = str(data.get(field, '')).strip()
          if constraints.get('required') and not val: errors[field] = 'Required'
          if val and constraints.get('min_len') and len(val) < constraints['min_len']: errors[field] = f'Min {constraints["min_len"]} chars'
          if val and constraints.get('max_len') and len(val) > constraints['max_len']: errors[field] = f'Max {constraints["max_len"]} chars'
          if val and constraints.get('email') and '@' not in val: errors[field] = 'Invalid email'
      return errors

Frontend (validate before submit):
  const validate = (data) => {
    const errs = {}
    if (!data.email?.trim()) errs.email = 'Email required'
    if (!/^[^@]+@[^@]+[.][^@]+$/.test(data.email)) errs.email = 'Invalid email'
    if (!data.password || data.password.length < 8) errs.password = 'Min 8 characters'
    return errs
  }
""",

"authentication": """
AUTHENTICATION SKILL (Clerk):
Backend JWT extraction:
  def get_user_id():
      auth = request.headers.get('Authorization','')
      if not auth.startswith('Bearer '): return None
      try:
          import base64, json
          p = auth.split(' ')[1].split('.')[1]
          p += '=' * (4 - len(p) % 4)
          return json.loads(base64.b64decode(p)).get('sub')
      except: return None

  def require_auth(f):
      from functools import wraps
      @wraps(f)
      def d(*args,**kwargs):
          if not get_user_id(): return jsonify({'success':False,'error':'Auth required','code':'UNAUTHORIZED'}),401
          return f(*args,**kwargs)
      return d

Frontend:
  const {getToken} = useAuth()
  const token = await getToken()
  headers: {'Authorization': `Bearer ${token}`}
""",

"database-patterns": """
DATABASE PATTERNS SKILL:
Model template:
  class Item(db.Model):
      __tablename__ = 'items'
      id = db.Column(db.Integer, primary_key=True)
      user_id = db.Column(db.String(255), nullable=False, index=True)
      name = db.Column(db.String(255), nullable=False)
      status = db.Column(db.Enum(StatusEnum), default=StatusEnum.ACTIVE)
      created_at = db.Column(db.DateTime, default=datetime.utcnow)
      updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
      __table_args__ = (db.Index('idx_user_status', 'user_id', 'status'),)
      def to_dict(self):
          return {'id':self.id,'name':self.name,'status':self.status.value,
                  'created_at':self.created_at.isoformat(),'updated_at':self.updated_at.isoformat()}

Rules:
- ALWAYS import db from extensions (never from app)
- Index all foreign keys and frequently filtered columns
- Use cascade="all, delete-orphan" on child relationships
- Enums for status/type fields
- to_dict() for ALL models - serialize dates with .isoformat()
""",

"query-optimization": """
QUERY OPTIMIZATION SKILL:
1. NEVER use .all() on unbounded queries - always .paginate() or .limit()
2. Prevent N+1: use .options(db.joinedload(Model.relation))
3. Select only needed columns: db.session.query(Model.id, Model.name)
4. Index: every ForeignKey column, every WHERE/ORDER BY column
5. Batch inserts: db.session.bulk_insert_mappings(Model, [dict1, dict2])
6. Count without loading: db.session.query(db.func.count(Model.id))
7. Paginate helper:
   def paginate(query, page=1, per_page=20):
       r = query.paginate(page=page, per_page=per_page, error_out=False)
       return {'data':[i.to_dict() for i in r.items],'total':r.total,'pages':r.pages,'has_next':r.has_next}
""",

"rate-limiting": """
RATE LIMITING SKILL:
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
limiter = Limiter(app=app, key_func=get_remote_address, default_limits=['200/day','50/hour'])

Apply to routes:
@bp.route('/auth/login', methods=['POST'])
@limiter.limit('5/minute')  # Strict on auth
def login(): ...

@bp.route('/api/search', methods=['GET'])
@limiter.limit('30/minute')  # Moderate on search
def search(): ...

429 response format: {success: false, error: "Rate limit exceeded", code: "RATE_LIMITED", retry_after: 60}
""",

# ── SECURITY ──────────────────────────────────────────────────────────────────

"security-auditor": """
SECURITY AUDIT CHECKLIST:
AUTH:
- All POST/PUT/DELETE require @require_auth
- Users can only access their own resources (check user_id matches)
- Admin routes check role before proceeding
- JWT tokens never logged or exposed in errors

INPUT:
- All string inputs .strip() and length-checked
- No raw SQL (use SQLAlchemy ORM always)
- File uploads check MIME type and size
- HTML input sanitized before storage

API:
- CORS allows only specific origins (never *)
- Rate limiting on auth endpoints
- No sensitive data in URL parameters
- Error messages don't expose internals or stack traces

FRONTEND:
- No API keys in frontend bundle (use VITE_ prefix only for safe keys)
- React's JSX escaping prevents XSS by default
- No dangerouslySetInnerHTML without sanitization
- Auth tokens in memory not localStorage

DEPLOY:
- All secrets in environment variables
- HTTPS only in production
- database URL uses postgresql:// not postgres://
""",

"cors-configuration": """
CORS CONFIGURATION SKILL:
from flask_cors import CORS
CORS(app, origins=['http://localhost:5173','http://localhost:3000'], supports_credentials=True)

Production:
origins = os.environ.get('CORS_ORIGINS','http://localhost:5173').split(',')
CORS(app, origins=origins, supports_credentials=True,
     allow_headers=['Content-Type','Authorization'],
     methods=['GET','POST','PUT','DELETE','PATCH','OPTIONS'])

NEVER use origins='*' with supports_credentials=True (browser blocks this).
""",

# ── DEVOPS & DEPLOYMENT ───────────────────────────────────────────────────────

"docker-best-practices": """
DOCKER BEST PRACTICES:
Dockerfile:
  FROM python:3.11-slim
  WORKDIR /app
  COPY requirements.txt .
  RUN pip install --no-cache-dir -r requirements.txt
  COPY . .
  RUN adduser --disabled-password appuser && chown -R appuser /app
  USER appuser
  EXPOSE 5000
  HEALTHCHECK --interval=30s CMD curl -f http://localhost:5000/health || exit 1
  CMD ["gunicorn","app:app","--workers","2","--bind","0.0.0.0:5000"]

Rules:
- Multi-stage builds for React (node build -> serve static)
- Pin base image versions
- Non-root user always
- .dockerignore: node_modules, __pycache__, .env, .git
- Health check endpoint required
""",

"ci-cd": """
CI/CD SKILL:
GitHub Actions workflow:
  name: Deploy
  on: push: branches: [main]
  jobs:
    test:
      runs-on: ubuntu-latest
      steps:
        - uses: actions/checkout@v4
        - uses: actions/setup-python@v5
          with: python-version: '3.11'
        - run: pip install -r backend/requirements.txt
        - run: cd backend && python -m pytest tests/ -v
    deploy:
      needs: test
      steps:
        - run: railway up
          env: RAILWAY_TOKEN: ${{secrets.RAILWAY_TOKEN}}

Environments: dev (auto-deploy on push), staging (manual), production (manual + approval)
""",

"environment-config": """
ENVIRONMENT CONFIG SKILL:
.env.example (ALWAYS provide this):
  # Required
  DATABASE_URL=postgresql://user:pass@localhost:5432/dbname
  SECRET_KEY=change-this-in-production-32-chars-minimum
  FLASK_ENV=development

  # Auth (Clerk)
  VITE_CLERK_PUBLISHABLE_KEY=pk_test_your_key_here

  # Payments (Stripe)
  STRIPE_SECRET_KEY=sk_test_your_key_here
  STRIPE_WEBHOOK_SECRET=whsec_your_secret_here

  # Email (Resend)
  RESEND_API_KEY=re_your_key_here

  # CORS
  CORS_ORIGINS=http://localhost:5173

config.py pattern:
  import os
  class Config:
      DATABASE_URL = os.environ.get('DATABASE_URL','sqlite:///app.db')
      if DATABASE_URL.startswith('postgres://'): DATABASE_URL = DATABASE_URL.replace('postgres://','postgresql://',1)
      SECRET_KEY = os.environ.get('SECRET_KEY','dev-change-this')
""",

"railway-deploy": """
RAILWAY DEPLOYMENT SKILL:
1. Procfile (backend): web: gunicorn app:app --workers 2 --bind 0.0.0.0:$PORT
2. railway.json: {"build":{"builder":"NIXPACKS"},"deploy":{"startCommand":"gunicorn app:app"}}
3. Required env vars in Railway dashboard:
   DATABASE_URL (auto-set by Railway PostgreSQL plugin)
   SECRET_KEY (generate random 32-char string)
   FLASK_ENV=production
   CORS_ORIGINS=https://yourapp.up.railway.app

Health check: GET /health returns {status: "ok", db: "connected"}
Database: Add PostgreSQL plugin in Railway dashboard - sets DATABASE_URL automatically
""",

# ── TESTING ───────────────────────────────────────────────────────────────────

"test-driven-development": """
TDD SKILL:
Cycle: Red (write failing test) -> Green (minimal code to pass) -> Refactor
Backend tests (pytest):
  def test_create_item(client, auth_header):
      res = client.post('/api/v1/items', json={'name':'Test'}, headers=auth_header)
      assert res.status_code == 201
      data = res.get_json()
      assert data['success'] == True
      assert data['data']['name'] == 'Test'

  def test_requires_auth(client):
      res = client.post('/api/v1/items', json={'name':'Test'})
      assert res.status_code == 401

  def test_validates_input(client, auth_header):
      res = client.post('/api/v1/items', json={}, headers=auth_header)
      assert res.status_code == 400
      assert 'error' in res.get_json()

Frontend tests (Vitest):
  it('shows empty state when no items', () => {
      render(<ItemList items={[]} />)
      expect(screen.getByText(/no items/i)).toBeInTheDocument()
  })
""",

"debugging-strategies": """
DEBUGGING STRATEGIES SKILL:
Systematic approach (never guess):
1. Reproduce the bug reliably
2. Read the full error message (the last line is the cause, the stack shows where)
3. Check: what changed recently?
4. Add print/console.log at the entry point, then narrow down
5. Check the data at each step (not just the code)
6. Use binary search: comment out half the code, is the bug still there?

Flask debugging:
  app.logger.debug(f'Request: {request.method} {request.path} {request.json}')
  # Check DB: flask shell -> from extensions import db; db.session.query(User).all()

React debugging:
  console.log('Component rendered:', {props, state})
  // React DevTools: check props, state, context at each component
  // Network tab: check API request/response
""",

"lint-and-validate": """
LINT AND VALIDATE SKILL:
Python:
  flake8 backend/ --max-line-length=120 --ignore=E501,W503
  black backend/ --check
  python -m py_compile backend/app.py  # Quick syntax check

JavaScript/TypeScript:
  npm run lint  # ESLint
  tsc --noEmit  # TypeScript type check

Pre-commit checks to run:
  1. python -m py_compile on all .py files
  2. No hardcoded API keys (grep for sk_, pk_live_, gsk_)
  3. No console.log in production code
  4. All TODO comments have ticket numbers
  5. requirements.txt up to date
""",

# ── AI & LLM ─────────────────────────────────────────────────────────────────

"ai-integration": """
AI INTEGRATION SKILL (OpenAI/Groq compatible):
Backend:
  from openai import OpenAI
  client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))

  def chat(messages: list, model='gpt-4o-mini') -> str:
      res = client.chat.completions.create(model=model, messages=messages, max_tokens=1000)
      return res.choices[0].message.content

  def stream_chat(messages: list, model='gpt-4o-mini'):
      stream = client.chat.completions.create(model=model, messages=messages, stream=True)
      for chunk in stream:
          if chunk.choices[0].delta.content: yield chunk.choices[0].delta.content

Streaming route:
  from flask import Response, stream_with_context
  @bp.route('/ai/chat', methods=['POST'])
  def ai_chat():
      messages = request.get_json().get('messages', [])
      def generate():
          for chunk in stream_chat(messages): yield f'data: {chunk}\\n\\n'
      return Response(stream_with_context(generate()), mimetype='text/event-stream')
""",

"prompt-engineering": """
PROMPT ENGINEERING SKILL:
Structure every prompt:
1. Role: "You are a senior [role] with [years] experience"
2. Context: specific details about the project/codebase
3. Task: exactly what to produce
4. Constraints: format, length, style requirements
5. Examples: show one good example if format matters

Patterns:
- System prompt: role + constraints (short, stable)
- User prompt: context + task (changes per request)
- Few-shot: include 2-3 examples for format-sensitive tasks
- Chain of thought: "Think step by step before answering"
- Output format: "Return ONLY JSON, no markdown, no explanation"

Anti-patterns to avoid:
- Vague requests ("make it better")
- Overloaded prompts (one task per prompt)
- Assuming context (always be explicit)
""",

"llm-error-handling": """
LLM ERROR HANDLING SKILL:
1. Always validate LLM output - it may be wrong or malformed
2. Parse JSON safely: find { and } bounds before json.loads()
3. Retry on malformed output (up to 3 times)
4. Set max_tokens explicitly to prevent truncation
5. Lower temperature (0.1-0.2) for deterministic code generation
6. Higher temperature (0.7-0.9) for creative/varied outputs
7. Rate limits: catch 429, wait 60s, retry
8. Timeout: set explicit timeout (180s for long generations)
9. Fallback: if AI fails, return a helpful error (not a crash)
10. Log all failures with the prompt for debugging
""",

# ── PERFORMANCE ───────────────────────────────────────────────────────────────

"performance-audit": """
PERFORMANCE AUDIT SKILL:
Backend:
1. All list endpoints paginated (never .all() unbounded)
2. Indexes on: all FK columns, all WHERE columns, all ORDER BY columns
3. N+1 prevention: use joinedload/selectinload
4. Cache expensive aggregations (flask-caching, 5-60 min TTL)
5. Connection pooling: SQLALCHEMY_ENGINE_OPTIONS = {'pool_recycle': 300}

Frontend:
1. Lazy load routes (React.lazy + Suspense)
2. Debounce search (300ms)
3. Memoize sorted/filtered lists (useMemo)
4. Virtualize long lists (100+ items)
5. Image optimization (WebP, lazy loading, proper dimensions)
6. Bundle size: import {specific} from 'lib' not import * from 'lib'

Network:
1. Compress API responses (gzip/brotli)
2. Cache GET responses with ETags
3. Minimize API round trips (batch requests where possible)
""",

"caching-strategy": """
CACHING STRATEGY SKILL:
Levels of caching (fastest to slowest):
1. In-memory variable (per-request, no latency)
2. Flask-caching SimpleCache (per-process, seconds)
3. Redis (shared across processes, minutes-hours)
4. Database materialized views (minutes-hours)
5. CDN (for static assets, hours-days)

When to cache:
- Expensive DB aggregations (dashboard stats, counts)
- External API calls (weather, exchange rates)
- Computed values that change rarely

When NOT to cache:
- User-specific data (cache per user_id)
- Real-time data (stock prices, live scores)
- Write-heavy data (updates invalidate constantly)

Cache invalidation: invalidate on write, use short TTLs, version keys.
""",

# ── CODE QUALITY ──────────────────────────────────────────────────────────────

"code-refactor": """
CODE REFACTOR SKILL:
Clean code principles:
1. Functions do ONE thing (single responsibility)
2. Max 20 lines per function - extract if longer
3. Max 3 parameters - use dict/dataclass if more needed
4. Meaningful names: getUserById() not getU(), is_active not flag
5. No magic numbers: MAX_RETRIES = 3 not while attempts < 3
6. DRY: if you wrote it twice, extract it
7. Early returns: guard clauses reduce nesting
8. Comments explain WHY, not WHAT (code explains what)

Python specific:
- List comprehensions over loops for simple transforms
- Context managers (with) for resources
- Dataclasses for data containers
- Type hints on all function signatures

JavaScript specific:
- Destructuring: const {name, email} = user
- Optional chaining: user?.profile?.avatar
- Nullish coalescing: name ?? 'Anonymous'
- Template literals for string building
""",

"systematic-debugging": """
SYSTEMATIC DEBUGGING SKILL:
Add these to every project for easy debugging:
Backend (app.py):
  import logging
  logging.basicConfig(level=logging.DEBUG if app.debug else logging.INFO)
  @app.before_request
  def log_request():
      if app.debug: app.logger.debug(f'{request.method} {request.path}')

  @app.errorhandler(Exception)
  def handle_exception(e):
      app.logger.error(f'Unhandled exception: {e}', exc_info=True)
      if app.debug:
          import traceback
          return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500
      return jsonify({'error': 'Internal server error'}), 500

Frontend (api.js):
  const DEBUG = import.meta.env.DEV
  if (DEBUG) console.log(`API ${method} ${path}`, {body, response})

React error boundary:
  class ErrorBoundary extends React.Component {
      state = {error: null}
      static getDerivedStateFromError(e) { return {error: e} }
      render() { return this.state.error
          ? <div className="alert-error p-6">Something went wrong. <button onClick={()=>this.setState({error:null})}>Retry</button></div>
          : this.props.children }
  }
""",

# ── DEPLOYMENT PATTERNS ───────────────────────────────────────────────────────

"deployment-skill": """
DEPLOYMENT SKILL:
RAILWAY (recommended):
1. railway.app -> New Project -> Deploy from GitHub
2. Add PostgreSQL: + New -> Database -> PostgreSQL
3. Set env vars: SECRET_KEY, FLASK_ENV=production, CORS_ORIGINS
4. Procfile: web: gunicorn app:app --workers 2 --bind 0.0.0.0:$PORT
5. Health check: /health endpoint returning {status: "ok"}

RENDER:
render.yaml auto-deploys:
  services:
    - type: web
      name: app-backend
      env: python
      buildCommand: pip install -r backend/requirements.txt
      startCommand: cd backend && gunicorn app:app --bind 0.0.0.0:$PORT
      envVars:
        - key: DATABASE_URL
          fromDatabase: {name: app-db, property: connectionString}
  databases:
    - name: app-db

DOCKER:
docker-compose up --build
Access: backend http://localhost:5000, frontend http://localhost:5173
""",

"monitoring-setup": """
MONITORING SETUP SKILL:
Health endpoint (required for all deployments):
  @app.route('/health')
  def health():
      try:
          db.session.execute(db.text('SELECT 1'))
          return jsonify({'status':'ok','db':'connected','version':'1.0.0'})
      except Exception as e:
          return jsonify({'status':'error','db':str(e)}), 500

Error tracking (Sentry - free tier):
  import sentry_sdk
  sentry_sdk.init(dsn=os.environ.get('SENTRY_DSN'), traces_sample_rate=0.1)

Analytics (PostHog - free tier):
  import posthog from 'posthog-js'
  posthog.init(import.meta.env.VITE_POSTHOG_KEY, {api_host: 'https://app.posthog.com'})
  posthog.capture('event_name', {property: 'value'})

Uptime monitoring: UptimeRobot (free) - monitors /health every 5 minutes
""",

# ── INTEGRATIONS ──────────────────────────────────────────────────────────────

"stripe-integration": """
STRIPE INTEGRATION SKILL:
Backend:
  import stripe, os
  stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')

  @bp.route('/payments/checkout', methods=['POST'])
  @require_auth
  def create_checkout():
      data = request.get_json()
      session = stripe.checkout.Session.create(
          payment_method_types=['card'],
          line_items=[{'price_data':{'currency':'usd','product_data':{'name':data['name']},'unit_amount':data['amount']},'quantity':1}],
          mode=data.get('mode','payment'),
          success_url='http://localhost:5173/success?session_id={CHECKOUT_SESSION_ID}',
          cancel_url='http://localhost:5173/pricing',
      )
      return jsonify({'success':True,'url':session.url})

  @bp.route('/payments/webhook', methods=['POST'])
  def webhook():
      event = stripe.Webhook.construct_event(request.data, request.headers['Stripe-Signature'], os.environ.get('STRIPE_WEBHOOK_SECRET'))
      if event['type'] == 'checkout.session.completed': pass  # Handle payment
      return jsonify({'success':True})

Frontend:
  const checkout = async (name, amount) => {
      const res = await api.post('/payments/checkout', {name, amount: amount*100})
      window.location.href = res.data.url
  }
""",

"clerk-integration": """
CLERK AUTH INTEGRATION SKILL:
main.jsx:
  import {ClerkProvider} from '@clerk/clerk-react'
  const appearance = {variables:{colorPrimary:'#f0c040',colorBackground:'#050505',
      colorInputBackground:'#141414',colorText:'#f0ede8',borderRadius:'10px'}}
  <ClerkProvider publishableKey={import.meta.env.VITE_CLERK_PUBLISHABLE_KEY} appearance={appearance}>

Protected routes:
  <SignedIn><ProtectedPage/></SignedIn>
  <SignedOut><RedirectToSignIn/></SignedOut>

Navbar:
  <SignedIn><UserButton afterSignOutUrl="/"/></SignedIn>
  <SignedOut><SignInButton mode="modal"><button className="btn btn-primary btn-sm">Sign In</button></SignInButton></SignedOut>

Backend auth:
  def get_user_id():
      auth = request.headers.get('Authorization','')
      if not auth.startswith('Bearer '): return None
      try:
          import base64,json
          p = auth.split(' ')[1].split('.')[1]
          p += '=' * (4-len(p)%4)
          return json.loads(base64.b64decode(p)).get('sub')
      except: return None
""",

"email-integration": """
EMAIL INTEGRATION SKILL (Resend):
  import resend, os
  resend.api_key = os.environ.get('RESEND_API_KEY')

  def send_email(to: str, subject: str, html: str) -> bool:
      try:
          resend.Emails.send({'from':os.environ.get('FROM_EMAIL','noreply@app.com'),'to':to,'subject':subject,'html':html})
          return True
      except Exception as e:
          print(f'Email error: {e}')
          return False

  def send_welcome(to: str, name: str):
      send_email(to, f'Welcome {name}!',
          f'<h1 style="font-family:sans-serif">Welcome {name}</h1><p>Your account is ready.</p>')

  def send_notification(to: str, title: str, message: str):
      send_email(to, title, f'<h2>{title}</h2><p>{message}</p>')
""",

"socketio-realtime": """
SOCKET.IO REALTIME SKILL:
Backend:
  from flask_socketio import SocketIO, emit, join_room, leave_room
  socketio = SocketIO(app, cors_allowed_origins="*")

  @socketio.on('join')
  def on_join(data): join_room(data['room'])

  @socketio.on('message')
  def on_message(data): emit('message', data, room=data['room'])

  @socketio.on('disconnect')
  def on_disconnect(): print(f'Client disconnected: {request.sid}')

  if __name__ == '__main__': socketio.run(app, debug=True)

Frontend:
  import {io} from 'socket.io-client'
  const socket = io('http://localhost:5000')
  socket.emit('join', {room: 'room-id'})
  socket.on('message', (data) => setMessages(prev => [...prev, data]))
  return () => socket.disconnect()
""",

# ── SPECIALIZED ───────────────────────────────────────────────────────────────

"create-pr": """
CREATE PR SKILL:
PR description template:
  ## What
  [One sentence: what does this PR do]

  ## Why
  [One sentence: why is this needed]

  ## Changes
  - Backend: [list key changes]
  - Frontend: [list key changes]
  - Database: [migrations if any]

  ## Testing
  - [ ] Backend tests pass (pytest)
  - [ ] Frontend tests pass (vitest)
  - [ ] Manual test: [describe what you tested]
  - [ ] No console.log in production code
  - [ ] No hardcoded secrets

  ## Screenshots
  [Before/After if UI change]

Branch naming: feature/description, fix/description, chore/description
Commit format: feat: add user auth, fix: correct JWT parsing, chore: update deps
""",

"git-workflow": """
GIT WORKFLOW SKILL:
Branch strategy:
  main -> production (protected, requires PR)
  dev  -> staging (auto-deploy)
  feature/X -> dev (PR required)

Commit messages (Conventional Commits):
  feat: add Stripe payments
  fix: correct user_id extraction from JWT
  chore: update flask to 3.1.0
  docs: add API documentation
  test: add auth endpoint tests
  refactor: extract email helper

Before every commit:
  git status  # Check what's changing
  git diff    # Review changes
  git add -p  # Stage selectively
  git commit -m "type: description"

Never commit: .env files, node_modules, __pycache__, *.sqlite, API keys
""",

"code-review": """
CODE REVIEW SKILL:
What to check as reviewer:
1. Does it do what the PR says?
2. Are edge cases handled? (empty input, null, zero, negative)
3. Are errors handled? (try/catch, rollback, user feedback)
4. Is it testable? (can I write a test for this?)
5. Is naming clear? (would a new engineer understand it?)
6. Any security issues? (auth checks, input validation, SQL injection)
7. Any performance issues? (N+1 queries, unbounded lists)
8. Is it consistent with the rest of the codebase?

What NOT to nitpick: formatting (let linter handle it), personal style preferences, minor naming choices when current is fine.
Approve with: clear description of what was checked and what passed.
""",

"documentation": """
DOCUMENTATION SKILL:
README.md structure:
  # AppName
  One sentence description.

  ## Features
  - Feature 1
  - Feature 2

  ## Tech Stack
  - Backend: Flask, SQLAlchemy, PostgreSQL
  - Frontend: React, TypeScript, Tailwind
  - Auth: Clerk

  ## Quick Start
  ```bash
  cd backend && pip install -r requirements.txt && py app.py
  cd frontend && npm install && npm run dev
  ```

  ## Environment Variables
  | Variable | Description | Required |
  |----------|-------------|----------|
  | DATABASE_URL | PostgreSQL connection string | Yes |
  | SECRET_KEY | Flask secret key | Yes |

  ## API
  GET /api/v1/items - List items
  POST /api/v1/items - Create item (auth required)

Docstrings: every function with a non-obvious purpose gets one.
""",

}


# ── SKILL CATEGORIES (from apex-pro, expanded) ────────────────────────────────

SKILL_CATEGORIES = {
    "frontend": ["react-best-practices", "frontend-design", "ui-polish",
                 "component-library", "responsive-design", "animation-patterns",
                 "state-management", "form-patterns", "accessibility", "performance-frontend"],
    "backend":  ["api-design", "flask-patterns", "error-handling", "input-validation",
                 "authentication", "database-patterns", "query-optimization", "rate-limiting"],
    "planning": ["brainstorming", "architecture-planning", "system-design", "mvp-design", "senior-engineer"],
    "security": ["security-auditor", "cors-configuration", "authentication", "input-validation"],
    "devops":   ["docker-best-practices", "ci-cd", "environment-config", "railway-deploy", "monitoring-setup"],
    "testing":  ["test-driven-development", "debugging-strategies", "lint-and-validate"],
    "ai":       ["ai-integration", "prompt-engineering", "llm-error-handling"],
    "performance": ["performance-audit", "caching-strategy", "query-optimization"],
    "quality":  ["code-refactor", "systematic-debugging", "create-pr", "git-workflow", "code-review", "documentation"],
    "integrations": ["stripe-integration", "clerk-integration", "email-integration", "socketio-realtime"],
    "database": ["database-patterns", "query-optimization"],
    "deployment": ["deployment-skill", "monitoring-setup", "railway-deploy", "environment-config"],
}

# Compact category prompts for injection into generation (from apex-pro pattern)
CATEGORY_PROMPTS = {
    "frontend": """React standards: functional components+hooks, TypeScript interfaces, error boundaries, loading/empty/error states, React.memo on expensive components, mobile-first responsive, Framer Motion animations.""",
    "backend":  """Flask standards: try/except every route, db.session.rollback() on errors, @require_auth on POST/PUT/DELETE, validate inputs before DB, paginate all lists, consistent {success,data,error,code} response format.""",
    "planning": """Architecture standards: define all endpoints before coding, list DB tables with relationships, identify auth requirements, estimate complexity.""",
    "security": """Security: auth on all mutations, user_id ownership checks, validate all inputs, no raw SQL, CORS specific origins, no secrets in frontend bundle.""",
    "devops":   """Deploy standards: Procfile with gunicorn, /health endpoint, all secrets in env vars, postgres:// -> postgresql:// fix.""",
    "testing":  """Test standards: pytest with SQLite in-memory fixture, test 200/201/400/401 responses, Vitest for React components.""",
    "database": """DB standards: id+created_at+updated_at on every model, index all FK columns, cascade delete on children, Enum for status fields, to_dict() returns JSON-serializable types.""",
    "quality":  """Code quality: single responsibility, max 20 lines per function, DRY patterns, meaningful names, early returns, no magic numbers.""",
}


def get_skill_prompt(skill_names: list) -> str:
    """Get combined skill prompts."""
    return "\n".join(SKILLS[n] for n in skill_names if n in SKILLS)


def get_category_prompt(category: str) -> str:
    """Get compact prompt for a category."""
    return CATEGORY_PROMPTS.get(category, "")


def get_skills_for_task(task_type: str) -> list:
    """Get skill names for a task type."""
    return SKILL_CATEGORIES.get(task_type, [])


def get_all_skills_for_complexity(complexity: str, spec: dict) -> str:
    """Get right skill set based on project complexity."""
    base = ["api-design", "security-auditor", "frontend-design"]
    if complexity in ("moderate", "complex", "advanced"):
        base += ["code-refactor", "performance-audit", "error-handling"]
    if complexity in ("complex", "advanced"):
        base += ["systematic-debugging", "deployment-skill", "database-patterns"]
    if spec.get("needs_payments"):
        base.append("stripe-integration")
    if spec.get("needs_auth"):
        base.append("clerk-integration")
    if spec.get("needs_realtime"):
        base.append("socketio-realtime")
    if spec.get("needs_email"):
        base.append("email-integration")
    return get_skill_prompt(list(dict.fromkeys(base)))  # deduplicate, preserve order
