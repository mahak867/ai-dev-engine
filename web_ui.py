#!/usr/bin/env python3
"""
APEX v3 — Local Web UI (Flask)
Run: python web_ui.py  →  open http://localhost:7331
"""
from __future__ import annotations
import json, threading, queue, time, os
from pathlib import Path

try:
    from flask import Flask, render_template_string, request, Response, jsonify, stream_with_context
except ImportError:
    print("Run: pip install flask")
    raise

from core.orchestrator import Orchestrator
from core.memory.store import MemoryStore

app   = Flask(__name__)
store = MemoryStore()

# ── HTML template ──────────────────────────────────────────────────────────────
HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>APEX AI Dev Engine v3</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Syne:wght@700;800&display=swap');
  :root{--amber:#f5b731;--teal:#1dcaa0;--red:#e74c3c;--green:#2ecc71;--bg:#0d0d10;--bg2:#141418;--bg3:#1c1c23;--border:#252530;--text:#dde0ea;--muted:#55556a}
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:var(--bg);color:var(--text);font-family:'JetBrains Mono',monospace;font-size:13px;display:grid;grid-template-rows:56px 1fr;min-height:100vh}
  header{background:var(--bg2);border-bottom:1px solid var(--border);display:flex;align-items:center;padding:0 24px;gap:16px}
  .logo{font-family:'Syne',sans-serif;font-weight:800;font-size:18px;color:var(--amber);letter-spacing:-1px}
  .tagline{color:var(--muted);font-size:11px}
  .status-bar{margin-left:auto;display:flex;gap:12px;font-size:11px;align-items:center}
  .dot{width:7px;height:7px;border-radius:50%}
  .dot.ok{background:var(--green)}
  .dot.warn{background:var(--amber);animation:blink 1s infinite}
  @keyframes blink{0%,100%{opacity:1}50%{opacity:0}}
  main{display:grid;grid-template-columns:280px 1fr 240px;height:calc(100vh - 56px)}
  .panel{padding:16px;overflow-y:auto}
  .left{background:var(--bg2);border-right:1px solid var(--border)}
  .right{background:var(--bg2);border-left:1px solid var(--border)}
  .center{background:var(--bg);display:flex;flex-direction:column}
  .section-label{font-size:9px;letter-spacing:2px;color:var(--muted);text-transform:uppercase;margin-bottom:10px;padding-bottom:6px;border-bottom:1px solid var(--border)}
  select,input,textarea{background:var(--bg3);border:1px solid var(--border);border-radius:5px;color:var(--text);font-family:'JetBrains Mono',monospace;font-size:12px;padding:7px 10px;width:100%;outline:none;transition:border .15s}
  select:focus,input:focus,textarea:focus{border-color:var(--amber)}
  textarea{resize:none;min-height:80px}
  .form-group{margin-bottom:12px}
  label{display:block;font-size:10px;color:var(--muted);margin-bottom:4px;letter-spacing:.5px}
  .btn{display:block;width:100%;padding:10px;border:none;border-radius:5px;cursor:pointer;font-family:'Syne',sans-serif;font-weight:700;font-size:12px;letter-spacing:.5px;transition:all .15s;margin-bottom:6px}
  .btn-primary{background:var(--amber);color:#000}
  .btn-primary:hover{background:#f0a820}
  .btn-primary:disabled{opacity:.4;cursor:not-allowed}
  .btn-secondary{background:var(--bg3);color:var(--text);border:1px solid var(--border)}
  .btn-secondary:hover{border-color:var(--teal);color:var(--teal)}
  .mode-tabs{display:flex;gap:4px;margin-bottom:14px;flex-wrap:wrap}
  .tab{padding:5px 10px;border-radius:4px;font-size:10px;font-family:'Syne',sans-serif;font-weight:700;letter-spacing:.5px;border:1px solid var(--border);background:transparent;color:var(--muted);cursor:pointer;transition:all .15s}
  .tab.active{background:var(--bg3);color:var(--amber);border-color:var(--amber)}
  .terminal{flex:1;padding:16px;overflow-y:auto;font-size:12px;line-height:1.8;min-height:0}
  .terminal::-webkit-scrollbar{width:4px}
  .terminal::-webkit-scrollbar-track{background:transparent}
  .terminal::-webkit-scrollbar-thumb{background:var(--border);border-radius:2px}
  .t-system{color:var(--muted)}
  .t-agent{color:var(--teal)}
  .t-running{color:var(--amber)}
  .t-done{color:var(--green)}
  .t-error{color:var(--red)}
  .t-code{color:#a78bfa;white-space:pre-wrap;font-size:11px;background:var(--bg3);padding:10px;border-radius:4px;margin:4px 0;display:block;border-left:2px solid #a78bfa}
  .t-output{color:var(--text)}
  .input-bar{padding:12px 16px;border-top:1px solid var(--border);display:flex;gap:8px;background:var(--bg2)}
  .input-bar textarea{flex:1;min-height:48px;max-height:120px}
  .send-btn{padding:0 16px;background:var(--amber);color:#000;border:none;border-radius:5px;cursor:pointer;font-weight:700;font-size:18px;transition:all .15s;align-self:flex-end;height:48px}
  .send-btn:hover{background:#f0a820}
  .agent-list{display:flex;flex-direction:column;gap:6px;margin-bottom:16px}
  .agent-item{padding:8px 10px;border-radius:5px;border:1px solid var(--border);background:var(--bg3);transition:all .15s}
  .agent-item.active{border-color:var(--amber);background:#1a1400}
  .agent-item.done{border-color:var(--teal);background:#0a1a15}
  .agent-name{font-size:11px;font-weight:600;display:flex;align-items:center;gap:6px}
  .agent-status{font-size:9px;color:var(--muted);margin-top:2px}
  .project-card{padding:8px 10px;border-radius:5px;border:1px solid var(--border);margin-bottom:6px;cursor:pointer;transition:all .15s}
  .project-card:hover{border-color:var(--amber)}
  .proj-name{font-size:11px;font-weight:600;color:var(--amber)}
  .proj-desc{font-size:10px;color:var(--muted);margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .model-select-wrapper{margin-bottom:12px}
  .file-tree{font-size:11px;line-height:1.8;color:var(--muted)}
  .file-tree .dir{color:var(--amber)}
  .file-tree .file{color:var(--teal)}
  .stats{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:14px}
  .stat{background:var(--bg3);border-radius:5px;padding:8px;text-align:center}
  .stat-val{font-size:18px;font-weight:700;color:var(--amber)}
  .stat-lbl{font-size:9px;color:var(--muted);letter-spacing:1px;text-transform:uppercase}
</style>
</head>
<body>
<header>
  <div class="logo">APEX</div>
  <div class="tagline">AI Dev Engine v3 • Multi-Agent</div>
  <div class="status-bar">
    <div class="dot ok" id="status-dot"></div>
    <span id="status-text">Ready</span>
  </div>
</header>
<main>
  <!-- LEFT PANEL -->
  <div class="panel left">
    <div class="section-label">Mode</div>
    <div class="mode-tabs" id="mode-tabs">
      <button class="tab active" onclick="setMode('generate')">Generate</button>
      <button class="tab" onclick="setMode('edit')">Edit</button>
      <button class="tab" onclick="setMode('debug')">Debug</button>
      <button class="tab" onclick="setMode('audit')">Audit</button>
    </div>

    <div id="generate-form">
      <div class="form-group">
        <label>Project Name</label>
        <input id="proj-name" placeholder="my_saas_app" value="my_app">
      </div>
      <div class="form-group">
        <label>What to build</label>
        <textarea id="proj-request" placeholder="e.g. SaaS dashboard with Next.js, FastAPI, PostgreSQL, and Stripe payments"></textarea>
      </div>
      <div class="form-group model-select-wrapper">
        <label>Model / Cascade</label>
        <select id="model-select">
          <option value="auto">auto (smart cascade)</option>
          <option value="coding">coding (Qwen/DeepSeek cascade)</option>
          <option value="reasoning">reasoning (QwQ/R1 cascade)</option>
          <option value="groq/llama-3.3-70b">groq / llama-3.3-70b</option>
          <option value="groq/qwen-qwq-32b">groq / qwen-qwq-32b</option>
          <option value="or/kimi-k2">openrouter / kimi-k2</option>
          <option value="or/gemini-2.5-pro">openrouter / gemini-2.5-pro</option>
          <option value="or/deepseek-r1">openrouter / deepseek-r1</option>
          <option value="mistral/codestral">mistral / codestral</option>
          <option value="ollama/qwen2.5-coder:32b">ollama / qwen2.5-coder:32b (local)</option>
        </select>
      </div>
      <label style="display:flex;align-items:center;gap:8px;font-size:11px;color:var(--muted);margin-bottom:12px;cursor:pointer">
        <input type="checkbox" id="stream-check"> Stream output
      </label>
      <button class="btn btn-primary" id="gen-btn" onclick="generate()">⚡ Generate</button>
      <button class="btn btn-secondary" onclick="clearTerminal()">Clear</button>
    </div>

    <div style="margin-top:20px">
      <div class="section-label">Agents</div>
      <div class="agent-list" id="agent-list">
        <div class="agent-item" id="ag-Planner"><div class="agent-name">🗺️ Planner</div><div class="agent-status">Idle</div></div>
        <div class="agent-item" id="ag-Architect"><div class="agent-name">🏛️ Architect</div><div class="agent-status">Idle</div></div>
        <div class="agent-item" id="ag-Coder"><div class="agent-name">👨‍💻 Coder</div><div class="agent-status">Idle</div></div>
        <div class="agent-item" id="ag-Reviewer"><div class="agent-name">🔍 Reviewer</div><div class="agent-status">Idle</div></div>
        <div class="agent-item" id="ag-SelfHealer"><div class="agent-name">🔧 Self-Healer</div><div class="agent-status">Idle</div></div>
        <div class="agent-item" id="ag-DocWriter"><div class="agent-name">📝 Doc Writer</div><div class="agent-status">Idle</div></div>
      </div>
    </div>
  </div>

  <!-- CENTER PANEL -->
  <div class="center">
    <div class="terminal" id="terminal">
      <span class="t-system">APEX AI Dev Engine v3.0 — Ready</span><br>
      <span class="t-system">Multi-Agent • Self-Healing • Persistent Memory</span><br>
      <span class="t-system">─────────────────────────────────────</span><br>
      <span class="t-system">Type a project idea and click Generate.</span><br>
    </div>
  </div>

  <!-- RIGHT PANEL -->
  <div class="panel right">
    <div class="section-label">Session Stats</div>
    <div class="stats">
      <div class="stat"><div class="stat-val" id="stat-projects">0</div><div class="stat-lbl">Projects</div></div>
      <div class="stat"><div class="stat-val" id="stat-files">0</div><div class="stat-lbl">Files Gen</div></div>
      <div class="stat"><div class="stat-val" id="stat-agents">6</div><div class="stat-lbl">Agents</div></div>
      <div class="stat"><div class="stat-val" id="stat-time">0s</div><div class="stat-lbl">Last Run</div></div>
    </div>

    <div class="section-label">Recent Projects</div>
    <div id="project-list"></div>

    <div class="section-label" style="margin-top:12px">Output Files</div>
    <div class="file-tree" id="file-tree"><span style="color:var(--muted)">No files yet</span></div>
  </div>
</main>

<script>
let mode = 'generate', startTime = 0, fileCount = 0, projectCount = 0;

function setMode(m){
  mode = m;
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  event.target.classList.add('active');
}

function clearTerminal(){
  document.getElementById('terminal').innerHTML =
    '<span class="t-system">Terminal cleared. Ready.</span><br>';
}

function appendTerminal(html){
  const t = document.getElementById('terminal');
  t.innerHTML += html;
  t.scrollTop = t.scrollHeight;
}

function setAgent(name, status){
  const el = document.getElementById('ag-'+name);
  if(!el) return;
  el.className = 'agent-item ' + (status === 'done' ? 'done' : status === 'running' ? 'active' : '');
  el.querySelector('.agent-status').textContent =
    status === 'running' ? '⟳ Running...' : status === 'done' ? '✓ Done' : 'Idle';
}

function setStatus(text, ok=true){
  document.getElementById('status-text').textContent = text;
  document.getElementById('status-dot').className = 'dot ' + (ok ? 'ok' : 'warn');
}

async function generate(){
  const name = document.getElementById('proj-name').value.trim() || 'my_app';
  const req  = document.getElementById('proj-request').value.trim();
  const model= document.getElementById('model-select').value;
  const stream = document.getElementById('stream-check').checked;
  if(!req){ alert('Enter a project description'); return; }

  document.getElementById('gen-btn').disabled = true;
  setStatus('Generating...', false);
  startTime = Date.now();
  clearTerminal();
  ['Planner','Architect','Coder','Reviewer','SelfHealer','DocWriter'].forEach(a => setAgent(a,''));

  if(stream){
    await generateStream(name, req, model);
  } else {
    await generateBlocking(name, req, model);
  }
}

async function generateBlocking(name, req, model){
  const evtSource = new EventSource(
    `/generate?name=${encodeURIComponent(name)}&request=${encodeURIComponent(req)}&model=${encodeURIComponent(model)}`
  );
  evtSource.onmessage = e => {
    const data = JSON.parse(e.data);
    if(data.type === 'event'){
      const {agent, status, msg} = data;
      setAgent(agent, status);
      const cls = status === 'done' ? 't-done' : status === 'running' ? 't-running' : 't-agent';
      appendTerminal(`<span class="${cls}">[${agent}] ${status}: ${msg}</span><br>`);
    } else if(data.type === 'files'){
      renderFileTree(data.files);
      fileCount += Object.keys(data.files).length;
      document.getElementById('stat-files').textContent = fileCount;
    } else if(data.type === 'done'){
      const elapsed = ((Date.now()-startTime)/1000).toFixed(1);
      appendTerminal(`<br><span class="t-done">✔ Complete in ${elapsed}s → ${data.path}</span><br>`);
      document.getElementById('stat-time').textContent = elapsed+'s';
      document.getElementById('stat-projects').textContent = ++projectCount;
      document.getElementById('gen-btn').disabled = false;
      setStatus('Ready');
      evtSource.close();
      loadProjects();
    } else if(data.type === 'error'){
      appendTerminal(`<span class="t-error">✗ Error: ${data.msg}</span><br>`);
      document.getElementById('gen-btn').disabled = false;
      setStatus('Error', false);
      evtSource.close();
    }
  };
  evtSource.onerror = () => {
    evtSource.close();
    document.getElementById('gen-btn').disabled = false;
    setStatus('Ready');
  };
}

async function generateStream(name, req, model){
  const resp = await fetch('/generate-stream', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({name, request: req, model})
  });
  const reader = resp.body.getReader();
  const dec = new TextDecoder();
  appendTerminal('<span class="t-code">');
  while(true){
    const {done, value} = await reader.read();
    if(done) break;
    const text = dec.decode(value);
    const t = document.getElementById('terminal');
    t.innerHTML += text.replace(/</g,'&lt;').replace(/>/g,'&gt;');
    t.scrollTop = t.scrollHeight;
  }
  appendTerminal('</span>');
  document.getElementById('gen-btn').disabled = false;
  setStatus('Ready');
}

function renderFileTree(files){
  const tree = document.getElementById('file-tree');
  const paths = Object.keys(files);
  const dirs = {};
  paths.forEach(p => {
    const parts = p.split('/');
    if(parts.length > 1) dirs[parts[0]] = (dirs[parts[0]]||0)+1;
  });
  let html = '';
  for(const [dir, count] of Object.entries(dirs)){
    html += `<div class="dir">📁 ${dir}/ <span style="color:var(--muted)">(${count})</span></div>`;
  }
  paths.filter(p => !p.includes('/')).forEach(f => {
    html += `<div class="file">📄 ${f}</div>`;
  });
  tree.innerHTML = html || '<span style="color:var(--muted)">No files</span>';
}

async function loadProjects(){
  const resp = await fetch('/projects');
  const data = await resp.json();
  const list = document.getElementById('project-list');
  list.innerHTML = data.projects.slice(0,8).map(p => `
    <div class="project-card">
      <div class="proj-name">${p.name}</div>
      <div class="proj-desc">${p.request}</div>
    </div>
  `).join('');
}

loadProjects();
</script>
</body>
</html>"""


# ── Routes ─────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/generate")
def generate_sse():
    name    = request.args.get("name",    "my_app")
    req_str = request.args.get("request", "")
    model   = request.args.get("model",   "auto")

    def _stream():
        event_q: queue.Queue = queue.Queue()
        all_files: dict[str, str] = {}

        def on_event(agent, status, msg):
            event_q.put(("event", {"type": "event", "agent": agent, "status": status, "msg": msg}))

        def run():
            try:
                orch = Orchestrator(model=model, on_event=on_event)
                path = orch.generate_fullstack(name=name, request=req_str)
                # collect files
                from pathlib import Path
                base = Path(path)
                files = {}
                skip = {".git","node_modules","__pycache__",".next","dist","build"}
                for p in base.rglob("*"):
                    if p.is_file() and not any(s in p.parts for s in skip):
                        try: files[str(p.relative_to(base))] = ""
                        except: pass
                event_q.put(("files", {"type": "files", "files": files}))
                event_q.put(("done",  {"type": "done",  "path": path}))
            except Exception as e:
                event_q.put(("error", {"type": "error", "msg": str(e)}))

        t = threading.Thread(target=run, daemon=True)
        t.start()

        while True:
            try:
                kind, data = event_q.get(timeout=120)
                yield f"data: {json.dumps(data)}\n\n"
                if kind in ("done", "error"):
                    break
            except queue.Empty:
                break

    return Response(stream_with_context(_stream()), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/generate-stream", methods=["POST"])
def generate_stream():
    data  = request.get_json()
    name  = data.get("name",    "my_app")
    req   = data.get("request", "")
    model = data.get("model",   "auto")

    def _gen():
        orch = Orchestrator(model=model)
        for token in orch.generate_stream(name, req):
            yield token

    return Response(stream_with_context(_gen()), mimetype="text/plain")


@app.route("/projects")
def list_projects():
    projects = store.list_projects()
    return jsonify({"projects": projects})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7331))
    print(f"\n  APEX Web UI → http://localhost:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=False)
