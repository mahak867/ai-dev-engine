# core/ai/post_fixer.py
# Auto-patches ALL known generation errors after files are written.

import os
import re
import json
from pathlib import Path


def _inject_integration_packages(path: Path, extras: dict):
    """Auto-add integration packages to package.json and requirements.txt."""
    # Frontend packages
    pkg_json = path / "frontend" / "package.json"
    if pkg_json.exists() and extras.get('frontend'):
        try:
            import json as _json
            pkg = _json.loads(pkg_json.read_text(encoding='utf-8'))
            deps = pkg.get('dependencies', {})
            changed = False
            for p in extras['frontend']:
                name = p.split('==')[0].split('>=')[0]
                if name not in deps:
                    deps[name] = 'latest'
                    changed = True
                    print(f"  [AutoFix] Added frontend package: {name}")
            if changed:
                pkg['dependencies'] = deps
                pkg_json.write_text(_json.dumps(pkg, indent=2), encoding='utf-8')
        except Exception:
            pass

    # Backend packages
    req_txt = path / "backend" / "requirements.txt"
    if not req_txt.exists():
        req_txt = path / "requirements.txt"
    if req_txt.exists() and extras.get('backend'):
        try:
            existing = req_txt.read_text(encoding='utf-8')
            new_lines = []
            for p in extras['backend']:
                pkg_name = p.split('==')[0].split('>=')[0].lower()
                if pkg_name not in existing.lower():
                    new_lines.append(p)
                    print(f"  [AutoFix] Added backend package: {p}")
            if new_lines:
                req_txt.write_text(existing.rstrip() + '\n' + '\n'.join(new_lines) + '\n', encoding='utf-8')
        except Exception:
            pass

    # Frontend .env
    env_file = path / "frontend" / ".env"
    if extras.get('env_frontend'):
        try:
            existing = env_file.read_text(encoding='utf-8') if env_file.exists() else ''
            new_lines = []
            for k, v in extras['env_frontend'].items():
                if k not in existing:
                    new_lines.append(f'{k}={v}')
            if new_lines:
                env_file.write_text(existing.rstrip() + chr(10) + chr(10).join(new_lines) + chr(10), encoding='utf-8')
        except Exception:
            pass

    # Backend .env
    backend_env = path / "backend" / ".env"
    if extras.get('env_backend'):
        try:
            existing = backend_env.read_text(encoding='utf-8') if backend_env.exists() else ''
            new_lines = []
            for k, v in extras['env_backend'].items():
                if k not in existing:
                    new_lines.append(f'{k}={v}')
            if new_lines:
                backend_env.write_text(existing.rstrip() + chr(10) + chr(10).join(new_lines) + chr(10), encoding='utf-8')
        except Exception:
            pass



def fix_project(project_path: str):
    """Run all fixers. Prints only when something is changed."""
    path = Path(project_path)
    _fix_sqlite_path(path)
    _fix_backend_imports(path)
    _fix_typos_in_extensions(path)
    _fix_index_html(path)
    _fix_vite_config(path)
    _fix_main_jsx(path)
    _fix_package_json(path)
    _fix_app_jsx_route(path)
    _fix_api_base_url(path)
    _fix_requirements(path)
    _ensure_missing_src_files(path)
    _create_missing_components(path)
    _fix_clerk_jwt_conflict(path)
    _fix_clerk_setup(path)
    _fix_runtime_errors(path)
    _validate_project_structure(path)


# ── Backend fixes ─────────────────────────────────────────────────

def _fix_sqlite_path(path: Path):
    for f in path.rglob("config.py"):
        text = f.read_text(encoding="utf-8", errors="ignore")
        fixed = re.sub(r"sqlite:///instance/(\S+\.db)", r"sqlite:///\1", text)
        fixed = re.sub(r"sqlite:///./(\S+\.db)", r"sqlite:///\1", fixed)
        if fixed != text:
            f.write_text(fixed, encoding="utf-8")
            print(f"  [AutoFix] Fixed SQLite path in {f.relative_to(path)}")


def _fix_backend_imports(path: Path):
    backend_dir = path / "backend"
    if not backend_dir.exists():
        return
    for f in backend_dir.rglob("*.py"):
        text = f.read_text(encoding="utf-8", errors="ignore")
        fixed = re.sub(r'from backend\.', 'from ', text)
        fixed = re.sub(r'import backend\.', 'import ', fixed)
        if fixed != text:
            f.write_text(fixed, encoding="utf-8")
            print(f"  [AutoFix] Fixed backend imports in {f.relative_to(path)}")


def _fix_typos_in_extensions(path: Path):
    for f in path.rglob("extensions.py"):
        text = f.read_text(encoding="utf-8", errors="ignore")
        fixed = re.sub(r'\bjtw\s*=\s*JWTManager', 'jwt = JWTManager', text)
        fixed = re.sub(r'\bjtw\b', 'jwt', fixed)
        fixed = re.sub(r'\bbcryp\s*=\s*Bcrypt', 'bcrypt = Bcrypt', fixed)
        fixed = re.sub(r'from flask import Flask\n', '', fixed)
        if fixed != text:
            f.write_text(fixed, encoding="utf-8")
            print(f"  [AutoFix] Fixed typos in {f.relative_to(path)}")


# ── Frontend fixes ────────────────────────────────────────────────

def _fix_index_html(path: Path):
    CORRECT_HTML = '''<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>App</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>'''
    for f in path.rglob("index.html"):
        text = f.read_text(encoding="utf-8", errors="ignore")
        fixed = re.sub(
            r'<script\s+src=["\'](?:/src/)?main\.[jt]sx?["\']',
            '<script type="module" src="/src/main.jsx"',
            text
        )
        if fixed != text:
            f.write_text(fixed, encoding="utf-8")
            print(f"  [AutoFix] Fixed index.html script tag")
            return
    frontend = path / "frontend"
    if frontend.exists() and not (frontend / "index.html").exists():
        (frontend / "index.html").write_text(CORRECT_HTML, encoding="utf-8")
        print(f"  [AutoFix] Created missing index.html")


def _fix_vite_config(path: Path):
    VITE_CONFIG = "import { defineConfig } from 'vite'\nimport react from '@vitejs/plugin-react'\nexport default defineConfig({ plugins: [react()] })\n"
    frontend = path / "frontend"
    if not frontend.exists():
        return
    cfg = frontend / "vite.config.js"
    if not cfg.exists():
        cfg.write_text(VITE_CONFIG, encoding="utf-8")
        print(f"  [AutoFix] Created missing vite.config.js")


def _fix_main_jsx(path: Path):
    for f in list(path.rglob("main.jsx")) + list(path.rglob("main.tsx")):
        text = f.read_text(encoding="utf-8", errors="ignore")
        if "index.css" not in text:
            lines = text.splitlines()
            last_import = 0
            for i, line in enumerate(lines):
                if line.strip().startswith("import "):
                    last_import = i
            lines.insert(last_import + 1, "import './index.css'")
            f.write_text("\n".join(lines) + "\n", encoding="utf-8")
            print(f"  [AutoFix] Added CSS import to main.jsx")
            return
    src = path / "frontend" / "src"
    if src.exists() and not (src / "main.jsx").exists():
        (src / "main.jsx").write_text(
            "import React from 'react'\nimport ReactDOM from 'react-dom/client'\nimport App from './App'\nimport './index.css'\nReactDOM.createRoot(document.getElementById('root')).render(<App />)\n",
            encoding="utf-8"
        )
        print(f"  [AutoFix] Created missing main.jsx")


def _fix_package_json(path: Path):
    for f in path.rglob("package.json"):
        if "node_modules" in str(f):
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
            pkg = json.loads(text)
            changed = False
            scripts = pkg.get("scripts", {})
            if "dev" not in scripts:
                scripts.update({"dev": "vite", "build": "vite build", "preview": "vite preview"})
                pkg["scripts"] = scripts
                changed = True
            dev = pkg.get("devDependencies", {})
            if "vite" not in dev and "vite" not in pkg.get("dependencies", {}):
                dev["vite"] = "^4.3.0"
                dev["@vitejs/plugin-react"] = "^4.0.0"
                pkg["devDependencies"] = dev
                changed = True
            deps = pkg.get("dependencies", {})
            if "react-router-dom" not in deps:
                deps["react-router-dom"] = "^6.8.0"
                pkg["dependencies"] = deps
                changed = True
            if "lucide-react" not in deps:
                deps["lucide-react"] = "^0.400.0"
                pkg["dependencies"] = deps
                changed = True
            if "clsx" not in deps:
                deps["clsx"] = "^2.1.0"
                pkg["dependencies"] = deps
                changed = True
            if "framer-motion" not in deps:
                deps["framer-motion"] = "^11.0.0"
                pkg["dependencies"] = deps
                changed = True
            if "@clerk/ui" not in deps:
                deps["@clerk/ui"] = "^1.0.0"
                pkg["dependencies"] = deps
                changed = True
            if "@stripe/stripe-js" not in deps:
                deps["@stripe/stripe-js"] = "^3.0.0"
                pkg["dependencies"] = deps
                changed = True
            if changed:
                f.write_text(json.dumps(pkg, indent=2), encoding="utf-8")
                print(f"  [AutoFix] Fixed package.json")
        except Exception:
            pass


def _fix_app_jsx_route(path: Path):
    for f in list(path.rglob("App.jsx")) + list(path.rglob("App.tsx")):
        text = f.read_text(encoding="utf-8", errors="ignore")
        fixed = text.replace('path="/:"', 'path="/"').replace("path='/:'", "path='/'")
        if fixed != text:
            f.write_text(fixed, encoding="utf-8")
            print(f"  [AutoFix] Fixed root route in App.jsx")


def _fix_api_base_url(path: Path):
    """Detect actual backend prefix and fix api.js BASE URL."""
    app_py = path / "backend" / "app.py"
    if not app_py.exists():
        return
    app_text = app_py.read_text(encoding="utf-8", errors="ignore")
    prefixes = re.findall("url_prefix=['\"]([^'\"]+)['\"]", app_text)
    if prefixes:
        first = prefixes[0].rstrip("/")
        parts = [p for p in first.split("/") if p]
        if len(parts) >= 2:
            base = "/" + "/".join(parts[:2])
        elif len(parts) == 1:
            base = "/" + parts[0]
        else:
            base = ""
    else:
        base = ""
    for f in path.rglob("api.js"):
        text = f.read_text(encoding="utf-8", errors="ignore")
        new_base = "http://127.0.0.1:5000" + base
        fixed = re.sub(
            r"(const BASE(?:_URL)?\s*=\s*['\"])http://127\.0\.0\.1:5000[^'\"]*(['\"])",
            r"\g<1>" + new_base + r"\g<2>",
            text
        )
        if fixed != text:
            f.write_text(fixed, encoding="utf-8")
            print(f"  [AutoFix] Set API base URL to: {new_base}")


def _ensure_missing_src_files(path: Path):
    src = path / "frontend" / "src"
    if not src.exists():
        return
    css = src / "index.css"
    if not css.exists():
        css.write_text(_base_css(), encoding="utf-8")
        print(f"  [AutoFix] Created missing index.css")
    
    # Create hooks directory and useToast
    hooks_dir = src / "hooks"
    hooks_dir.mkdir(exist_ok=True)
    toast_hook = hooks_dir / "useToast.js"
    if not toast_hook.exists():
        toast_hook.write_text("""import { useState, useCallback } from 'react'
export function useToast() {
  const [toasts, setToasts] = useState([])
  const toast = useCallback((message, type = 'success') => {
    const id = Date.now()
    setToasts(prev => [...prev, { id, message, type }])
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 3500)
  }, [])
  const dismiss = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])
  return { toasts, toast, dismiss }
}
""", encoding="utf-8")
        print(f"  [AutoFix] Created hooks/useToast.js")


def _base_css():
    """2026 world-class CSS design system - liquid glass, bento grid, micro-animations."""
    return """@import url('https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,700;0,9..144,900&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600&display=swap');
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#050505;--surface:#0c0c0c;--surface-2:#141414;--surface-3:#1c1c1c;
  --border:rgba(255,255,255,0.06);--border-hover:rgba(255,255,255,0.12);--border-focus:#f0c040;
  --glass:rgba(255,255,255,0.04);--glass-hover:rgba(255,255,255,0.07);
  --glass-border:rgba(255,255,255,0.08);
  --accent:#f0c040;--accent-2:#e8a020;--accent-dim:rgba(240,192,64,0.08);--accent-glow:0 0 40px rgba(240,192,64,0.15);
  --text:#f0ede8;--text-2:#888;--text-3:#444;
  --green:#34d399;--green-dim:rgba(52,211,153,0.08);
  --red:#f87171;--red-dim:rgba(248,113,113,0.08);
  --blue:#60a5fa;--blue-dim:rgba(96,165,250,0.08);
  --purple:#a78bfa;--purple-dim:rgba(167,139,250,0.08);
  --r:10px;--r-lg:16px;--r-xl:22px;--r-2xl:28px;
  --t:0.18s cubic-bezier(0.4,0,0.2,1);--t-spring:0.4s cubic-bezier(0.34,1.56,0.64,1);
  --shadow:0 1px 3px rgba(0,0,0,0.5);
  --shadow-lg:0 20px 60px rgba(0,0,0,0.8);
  --shadow-glow:0 0 40px rgba(240,192,64,0.12),0 20px 60px rgba(0,0,0,0.8);
  --font-display:'Fraunces',Georgia,serif;
  --font-body:'DM Sans',system-ui,sans-serif;
}
html{scroll-behavior:smooth;-webkit-text-size-adjust:100%}
body{background:var(--bg);color:var(--text);font-family:var(--font-body);font-weight:300;min-height:100vh;line-height:1.65;-webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale}
body::before{content:'';position:fixed;inset:0;background:radial-gradient(ellipse 80% 60% at 50% -20%,rgba(240,192,64,0.04),transparent),radial-gradient(ellipse 60% 40% at 80% 100%,rgba(96,165,250,0.03),transparent);pointer-events:none;z-index:0}
#root{position:relative;z-index:1}
::selection{background:var(--accent-dim);color:var(--accent)}
::-webkit-scrollbar{width:4px;height:4px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:rgba(255,255,255,0.1);border-radius:2px}
img,svg{max-width:100%;height:auto}
a{color:inherit;text-decoration:none}

/* TYPOGRAPHY */
h1,h2,h3,h4{font-family:var(--font-display);font-weight:700;line-height:1.15;letter-spacing:-0.025em}
h1{font-size:clamp(2.8rem,7vw,5rem);font-weight:900;letter-spacing:-0.04em}
h2{font-size:clamp(1.8rem,4vw,3rem)}
h3{font-size:1.35rem}
.display{font-family:var(--font-display);font-weight:900;letter-spacing:-0.05em;line-height:0.95}
.eyebrow{font-size:0.7rem;font-weight:600;letter-spacing:0.12em;text-transform:uppercase;color:var(--text-3)}

/* NAVBAR - liquid glass */
.navbar{
  position:fixed;top:0;left:0;right:0;z-index:200;height:58px;
  display:flex;align-items:center;justify-content:space-between;padding:0 24px;
  background:rgba(5,5,5,0.7);
  backdrop-filter:blur(32px) saturate(180%);
  -webkit-backdrop-filter:blur(32px) saturate(180%);
  border-bottom:1px solid var(--border);
  transition:background var(--t);
}
.navbar-logo{
  font-family:var(--font-display);font-size:1.15rem;font-weight:700;
  color:var(--accent);letter-spacing:-0.02em;
  display:flex;align-items:center;gap:8px;
}
.navbar-center{display:flex;align-items:center;gap:2px}
.navbar-right{display:flex;align-items:center;gap:8px}
.nav-link{
  color:var(--text-2);font-size:0.85rem;padding:6px 13px;
  border-radius:var(--r);transition:var(--t);font-weight:400;
  position:relative;
}
.nav-link:hover{color:var(--text);background:var(--glass-hover)}
.nav-link.active{color:var(--text);background:var(--glass);font-weight:500}
.nav-link.active::after{content:'';position:absolute;bottom:-1px;left:50%;transform:translateX(-50%);width:16px;height:2px;background:var(--accent);border-radius:1px}

/* PAGE */
.page{min-height:100vh;padding:78px 24px 80px;max-width:1240px;margin:0 auto}
.page-sm{max-width:680px;margin:0 auto}
.page-md{max-width:960px;margin:0 auto}
.page-wide{max-width:1440px;margin:0 auto}

/* HERO */
.hero{padding:100px 0 80px;text-align:center;position:relative}
.hero-badge{
  display:inline-flex;align-items:center;gap:8px;
  background:var(--accent-dim);color:var(--accent);
  border:1px solid rgba(240,192,64,0.2);border-radius:100px;
  padding:5px 16px;font-size:0.72rem;font-weight:600;
  letter-spacing:0.1em;text-transform:uppercase;margin-bottom:32px;
}
.hero h1{margin-bottom:20px}
.hero h1 em{font-style:normal;color:var(--accent)}
.hero-sub{color:var(--text-2);font-size:1.1rem;max-width:540px;margin:0 auto 44px;line-height:1.8;font-weight:300}
.hero-cta{display:flex;gap:14px;justify-content:center;flex-wrap:wrap}
.hero-glow{position:absolute;top:10%;left:50%;transform:translateX(-50%);width:600px;height:300px;background:radial-gradient(ellipse,rgba(240,192,64,0.06) 0%,transparent 70%);pointer-events:none;filter:blur(40px)}

/* BUTTONS */
.btn{
  display:inline-flex;align-items:center;justify-content:center;gap:8px;
  border-radius:var(--r);font-family:var(--font-body);font-weight:500;
  cursor:pointer;transition:var(--t);white-space:nowrap;border:none;
  font-size:0.875rem;letter-spacing:0.01em;position:relative;
  overflow:hidden;
}
.btn::before{content:'';position:absolute;inset:0;background:linear-gradient(180deg,rgba(255,255,255,0.08),transparent);opacity:0;transition:opacity var(--t)}
.btn:hover::before{opacity:1}
.btn:active{transform:scale(0.97)}
.btn-primary{background:var(--accent);color:#050505;padding:10px 22px;font-weight:600;box-shadow:0 0 0 0 rgba(240,192,64,0)}
.btn-primary:hover{background:var(--accent-2);box-shadow:var(--accent-glow)}
.btn-secondary{background:var(--glass);color:var(--text);padding:10px 22px;border:1px solid var(--glass-border);backdrop-filter:blur(10px)}
.btn-secondary:hover{background:var(--glass-hover);border-color:var(--border-hover)}
.btn-outline{background:transparent;color:var(--text);padding:10px 22px;border:1px solid var(--border)}
.btn-outline:hover{border-color:var(--border-hover);background:var(--glass)}
.btn-ghost{background:transparent;color:var(--text-2);padding:8px 14px}
.btn-ghost:hover{color:var(--text);background:var(--glass)}
.btn-danger{background:var(--red-dim);color:var(--red);border:1px solid rgba(248,113,113,0.2);padding:8px 16px}
.btn-danger:hover{background:rgba(248,113,113,0.14)}
.btn-sm{padding:6px 14px;font-size:0.8rem;border-radius:8px}
.btn-lg{padding:13px 28px;font-size:0.95rem;border-radius:12px}
.btn-xl{padding:16px 36px;font-size:1rem;border-radius:14px}
.btn-icon{padding:8px;aspect-ratio:1/1}
.btn:disabled{opacity:0.35;cursor:not-allowed;transform:none!important;box-shadow:none!important}
.w-full{width:100%}

/* FORM */
.form-group{display:flex;flex-direction:column;gap:8px;margin-bottom:20px}
.form-label{font-size:0.72rem;font-weight:600;color:var(--text-2);text-transform:uppercase;letter-spacing:0.08em}
.form-hint{font-size:0.75rem;color:var(--text-3)}
.form-error{font-size:0.75rem;color:var(--red)}
.input,.textarea,.select{
  width:100%;background:var(--surface-2);border:1px solid var(--border);
  border-radius:var(--r);padding:10px 14px;color:var(--text);
  font-family:var(--font-body);font-size:0.875rem;font-weight:300;
  outline:none;transition:var(--t);
}
.input:hover,.textarea:hover{border-color:var(--border-hover)}
.input:focus,.textarea:focus,.select:focus{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-dim)}
.input::placeholder,.textarea::placeholder{color:var(--text-3)}
.input.error{border-color:var(--red)}
.textarea{resize:vertical;min-height:100px;line-height:1.65}
.input-group{display:flex;gap:8px;align-items:flex-end}
.input-icon{position:relative}
.input-icon .input{padding-left:38px}
.input-icon .icon{position:absolute;left:12px;top:50%;transform:translateY(-50%);color:var(--text-3);pointer-events:none}

/* GLASS CARDS - liquid glass effect */
.card{
  background:var(--glass);border:1px solid var(--glass-border);
  border-radius:var(--r-lg);padding:24px;
  backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);
  transition:var(--t);position:relative;overflow:hidden;
}
.card::before{content:'';position:absolute;inset:0;background:linear-gradient(135deg,rgba(255,255,255,0.04) 0%,transparent 60%);pointer-events:none;border-radius:inherit}
.card:hover{border-color:var(--border-hover);background:var(--glass-hover)}
.card-solid{background:var(--surface);backdrop-filter:none}
.card-solid:hover{border-color:var(--border-hover)}
.card-glow:hover{box-shadow:var(--shadow-glow)}
.card-interactive{cursor:pointer}
.card-interactive:hover{transform:translateY(-2px);box-shadow:var(--shadow-lg)}
.card-selected{border-color:var(--accent);background:var(--accent-dim)}
.card-header{display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:20px;gap:12px}
.card-title{font-family:var(--font-display);font-size:1.1rem;font-weight:700;letter-spacing:-0.015em}
.card-subtitle{font-size:0.82rem;color:var(--text-2);margin-top:4px;font-weight:300}
.card-body{color:var(--text-2);font-size:0.875rem;line-height:1.7}
.card-footer{display:flex;align-items:center;justify-content:space-between;margin-top:20px;padding-top:18px;border-top:1px solid var(--border)}

/* BENTO GRID */
.bento{display:grid;gap:16px;grid-template-columns:repeat(auto-fill,minmax(280px,1fr))}
.bento-2{grid-template-columns:repeat(2,1fr)}
.bento-3{grid-template-columns:repeat(3,1fr)}
.bento-4{grid-template-columns:repeat(4,1fr)}
.bento-span-2{grid-column:span 2}
.bento-span-3{grid-column:span 3}
.bento-tall{grid-row:span 2}

/* GRID SYSTEM */
.grid{display:grid;gap:16px}
.grid-2{grid-template-columns:repeat(2,1fr)}
.grid-3{grid-template-columns:repeat(3,1fr)}
.grid-4{grid-template-columns:repeat(4,1fr)}
.grid-auto{grid-template-columns:repeat(auto-fill,minmax(280px,1fr))}

/* STAT CARDS */
.stat-card{
  background:var(--glass);border:1px solid var(--glass-border);
  border-radius:var(--r-lg);padding:24px;
  backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);
  position:relative;overflow:hidden;transition:var(--t);
}
.stat-card::after{content:'';position:absolute;top:0;left:0;right:0;height:1px;background:linear-gradient(90deg,transparent,var(--accent),transparent)}
.stat-card:hover{border-color:var(--border-hover);transform:translateY(-1px)}
.stat-icon{width:36px;height:36px;border-radius:var(--r);background:var(--accent-dim);display:flex;align-items:center;justify-content:center;margin-bottom:14px;flex-shrink:0}
.stat-value{font-family:var(--font-display);font-size:2.4rem;font-weight:700;color:var(--accent);line-height:1;margin-bottom:4px;letter-spacing:-0.03em}
.stat-label{font-size:0.7rem;color:var(--text-3);text-transform:uppercase;letter-spacing:0.1em;font-weight:500}
.stat-change{font-size:0.78rem;margin-top:10px;font-weight:500;display:flex;align-items:center;gap:5px}
.stat-change.up{color:var(--green)}
.stat-change.down{color:var(--red)}

/* BADGES */
.badge{display:inline-flex;align-items:center;gap:4px;padding:3px 10px;border-radius:100px;font-size:0.68rem;font-weight:600;letter-spacing:0.05em}
.badge::before{content:'';width:5px;height:5px;border-radius:50%;background:currentColor;opacity:0.7}
.badge-accent{background:var(--accent-dim);color:var(--accent);border:1px solid rgba(240,192,64,0.2)}
.badge-green{background:var(--green-dim);color:var(--green);border:1px solid rgba(52,211,153,0.2)}
.badge-red{background:var(--red-dim);color:var(--red);border:1px solid rgba(248,113,113,0.2)}
.badge-blue{background:var(--blue-dim);color:var(--blue);border:1px solid rgba(96,165,250,0.2)}
.badge-purple{background:var(--purple-dim);color:var(--purple);border:1px solid rgba(167,139,250,0.2)}
.badge-gray{background:var(--surface-2);color:var(--text-2);border:1px solid var(--border)}

/* TABLE */
.table-wrap{border:1px solid var(--border);border-radius:var(--r-lg);overflow:hidden;background:var(--surface)}
.table-toolbar{padding:14px 20px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;background:var(--surface)}
table{width:100%;border-collapse:collapse}
thead tr{background:var(--surface-2)}
th{padding:11px 16px;text-align:left;font-size:0.68rem;font-weight:600;color:var(--text-3);text-transform:uppercase;letter-spacing:0.1em;border-bottom:1px solid var(--border);white-space:nowrap}
td{padding:13px 16px;font-size:0.875rem;border-bottom:1px solid var(--border);color:var(--text)}
tr:last-child td{border-bottom:none}
tbody tr{transition:background var(--t)}
tbody tr:hover{background:var(--glass)}

/* PROGRESS */
.progress{height:4px;background:var(--surface-2);border-radius:2px;overflow:hidden}
.progress-bar{height:100%;background:linear-gradient(90deg,var(--accent),var(--accent-2));border-radius:2px;transition:width 0.5s ease}

/* ALERTS */
.alert{padding:14px 16px;border-radius:var(--r);font-size:0.875rem;display:flex;align-items:flex-start;gap:12px;line-height:1.5}
.alert-error{background:var(--red-dim);border:1px solid rgba(248,113,113,0.25);color:var(--red)}
.alert-success{background:var(--green-dim);border:1px solid rgba(52,211,153,0.25);color:var(--green)}
.alert-warning{background:rgba(251,191,36,0.08);border:1px solid rgba(251,191,36,0.25);color:#fbbf24}
.alert-info{background:var(--blue-dim);border:1px solid rgba(96,165,250,0.25);color:var(--blue)}

/* LOADING */
.spinner{width:24px;height:24px;border:2px solid var(--border);border-top-color:var(--accent);border-radius:50%;animation:spin 0.65s linear infinite;flex-shrink:0}
.spinner-lg{width:40px;height:40px;border-width:3px}
.spinner-sm{width:16px;height:16px;border-width:1.5px}
.loading-screen{min-height:100vh;display:flex;align-items:center;justify-content:center;flex-direction:column;gap:16px;color:var(--text-2)}
.skeleton{background:linear-gradient(90deg,var(--surface-2) 25%,var(--surface-3) 50%,var(--surface-2) 75%);background-size:200% 100%;animation:shimmer 1.6s infinite;border-radius:var(--r)}

/* EMPTY STATE */
.empty-state{text-align:center;padding:80px 24px;color:var(--text-3)}
.empty-icon{width:64px;height:64px;border-radius:var(--r-xl);background:var(--surface-2);display:flex;align-items:center;justify-content:center;margin:0 auto 20px;color:var(--text-3)}

/* MODAL - liquid glass */
.modal-overlay{position:fixed;inset:0;background:rgba(0,0,0,0.65);backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);z-index:300;display:flex;align-items:center;justify-content:center;padding:20px;animation:fadeIn 0.18s ease}
.modal{
  background:rgba(12,12,12,0.92);border:1px solid var(--glass-border);
  border-radius:var(--r-2xl);width:100%;max-width:480px;
  max-height:90vh;overflow-y:auto;
  box-shadow:var(--shadow-lg);
  animation:scaleIn 0.22s cubic-bezier(0.34,1.3,0.64,1);
  backdrop-filter:blur(40px);-webkit-backdrop-filter:blur(40px);
}
.modal-header{padding:24px 28px 0;display:flex;align-items:center;justify-content:space-between}
.modal-title{font-family:var(--font-display);font-size:1.3rem;font-weight:700}
.modal-body{padding:20px 28px}
.modal-footer{padding:16px 28px 24px;display:flex;justify-content:flex-end;gap:10px;border-top:1px solid var(--border);margin-top:4px}
.modal-close{background:none;border:none;color:var(--text-3);cursor:pointer;padding:6px;border-radius:var(--r);transition:var(--t);display:flex;line-height:1}
.modal-close:hover{color:var(--text);background:var(--glass)}

/* TOAST */
.toast-container{position:fixed;bottom:24px;right:24px;z-index:400;display:flex;flex-direction:column;gap:10px;pointer-events:none;max-width:380px}
.toast{
  background:rgba(20,20,20,0.92);border:1px solid var(--glass-border);
  border-radius:var(--r-lg);padding:14px 18px;font-size:0.875rem;
  box-shadow:var(--shadow-lg);animation:slideUp 0.28s var(--t-spring);
  pointer-events:all;display:flex;align-items:center;gap:12px;
  backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);
}
.toast-success{border-color:rgba(52,211,153,0.3)}
.toast-error{border-color:rgba(248,113,113,0.3)}
.toast-info{border-color:rgba(96,165,250,0.3)}

/* SIDEBAR */
.app-layout{display:flex;min-height:100vh}
.sidebar{width:240px;min-height:100vh;background:rgba(8,8,8,0.9);border-right:1px solid var(--border);display:flex;flex-direction:column;position:fixed;top:0;left:0;z-index:100;backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px)}
.sidebar-header{padding:18px 16px;border-bottom:1px solid var(--border)}
.sidebar-logo{font-family:var(--font-display);font-size:1.1rem;font-weight:700;color:var(--accent);display:flex;align-items:center;gap:8px;letter-spacing:-0.02em}
.sidebar-body{padding:10px 8px;flex:1;overflow-y:auto}
.sidebar-section{margin-bottom:20px}
.sidebar-section-title{font-size:0.65rem;font-weight:600;color:var(--text-3);text-transform:uppercase;letter-spacing:0.12em;padding:0 10px;margin-bottom:4px}
.sidebar-link{display:flex;align-items:center;gap:10px;padding:9px 12px;border-radius:var(--r);color:var(--text-2);font-size:0.84rem;transition:var(--t);margin-bottom:1px;cursor:pointer}
.sidebar-link:hover{color:var(--text);background:var(--glass)}
.sidebar-link.active{color:var(--text);background:var(--glass-hover);font-weight:500}
.sidebar-link.active .sidebar-dot{background:var(--accent)}
.sidebar-dot{width:5px;height:5px;border-radius:50%;background:transparent;transition:var(--t);flex-shrink:0}
.sidebar-footer{padding:12px 8px;border-top:1px solid var(--border)}
.main-content{margin-left:240px;flex:1;padding:32px;min-height:100vh}

/* DIVIDER */
.divider{height:1px;background:var(--border);margin:24px 0}
.divider-v{width:1px;background:var(--border);align-self:stretch}

/* ANIMATIONS */
@keyframes fadeIn{from{opacity:0}to{opacity:1}}
@keyframes fadeUp{from{opacity:0;transform:translateY(18px)}to{opacity:1;transform:translateY(0)}}
@keyframes scaleIn{from{opacity:0;transform:scale(0.94)}to{opacity:1;transform:scale(1)}}
@keyframes slideUp{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:translateY(0)}}
@keyframes slideRight{from{opacity:0;transform:translateX(-12px)}to{opacity:1;transform:translateX(0)}}
@keyframes spin{to{transform:rotate(360deg)}}
@keyframes shimmer{0%{background-position:200% 0}100%{background-position:-200% 0}}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.5}}
@keyframes glow{0%,100%{box-shadow:0 0 20px rgba(240,192,64,0.1)}50%{box-shadow:0 0 40px rgba(240,192,64,0.25)}}
.animate-fade-up{animation:fadeUp 0.35s ease forwards}
.animate-fade-in{animation:fadeIn 0.25s ease forwards}
.animate-scale{animation:scaleIn 0.22s cubic-bezier(0.34,1.3,0.64,1) forwards}
.animate-glow{animation:glow 3s ease-in-out infinite}
.stagger-1{animation-delay:0.06s;opacity:0}
.stagger-2{animation-delay:0.12s;opacity:0}
.stagger-3{animation-delay:0.18s;opacity:0}
.stagger-4{animation-delay:0.24s;opacity:0}
.stagger-5{animation-delay:0.30s;opacity:0}

/* UTILITIES */
.flex{display:flex}.flex-col{flex-direction:column}.items-center{align-items:center}.items-start{align-items:flex-start}.justify-between{justify-content:space-between}.justify-center{justify-content:center}.justify-end{justify-content:flex-end}
.gap-1{gap:4px}.gap-2{gap:8px}.gap-3{gap:12px}.gap-4{gap:16px}.gap-6{gap:24px}.gap-8{gap:32px}
.flex-1{flex:1}.flex-wrap{flex-wrap:wrap}
.text-center{text-align:center}.text-right{text-align:right}
.text-xs{font-size:0.72rem}.text-sm{font-size:0.82rem}.text-base{font-size:0.95rem}.text-lg{font-size:1.1rem}.text-xl{font-size:1.3rem}
.text-muted{color:var(--text-2)}.text-dim{color:var(--text-3)}.text-accent{color:var(--accent)}.text-green{color:var(--green)}.text-red{color:var(--red)}.text-blue{color:var(--blue)}
.font-light{font-weight:300}.font-normal{font-weight:400}.font-medium{font-weight:500}.font-semibold{font-weight:600}.font-bold{font-weight:700}.font-display{font-family:var(--font-display)}
.truncate{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.rounded{border-radius:var(--r)}.rounded-lg{border-radius:var(--r-lg)}.rounded-xl{border-radius:var(--r-xl)}.rounded-full{border-radius:100px}
.border{border:1px solid var(--border)}.border-accent{border:1px solid var(--accent)}
.bg-surface{background:var(--surface)}.bg-glass{background:var(--glass)}
.opacity-50{opacity:0.5}.opacity-0{opacity:0}
.cursor-pointer{cursor:pointer}
.overflow-hidden{overflow:hidden}
.relative{position:relative}.absolute{position:absolute}
.w-full{width:100%}.h-full{height:100%}
.mt-1{margin-top:4px}.mt-2{margin-top:8px}.mt-3{margin-top:12px}.mt-4{margin-top:16px}.mt-6{margin-top:24px}.mt-8{margin-top:32px}
.mb-2{margin-bottom:8px}.mb-3{margin-bottom:12px}.mb-4{margin-bottom:16px}.mb-6{margin-bottom:24px}
.p-3{padding:12px}.p-4{padding:16px}.p-6{padding:24px}
.px-3{padding-left:12px;padding-right:12px}.px-4{padding-left:16px;padding-right:16px}
.py-2{padding-top:8px;padding-bottom:8px}.py-3{padding-top:12px;padding-bottom:12px}
.error-box{background:var(--red-dim);border:1px solid rgba(248,113,113,0.25);border-radius:var(--r);padding:12px 16px;margin-bottom:16px;font-size:0.875rem;color:var(--red)}

/* RESPONSIVE */
@media(max-width:1200px){.bento-4,.grid-4{grid-template-columns:repeat(2,1fr)}}
@media(max-width:1024px){.main-content{margin-left:0}.sidebar{transform:translateX(-100%);transition:transform var(--t)}.sidebar.open{transform:translateX(0)}}
@media(max-width:768px){.navbar{padding:0 16px}.page{padding:68px 16px 60px}.bento-2,.bento-3,.bento-4,.grid-2,.grid-3,.grid-4{grid-template-columns:1fr}.bento-span-2,.bento-span-3{grid-column:span 1}.hero{padding:60px 0 48px}.modal{border-radius:var(--r-xl) var(--r-xl) 0 0}.modal-overlay{align-items:flex-end}}
@media(max-width:480px){.hero h1{font-size:2.2rem}.hero-cta{flex-direction:column;align-items:stretch}.grid-auto,.bento{grid-template-columns:1fr}}
@media(prefers-reduced-motion:reduce){*{animation-duration:0.01ms!important;transition-duration:0.01ms!important}}
"""

def _create_missing_components(path: Path):
    """Parse App.jsx imports and create any missing component/page files."""
    for app_jsx in list(path.rglob("App.jsx")) + list(path.rglob("App.tsx")):
        src_dir = app_jsx.parent
        try:
            text = app_jsx.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        imports = re.findall(r'from ["\'](\./[^"\']+)["\']', text)
        for imp in imports:
            rel = imp.replace("./", "")
            candidates = [
                src_dir / (rel + ".jsx"),
                src_dir / (rel + ".tsx"),
                src_dir / (rel + ".js"),
            ]
            if any(c.exists() for c in candidates):
                continue
            file_path = src_dir / (rel + ".jsx")
            file_path.parent.mkdir(parents=True, exist_ok=True)
            name = rel.split("/")[-1]
            if any(x in name for x in ["Navbar", "Nav", "Header"]):
                stub = _navbar_stub(name)
            elif any(x in name for x in ["Protected", "Guard", "Private"]):
                stub = _protected_stub(name)
            elif any(x in name for x in ["Login", "Signin", "SignIn"]):
                stub = _login_stub(name)
            elif any(x in name for x in ["Register", "Signup", "SignUp"]):
                stub = _register_stub(name)
            elif any(x in name for x in ["Dashboard", "Home", "Landing"]):
                stub = _dashboard_stub(name)
            else:
                stub = _generic_stub(name)
            if file_path.exists() and file_path.stat().st_size > 200:
                continue  # Don't overwrite real files with stubs
            file_path.write_text(stub, encoding="utf-8")
            print(f"  [AutoFix] Created missing: {file_path.relative_to(path)}")


def _navbar_stub(name):
    return (
        'import React from "react"\n'
        'import { Link, useNavigate, useLocation } from "react-router-dom"\n'
        'import { Menu, X, Bell, Settings } from "lucide-react"\n'

        'import { Link, useNavigate } from "react-router-dom"\n'
        'export default function ' + name + '({ user, onLogout }) {\n'
        '  const nav = useNavigate()\n'
        '  const logout = () => { if(onLogout) onLogout(); nav("/login") }\n'
        '  return (\n'
        '    <nav className="navbar">\n'
        '      <div className="navbar-logo">App</div>\n'
        '      <div className="navbar-links">\n'
        '        {user ? (<>\n'
        '          <Link to="/">Home</Link>\n'
        '          <Link to="/dashboard">Dashboard</Link>\n'
        '          <span style={{color:"var(--text-secondary)"}}>{user.name||user.email||"User"}</span>\n'
        '          <button className="btn-secondary" onClick={logout}>Logout</button>\n'
        '        </>) : (<>\n'
        '          <Link to="/login">Login</Link>\n'
        '          <Link to="/register"><button className="btn-primary">Get Started</button></Link>\n'
        '        </>)}\n'
        '      </div>\n'
        '    </nav>\n'
        '  )\n'
        '}\n'
    )


def _protected_stub(name):
    return f'''import React from "react"
import {{ Navigate }} from "react-router-dom"
export default function {name}({{ user, children }}) {{
  const token = localStorage.getItem("token")
  if (!user && !token) return <Navigate to="/login" replace />
  return children
}}'''


def _login_stub(name):
    return f'''import React, {{ useState }} from "react"
import {{ Link, useNavigate }} from "react-router-dom"
export default function {name}({{ setUser, onLogin }}) {{
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)
  const nav = useNavigate()
  const handleSubmit = async (e) => {{
    e.preventDefault(); setLoading(true); setError("")
    try {{
      const res = await fetch("http://127.0.0.1:5000/auth/login", {{
        method:"POST", headers:{{"Content-Type":"application/json"}},
        body: JSON.stringify({{email, password}})
      }})
      const data = await res.json()
      if (!res.ok) throw new Error(data.error||"Login failed")
      if (data.access_token) localStorage.setItem("token", data.access_token)
      if (setUser) setUser({{email}})
      if (onLogin) onLogin({{email}})
      nav("/dashboard")
    }} catch(err) {{ setError(err.message) }}
    finally {{ setLoading(false) }}
  }}
  return (
    <div className="page" style={{{{display:"flex",justifyContent:"center",paddingTop:"80px"}}}}>
      <div className="card animate-in" style={{{{width:"100%",maxWidth:"420px"}}}}>
        <h2 style={{{{fontFamily:"serif",fontSize:"1.8rem",marginBottom:"8px"}}}}>Welcome back</h2>
        <p style={{{{color:"var(--text-secondary)",marginBottom:"28px"}}}}>Sign in to your account</p>
        {{error && <div className="error-box">{{error}}</div>}}
        <form onSubmit={{handleSubmit}}>
          <div className="form-group"><label>Email</label><input className="input" type="email" value={{email}} onChange={{e=>setEmail(e.target.value)}} placeholder="you@example.com" required /></div>
          <div className="form-group"><label>Password</label><input className="input" type="password" value={{password}} onChange={{e=>setPassword(e.target.value)}} placeholder="••••••••" required /></div>
          <button className="btn-primary" type="submit" style={{{{width:"100%",padding:"12px",marginTop:"8px"}}}} disabled={{loading}}>{{loading?"Signing in...":"Sign in"}}</button>
        </form>
        <p style={{{{textAlign:"center",marginTop:"20px",fontSize:"0.88rem",color:"var(--text-secondary)"}}}}>No account? <Link to="/register" style={{{{color:"var(--accent)"}}}}>Register</Link></p>
      </div>
    </div>
  )
}}'''


def _register_stub(name):
    return f'''import React, {{ useState }} from "react"
import {{ Link, useNavigate }} from "react-router-dom"
export default function {name}() {{
  const [form, setForm] = useState({{username:"",email:"",password:""}})
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)
  const nav = useNavigate()
  const handleSubmit = async (e) => {{
    e.preventDefault(); setLoading(true); setError("")
    try {{
      const res = await fetch("http://127.0.0.1:5000/auth/register", {{
        method:"POST", headers:{{"Content-Type":"application/json"}},
        body: JSON.stringify(form)
      }})
      const data = await res.json()
      if (!res.ok) throw new Error(data.error||"Registration failed")
      nav("/login")
    }} catch(err) {{ setError(err.message) }}
    finally {{ setLoading(false) }}
  }}
  return (
    <div className="page" style={{{{display:"flex",justifyContent:"center",paddingTop:"80px"}}}}>
      <div className="card animate-in" style={{{{width:"100%",maxWidth:"420px"}}}}>
        <h2 style={{{{fontFamily:"serif",fontSize:"1.8rem",marginBottom:"8px"}}}}>Create account</h2>
        <p style={{{{color:"var(--text-secondary)",marginBottom:"28px"}}}}>Start for free today</p>
        {{error && <div className="error-box">{{error}}</div>}}
        <form onSubmit={{handleSubmit}}>
          <div className="form-group"><label>Username</label><input className="input" value={{form.username}} onChange={{e=>setForm({{...form,username:e.target.value}})}} placeholder="yourname" required /></div>
          <div className="form-group"><label>Email</label><input className="input" type="email" value={{form.email}} onChange={{e=>setForm({{...form,email:e.target.value}})}} placeholder="you@example.com" required /></div>
          <div className="form-group"><label>Password</label><input className="input" type="password" value={{form.password}} onChange={{e=>setForm({{...form,password:e.target.value}})}} placeholder="••••••••" required /></div>
          <button className="btn-primary" type="submit" style={{{{width:"100%",padding:"12px",marginTop:"8px"}}}} disabled={{loading}}>{{loading?"Creating...":"Create account"}}</button>
        </form>
        <p style={{{{textAlign:"center",marginTop:"20px",fontSize:"0.88rem",color:"var(--text-secondary)"}}}}>Have an account? <Link to="/login" style={{{{color:"var(--accent)"}}}}>Sign in</Link></p>
      </div>
    </div>
  )
}}'''


def _dashboard_stub(name):
    return f'''import React from "react"
export default function {name}() {{
  const stats = [
    {{label:"Total",value:"1,284",icon:"📊",change:"+12%"}},
    {{label:"Active",value:"342",icon:"⚡",change:"+24%"}},
    {{label:"Revenue",value:"$48k",icon:"💰",change:"+8%"}},
    {{label:"Uptime",value:"99.9%",icon:"✅",change:"stable"}},
  ]
  return (
    <div className="page">
      <div style={{{{marginBottom:"32px"}}}}>
        <h1 style={{{{fontFamily:"serif",fontSize:"2rem",fontWeight:"700",marginBottom:"6px"}}}}>Dashboard</h1>
        <p style={{{{color:"var(--text-secondary)"}}}}>Welcome back.</p>
      </div>
      <div className="grid" style={{{{marginBottom:"32px"}}}}>
        {{stats.map((s,i)=>(
          <div className="card animate-in" key={{i}} style={{{{animationDelay:`${{i*0.08}}s`}}}}>
            <div style={{{{display:"flex",justifyContent:"space-between",marginBottom:"12px"}}}}>
              <span style={{{{fontSize:"1.5rem"}}}}>{{s.icon}}</span>
              <span className="badge badge-success">{{s.change}}</span>
            </div>
            <div style={{{{fontSize:"2rem",fontWeight:"700",color:"var(--accent)",marginBottom:"4px"}}}}>{{s.value}}</div>
            <div style={{{{fontSize:"0.75rem",color:"var(--text-muted)",textTransform:"uppercase",letterSpacing:"0.06em"}}}}>{{s.label}}</div>
          </div>
        ))}}
      </div>
    </div>
  )
}}'''


def _generic_stub(name):
    return f'''import React from "react"
export default function {name}() {{
  return (
    <div className="page">
      <div className="card animate-in">
        <h1 style={{{{fontFamily:"serif",fontSize:"1.8rem",marginBottom:"16px"}}}}>{name.replace("Page","").replace("View","")}</h1>
        <p style={{{{color:"var(--text-secondary)"}}}}>This page is ready to build.</p>
      </div>
    </div>
  )
}}'''


# ── Clerk setup ───────────────────────────────────────────────────


def _fix_clerk_jwt_conflict(path: Path):
    """If Clerk is used on frontend, remove @jwt_required from backend routes."""
    src = path / "frontend" / "src"
    if not src.exists():
        return
    uses_clerk = False
    for f in list(src.rglob("*.jsx")) + list(src.rglob("*.tsx")):
        try:
            if "@clerk/clerk-react" in f.read_text(encoding="utf-8", errors="ignore"):
                uses_clerk = True
                break
        except Exception:
            pass
    if not uses_clerk:
        return
    backend = path / "backend"
    if not backend.exists():
        return
    for f in backend.rglob("*.py"):
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
            fixed = text
            fixed = fixed.replace("@jwt_required()", "")
            fixed = fixed.replace("@jwt_required()", "")
            if fixed != text:
                f.write_text(fixed, encoding="utf-8")
                print(f"  [AutoFix] Removed JWT decorators (using Clerk) in {f.name}")
        except Exception:
            pass

def _fix_clerk_setup(path: Path):
    """If Clerk is used, ensure ClerkProvider wraps app and package.json has the dep."""
    src = path / "frontend" / "src"
    if not src.exists():
        return
    uses_clerk = False
    for f in list(src.rglob("*.jsx")) + list(src.rglob("*.tsx")):
        try:
            if "@clerk/clerk-react" in f.read_text(encoding="utf-8", errors="ignore"):
                uses_clerk = True
                break
        except Exception:
            pass
    if not uses_clerk:
        return
    main_jsx = src / "main.jsx"
    if main_jsx.exists():
        text = main_jsx.read_text(encoding="utf-8", errors="ignore")
        if "ClerkProvider" not in text:
            # Only rewrite main.jsx if it uses a placeholder key
            existing = main_jsx.read_text(encoding='utf-8', errors='ignore') if main_jsx.exists() else ''
            if 'pk_test_placeholder' not in existing and 'ClerkProvider' in existing:
                return  # Already properly configured
            main_jsx.write_text(
                """import React from 'react'
import ReactDOM from 'react-dom/client'
import { ClerkProvider } from '@clerk/clerk-react'
import App from './App'
import './index.css'

const KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY || 'pk_test_placeholder'

const clerkAppearance = {
  variables: {
    colorPrimary: '#f0c040',
    colorBackground: '#080808',
    colorInputBackground: '#161616',
    colorInputText: '#f0ede8',
    colorText: '#f0ede8',
    colorTextSecondary: '#909090',
    borderRadius: '8px',
    fontFamily: 'DM Sans, sans-serif',
  },
  elements: {
    card: 'background:#111111;border:1px solid #222222;box-shadow:0 16px 48px rgba(0,0,0,0.8)',
    formButtonPrimary: 'background:#f0c040;color:#080808;font-weight:600',
    footerActionLink: 'color:#f0c040',
    userButtonPopoverCard: 'background:#111111;border:1px solid #222222',
  }
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <ClerkProvider publishableKey={KEY} appearance={clerkAppearance}>
    <App />
  </ClerkProvider>
)
""",
                encoding="utf-8"
            )
            print("  [AutoFix] Added ClerkProvider with dark theme to main.jsx")
    pkg_json = path / "frontend" / "package.json"
    if pkg_json.exists():
        try:
            pkg = json.loads(pkg_json.read_text(encoding="utf-8"))
            deps = pkg.get("dependencies", {})
            if "@clerk/clerk-react" not in deps:
                deps["@clerk/clerk-react"] = "^4.0.0"
                pkg["dependencies"] = deps
                pkg_json.write_text(json.dumps(pkg, indent=2), encoding="utf-8")
                print("  [AutoFix] Added @clerk/clerk-react to package.json")
        except Exception:
            pass
    env_file = path / "frontend" / ".env"
    if not env_file.exists():
        env_file.write_text(
            "VITE_CLERK_PUBLISHABLE_KEY=pk_test_your_key_here\n"
            "VITE_STRIPE_PUBLISHABLE_KEY=pk_test_your_stripe_key_here\n",
            encoding="utf-8"
        )
        print("  [AutoFix] Created frontend/.env — add Clerk + Stripe keys")
    
    # Create backend .env if missing
    backend_env = path / "backend" / ".env"
    if not backend_env.exists():
        backend_env.write_text(
            "STRIPE_SECRET_KEY=sk_test_your_stripe_secret_here\n"
            "STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret_here\n"
            "SECRET_KEY=change-this-in-production\n",
            encoding="utf-8"
        )
        print("  [AutoFix] Created backend/.env — add Stripe secret keys")


# ── Requirements ──────────────────────────────────────────────────

def _fix_requirements(path: Path):
    for req_file in path.rglob("requirements.txt"):
        if "node_modules" in str(req_file):
            continue
        text = req_file.read_text(encoding="utf-8", errors="ignore")
        py_files = list(path.rglob("*.py"))
        def uses(pkg):
            return any(pkg in f.read_text(encoding="utf-8", errors="ignore") for f in py_files)
        additions = []
        checks = [
            ("bcrypt", "flask-bcrypt"),
            ("jwt", "flask-jwt-extended"),
            ("flask_cors", "flask-cors"),
            ("flask_sqlalchemy", "flask-sqlalchemy"),
            ("dotenv", "python-dotenv"),
            ("stripe", "stripe"),
        ]
        for keyword, package in checks:
            if uses(keyword) and package not in text.lower():
                additions.append(package)
        if additions:
            req_file.write_text(text.rstrip() + "\n" + "\n".join(additions) + "\n", encoding="utf-8")
            print(f"  [AutoFix] Added to requirements.txt: {', '.join(additions)}")

def print_run_instructions(path):
    """Print clear run instructions after generation."""
    from pathlib import Path
    p = Path(path)
    has_backend = (p / "backend" / "app.py").exists()
    has_frontend = (p / "frontend" / "package.json").exists()
    has_env = (p / "frontend" / ".env").exists()
    
    print("\n" + "="*55)
    print("  🚀  HOW TO RUN YOUR APP")
    print("="*55)
    
    if has_backend:
        print("\n  BACKEND (Terminal 1):")
        print(f"    cd {p.name}\\backend")
        print("    py app.py")
        print("    → http://127.0.0.1:5000")
    
    if has_frontend:
        print("\n  FRONTEND (Terminal 2):")
        print(f"    cd {p.name}\\frontend")
        print("    npm install")
        print("    npm run dev")
        print("    → http://localhost:5173")
    
    if has_env:
        print("\n  ⚠️  CLERK AUTH:")
        print("    Add your key to frontend\\.env:")
        print("    VITE_CLERK_PUBLISHABLE_KEY=pk_test_...")
        print("    Get free key at: clerk.com")
    
    print("\n" + "="*55 + "\n")

def _fix_runtime_errors(path: Path):
    """Fix the most common Python runtime errors automatically."""
    backend = path / "backend"
    if not backend.exists():
        return

    for py_file in backend.rglob("*.py"):
        try:
            text = py_file.read_text(encoding="utf-8", errors="ignore")
            original = text
            
            # Fix 1: from app import db -> from extensions import db
            text = text.replace("from app import db", "from extensions import db")
            text = text.replace("from app import bcrypt", "from extensions import bcrypt")
            text = text.replace("from ..app import db", "from extensions import db")
            
            # Fix 2: missing jsonify import
            if "jsonify(" in text and "from flask import" in text and "jsonify" not in text.split("from flask import")[1].split("\n")[0]:
                text = text.replace("from flask import", "from flask import jsonify, ", 1)
            
            # Fix 3: app.db -> db (wrong reference)
            text = text.replace("app.db.", "db.")
            
            # Fix 4: db.session.add without commit
            if "db.session.add(" in text and "db.session.commit()" not in text:
                text = text.replace("db.session.add(", "db.session.add(")
                text = text.replace("return jsonify", "db.session.commit()\n    return jsonify", 1)
            
            # Fix 5: Missing request import in routes
            if "request.get_json()" in text and "from flask import" in text:
                flask_import_line = text.split("from flask import")[1].split("\n")[0]
                if "request" not in flask_import_line:
                    text = text.replace("from flask import", "from flask import request, ", 1)
            
            # Fix 6: postgres:// -> postgresql://
            text = text.replace("'postgres://", "'postgresql://")
            text = text.replace('"postgres://', '"postgresql://')
            
            # Fix 7: SQLite path with instance/ prefix
            text = text.replace("sqlite:///instance/", "sqlite:///")
            
            # Fix 8: Missing Blueprint import
            if "Blueprint(" in text and "from flask import" in text and "Blueprint" not in text.split("from flask import")[1].split("\n")[0]:
                text = text.replace("from flask import", "from flask import Blueprint, ", 1)
            
            if text != original:
                py_file.write_text(text, encoding="utf-8")
                print(f"  [AutoFix] Runtime fixes applied to {py_file.name}")
        except Exception:
            pass

    # Fix React runtime errors
    src = path / "frontend" / "src"
    if src.exists():
        for jsx_file in src.rglob("*.jsx"):
            try:
                text = jsx_file.read_text(encoding="utf-8", errors="ignore")
                original = text

                # Fix 1: path="/:" -> path="/"
                text = text.replace('path="/:"', 'path="/"')
                text = text.replace("path='/:'", "path='/'")

                # Fix 2: Missing key in map
                import re
                # Find .map( calls without key prop
                def add_key_to_map(match):
                    return match.group(0)  # Don't auto-fix, too risky
                
                # Fix 3: Direct window.location without router
                text = text.replace("window.location.href = '/'", "// navigate('/')")
                
                # Fix 4: console.log left in production code (keep but note)
                # Don't remove - useful for debugging

                if text != original:
                    jsx_file.write_text(text, encoding="utf-8")
                    print(f"  [AutoFix] React fixes applied to {jsx_file.name}")
            except Exception:
                pass


def _validate_project_structure(path: Path) -> dict:
    """Validate the generated project has all required files."""
    issues = []
    warnings = []
    
    # Required backend files
    required_backend = [
        "backend/app.py",
        "backend/extensions.py", 
        "backend/config.py",
        "backend/models.py",
    ]
    for f in required_backend:
        if not (path / f).exists():
            issues.append(f"Missing required file: {f}")
    
    # Required frontend files
    required_frontend = [
        "frontend/src/App.jsx",
        "frontend/src/main.jsx",
        "frontend/src/index.css",
        "frontend/package.json",
        "frontend/vite.config.js",
    ]
    for f in required_frontend:
        if not (path / f).exists():
            issues.append(f"Missing required file: {f}")
    
    # Check for common issues
    app_py = path / "backend" / "app.py"
    if app_py.exists():
        content = app_py.read_text(encoding="utf-8", errors="ignore")
        if "create_app" not in content:
            issues.append("backend/app.py missing create_app() factory function")
        if "db.create_all()" not in content:
            warnings.append("backend/app.py may be missing db.create_all()")
        if "CORS(" not in content:
            issues.append("backend/app.py missing CORS configuration")
    
    extensions_py = path / "backend" / "extensions.py"
    if extensions_py.exists():
        content = extensions_py.read_text(encoding="utf-8", errors="ignore")
        if "db = SQLAlchemy()" not in content:
            issues.append("backend/extensions.py missing db = SQLAlchemy()")
    
    if issues:
        print(f"\n  ⚠️  Structure issues found:")
        for issue in issues:
            print(f"     → {issue}")
    
    if not issues:
        print(f"  ✅ Project structure validated — all required files present")
    
    return {"issues": issues, "warnings": warnings, "valid": len(issues) == 0}
