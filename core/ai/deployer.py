# core/ai/deployer.py
import os, subprocess
from pathlib import Path

def create_procfile(project_path):
    backend = Path(project_path) / "backend"
    proc = backend / "Procfile"
    if backend.exists() and not proc.exists():
        proc.write_text("web: gunicorn app:app --workers 2 --bind 0.0.0.0:$PORT\n")
        print("  [Deploy] Created Procfile")

def deploy_to_render(project_path):
    path = Path(project_path)
    name = path.name.replace("-","_")
    yaml = f"""services:
  - type: web
    name: {path.name}-backend
    env: python
    buildCommand: pip install -r backend/requirements.txt
    startCommand: cd backend && gunicorn app:app --workers 2 --bind 0.0.0.0:$PORT
    envVars:
      - key: SECRET_KEY
        generateValue: true
      - key: DATABASE_URL
        fromDatabase:
          name: {path.name}-db
          property: connectionString
databases:
  - name: {path.name}-db
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

def deploy_to_railway(project_path):
    result = subprocess.run(["railway","--version"], capture_output=True)
    if result.returncode != 0:
        return {"success": False, "error": "Railway CLI not installed", "install": "npm install -g @railway/cli"}
    try:
        r = subprocess.run(["railway","up"], cwd=str(Path(project_path)/"backend"), capture_output=True, text=True)
        return {"success": r.returncode==0, "output": r.stdout, "error": r.stderr}
    except Exception as e:
        return {"success": False, "error": str(e)}

def print_deploy_guide(project_path, name):
    print(f"""
  DEPLOY {name}:
  Railway: railway.app -> New -> GitHub repo -> Add PostgreSQL
  Render:  render.com -> New -> Blueprint -> Connect GitHub (render.yaml included)
  Docker:  cd {name} && docker-compose up --build
""")
