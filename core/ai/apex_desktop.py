import json
import os
import re
import subprocess
import sys
import threading
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

from core.ai.cloud_router import available_profiles, cloud_status, generate_cloud_text
from core.ai.elite_engine import generate_elite_artifacts
from core.ai.elite_pipeline import run_elite_pipeline


APP_HOME = Path.home() / ".apex_engine"
STATE_FILE = APP_HOME / "state.json"
SETTINGS_FILE = APP_HOME / "settings.json"
DEFAULT_OUT = APP_HOME / "projects"

BG = "#0A0C10"
SURFACE = "#121822"
CARD = "#1A2230"
BORDER = "#2A3444"
TEXT = "#F4F7FB"
MUTED = "#A5B0C0"
SOFT = "#728096"
ACCENT = "#9FE870"


@dataclass
class ProjectRecord:
    name: str
    mode: str
    prompt: str
    path: str
    created_at: str


class ApexDesktop:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Apex Local Builder")
        self.root.geometry("1320x820")
        self.root.minsize(1080, 720)
        self.root.configure(bg=BG)

        APP_HOME.mkdir(parents=True, exist_ok=True)
        DEFAULT_OUT.mkdir(parents=True, exist_ok=True)

        self.settings = self._load_json(SETTINGS_FILE, {})
        self.projects = [ProjectRecord(**p) for p in self._load_json(STATE_FILE, {}).get("projects", [])]

        self.page = tk.StringVar(value="Home")
        self.project_name = tk.StringVar(value="apex-workspace")
        self.mode = tk.StringVar(value="Agent Builder")
        self.output_dir = tk.StringVar(value=self.settings.get("output_dir", str(DEFAULT_OUT)))
        self.api_key = tk.StringVar(value=self.settings.get("groq_api_key", ""))
        self.openrouter_key = tk.StringVar(value=self.settings.get("openrouter_api_key", ""))
        self.cloud_provider = tk.StringVar(value=self.settings.get("cloud_provider", "Auto"))
        self.cloud_profile = tk.StringVar(value=self.settings.get("cloud_profile", "quality_max"))
        self.cloud_enhance = tk.BooleanVar(value=bool(self.settings.get("cloud_enhance", True)))
        self.status = tk.StringVar(value=cloud_status(self.openrouter_key.get(), self.api_key.get()))

        self.apps_list = None
        self.log_box = None
        self.generate_btn = None
        self._generation_running = False
        self._build_ui()
        self._show_page("Home")
        self._log("Apex is ready.")
        self._log("This build is local-first and free by default.")

    def _build_ui(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        sidebar = tk.Frame(self.root, bg=SURFACE, width=240)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        brand = tk.Frame(sidebar, bg=SURFACE, padx=18, pady=18)
        brand.pack(fill="x")
        tk.Label(brand, text="Apex", font=("Segoe UI Semibold", 22), bg=SURFACE, fg=TEXT).pack(anchor="w")
        tk.Label(
            brand,
            text="Glaze-inspired local dev tool with Claude/Replit-style workflow packs",
            font=("Segoe UI", 9),
            bg=SURFACE,
            fg=MUTED,
            wraplength=190,
            justify="left",
        ).pack(anchor="w", pady=(4, 0))

        self.nav = {}
        for name in ["Home", "Builder", "Projects", "Hackathon", "CTF Lab", "Settings"]:
            btn = tk.Button(
                sidebar, text=name, font=("Segoe UI Semibold", 10), bg=SURFACE, fg=MUTED,
                relief="flat", bd=0, padx=18, pady=12, anchor="w", cursor="hand2",
                activebackground=CARD, activeforeground=TEXT, command=lambda n=name: self._show_page(n)
            )
            btn.pack(fill="x", padx=10, pady=3)
            self.nav[name] = btn

        footer = tk.Frame(sidebar, bg=SURFACE, padx=18, pady=18)
        footer.pack(side="bottom", fill="x")
        tk.Label(footer, textvariable=self.status, font=("Segoe UI", 9), bg=SURFACE, fg=ACCENT, wraplength=190, justify="left").pack(anchor="w")
        tk.Label(
            footer,
            text="CTF tools here are for legal labs and challenge boxes only.",
            font=("Segoe UI", 8), bg=SURFACE, fg=SOFT, wraplength=190, justify="left"
        ).pack(anchor="w", pady=(6, 0))

        main = tk.Frame(self.root, bg=BG)
        main.pack(side="left", fill="both", expand=True)
        top = tk.Frame(main, bg=BG, padx=24, pady=18)
        top.pack(fill="x")
        self.page_title = tk.Label(top, text="Home", font=("Segoe UI Semibold", 18), bg=BG, fg=TEXT)
        self.page_title.pack(side="left")
        tk.Button(
            top, text="Open Output Folder", font=("Segoe UI Semibold", 10), bg=CARD, fg=TEXT,
            relief="flat", bd=0, padx=14, pady=8, cursor="hand2", command=lambda: self._open_path(Path(self.output_dir.get()))
        ).pack(side="right")

        self.container = tk.Frame(main, bg=BG)
        self.container.pack(fill="both", expand=True, padx=22, pady=(0, 18))
        self.frames = {}
        for name in ["Home", "Builder", "Projects", "Hackathon", "CTF Lab", "Settings"]:
            frame = tk.Frame(self.container, bg=BG)
            self.frames[name] = frame
            getattr(self, f"_build_{name.lower().replace(' ', '_')}")(frame)

    def _build_home(self, parent):
        hero = self._card(parent)
        hero.pack(fill="x")
        tk.Label(hero, text="Desktop tools, reimagined for you.", font=("Segoe UI Semibold", 28), bg=CARD, fg=TEXT).pack(anchor="w")
        tk.Label(
            hero,
            text="Create local workspaces that feel closer to Claude or Replit: prompt-driven setup, starter files, notes, and a fast path to iterate on your own machine.",
            font=("Segoe UI", 11), bg=CARD, fg=MUTED, wraplength=820, justify="left"
        ).pack(anchor="w", pady=(10, 18))
        self._button(hero, "Start Building", ACCENT, BG, lambda: self._show_page("Builder"))
        self._button(hero, "Open Projects", CARD, TEXT, lambda: self._show_page("Projects"))

        grid = tk.Frame(parent, bg=BG)
        grid.pack(fill="x", pady=14)
        for i, text in enumerate([
            "Elite Agent Run: autonomous plan/build/review/ship pipeline",
            "Agent Builder: create a prompt workspace with starter app files",
            "Hackathon Pack: README, timeline, pitch, and MVP docs",
            "CTF Lab: legal challenge notes plus decoding helpers",
            "Projects: review and reopen generated workspaces fast",
        ]):
            card = self._card(grid)
            card.grid(row=i // 2, column=i % 2, sticky="nsew", padx=6, pady=6)
            grid.columnconfigure(i % 2, weight=1)
            tk.Label(card, text=text, font=("Segoe UI", 10), bg=CARD, fg=MUTED, wraplength=360, justify="left").pack(anchor="w")

    def _build_builder(self, parent):
        left = self._card(parent)
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))
        right = self._card(parent)
        right.pack(side="left", fill="both", expand=True)

        self._label(left, "Project name")
        tk.Entry(left, textvariable=self.project_name, bg=BG, fg=TEXT, relief="flat", bd=0, insertbackground=TEXT, font=("Segoe UI", 10)).pack(fill="x", ipady=9)
        self._label(left, "Mode")
        ttk.Combobox(
            left,
            textvariable=self.mode,
            values=["Elite Agent Run", "Agent Builder", "Hackathon Pack", "CTF Lab"],
            state="readonly",
        ).pack(fill="x")
        self._label(left, "Output folder")
        row = tk.Frame(left, bg=CARD)
        row.pack(fill="x")
        tk.Entry(row, textvariable=self.output_dir, bg=BG, fg=TEXT, relief="flat", bd=0, insertbackground=TEXT, font=("Segoe UI", 10)).pack(side="left", fill="x", expand=True, ipady=9)
        tk.Button(row, text="Browse", bg=BG, fg=TEXT, relief="flat", bd=0, padx=14, cursor="hand2", command=self._pick_output).pack(side="left", padx=(8, 0))
        self._label(left, "Prompt")
        self.prompt_box = scrolledtext.ScrolledText(left, height=14, bg=BG, fg=TEXT, relief="flat", bd=0, insertbackground=TEXT, wrap="word", font=("Segoe UI", 10), padx=10, pady=10)
        self.prompt_box.pack(fill="both", expand=True)
        self.prompt_box.insert("1.0", "Build a local personal dev tool with a polished homepage, project workspace, and a simple way to plan coding tasks.")
        actions = tk.Frame(left, bg=CARD)
        actions.pack(fill="x", pady=(14, 0))
        self.generate_btn = self._button(actions, "Generate Workspace", ACCENT, BG, self._generate_current)
        self._button(actions, "Elite Example", CARD, TEXT, lambda: self._load_prompt("Elite Agent Run"))
        self._button(actions, "Hackathon Example", CARD, TEXT, lambda: self._load_prompt("Hackathon Pack"))
        self._button(actions, "CTF Example", CARD, TEXT, lambda: self._load_prompt("CTF Lab"))

        tk.Label(right, text="Activity log", font=("Segoe UI Semibold", 10), bg=CARD, fg=TEXT).pack(anchor="w")
        self.log_box = scrolledtext.ScrolledText(right, bg=BG, fg=TEXT, relief="flat", bd=0, wrap="word", font=("Consolas", 10), padx=10, pady=10)
        self.log_box.pack(fill="both", expand=True, pady=(12, 0))
        self.log_box.config(state="disabled")

    def _build_projects(self, parent):
        left = self._card(parent)
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))
        right = self._card(parent)
        right.pack(side="left", fill="both", expand=True)
        self.apps_list = tk.Listbox(left, bg=BG, fg=TEXT, selectbackground=BORDER, relief="flat", bd=0, font=("Segoe UI", 10))
        self.apps_list.pack(fill="both", expand=True)
        self.apps_list.bind("<<ListboxSelect>>", lambda _e: self._render_project())
        self.details = scrolledtext.ScrolledText(right, bg=BG, fg=TEXT, relief="flat", bd=0, wrap="word", font=("Consolas", 10), padx=10, pady=10)
        self.details.pack(fill="both", expand=True)
        actions = tk.Frame(right, bg=CARD)
        actions.pack(fill="x", pady=(12, 0))
        self._button(actions, "Open Folder", ACCENT, BG, self._open_selected)
        self._button(actions, "Open README", CARD, TEXT, self._open_selected_readme)
        self._button(actions, "Refresh", CARD, TEXT, self._refresh_projects)

    def _build_hackathon(self, parent):
        card = self._card(parent)
        card.pack(fill="both", expand=True)
        tk.Label(card, text="Hackathon mode", font=("Segoe UI Semibold", 12), bg=CARD, fg=TEXT).pack(anchor="w")
        self.hack_box = scrolledtext.ScrolledText(card, height=18, bg=BG, fg=TEXT, relief="flat", bd=0, wrap="word", font=("Segoe UI", 10), padx=10, pady=10)
        self.hack_box.pack(fill="both", expand=True, pady=(12, 0))
        self.hack_box.insert("1.0", "Theme: AI for student productivity\nNeed: README, pitch, MVP scope, 24-hour plan, and demo checklist.")
        bar = tk.Frame(card, bg=CARD)
        bar.pack(fill="x", pady=(14, 0))
        self._button(bar, "Generate Hackathon Pack", ACCENT, BG, lambda: self._generate_named("hackathon-pack", "Hackathon Pack", self.hack_box.get("1.0", "end").strip()))

    def _build_ctf_lab(self, parent):
        card = self._card(parent)
        card.pack(fill="both", expand=True)
        tk.Label(card, text="CTF lab", font=("Segoe UI Semibold", 12), bg=CARD, fg=TEXT).pack(anchor="w")
        self.ctf_box = scrolledtext.ScrolledText(card, height=18, bg=BG, fg=TEXT, relief="flat", bd=0, wrap="word", font=("Segoe UI", 10), padx=10, pady=10)
        self.ctf_box.pack(fill="both", expand=True, pady=(12, 0))
        self.ctf_box.insert("1.0", "Challenge types: crypto and web basics\nNeed: notes, checklist, findings sheet, and a small decode helper script for legal CTF practice.")
        bar = tk.Frame(card, bg=CARD)
        bar.pack(fill="x", pady=(14, 0))
        self._button(bar, "Generate CTF Workspace", ACCENT, BG, lambda: self._generate_named("ctf-lab", "CTF Lab", self.ctf_box.get("1.0", "end").strip()))

    def _build_settings(self, parent):
        card = self._card(parent)
        card.pack(fill="both", expand=True)
        self._label(card, "Default output folder")
        tk.Entry(card, textvariable=self.output_dir, bg=BG, fg=TEXT, relief="flat", bd=0, insertbackground=TEXT, font=("Segoe UI", 10)).pack(fill="x", ipady=9)
        self._label(card, "Optional Groq API key")
        tk.Entry(card, textvariable=self.api_key, bg=BG, fg=TEXT, relief="flat", bd=0, insertbackground=TEXT, show="*", font=("Segoe UI", 10)).pack(fill="x", ipady=9)
        self._label(card, "Optional OpenRouter API key")
        tk.Entry(card, textvariable=self.openrouter_key, bg=BG, fg=TEXT, relief="flat", bd=0, insertbackground=TEXT, show="*", font=("Segoe UI", 10)).pack(fill="x", ipady=9)
        self._label(card, "Provider preference")
        ttk.Combobox(card, textvariable=self.cloud_provider, values=["Auto", "OpenRouter", "Groq"], state="readonly").pack(fill="x")
        self._label(card, "Cloud profile")
        ttk.Combobox(card, textvariable=self.cloud_profile, values=available_profiles(), state="readonly").pack(fill="x")
        tk.Checkbutton(
            card,
            text="Run cloud enhancement pass after workspace generation",
            variable=self.cloud_enhance,
            bg=CARD,
            fg=MUTED,
            activebackground=CARD,
            activeforeground=TEXT,
            selectcolor=CARD,
            font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(12, 0))
        tk.Label(
            card,
            text="Recommended: OpenRouter + quality_max for best quality, with Groq as failover for speed.",
            font=("Segoe UI", 9),
            bg=CARD,
            fg=MUTED,
            wraplength=780,
            justify="left",
        ).pack(anchor="w", pady=(8, 0))
        bar = tk.Frame(card, bg=CARD)
        bar.pack(fill="x", pady=(14, 0))
        self._button(bar, "Save Settings", ACCENT, BG, self._save_settings)

    def _show_page(self, name: str):
        self.page.set(name)
        self.page_title.config(text=name)
        for key, btn in self.nav.items():
            btn.config(bg=CARD if key == name else SURFACE, fg=TEXT if key == name else MUTED)
        for frame in self.frames.values():
            frame.pack_forget()
        self.frames[name].pack(fill="both", expand=True)
        if name == "Projects":
            self._refresh_projects()

    def _generate_current(self):
        self._generate_named(self.project_name.get(), self.mode.get(), self.prompt_box.get("1.0", "end").strip())

    def _generate_named(self, name: str, mode: str, prompt: str):
        if self._generation_running:
            messagebox.showinfo("Apex", "Generation is already in progress. Please wait.")
            return
        if not prompt:
            messagebox.showerror("Apex", "Please enter a prompt first.")
            return
        slug = self._slug(name)
        out = Path(self.output_dir.get().strip() or DEFAULT_OUT)
        out.mkdir(parents=True, exist_ok=True)
        cloud_provider = self.cloud_provider.get()
        cloud_profile = self.cloud_profile.get()
        openrouter_key = self.openrouter_key.get()
        groq_key = self.api_key.get()
        cloud_enhance = bool(self.cloud_enhance.get())
        self._set_generation_state(True)
        self._log(f"Starting generation: {slug} ({mode})")

        def worker():
            try:
                project = self._generate_workspace_worker(
                    slug=slug,
                    mode=mode,
                    prompt=prompt,
                    out=out,
                    cloud_provider=cloud_provider,
                    cloud_profile=cloud_profile,
                    openrouter_key=openrouter_key,
                    groq_key=groq_key,
                    cloud_enhance=cloud_enhance,
                )
                self.root.after(0, lambda: self._on_generation_success(slug, mode, prompt, project))
            except Exception as exc:
                self.root.after(0, lambda: self._on_generation_error(str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _generate_workspace_worker(
        self,
        slug: str,
        mode: str,
        prompt: str,
        out: Path,
        cloud_provider: str,
        cloud_profile: str,
        openrouter_key: str,
        groq_key: str,
        cloud_enhance: bool,
    ) -> Path:
        project = out / slug
        project.mkdir(parents=True, exist_ok=True)
        files = self._files_for(slug, mode, prompt)
        for rel, content in files.items():
            path = project / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        elite_files = generate_elite_artifacts(
            project_path=project,
            mode=mode,
            prompt=prompt,
            cloud_provider=cloud_provider,
            cloud_profile=cloud_profile,
        )
        for rel, content in elite_files.items():
            path = project / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        self._log("Elite artifacts written: manifest, integration matrix, skills bundle, doctor report.")
        pipeline_files = run_elite_pipeline(
            project_path=project,
            mode=mode,
            prompt=prompt,
            cloud_provider=cloud_provider,
            cloud_profile=cloud_profile,
            openrouter_key=openrouter_key,
            groq_key=groq_key,
        )
        for rel, content in pipeline_files.items():
            path = project / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        self._log("Elite pipeline completed: plan, review, release checklist, doctor, task board.")
        if cloud_enhance:
            self._cloud_enhance_workspace_with_config(
                project=project,
                mode=mode,
                prompt=prompt,
                cloud_profile=cloud_profile,
                cloud_provider=cloud_provider,
                openrouter_key=openrouter_key,
                groq_key=groq_key,
            )
        return project

    def _on_generation_success(self, slug: str, mode: str, prompt: str, project: Path):
        record = ProjectRecord(slug, mode, prompt, str(project), datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        self.projects = [p for p in self.projects if p.path != record.path] + [record]
        self._save_state()
        self._refresh_projects()
        self._log(f"Generated {mode} workspace at {project}")
        self._set_generation_state(False)
        self._show_page("Projects")
        messagebox.showinfo("Apex", f"Workspace generated:\n{project}")

    def _on_generation_error(self, message: str):
        self._log(f"Generation failed: {message}")
        self._set_generation_state(False)
        messagebox.showerror("Apex", f"Generation failed:\n{message}")

    def _set_generation_state(self, running: bool):
        self._generation_running = running
        if self.generate_btn is not None:
            self.generate_btn.config(state="disabled" if running else "normal")
            self.generate_btn.config(text="Generating..." if running else "Generate Workspace")
        self.root.config(cursor="watch" if running else "")

    def _files_for(self, name: str, mode: str, prompt: str):
        summary = " ".join(prompt.split())
        if len(summary) > 160:
            summary = summary[:157] + "..."
        if mode == "Hackathon Pack":
            return {
                "README.md": f"# {name}\n\n## Prompt\n{prompt}\n\n## Included\n- docs/problem.md\n- docs/mvp.md\n- docs/timeline.md\n- docs/pitch.md\n- docs/demo.md\n",
                "docs/problem.md": f"# Problem\n\n{summary}\n",
                "docs/mvp.md": "# MVP\n\n- One memorable core flow\n- One visible outcome\n- One polished demo path\n",
                "docs/timeline.md": "# Timeline\n\n## Hour 0-2\n- Lock scope\n\n## Hour 2-8\n- Build end to end\n\n## Hour 8-16\n- Polish and refine\n\n## Hour 16-24\n- Demo practice and bug fixes\n",
                "docs/pitch.md": "# Pitch\n\nState the problem, show the product, prove the impact.\n",
                "docs/demo.md": "# Demo\n\n- Open the app\n- Show the core flow\n- End with the outcome and next step\n",
            }
        if mode == "CTF Lab":
            return {
                "README.md": f"# {name}\n\nLegal educational CTF workspace only.\n\n## Prompt\n{prompt}\n",
                "notes/challenge-notes.md": f"# Challenge Notes\n\n{prompt}\n",
                "notes/checklist.md": "# Checklist\n\n- Confirm category\n- Keep notes\n- Test hypotheses safely\n- Stay inside the official CTF environment\n",
                "notes/findings.md": "# Findings\n\n- Theory:\n- Commands tried:\n- Result:\n",
                "tools/decode_helpers.py": "import base64\n\n\ndef from_hex(value: str) -> bytes:\n    return bytes.fromhex(value.strip())\n\n\ndef from_base64(value: str) -> bytes:\n    return base64.b64decode(value.strip())\n\n\nif __name__ == '__main__':\n    print(from_hex('48656c6c6f').decode('utf-8'))\n",
            }
        return {
            "README.md": f"# {name}\n\n## Prompt\n{prompt}\n\n## Included\n- `web/index.html`: Claude/Gravity-inspired workspace UI\n- `web/styles.css`: premium visual system + responsive layout\n- `web/app.js`: interactions (chat feed, command palette, task flow)\n- `notes/plan.md`: execution blueprint\n- `docs/elite-manifest.json`: model/integration/skill snapshot\n- `docs/integration-matrix.md`: detected integrations + packages\n- `docs/skill-bundle.md`: selected skills from full local library\n- `docs/doctor-report.md`: runtime health report\n- `docs/catalog-integrations.md`: full integrations catalog\n- `docs/catalog-skills.md`: full skills catalog\n- `docs/elite/*`: autonomous plan/review/release/doctor/task-board artifacts\n- `tools/elite_runtime_runner.py`: local autonomous runtime pass\n- `scripts/start_elite.bat`: one-command local startup\n- `scripts/doctor.bat`: health checks\n- `scripts/run_agent.bat`: execute autonomous runtime pass\n- `scripts/ship_check.bat`: release-quality quick audit\n- `scripts/run_full_cycle.bat`: doctor + agent + ship check chain\n\n## Run\n```powershell\nscripts\\run_full_cycle.bat\n```\nThen open http://localhost:5173\n",
            "notes/plan.md": f"# Plan\n\n{summary}\n\n## Objective\nDeliver an elite personal dev workspace with strong UX, fast command flow, and execution tracking.\n",
            "notes/commands.md": "# Command ideas\n\n- /plan: create implementation strategy\n- /build: scaffold next module\n- /review: code quality pass\n- /ship: release checklist\n",
            "web/index.html": f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{name}</title>
  <link rel="stylesheet" href="./styles.css" />
</head>
<body>
  <div class="bg-glow"></div>
  <header class="topbar">
    <div class="brand">
      <span class="dot"></span>
      <h1>{name}</h1>
      <p>Elite local dev workspace</p>
    </div>
    <div class="top-actions">
      <button id="runPlanBtn">Run Plan</button>
      <button id="openPaletteBtn" class="accent">Command Palette</button>
    </div>
  </header>

  <main class="layout">
    <aside class="sidebar">
      <section>
        <h2>Project</h2>
        <ul>
          <li class="active">workspace/</li>
          <li>web/</li>
          <li>api/</li>
          <li>tests/</li>
          <li>docs/</li>
        </ul>
      </section>
      <section>
        <h2>Stacks</h2>
        <div class="chips">
          <span>Frontend</span>
          <span>Backend</span>
          <span>Agent Ops</span>
          <span>CI/CD</span>
        </div>
      </section>
      <section>
        <h2>Prompt</h2>
        <p>{summary}</p>
      </section>
    </aside>

    <section class="center">
      <div class="panel heading">
        <h2>Mission Control</h2>
        <p>Command-first workflow inspired by top AI dev tools.</p>
      </div>

      <div class="grid">
        <article class="panel">
          <h3>Execution Plan</h3>
          <ol id="planList">
            <li>Define architecture and modules</li>
            <li>Ship first vertical slice</li>
            <li>Set up test and review loop</li>
            <li>Polish UX and deployment</li>
          </ol>
        </article>
        <article class="panel">
          <h3>Tasks</h3>
          <div id="tasks" class="tasks">
            <label><input type="checkbox" /> Build auth and session flow</label>
            <label><input type="checkbox" /> Add API contracts and validation</label>
            <label><input type="checkbox" /> Implement core command bus</label>
            <label><input type="checkbox" /> Add observability dashboard</label>
          </div>
        </article>
      </div>

      <article class="panel log-panel">
        <h3>Operator Feed</h3>
        <div id="feed" class="feed"></div>
      </article>
      <article class="panel">
        <h3>Quality Gates</h3>
        <ul id="qualityGates" class="quality-gates">
          <li>Doctor report present</li>
          <li>Plan and review artifacts generated</li>
          <li>Release checklist generated</li>
          <li>Runtime report available</li>
        </ul>
      </article>
      <article class="panel workbench">
        <h3>Workspace Editor</h3>
        <p>Connect a local folder (Chromium-based browsers) to browse, edit, save, and revert files.</p>
        <div class="workbench-actions">
          <button id="connectWorkspaceBtn">Connect Folder</button>
          <button id="refreshFilesBtn">Refresh</button>
          <button id="saveFileBtn" class="accent-action">Save File</button>
          <button id="revertFileBtn">Revert</button>
        </div>
        <div class="workbench-layout">
          <ul id="fileList" class="file-list"></ul>
          <textarea id="fileEditor" class="file-editor" spellcheck="false"></textarea>
        </div>
      </article>
    </section>

    <aside class="assistant">
      <div class="panel chat">
        <h3>Agent Console</h3>
        <div id="chatBox" class="chat-box"></div>
        <form id="chatForm" class="chat-form">
          <input id="chatInput" placeholder="Ask your agent to plan, build, or review..." />
          <button type="submit">Send</button>
        </form>
      </div>
      <div class="panel terminal">
        <h3>Terminal</h3>
        <pre id="terminalLog">$ Ready
$ Local mode active
$ Cloud enhancement available</pre>
      </div>
    </aside>
  </main>

  <div id="palette" class="palette hidden">
    <div class="palette-box">
      <input id="paletteInput" placeholder="Type command: /plan /build /review /ship" />
      <ul id="paletteSuggestions">
        <li>/plan - Generate architecture plan</li>
        <li>/build - Scaffold next feature</li>
        <li>/review - Run quality audit</li>
        <li>/ship - Build release checklist</li>
      </ul>
    </div>
  </div>

  <script>window.APP_PROMPT = {prompt!r};</script>
  <script src="./app.js"></script>
</body>
</html>
""",
            "web/styles.css": """:root {
  --bg: #080b12;
  --surface: #121827;
  --surface-2: #1a2234;
  --line: #2e3a54;
  --text: #f4f7ff;
  --muted: #9aa9c7;
  --accent: #9de56d;
  --accent-2: #69b7ff;
  --danger: #ff7b88;
}
* { box-sizing: border-box; }
html, body { margin: 0; height: 100%; font-family: "Segoe UI", "SF Pro Display", sans-serif; background: var(--bg); color: var(--text); }
.bg-glow {
  position: fixed; inset: -20%;
  background: radial-gradient(circle at 15% 20%, rgba(105,183,255,.2), transparent 35%),
              radial-gradient(circle at 80% 10%, rgba(157,229,109,.17), transparent 35%),
              radial-gradient(circle at 50% 90%, rgba(122,128,255,.15), transparent 45%);
  pointer-events: none;
}
.topbar {
  display: flex; justify-content: space-between; align-items: center;
  padding: 14px 20px; border-bottom: 1px solid var(--line);
  background: linear-gradient(180deg, rgba(18,24,39,.95), rgba(18,24,39,.7));
  position: sticky; top: 0; backdrop-filter: blur(8px); z-index: 5;
}
.brand { display: flex; gap: 10px; align-items: center; }
.brand h1 { font-size: 18px; margin: 0; letter-spacing: .4px; }
.brand p { margin: 0; color: var(--muted); font-size: 12px; }
.dot { width: 10px; height: 10px; border-radius: 999px; background: var(--accent); box-shadow: 0 0 14px rgba(157,229,109,.8); }
.top-actions button, .chat-form button {
  border: 1px solid var(--line); background: var(--surface-2); color: var(--text);
  border-radius: 10px; padding: 10px 14px; font-weight: 600; cursor: pointer;
}
.top-actions .accent { background: linear-gradient(120deg, #9de56d, #87ce5c); color: #0d111a; border-color: #9de56d; }
.layout {
  display: grid; grid-template-columns: 260px 1fr 360px; gap: 12px;
  padding: 14px; min-height: calc(100vh - 69px);
}
.sidebar, .assistant { display: flex; flex-direction: column; gap: 12px; }
.sidebar section {
  background: rgba(18,24,39,.88); border: 1px solid var(--line); border-radius: 14px; padding: 12px;
}
h2, h3 { margin: 0 0 10px 0; }
.sidebar ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 6px; color: var(--muted); }
.sidebar li.active { color: var(--text); font-weight: 700; }
.chips { display: flex; flex-wrap: wrap; gap: 7px; }
.chips span { background: rgba(105,183,255,.15); border: 1px solid rgba(105,183,255,.35); color: #cde6ff; border-radius: 999px; padding: 4px 10px; font-size: 12px; }
.center { display: flex; flex-direction: column; gap: 12px; }
.panel {
  background: rgba(18,24,39,.88); border: 1px solid var(--line); border-radius: 14px; padding: 14px;
  box-shadow: 0 10px 28px rgba(0,0,0,.25);
}
.panel.heading p { color: var(--muted); margin: 0; }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
ol { margin: 0; padding-left: 18px; color: var(--muted); display: grid; gap: 8px; }
.tasks { display: grid; gap: 8px; color: var(--muted); }
.feed { max-height: 210px; overflow: auto; display: grid; gap: 8px; font-family: "Consolas", monospace; font-size: 13px; color: #d5def0; }
.feed div { padding: 8px 10px; border-radius: 10px; background: rgba(24,31,48,.85); border: 1px solid rgba(82,102,139,.4); }
.quality-gates { margin: 0; padding-left: 18px; display: grid; gap: 8px; color: var(--muted); }
.quality-gates li.ok { color: #9de56d; }
.workbench p { margin: 0 0 10px 0; color: var(--muted); }
.workbench-actions { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
.workbench-actions button {
  border: 1px solid var(--line);
  background: #172039;
  color: var(--text);
  border-radius: 10px;
  padding: 8px 12px;
  cursor: pointer;
  font-weight: 600;
}
.workbench-actions .accent-action {
  background: linear-gradient(120deg, #9de56d, #87ce5c);
  color: #0f1524;
  border-color: #9de56d;
}
.workbench-layout {
  display: grid;
  grid-template-columns: 260px 1fr;
  gap: 10px;
}
.file-list {
  margin: 0;
  padding: 8px;
  list-style: none;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: #0b1327;
  max-height: 300px;
  overflow: auto;
  display: grid;
  gap: 4px;
}
.file-list li {
  padding: 6px 8px;
  border-radius: 8px;
  cursor: pointer;
  color: #c8d6f4;
}
.file-list li:hover { background: rgba(105, 183, 255, 0.14); }
.file-list li.active { background: rgba(157, 229, 109, 0.2); color: #effbdc; }
.file-editor {
  width: 100%;
  min-height: 300px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: #0b1327;
  color: #d7e4ff;
  padding: 10px;
  font-family: "Consolas", monospace;
  resize: vertical;
}
.chat-box {
  min-height: 240px; max-height: 320px; overflow: auto;
  border: 1px solid var(--line); border-radius: 10px; padding: 10px;
  background: rgba(12,17,29,.9); display: grid; gap: 10px;
}
.chat-msg { padding: 8px 10px; border-radius: 10px; line-height: 1.4; }
.chat-msg.user { background: rgba(105,183,255,.16); border: 1px solid rgba(105,183,255,.32); }
.chat-msg.ai { background: rgba(157,229,109,.14); border: 1px solid rgba(157,229,109,.3); }
.chat-form { margin-top: 10px; display: flex; gap: 8px; }
.chat-form input {
  flex: 1; border: 1px solid var(--line); border-radius: 10px; background: #0e1422; color: var(--text);
  padding: 10px;
}
.terminal pre {
  margin: 0; border-radius: 10px; border: 1px solid var(--line);
  background: #0a111f; color: #bbcdf1; padding: 12px; min-height: 150px; overflow: auto;
}
.palette {
  position: fixed; inset: 0; background: rgba(3,6,10,.6); display: grid; place-items: center; z-index: 10;
}
.palette.hidden { display: none; }
.palette-box {
  width: min(720px, 92vw); background: #0f1626; border: 1px solid var(--line);
  border-radius: 14px; padding: 14px; box-shadow: 0 24px 60px rgba(0,0,0,.55);
}
.palette-box input {
  width: 100%; padding: 12px; border-radius: 10px; border: 1px solid var(--line);
  background: #0a111f; color: var(--text);
}
#paletteSuggestions { margin: 10px 0 0; padding: 0; list-style: none; color: var(--muted); display: grid; gap: 7px; }
@media (max-width: 1180px) {
  .layout { grid-template-columns: 1fr; }
  .assistant { order: 3; }
  .sidebar { order: 2; }
  .workbench-layout { grid-template-columns: 1fr; }
}
""",
            "web/app.js": """const feed = document.getElementById("feed");
const chatBox = document.getElementById("chatBox");
const chatForm = document.getElementById("chatForm");
const chatInput = document.getElementById("chatInput");
const tasks = document.getElementById("tasks");
const planList = document.getElementById("planList");
const qualityGates = document.getElementById("qualityGates");
const runPlanBtn = document.getElementById("runPlanBtn");
const openPaletteBtn = document.getElementById("openPaletteBtn");
const palette = document.getElementById("palette");
const paletteInput = document.getElementById("paletteInput");
const terminalLog = document.getElementById("terminalLog");
const connectWorkspaceBtn = document.getElementById("connectWorkspaceBtn");
const refreshFilesBtn = document.getElementById("refreshFilesBtn");
const saveFileBtn = document.getElementById("saveFileBtn");
const revertFileBtn = document.getElementById("revertFileBtn");
const fileList = document.getElementById("fileList");
const fileEditor = document.getElementById("fileEditor");

let workspaceHandle = null;
let currentFilePath = "";
let currentFileHandle = null;
let backupCache = {};

function addFeed(message) {
  const item = document.createElement("div");
  item.textContent = message;
  feed.prepend(item);
}

function addChat(role, text) {
  const msg = document.createElement("div");
  msg.className = `chat-msg ${role}`;
  msg.textContent = text;
  chatBox.appendChild(msg);
  chatBox.scrollTop = chatBox.scrollHeight;
}

function normalizePath(parts) {
  return parts.join("/");
}

function rememberBackup(path, content) {
  backupCache[path] = content;
  localStorage.setItem("elite_workbench_backups", JSON.stringify(backupCache));
}

function loadBackups() {
  try {
    backupCache = JSON.parse(localStorage.getItem("elite_workbench_backups") || "{}");
  } catch (_) {
    backupCache = {};
  }
}

async function listFilesRecursive(dirHandle, prefix = []) {
  const out = [];
  for await (const [name, handle] of dirHandle.entries()) {
    if (name.startsWith(".")) continue;
    if (handle.kind === "directory") {
      if (["node_modules", "__pycache__", ".git"].includes(name)) continue;
      out.push(...(await listFilesRecursive(handle, [...prefix, name])));
    } else {
      const rel = normalizePath([...prefix, name]);
      if (rel.length < 140) out.push({ rel, handle });
    }
  }
  return out;
}

function renderFileList(files) {
  fileList.innerHTML = "";
  files.sort((a, b) => a.rel.localeCompare(b.rel));
  files.forEach((file) => {
    const li = document.createElement("li");
    li.textContent = file.rel;
    li.addEventListener("click", async () => {
      currentFilePath = file.rel;
      currentFileHandle = file.handle;
      document.querySelectorAll("#fileList li").forEach((x) => x.classList.remove("active"));
      li.classList.add("active");
      const f = await file.handle.getFile();
      const content = await f.text();
      fileEditor.value = content;
      addFeed("Opened file: " + file.rel);
      terminalLog.textContent += "\\n$ open " + file.rel;
    });
    fileList.appendChild(li);
  });
}

async function connectWorkspace() {
  if (!window.showDirectoryPicker) {
    addFeed("Folder picker unsupported in this browser. Use Edge/Chrome.");
    return;
  }
  try {
    workspaceHandle = await window.showDirectoryPicker();
    addFeed("Connected workspace folder.");
    terminalLog.textContent += "\\n$ workspace connected";
    await refreshFiles();
  } catch (err) {
    addFeed("Workspace connect canceled.");
  }
}

async function refreshFiles() {
  if (!workspaceHandle) {
    addFeed("Connect a folder first.");
    return;
  }
  const files = await listFilesRecursive(workspaceHandle);
  renderFileList(files.slice(0, 400));
  addFeed("Loaded files: " + files.length);
  terminalLog.textContent += "\\n$ files indexed " + files.length;
}

async function saveCurrentFile() {
  if (!currentFileHandle || !currentFilePath) {
    addFeed("No file selected.");
    return;
  }
  try {
    const originalFile = await currentFileHandle.getFile();
    const original = await originalFile.text();
    if (!(currentFilePath in backupCache)) {
      rememberBackup(currentFilePath, original);
    }
    const writable = await currentFileHandle.createWritable();
    await writable.write(fileEditor.value);
    await writable.close();
    addFeed("Saved file: " + currentFilePath);
    terminalLog.textContent += "\\n$ save " + currentFilePath;
  } catch (err) {
    addFeed("Save failed: " + err.message);
  }
}

async function revertCurrentFile() {
  if (!currentFileHandle || !currentFilePath) {
    addFeed("No file selected.");
    return;
  }
  if (!(currentFilePath in backupCache)) {
    addFeed("No backup snapshot for selected file.");
    return;
  }
  try {
    const writable = await currentFileHandle.createWritable();
    await writable.write(backupCache[currentFilePath]);
    await writable.close();
    fileEditor.value = backupCache[currentFilePath];
    addFeed("Reverted file from backup: " + currentFilePath);
    terminalLog.textContent += "\\n$ revert " + currentFilePath;
  } catch (err) {
    addFeed("Revert failed: " + err.message);
  }
}

async function loadJson(path) {
  try {
    const res = await fetch(path);
    if (!res.ok) return null;
    return await res.json();
  } catch (_) {
    return null;
  }
}

async function hydrateFromEliteFiles() {
  const board = await loadJson("../docs/elite/task-board.json");
  const meta = await loadJson("../docs/elite/meta.json");
  const manifest = await loadJson("../docs/elite-manifest.json");
  const commandCenter = await loadJson("../docs/elite/command-center.json");
  if (board && board.lanes && Array.isArray(board.lanes.todo)) {
    tasks.innerHTML = "";
    board.lanes.todo.slice(0, 8).forEach((item) => {
      const label = document.createElement("label");
      label.innerHTML = `<input type="checkbox" /> ${item}`;
      tasks.appendChild(label);
    });
    addFeed("Loaded elite task-board from docs/elite/task-board.json");
  }
  if (meta && meta.cloud) {
    terminalLog.textContent += `\\n$ cloud provider preference: ${meta.cloud.provider_preference || "n/a"}`;
    terminalLog.textContent += `\\n$ cloud profile: ${meta.cloud.profile || "n/a"}`;
    addFeed("Loaded elite meta information.");
  }
  if (commandCenter && Array.isArray(commandCenter.commands)) {
    commandCenter.commands.forEach((item) => addFeed(`Command mapped: ${item.name} -> ${item.action}`));
  }
  if (manifest && manifest.counts) {
    addFeed(
      `Manifest: integrations=${manifest.counts.all_integrations_available}, skills=${manifest.counts.all_skills_available}`
    );
    terminalLog.textContent += `\\n$ detected integrations: ${manifest.counts.detected_integrations}`;
    terminalLog.textContent += `\\n$ selected skills: ${manifest.counts.selected_skills}`;
  }
  const doctor = await fetch("../docs/elite/doctor.md").then((r) => (r.ok ? r.text() : ""));
  if (doctor && doctor.includes("Health Score")) {
    const scoreLine = doctor.split("\\n").find((line) => line.includes("Health Score"));
    if (scoreLine) {
      terminalLog.textContent += `\\n$ ${scoreLine.replace("- ", "")}`;
      addFeed("Doctor score imported into terminal view.");
    }
  }
  const runtime = await loadJson("../docs/elite/runtime-report.json");
  if (runtime && runtime.validation) {
    addFeed("Runtime report detected.");
  }
  if (qualityGates) {
    const gates = Array.from(qualityGates.querySelectorAll("li"));
    const flags = [
      Boolean(doctor),
      Boolean(board),
      Boolean(meta),
      Boolean(runtime),
    ];
    gates.forEach((li, idx) => {
      if (flags[idx]) li.classList.add("ok");
    });
  }
}

function aiReply(text) {
  const lower = text.toLowerCase();
  if (lower.includes("plan")) {
    return "Plan mode: architecture, milestones, and risk map are now queued.";
  }
  if (lower.includes("build")) {
    return "Build mode: next feature scaffold and API contract tasks are prepared.";
  }
  if (lower.includes("review")) {
    return "Review mode: quality gates include test depth, security checks, and DX polish.";
  }
  if (lower.includes("ship")) {
    return "Ship mode: release checklist generated with smoke test and rollback notes.";
  }
  return "Agent ready. Try asking for /plan, /build, /review, or /ship for focused execution.";
}

addFeed("Workspace initialized.");
addFeed("Prompt loaded into mission context.");
addChat("ai", "Agent online. Describe your goal and I will map execution steps.");
terminalLog.textContent += "\\n$ Prompt: " + (window.APP_PROMPT || "n/a");
loadBackups();
hydrateFromEliteFiles();

chatForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const value = chatInput.value.trim();
  if (!value) return;
  addChat("user", value);
  const reply = aiReply(value);
  addChat("ai", reply);
  addFeed("Agent: " + reply);
  chatInput.value = "";
});

runPlanBtn.addEventListener("click", () => {
  addFeed("Execution plan started.");
  terminalLog.textContent += "\\n$ scripts\\\\run_agent.bat";
  const li = document.createElement("li");
  li.textContent = "Run autonomous plan/build/review/ship cycle";
  planList.appendChild(li);
});
connectWorkspaceBtn.addEventListener("click", connectWorkspace);
refreshFilesBtn.addEventListener("click", refreshFiles);
saveFileBtn.addEventListener("click", saveCurrentFile);
revertFileBtn.addEventListener("click", revertCurrentFile);

function openPalette() {
  palette.classList.remove("hidden");
  paletteInput.focus();
}

function closePalette() {
  palette.classList.add("hidden");
}

openPaletteBtn.addEventListener("click", openPalette);
window.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
    event.preventDefault();
    openPalette();
  }
  if (event.key === "Escape") {
    closePalette();
  }
});
palette.addEventListener("click", (event) => {
  if (event.target === palette) closePalette();
});
paletteInput.addEventListener("keydown", (event) => {
  if (event.key !== "Enter") return;
  const command = paletteInput.value.trim();
  if (!command) return;
  addFeed("Command executed: " + command);
  terminalLog.textContent += "\\n$ " + command;
  paletteInput.value = "";
  closePalette();
});
""",
            "scripts/start_elite.bat": "@echo off\r\ncd /d %~dp0\\..\\web\r\npy -m http.server 5173\r\n",
            "scripts/doctor.bat": "@echo off\r\ncd /d %~dp0\\..\r\npy -m py_compile tools\\*.py app\\*.py 2>nul\r\necho Elite doctor quick check complete.\r\n",
            "scripts/run_agent.bat": "@echo off\r\ncd /d %~dp0\\..\r\npy tools\\elite_runtime_runner.py\r\n",
            "scripts/ship_check.bat": "@echo off\r\ncd /d %~dp0\\..\r\necho Running elite ship checks...\r\nif exist docs\\elite\\release-checklist.md (echo release checklist: found) else (echo release checklist: missing)\r\nif exist docs\\elite\\doctor.md (echo doctor report: found) else (echo doctor report: missing)\r\necho Done.\r\n",
            "scripts/run_full_cycle.bat": "@echo off\r\ncd /d %~dp0\\..\r\ncall scripts\\doctor.bat\r\ncall scripts\\run_agent.bat\r\ncall scripts\\ship_check.bat\r\necho Full elite cycle complete.\r\n",
            "scripts/verify_workspace.bat": "@echo off\r\ncd /d %~dp0\\..\r\nif exist docs\\elite\\plan.md (echo plan: ok) else (echo plan: missing)\r\nif exist docs\\elite\\review.md (echo review: ok) else (echo review: missing)\r\nif exist docs\\elite\\release-checklist.md (echo release: ok) else (echo release: missing)\r\nif exist docs\\elite\\doctor.md (echo doctor: ok) else (echo doctor: missing)\r\nif exist web\\app.js (echo web app: ok) else (echo web app: missing)\r\n",
            "tools/elite_runtime_runner.py": "import json\\nfrom datetime import datetime\\nfrom pathlib import Path\\n\\nROOT = Path(__file__).resolve().parents[1]\\nELITE = ROOT / 'docs' / 'elite'\\nELITE.mkdir(parents=True, exist_ok=True)\\n\\nreport = {\\n    'generated_at': datetime.now().isoformat(timespec='seconds'),\\n    'project': ROOT.name,\\n    'checks': {\\n        'plan_exists': (ELITE / 'plan.md').exists(),\\n        'review_exists': (ELITE / 'review.md').exists(),\\n        'release_exists': (ELITE / 'release-checklist.md').exists(),\\n        'doctor_exists': (ELITE / 'doctor.md').exists(),\\n    },\\n    'actions': [\\n        'Review docs/elite/plan.md',\\n        'Execute tasks from docs/elite/task-board.json',\\n        'Re-run ship checks before release',\\n    ],\\n}\\n(ELITE / 'runtime-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')\\nprint('Elite runtime report written to docs/elite/runtime-report.json')\\n",
            "run.bat": "@echo off\r\ncd web\r\npy -m http.server 5173\r\n",
        }

    def _refresh_projects(self):
        if self.apps_list is None:
            return
        self.apps_list.delete(0, "end")
        for item in reversed(self.projects):
            self.apps_list.insert("end", f"{item.name} [{item.mode}]")
        self._render_project()

    def _render_project(self):
        self.details.config(state="normal")
        self.details.delete("1.0", "end")
        item = self._selected_project()
        if not item:
            self.details.insert("1.0", "No workspace selected.")
        else:
            self.details.insert("1.0", f"Name: {item.name}\nMode: {item.mode}\nCreated: {item.created_at}\nPath: {item.path}\n\nPrompt:\n{item.prompt}")
        self.details.config(state="disabled")

    def _selected_project(self):
        if not self.projects:
            return None
        if not self.apps_list.curselection():
            return self.projects[-1]
        idx = len(self.projects) - 1 - self.apps_list.curselection()[0]
        return self.projects[idx]

    def _open_selected(self):
        item = self._selected_project()
        if item:
            self._open_path(Path(item.path))

    def _open_selected_readme(self):
        item = self._selected_project()
        if item:
            self._open_path(Path(item.path) / "README.md")

    def _open_path(self, path: Path):
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(path))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as exc:
            messagebox.showerror("Apex", f"Could not open path:\n{exc}")

    def _pick_output(self):
        chosen = filedialog.askdirectory(initialdir=self.output_dir.get() or str(DEFAULT_OUT))
        if chosen:
            self.output_dir.set(chosen)

    def _load_prompt(self, mode: str):
        self.mode.set(mode)
        self.prompt_box.delete("1.0", "end")
        if mode == "Elite Agent Run":
            self.project_name.set("elite-agent-workspace")
            self.prompt_box.insert(
                "1.0",
                "Build an elite software engineering workspace with autonomous plan/build/review/ship flow, integration matrix, skill bundles, quality gates, and release automation.",
            )
        elif mode == "Hackathon Pack":
            self.project_name.set("hackathon-studio")
            self.prompt_box.insert("1.0", "Build a hackathon workspace for an AI productivity project with a README, pitch, MVP scope, 24-hour timeline, and demo checklist.")
        elif mode == "CTF Lab":
            self.project_name.set("ctf-study-lab")
            self.prompt_box.insert("1.0", "Build an educational CTF workspace with notes, checklist, findings sheet, and a small decoding helper script for legal challenge boxes.")
        else:
            self.project_name.set("apex-workspace")
            self.prompt_box.insert(
                "1.0",
                "Build a local personal dev tool with a polished homepage, project workspace, and a simple way to plan coding tasks.",
            )

    def _save_settings(self):
        self.settings["output_dir"] = self.output_dir.get().strip()
        self.settings["groq_api_key"] = self.api_key.get().strip()
        self.settings["openrouter_api_key"] = self.openrouter_key.get().strip()
        self.settings["cloud_provider"] = self.cloud_provider.get().strip()
        self.settings["cloud_profile"] = self.cloud_profile.get().strip()
        self.settings["cloud_enhance"] = bool(self.cloud_enhance.get())
        SETTINGS_FILE.write_text(json.dumps(self.settings, indent=2), encoding="utf-8")
        self.status.set(cloud_status(self.openrouter_key.get(), self.api_key.get()))
        messagebox.showinfo("Apex", "Settings saved.")

    def _cloud_enhance_workspace(self, project: Path, mode: str, prompt: str):
        self._cloud_enhance_workspace_with_config(
            project=project,
            mode=mode,
            prompt=prompt,
            cloud_profile=self.cloud_profile.get(),
            cloud_provider=self.cloud_provider.get(),
            openrouter_key=self.openrouter_key.get(),
            groq_key=self.api_key.get(),
        )

    def _cloud_enhance_workspace_with_config(
        self,
        project: Path,
        mode: str,
        prompt: str,
        cloud_profile: str,
        cloud_provider: str,
        openrouter_key: str,
        groq_key: str,
    ):
        if not openrouter_key.strip() and not groq_key.strip():
            self._log("Cloud enhancement skipped: no cloud API key configured.")
            return
        cloud_prompt, system_prompt, out_file = self._build_cloud_prompt(mode, prompt)
        self._log(
            f"Cloud enhancement: profile={cloud_profile} provider={cloud_provider}."
        )
        result = generate_cloud_text(
            prompt=cloud_prompt,
            profile=cloud_profile,
            provider_preference=cloud_provider,
            openrouter_key=openrouter_key,
            groq_key=groq_key,
            system_prompt=system_prompt,
        )
        if result.get("ok") != "1":
            self._log(f"Cloud enhancement failed: {result.get('error', 'unknown error')}")
            return
        target = project / out_file
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(result["text"], encoding="utf-8")
        meta = project / "cloud" / "meta.txt"
        meta.parent.mkdir(parents=True, exist_ok=True)
        meta.write_text(
            f"provider={result.get('provider', '')}\nmodel={result.get('model', '')}\nprofile={cloud_profile}\n",
            encoding="utf-8",
        )
        self._log(
            f"Cloud enhancement saved using {result.get('provider')} ({result.get('model')})."
        )

    def _build_cloud_prompt(self, mode: str, prompt: str):
        if mode == "Hackathon Pack":
            return (
                f"""Create a detailed hackathon execution brief from this prompt:
{prompt}

Format:
1. Problem framing
2. Differentiated product strategy
3. Technical architecture
4. MVP scope with acceptance criteria
5. 24-hour execution timeline by blocks
6. 2-minute judge pitch
7. Demo script
8. Risk checklist and mitigation
""",
                "You are a principal engineer and hackathon mentor. Be specific and execution-focused.",
                "docs/cloud-hackathon-brief.md",
            )
        if mode == "CTF Lab":
            return (
                f"""Create a legal CTF learning strategy from this prompt:
{prompt}

Rules:
- Educational sandbox use only
- No real-world target exploitation guidance

Format:
1. Challenge triage workflow
2. Safe analysis checklist
3. Category-specific playbook (crypto/web/forensics/reversing)
4. Note-taking structure for flags and proofs
5. Timeboxing strategy under pressure
6. Post-challenge learning review
""",
                "You are a CTF coach focused on legal educational environments and safe practice.",
                "notes/cloud-ctf-strategy.md",
            )
        return (
            f"""Design an implementation plan for this dev-tool idea:
{prompt}

Output:
1. Product scope and user stories
2. Architecture and modules
3. Suggested file tree
4. Milestone plan (M1/M2/M3)
5. Test strategy
6. Technical risks and mitigations
7. Next 10 development tasks
""",
            "You are a senior software architect producing practical implementation plans.",
            "notes/cloud-implementation-plan.md",
        )

    def _save_state(self):
        STATE_FILE.write_text(json.dumps({"projects": [asdict(p) for p in self.projects]}, indent=2), encoding="utf-8")

    def _load_json(self, path: Path, default):
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default

    def _slug(self, text: str):
        value = re.sub(r"[^a-zA-Z0-9-_]+", "-", text.strip().lower()).strip("-")
        return value or f"workspace-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    def _card(self, parent):
        return tk.Frame(parent, bg=CARD, highlightbackground=BORDER, highlightthickness=1, padx=18, pady=18)

    def _label(self, parent, text: str):
        tk.Label(parent, text=text, font=("Segoe UI Semibold", 10), bg=CARD, fg=TEXT).pack(anchor="w", pady=(12, 6))

    def _button(self, parent, text, bg, fg, command):
        btn = tk.Button(parent, text=text, font=("Segoe UI Semibold", 10), bg=bg, fg=fg, relief="flat", bd=0, padx=14, pady=10, cursor="hand2", command=command)
        btn.pack(side="left", padx=(0, 10))
        return btn

    def _log(self, text: str):
        if self.log_box is None:
            return
        def append():
            self.log_box.config(state="normal")
            self.log_box.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] {text}\n")
            self.log_box.see("end")
            self.log_box.config(state="disabled")
        self.root.after(0, append)


def main():
    root = tk.Tk()
    ApexDesktop(root)
    root.mainloop()


if __name__ == "__main__":
    main()
