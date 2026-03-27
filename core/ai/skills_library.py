# core/ai/skills_library.py
# Battle-tested skill patterns inspired by the Antigravity Awesome Skills library
# Baked directly into generation prompts - no external dependency needed
# Sources: brainstorming, security-auditor, api-design, systematic-debugging,
#          lint-and-validate, frontend-design, code-refactor, senior-engineer

SKILLS = {

    "brainstorming": """
━━━ BRAINSTORMING SKILL (Pre-Generation Planning) ━━━
Before writing any code, answer these questions:

PROBLEM DEFINITION
- What exact problem does this solve?
- Who experiences this problem?
- How do they solve it today?

CORE USER JOURNEYS (top 3)
- Journey 1: New user → [goal] → [outcome]
- Journey 2: Power user → [goal] → [outcome]
- Journey 3: Admin → [goal] → [outcome]

MVP SCOPE (what MUST exist day 1)
- Feature 1: [why it's essential]
- Feature 2: [why it's essential]
- Feature 3: [why it's essential]

NOT IN SCOPE (what to cut)
- [Feature]: Too complex for MVP
- [Feature]: Can be added later

SUCCESS METRICS
- How will we know this works?
- What are the key numbers to track?

TECHNICAL RISKS
- [Risk]: Mitigation strategy
""",

    "security_auditor": """
━━━ SECURITY AUDITOR SKILL ━━━
Every generated app MUST pass this security checklist:

AUTHENTICATION
✓ All state-modifying endpoints (POST/PUT/DELETE) require auth
✓ User can only access their own resources (check user_id matches)
✓ Admin endpoints check role === 'admin' before proceeding
✓ JWT tokens are never logged or exposed in error messages

INPUT VALIDATION
✓ All string inputs are .strip()ed and length-checked
✓ Integer inputs are validated as actual integers
✓ Email inputs match email pattern
✓ File uploads check MIME type and file size
✓ No raw SQL strings (always use SQLAlchemy ORM)
✓ HTML content is escaped before storage

API SECURITY
✓ CORS only allows specific origins (not *)
✓ Rate limiting on auth endpoints (login, register)
✓ No sensitive data in URL parameters
✓ Error messages don't expose internal stack traces
✓ Health endpoint doesn't expose system info

DATA SECURITY
✓ Passwords always bcrypt hashed, never plain text
✓ API keys stored in .env, never hardcoded
✓ Database connection strings in environment variables
✓ Stripe webhooks verify signature before processing

FRONTEND SECURITY
✓ No API keys exposed in frontend bundle
✓ User input displayed with React's built-in XSS protection
✓ No dangerouslySetInnerHTML without sanitization
✓ Auth tokens stored in memory, not localStorage

APPLY EVERY ITEM TO GENERATED CODE.
""",

    "api_design": """
━━━ API DESIGN SKILL (REST Best Practices) ━━━

URL CONVENTIONS
✓ Plural nouns: /users, /projects, /tasks (not /getUser)
✓ Nested resources: /projects/:id/tasks
✓ Query params for filtering: /tasks?status=todo&assigned_to=user123
✓ Query params for pagination: /tasks?page=1&per_page=20
✓ Query params for sorting: /tasks?sort=created_at&order=desc

HTTP METHODS
✓ GET: read only, idempotent, cacheable
✓ POST: create new resource, returns 201
✓ PUT: full update of resource, returns 200
✓ PATCH: partial update, returns 200
✓ DELETE: remove resource, returns 200 with {success: true, message: 'Deleted'}

STATUS CODES
✓ 200: success
✓ 201: resource created
✓ 400: bad request (validation error)
✓ 401: unauthenticated
✓ 403: unauthorized (authenticated but wrong role)
✓ 404: resource not found
✓ 422: unprocessable entity (semantic error)
✓ 429: rate limit exceeded
✓ 500: server error

RESPONSE FORMAT (consistent across ALL endpoints)
Success single: {success: true, data: {...}, message: "..."}
Success list:   {success: true, data: [...], total: N, page: 1, pages: N, has_next: bool}
Error:          {success: false, error: "Human readable message", code: "SNAKE_CASE_CODE"}

VERSIONING
✓ Always prefix with /api/v1/
✓ Never break backwards compatibility within v1

PERFORMANCE
✓ Paginate all list endpoints (max 100 per page)
✓ Add database indexes on all foreign keys
✓ N+1 query prevention: use .joinedload() or .selectinload()
✓ Return only needed fields (not entire model)
""",

    "systematic_debugging": """
━━━ SYSTEMATIC DEBUGGING SKILL ━━━
When generating code that could fail, add these defensive patterns:

BACKEND DEBUGGING AIDS
# Add to app.py for development
import logging
logging.basicConfig(level=logging.DEBUG)

# Add to every route for tracing
@app.before_request
def log_request():
    app.logger.debug(f'{request.method} {request.path}')

# Error context in responses (dev only)
@app.errorhandler(Exception)
def handle_exception(e):
    if app.debug:
        import traceback
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500
    return jsonify({'error': 'Internal server error'}), 500

FRONTEND DEBUGGING AIDS
// Add to api.js for request tracing
const DEBUG = import.meta.env.DEV
if (DEBUG) console.log(`API ${method} ${path}`, body)

// Error boundary for React
class ErrorBoundary extends React.Component {
    state = {hasError: false, error: null}
    static getDerivedStateFromError(error) { return {hasError: true, error} }
    render() {
        if (this.state.hasError) return (
            <div className="alert-error p-6">
                <h3>Something went wrong</h3>
                <p>{this.state.error?.message}</p>
                <button onClick={() => this.setState({hasError: false})} className="btn btn-secondary mt-4">Try Again</button>
            </div>
        )
        return this.props.children
    }
}
// Wrap entire app: <ErrorBoundary><App/></ErrorBoundary>
""",

    "code_refactor": """
━━━ CODE REFACTOR SKILL (Clean Code Principles) ━━━

NAMING CONVENTIONS
✓ Functions: verb + noun (getUserById, createTask, deleteProject)
✓ Booleans: is/has/can prefix (isLoading, hasError, canEdit)
✓ Constants: SCREAMING_SNAKE_CASE
✓ Components: PascalCase (TaskCard, UserProfile)
✓ Files: kebab-case for utils, PascalCase for components

FUNCTION DESIGN
✓ Single responsibility - one function does one thing
✓ Max 20 lines per function - extract if longer
✓ Max 3 parameters - use object if more needed
✓ Pure functions where possible (no side effects)
✓ Early returns to avoid deep nesting

REACT PATTERNS
✓ Custom hooks for reusable logic (useAuth, useToast, useDebounce)
✓ Memoize expensive computations with useMemo
✓ Stable callbacks with useCallback
✓ Colocate state as close to where it's used as possible
✓ Avoid prop drilling - use context for deeply shared state

FLASK PATTERNS
✓ Blueprint per resource domain (auth, users, projects)
✓ Service layer for complex business logic
✓ Repository pattern for data access
✓ Config class hierarchy (base, dev, prod, test)
✓ Application factory with extension init

DRY PRINCIPLES
✓ Extract repeated validation into a validate_required() helper
✓ Extract repeated DB queries into model class methods
✓ Extract repeated API calls into api.js service
✓ Extract repeated UI patterns into reusable components
""",

    "frontend_design": """
━━━ FRONTEND DESIGN SKILL (Visual Excellence) ━━━

TYPOGRAPHY HIERARCHY
✓ Page titles: font-display (Fraunces), 2-3rem, weight 700-900
✓ Section headers: font-display, 1.3-1.5rem, weight 700
✓ Body text: font-body (DM Sans), 0.875rem, weight 300
✓ Labels: 0.72-0.75rem, uppercase, letter-spacing 0.07-0.1em
✓ Captions: 0.75rem, color var(--text-3)

SPACING SYSTEM
✓ Use consistent spacing: 4, 8, 12, 16, 20, 24, 32, 48, 64px
✓ Section margins: 48-64px between major sections
✓ Card padding: 24px standard, 16px compact
✓ Button padding: 10px vertical, 22px horizontal

COLOR USAGE
✓ Accent (gold) for: primary CTAs, active states, key numbers
✓ Green for: success, positive trends, confirmations
✓ Red for: errors, destructive actions, negative trends
✓ Text-2 for: secondary info, labels, descriptions
✓ Text-3 for: placeholders, disabled, timestamps

INTERACTION PATTERNS
✓ Hover: subtle border-color change + slight scale or translate
✓ Active: scale(0.97) on buttons
✓ Focus: visible ring using var(--accent-dim)
✓ Loading: spinner or skeleton, never blank screen
✓ Transitions: 0.15-0.2s cubic-bezier(0.4,0,0.2,1)

LAYOUT PRINCIPLES
✓ Max content width: 1240px, centered
✓ Generous whitespace between sections
✓ Consistent 16px gap in grids
✓ Fixed navbar: 56-58px height with backdrop blur
✓ Footer: simple, not heavy

COMPONENT QUALITY BAR (reference: Linear, Vercel, Stripe)
✓ Every card has a clear hierarchy: title > subtitle > content > action
✓ Every list has an empty state with icon + message + CTA
✓ Every form has labels, placeholders, validation, and submit feedback
✓ Every page has a clear primary action
✓ Dark backgrounds use glass morphism not flat colors
""",

    "performance_audit": """
━━━ PERFORMANCE AUDIT SKILL ━━━

BACKEND PERFORMANCE
✓ Add .paginate() to ALL list queries - never .all() on large tables
✓ Add indexes: db.Index('idx_name', 'field') on filtered/sorted fields
✓ Use .options(db.joinedload(Model.relation)) to prevent N+1 queries
✓ Cache expensive aggregations with flask-caching
✓ Use db.session.bulk_insert_mappings() for bulk inserts
✓ Add SQLALCHEMY_ENGINE_OPTIONS pool settings to config

FRONTEND PERFORMANCE
✓ Lazy load pages: const Dashboard = React.lazy(() => import('./pages/Dashboard'))
✓ Wrap lazy routes: <Suspense fallback={<Spinner/>}><Dashboard/></Suspense>
✓ Debounce search inputs (300ms minimum)
✓ Memoize filtered/sorted lists: useMemo(() => items.filter(...), [items, filter])
✓ Use React.memo() on expensive pure components
✓ Avoid useEffect with missing dependencies (lint warning = bug)
✓ Cancel API requests on component unmount using AbortController

BUNDLE PERFORMANCE
✓ vite.config.js: add build.rollupOptions.output.manualChunks
✓ Import icons individually: import { Plus } from 'lucide-react' (not *)
✓ Use dynamic imports for heavy libraries (charts, maps, editors)

DATABASE PERFORMANCE
✓ Every foreign key column has an index
✓ Composite indexes for frequently combined queries
✓ Use db.Column(db.Text) for variable-length content
✓ Use db.Column(db.String(N)) for bounded strings
""",

    "testing_strategy": """
━━━ TESTING STRATEGY SKILL ━━━

BACKEND TEST PATTERNS (pytest)
tests/conftest.py:
    import pytest
    from app import create_app
    from extensions import db as _db

    @pytest.fixture
    def app():
        app = create_app()
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        with app.app_context():
            _db.create_all()
            yield app
            _db.drop_all()

    @pytest.fixture
    def client(app):
        return app.test_client()

Test patterns:
    def test_create_item(client):
        res = client.post('/api/v1/items', json={'name': 'Test'})
        assert res.status_code == 201
        data = res.get_json()
        assert data['success'] == True
        assert data['data']['name'] == 'Test'

    def test_requires_auth(client):
        res = client.post('/api/v1/protected', json={})
        assert res.status_code == 401

FRONTEND TEST PATTERNS (Vitest + Testing Library)
    import { render, screen, fireEvent } from '@testing-library/react'
    import { describe, it, expect, vi } from 'vitest'

    it('shows empty state when no items', () => {
        render(<ItemList items={[]} />)
        expect(screen.getByText(/no items yet/i)).toBeInTheDocument()
    })

    it('calls onDelete when delete button clicked', () => {
        const onDelete = vi.fn()
        render(<ItemCard item={{id:1, name:'Test'}} onDelete={onDelete} />)
        fireEvent.click(screen.getByRole('button', {name: /delete/i}))
        expect(onDelete).toHaveBeenCalledWith(1)
    })
""",

    "deployment_skill": """
━━━ DEPLOYMENT SKILL (Production Ready) ━━━

RAILWAY DEPLOYMENT (recommended - zero config)
1. Push to GitHub
2. railway.app → New Project → Deploy from GitHub
3. Add PostgreSQL: railway.app → New → Database → PostgreSQL
4. Set env vars: FLASK_ENV=production, SECRET_KEY=<random>, DATABASE_URL=<from railway>
5. Add Procfile: web: gunicorn app:app --workers 2 --bind 0.0.0.0:$PORT

RENDER DEPLOYMENT
1. render.com → New Web Service → Connect GitHub
2. Build command: pip install -r requirements.txt
3. Start command: gunicorn app:app --workers 2 --bind 0.0.0.0:$PORT
4. Add PostgreSQL: New → PostgreSQL
5. Environment: add DATABASE_URL, SECRET_KEY, FLASK_ENV=production

DOCKER DEPLOYMENT
Dockerfile:
    FROM python:3.11-slim
    WORKDIR /app
    COPY requirements.txt .
    RUN pip install --no-cache-dir -r requirements.txt
    COPY . .
    EXPOSE 5000
    CMD ["gunicorn", "app:app", "--workers", "2", "--bind", "0.0.0.0:5000"]

docker-compose.yml:
    services:
      backend:
        build: ./backend
        ports: ["5000:5000"]
        env_file: ./backend/.env
        depends_on: [db]
      db:
        image: postgres:15
        environment:
          POSTGRES_DB: appdb
          POSTGRES_USER: user
          POSTGRES_PASSWORD: password
        volumes: [pgdata:/var/lib/postgresql/data]
    volumes:
      pgdata:

HEALTH CHECK ENDPOINT (required for all platforms)
@app.route('/health')
def health():
    try:
        db.session.execute(db.text('SELECT 1'))
        return jsonify({'status': 'ok', 'db': 'connected'})
    except Exception as e:
        return jsonify({'status': 'error', 'db': str(e)}), 500

ENVIRONMENT VARIABLES CHECKLIST
Production must have:
✓ DATABASE_URL (postgres, not sqlite)
✓ SECRET_KEY (random 32+ char string)
✓ FLASK_ENV=production
✓ STRIPE_SECRET_KEY (if payments)
✓ STRIPE_WEBHOOK_SECRET (if webhooks)
✓ RESEND_API_KEY (if email)
✓ CORS_ORIGINS (your frontend domain)
"""
}


def get_skill_prompt(skill_names: list) -> str:
    """Get combined skill prompts for injection into generation."""
    parts = []
    for name in skill_names:
        if name in SKILLS:
            parts.append(SKILLS[name])
    return "\n".join(parts)


def get_all_skills_for_complexity(complexity: str, spec: dict) -> str:
    """Get the right set of skills based on project complexity."""
    # Always include these
    base_skills = ["api_design", "security_auditor", "frontend_design"]
    
    # Add based on complexity
    if complexity in ("moderate", "complex", "advanced"):
        base_skills += ["code_refactor", "performance_audit"]
    
    if complexity in ("complex", "advanced"):
        base_skills += ["systematic_debugging", "deployment_skill"]
    
    # Add based on spec
    if spec.get("needs_payments"):
        base_skills.append("deployment_skill")
    
    return get_skill_prompt(base_skills)
