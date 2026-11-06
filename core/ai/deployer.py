# core/ai/deployer.py
import re
from pathlib import Path

from core.security import minimal_env, require_approval, run_argv

def create_procfile(project_path):
    backend = Path(project_path) / "backend"
    proc = backend / "Procfile"
    if backend.exists() and not proc.exists():
        proc.write_text("web: gunicorn app:app --workers 2 --bind 0.0.0.0:$PORT\n")
        print("  [Deploy] Created Procfile")

def deploy_to_render(project_path):
    path = Path(project_path)
    # Project names end up inside YAML; keep them to a safe charset.
    safe = re.sub(r"[^A-Za-z0-9_-]", "-", path.name)[:50] or "app"
    name = safe.replace("-", "_")
    yaml = f"""services:
  - type: web
    name: {safe}-backend
    env: python
    buildCommand: pip install -r backend/requirements.txt
    startCommand: cd backend && gunicorn app:app --workers 2 --bind 0.0.0.0:$PORT
    envVars:
      - key: SECRET_KEY
        generateValue: true
      - key: DATABASE_URL
        fromDatabase:
          name: {safe}-db
          property: connectionString
databases:
  - name: {safe}-db
    databaseName: {name}
"""
    (path / "render.yaml").write_text(yaml)
    return {"success": True}

def generate_github_actions(project_path):
    path = Path(project_path)
    wf = path / ".github" / "workflows"
    wf.mkdir(parents=True, exist_ok=True)
    (wf / "deploy.yml").write_text("""name: Deploy
on:
  push:
    branches: [main]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: cd backend && pip install -r requirements.txt && python -c "from app import create_app; create_app(); print('OK')"
""")

def deploy_to_railway(project_path, *, approved: bool | None = None):
    """
    Publish ``<project>/backend`` with the Railway CLI.

    This uploads code and can incur charges, so it requires explicit approval
    (approved=True or APEX_ALLOW_EXECUTION=1). Only Railway's own token is
    passed through to the CLI; provider API keys are not.
    """
    require_approval("deploy_to_railway", approved)
    backend = Path(project_path).resolve() / "backend"
    if not backend.is_dir():
        return {"success": False, "error": f"No backend directory at {backend}"}
    env = minimal_env(passthrough=("RAILWAY_TOKEN", "RAILWAY_API_TOKEN"))
    ver = run_argv(["railway", "--version"], backend, timeout=30, env=env)
    if ver.returncode != 0:
        return {"success": False, "error": "Railway CLI not installed", "install": "npm install -g @railway/cli"}
    r = run_argv(["railway", "up"], backend, timeout=900, env=env)
    return {"success": r.returncode == 0, "output": r.stdout, "error": r.error}


def print_deploy_guide(project_path, name):
    print(f"""
  DEPLOY {name}:
  Railway: railway.app -> New -> GitHub repo -> Add PostgreSQL
  Render:  render.com -> New -> Blueprint -> Connect GitHub (render.yaml included)
  Docker:  cd {name} && docker-compose up --build
""")
