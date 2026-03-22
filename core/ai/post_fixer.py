# core/ai/post_fixer.py
# Auto-patches ALL known generation errors after files are written.

import os
import re
import json
from pathlib import Path


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
    """Returns the complete competition-grade CSS design system."""
    return """@import url('https://fonts.googleapis.com/css2?family=Fraunces:wght@700;900&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500&display=swap');
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#080808;--surface:#0f0f0f;--surface-2:#161616;--surface-3:#1e1e1e;--border:#222;--border-hover:#333;--accent:#f0c040;--accent-dim:rgba(240,192,64,0.08);--accent-glow:rgba(240,192,64,0.2);--text:#f0ede8;--text-2:#909090;--text-3:#505050;--green:#34d399;--red:#f87171;--blue:#60a5fa;--yellow:#fbbf24;--r:8px;--r-lg:14px;--r-xl:20px;--t:0.15s cubic-bezier(0.4,0,0.2,1);--shadow-lg:0 16px 48px rgba(0,0,0,0.8);--font-display:'Fraunces',Georgia,serif;--font-body:'DM Sans',system-ui,sans-serif}
html{scroll-behavior:smooth}body{background:var(--bg);color:var(--text);font-family:var(--font-body);font-weight:300;min-height:100vh;line-height:1.6;-webkit-font-smoothing:antialiased}
::selection{background:var(--accent-dim);color:var(--accent)}::-webkit-scrollbar{width:5px}::-webkit-scrollbar-thumb{background:var(--border-hover);border-radius:3px}
.navbar{position:fixed;top:0;left:0;right:0;z-index:100;height:56px;display:flex;align-items:center;justify-content:space-between;padding:0 24px;background:rgba(8,8,8,0.8);backdrop-filter:blur(24px);border-bottom:1px solid var(--border)}
.navbar-logo{font-family:var(--font-display);font-size:1.1rem;font-weight:700;color:var(--accent)}
.navbar-links{display:flex;align-items:center;gap:6px}
.nav-link{color:var(--text-2);font-size:0.85rem;padding:6px 12px;border-radius:var(--r);transition:var(--t)}
.nav-link:hover{color:var(--text);background:var(--surface-2)}
.page{min-height:100vh;padding:76px 24px 80px;max-width:1200px;margin:0 auto}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;border-radius:var(--r);font-family:var(--font-body);font-weight:500;cursor:pointer;transition:var(--t);white-space:nowrap;border:none;font-size:0.875rem}
.btn-primary{background:var(--accent);color:#080808;padding:10px 22px;font-weight:600}.btn-primary:hover{filter:brightness(1.08)}
.btn-secondary{background:var(--surface-2);color:var(--text);padding:10px 22px;border:1px solid var(--border)}.btn-secondary:hover{border-color:var(--border-hover)}
.btn-ghost{background:transparent;color:var(--text-2);padding:8px 14px}.btn-ghost:hover{color:var(--text);background:var(--surface-2)}
.btn-danger{background:rgba(248,113,113,0.1);color:var(--red);border:1px solid rgba(248,113,113,0.2);padding:8px 16px}
.btn-sm{padding:6px 14px;font-size:0.8rem}.btn-lg{padding:13px 30px;font-size:0.95rem}.btn:disabled{opacity:0.35;cursor:not-allowed}
.input,.textarea{width:100%;background:var(--surface-2);border:1px solid var(--border);border-radius:var(--r);padding:10px 14px;color:var(--text);font-family:var(--font-body);font-size:0.875rem;font-weight:300;outline:none;transition:var(--t)}
.input:focus,.textarea:focus{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-dim)}.input::placeholder{color:var(--text-3)}
.form-group{display:flex;flex-direction:column;gap:7px;margin-bottom:20px}
.form-label{font-size:0.75rem;font-weight:600;color:var(--text-2);text-transform:uppercase;letter-spacing:0.07em}
.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--r-lg);padding:24px;transition:var(--t)}.card:hover{border-color:var(--border-hover)}
.card-hover:hover{transform:translateY(-2px);box-shadow:var(--shadow-lg)}
.grid{display:grid;gap:16px}.grid-2{grid-template-columns:repeat(2,1fr)}.grid-3{grid-template-columns:repeat(3,1fr)}.grid-auto{grid-template-columns:repeat(auto-fill,minmax(280px,1fr))}
.stat-card{background:var(--surface);border:1px solid var(--border);border-radius:var(--r-lg);padding:24px}
.stat-value{font-family:var(--font-display);font-size:2.2rem;font-weight:700;color:var(--accent);line-height:1;margin-bottom:4px}
.stat-label{font-size:0.72rem;color:var(--text-3);text-transform:uppercase;letter-spacing:0.07em}
.badge{display:inline-flex;align-items:center;padding:3px 10px;border-radius:100px;font-size:0.7rem;font-weight:600;letter-spacing:0.04em}
.badge-accent{background:var(--accent-dim);color:var(--accent)}.badge-green{background:rgba(52,211,153,0.1);color:var(--green)}.badge-red{background:rgba(248,113,113,0.1);color:var(--red)}
.spinner{width:24px;height:24px;border:2px solid var(--border);border-top-color:var(--accent);border-radius:50%;animation:spin 0.6s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
.empty-state{text-align:center;padding:80px 24px;color:var(--text-3)}.empty-icon{font-size:3rem;opacity:0.15;margin-bottom:16px;display:block}
.alert{padding:14px 16px;border-radius:var(--r);font-size:0.875rem}.alert-error{background:rgba(248,113,113,0.08);border:1px solid rgba(248,113,113,0.25);color:var(--red)}.alert-success{background:rgba(52,211,153,0.08);border:1px solid rgba(52,211,153,0.25);color:var(--green)}
.modal-overlay{position:fixed;inset:0;background:rgba(0,0,0,0.7);backdrop-filter:blur(8px);z-index:200;display:flex;align-items:center;justify-content:center;padding:20px}
.modal{background:var(--surface);border:1px solid var(--border);border-radius:var(--r-xl);padding:28px;width:100%;max-width:480px;animation:scaleIn 0.2s ease}
@keyframes fadeUp{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:translateY(0)}}
@keyframes scaleIn{from{opacity:0;transform:scale(0.95)}to{opacity:1;transform:scale(1)}}
.animate-fade-up{animation:fadeUp 0.3s ease forwards}.stagger-1{animation-delay:0.06s;opacity:0}.stagger-2{animation-delay:0.12s;opacity:0}.stagger-3{animation-delay:0.18s;opacity:0}
.flex{display:flex}.items-center{align-items:center}.justify-between{justify-content:space-between}.gap-3{gap:12px}.gap-4{gap:16px}.flex-1{flex:1}.w-full{width:100%}.text-center{text-align:center}
.text-muted{color:var(--text-2)}.text-dim{color:var(--text-3)}.text-accent{color:var(--accent)}.text-sm{font-size:0.82rem}.text-xs{font-size:0.72rem}
.error-box{background:rgba(248,113,113,0.08);border:1px solid rgba(248,113,113,0.25);border-radius:var(--r);padding:12px 16px;margin-bottom:16px;font-size:0.875rem;color:var(--red)}
.loading-center{display:flex;justify-content:center;align-items:center;padding:60px}
@media(max-width:768px){.navbar{padding:0 16px}.page{padding:68px 16px 60px}.grid-2,.grid-3{grid-template-columns:1fr}}
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
        env_file.write_text("VITE_CLERK_PUBLISHABLE_KEY=pk_test_your_key_here\n", encoding="utf-8")
        print("  [AutoFix] Created frontend/.env — add your Clerk key from clerk.com")


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
