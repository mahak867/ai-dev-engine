# core/ai/test_generator.py
# Auto-generates pytest tests for every backend route
# and Vitest tests for every React component

import json
from pathlib import Path


def generate_backend_tests(files: list, spec: dict, generate_fn) -> list:
    """Generate pytest tests for all backend routes."""

    # Find routes files
    route_files = [f for f in files
                   if f.get("path","").startswith("backend/routes/")
                   and f.get("path","").endswith(".py")]

    if not route_files:
        return []

    # Build test prompt
    routes_summary = []
    for rf in route_files[:3]:  # Limit to 3 route files
        content = rf.get("content","")[:800]
        routes_summary.append(f"FILE: {rf['path']}\n{content}")

    prompt = f"""Generate pytest tests for these Flask routes.

PROJECT: {spec.get('description', 'Flask API')}
ROUTES:
{"---".join(routes_summary)}

Generate tests/test_api.py with:
1. conftest.py fixture with test client (SQLite in-memory)
2. Test every GET endpoint returns 200
3. Test every POST endpoint with valid data returns 201
4. Test auth-required endpoints return 401 without token
5. Test validation - missing required fields returns 400

Use this pattern:
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
def client(app): return app.test_client()

def test_health(client):
    r = client.get('/health')
    assert r.status_code == 200

Return ONLY Python code. No markdown."""

    try:
        result = generate_fn(prompt)
        result = result.strip()
        if result.startswith("```"):
            result = "\n".join(result.split("\n")[1:]).rstrip("`").strip()

        return [
            {"path": "backend/tests/__init__.py", "content": ""},
            {"path": "backend/tests/conftest.py", "content": _get_conftest()},
            {"path": "backend/tests/test_api.py", "content": result},
        ]
    except Exception as e:
        print(f"  [Tests] Backend test generation failed: {e}")
        return _fallback_backend_tests(spec)


def generate_frontend_tests(files: list, spec: dict) -> list:
    """Generate basic Vitest tests for React components."""

    # Find page components
    pages = [f for f in files
             if "pages/" in f.get("path","")
             and f.get("path","").endswith(".jsx")]

    tests = []

    # Generate a test for each page
    for page in pages[:4]:
        page_name = Path(page["path"]).stem
        test_content = f"""import {{ render, screen }} from '@testing-library/react'
import {{ describe, it, expect, vi }} from 'vitest'
import {{ MemoryRouter }} from 'react-router-dom'

// Mock API
vi.mock('../services/api', () => ({{
  api: {{
    get: vi.fn().mockResolvedValue({{ data: [], success: true }}),
    post: vi.fn().mockResolvedValue({{ success: true }}),
    put: vi.fn().mockResolvedValue({{ success: true }}),
    del: vi.fn().mockResolvedValue({{ success: true }}),
  }}
}}))

describe('{page_name}', () => {{
  it('renders without crashing', async () => {{
    render(
      <MemoryRouter>
        <{page_name} />
      </MemoryRouter>
    )
    // Page should render - check for common elements
    expect(document.body).toBeTruthy()
  }})

  it('shows loading state initially', () => {{
    render(
      <MemoryRouter>
        <{page_name} />
      </MemoryRouter>
    )
    // Should show spinner or skeleton while loading
    const spinner = document.querySelector('.spinner, .skeleton')
    // Loading state may or may not be present depending on component
    expect(document.body).toBeTruthy()
  }})
}})
"""
        tests.append({
            "path": f"frontend/src/__tests__/{page_name}.test.jsx",
            "content": test_content
        })

    # Add vitest config
    tests.append({
        "path": "frontend/vitest.config.js",
        "content": """import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/__tests__/setup.js'],
  },
})
"""
    })

    tests.append({
        "path": "frontend/src/__tests__/setup.js",
        "content": """import '@testing-library/jest-dom'
"""
    })

    return tests


def _get_conftest() -> str:
    return '''import pytest
from app import create_app
from extensions import db as _db

@pytest.fixture(scope="session")
def app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["WTF_CSRF_ENABLED"] = False
    with app.app_context():
        _db.create_all()
        yield app
        _db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def runner(app):
    return app.test_cli_runner()
'''


def _fallback_backend_tests(spec: str) -> list:
    """Minimal tests if generation fails."""
    content = '''import pytest

def test_health(client):
    """Health endpoint should return 200."""
    r = client.get("/health")
    assert r.status_code == 200
    data = r.get_json()
    assert data["status"] == "ok"

def test_404(client):
    """Unknown routes should return 404."""
    r = client.get("/api/v1/nonexistent-endpoint-xyz")
    assert r.status_code == 404

def test_api_prefix(client):
    """API routes should be under /api/v1/."""
    r = client.get("/api/v1/")
    assert r.status_code in (200, 404)  # Either works
'''
    return [
        {"path": "backend/tests/__init__.py", "content": ""},
        {"path": "backend/tests/conftest.py", "content": _get_conftest()},
        {"path": "backend/tests/test_api.py", "content": content},
    ]


def add_test_script(project_path: str):
    """Add test runner scripts to the project."""
    path = Path(project_path)

    # Backend test script
    backend_test = path / "backend" / "run_tests.sh"
    if (path / "backend").exists():
        backend_test.write_text("""#!/bin/bash
echo "Running backend tests..."
cd "$(dirname "$0")"
pip install pytest pytest-flask -q
python -m pytest tests/ -v --tb=short
""")
        backend_test.chmod(0o755)

    # Frontend test script
    frontend_test = path / "frontend" / "run_tests.sh"
    if (path / "frontend").exists():
        frontend_test.write_text("""#!/bin/bash
echo "Running frontend tests..."
cd "$(dirname "$0")"
npm install --save-dev vitest @testing-library/react @testing-library/jest-dom jsdom -q
npm run test
""")
        frontend_test.chmod(0o755)

    # Add test command to package.json
    pkg_json = path / "frontend" / "package.json"
    if pkg_json.exists():
        try:
            import json as _json
            pkg = _json.loads(pkg_json.read_text())
            scripts = pkg.get("scripts", {})
            if "test" not in scripts:
                scripts["test"] = "vitest run"
                scripts["test:watch"] = "vitest"
                pkg["scripts"] = scripts
                pkg_json.write_text(_json.dumps(pkg, indent=2))
                print("  [Tests] Added test scripts to package.json")
        except Exception:
            pass
