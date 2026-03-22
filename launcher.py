# launcher.py — APEX Engine Desktop UI
# Run: py launcher.py

import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog
import subprocess
import threading
import os
import sys
from pathlib import Path

# ── Theme Colors ──────────────────────────────────────────────────
BG        = "#0a0a0a"
SURFACE   = "#111111"
SURFACE2  = "#1a1a1a"
BORDER    = "#2a2a2a"
ACCENT    = "#f0c040"
TEXT      = "#f0ede8"
TEXT2     = "#888888"
GREEN     = "#34d399"
RED       = "#f87171"
FONT_MAIN = ("Segoe UI", 10)
FONT_MONO = ("Consolas", 9)
FONT_BIG  = ("Segoe UI", 12, "bold")
FONT_TITLE= ("Segoe UI", 16, "bold")


class ApexLauncher:
    def __init__(self, root):
        self.root = root
        self.root.title("APEX AI Dev Engine")
        self.root.configure(bg=BG)
        self.root.geometry("900x680")
        self.root.minsize(800, 600)
        self.running = False
        self.process = None
        self._build_ui()

    def _build_ui(self):
        # ── Header ────────────────────────────────────────────────
        header = tk.Frame(self.root, bg=SURFACE, pady=14)
        header.pack(fill="x")
        tk.Label(header, text="⬡  APEX", font=("Segoe UI", 18, "bold"),
                 bg=SURFACE, fg=ACCENT).pack(side="left", padx=20)
        tk.Label(header, text="AI Dev Engine  v2.0",
                 font=FONT_MAIN, bg=SURFACE, fg=TEXT2).pack(side="left")
        self.status_dot = tk.Label(header, text="●", font=("Segoe UI", 14),
                                   bg=SURFACE, fg=GREEN)
        self.status_dot.pack(side="right", padx=10)
        self.status_label = tk.Label(header, text="Ready",
                                     font=FONT_MAIN, bg=SURFACE, fg=TEXT2)
        self.status_label.pack(side="right")

        # ── Main content ──────────────────────────────────────────
        content = tk.Frame(self.root, bg=BG)
        content.pack(fill="both", expand=True, padx=16, pady=12)

        # Left panel — controls
        left = tk.Frame(content, bg=BG, width=320)
        left.pack(side="left", fill="y", padx=(0, 12))
        left.pack_propagate(False)

        # App idea
        tk.Label(left, text="APP IDEA", font=("Segoe UI", 8, "bold"),
                 bg=BG, fg=TEXT2).pack(anchor="w", pady=(0, 4))
        self.idea_text = scrolledtext.ScrolledText(
            left, height=5, wrap="word",
            bg=SURFACE2, fg=TEXT, font=FONT_MAIN,
            insertbackground=ACCENT, relief="flat",
            borderwidth=1, highlightthickness=1,
            highlightcolor=ACCENT, highlightbackground=BORDER)
        self.idea_text.pack(fill="x")
        self.idea_text.insert("1.0", "Build a task manager with React and Flask")

        # Project name
        tk.Label(left, text="PROJECT NAME", font=("Segoe UI", 8, "bold"),
                 bg=BG, fg=TEXT2).pack(anchor="w", pady=(14, 4))
        self.name_var = tk.StringVar(value="my_app")
        name_entry = tk.Entry(left, textvariable=self.name_var,
                              bg=SURFACE2, fg=TEXT, font=FONT_MAIN,
                              insertbackground=ACCENT, relief="flat",
                              borderwidth=1, highlightthickness=1,
                              highlightcolor=ACCENT, highlightbackground=BORDER)
        name_entry.pack(fill="x", ipady=6)

        # Output folder
        tk.Label(left, text="OUTPUT FOLDER", font=("Segoe UI", 8, "bold"),
                 bg=BG, fg=TEXT2).pack(anchor="w", pady=(14, 4))
        folder_frame = tk.Frame(left, bg=BG)
        folder_frame.pack(fill="x")
        self.folder_var = tk.StringVar(value=str(Path.home() / "Desktop"))
        folder_entry = tk.Entry(folder_frame, textvariable=self.folder_var,
                                bg=SURFACE2, fg=TEXT, font=FONT_MAIN,
                                insertbackground=ACCENT, relief="flat",
                                borderwidth=1, highlightthickness=1,
                                highlightcolor=ACCENT, highlightbackground=BORDER)
        folder_entry.pack(side="left", fill="x", expand=True, ipady=6)
        tk.Button(folder_frame, text="...", bg=SURFACE2, fg=TEXT2,
                  font=FONT_MAIN, relief="flat", cursor="hand2",
                  command=self._browse_folder).pack(side="right", padx=(4, 0), ipady=6, ipadx=8)

        # Provider
        tk.Label(left, text="PROVIDER", font=("Segoe UI", 8, "bold"),
                 bg=BG, fg=TEXT2).pack(anchor="w", pady=(14, 4))
        self.provider_var = tk.StringVar(value="groq")
        prov_frame = tk.Frame(left, bg=BG)
        prov_frame.pack(fill="x")
        for p in ["groq", "ollama"]:
            tk.Radiobutton(prov_frame, text=p.upper(), variable=self.provider_var,
                           value=p, bg=BG, fg=TEXT2, selectcolor=SURFACE2,
                           activebackground=BG, activeforeground=TEXT,
                           font=FONT_MAIN).pack(side="left", padx=(0, 12))

        # Groq key
        tk.Label(left, text="GROQ API KEY", font=("Segoe UI", 8, "bold"),
                 bg=BG, fg=TEXT2).pack(anchor="w", pady=(14, 4))
        self.key_var = tk.StringVar(value=os.environ.get("GROQ_API_KEY", ""))
        key_entry = tk.Entry(left, textvariable=self.key_var, show="*",
                             bg=SURFACE2, fg=TEXT, font=FONT_MAIN,
                             insertbackground=ACCENT, relief="flat",
                             borderwidth=1, highlightthickness=1,
                             highlightcolor=ACCENT, highlightbackground=BORDER)
        key_entry.pack(fill="x", ipady=6)

        # Generate button
        self.gen_btn = tk.Button(
            left, text="  Generate App  ",
            font=("Segoe UI", 11, "bold"),
            bg=ACCENT, fg="#080808", relief="flat",
            cursor="hand2", pady=10,
            command=self._generate)
        self.gen_btn.pack(fill="x", pady=(20, 6))

        self.stop_btn = tk.Button(
            left, text="Stop",
            font=FONT_MAIN,
            bg=SURFACE2, fg=RED, relief="flat",
            cursor="hand2", pady=6,
            command=self._stop, state="disabled")
        self.stop_btn.pack(fill="x")

        # Quick presets
        tk.Label(left, text="QUICK PRESETS", font=("Segoe UI", 8, "bold"),
                 bg=BG, fg=TEXT2).pack(anchor="w", pady=(20, 6))
        presets = [
            ("Todo App",        "Build a todo app with React and Flask"),
            ("Finance Tracker", "Build a personal finance tracker with charts"),
            ("SaaS Dashboard",  "Build a SaaS analytics dashboard"),
            ("Blog Platform",   "Build a blog platform with markdown support"),
            ("CTF Tool",        "Build a CTF challenge tracker and notes app"),
        ]
        for label, idea in presets:
            btn = tk.Button(left, text=label, font=("Segoe UI", 9),
                           bg=SURFACE2, fg=TEXT2, relief="flat",
                           cursor="hand2", pady=5, anchor="w", padx=10,
                           command=lambda i=idea: self._set_preset(i))
            btn.pack(fill="x", pady=1)
            btn.bind("<Enter>", lambda e, b=btn: b.config(fg=TEXT, bg=BORDER))
            btn.bind("<Leave>", lambda e, b=btn: b.config(fg=TEXT2, bg=SURFACE2))

        # Right panel — output log
        right = tk.Frame(content, bg=BG)
        right.pack(side="right", fill="both", expand=True)

        log_header = tk.Frame(right, bg=SURFACE)
        log_header.pack(fill="x")
        tk.Label(log_header, text="OUTPUT LOG", font=("Segoe UI", 8, "bold"),
                 bg=SURFACE, fg=TEXT2, pady=8, padx=12).pack(side="left")
        tk.Button(log_header, text="Clear", font=("Segoe UI", 8),
                  bg=SURFACE, fg=TEXT2, relief="flat", cursor="hand2",
                  command=self._clear_log, pady=8, padx=8).pack(side="right")

        self.log = scrolledtext.ScrolledText(
            right, wrap="word",
            bg=SURFACE, fg=TEXT, font=FONT_MONO,
            insertbackground=ACCENT, relief="flat",
            state="disabled")
        self.log.pack(fill="both", expand=True)

        # Configure log tags
        self.log.tag_config("accent", foreground=ACCENT)
        self.log.tag_config("green",  foreground=GREEN)
        self.log.tag_config("red",    foreground=RED)
        self.log.tag_config("dim",    foreground=TEXT2)
        self.log.tag_config("bold",   font=("Consolas", 9, "bold"))

        # Progress bar
        self.progress = ttk.Progressbar(self.root, mode="indeterminate")
        style = ttk.Style()
        style.theme_use("default")
        style.configure("TProgressbar", troughcolor=SURFACE, background=ACCENT, thickness=3)

        # Footer
        footer = tk.Frame(self.root, bg=SURFACE, pady=8)
        footer.pack(fill="x", side="bottom")
        tk.Label(footer, text="Powered by Kimi K2 + Qwen3-32B + Llama 3.3 70B on Groq",
                 font=("Segoe UI", 8), bg=SURFACE, fg=TEXT2).pack()

        self._log("APEX AI Dev Engine ready.\n", "accent")
        self._log("Enter your app idea and click Generate.\n", "dim")

    def _log(self, msg, tag=None):
        self.log.config(state="normal")
        if tag:
            self.log.insert("end", msg, tag)
        else:
            self.log.insert("end", msg)
        self.log.see("end")
        self.log.config(state="disabled")

    def _clear_log(self):
        self.log.config(state="normal")
        self.log.delete("1.0", "end")
        self.log.config(state="disabled")

    def _browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.folder_var.set(folder)

    def _set_preset(self, idea):
        self.idea_text.delete("1.0", "end")
        self.idea_text.insert("1.0", idea)

    def _set_status(self, text, color=TEXT2):
        self.status_label.config(text=text, fg=color)
        self.status_dot.config(fg=color)

    def _generate(self):
        if self.running:
            return

        idea = self.idea_text.get("1.0", "end").strip()
        name = self.name_var.get().strip().replace(" ", "_") or "my_app"
        provider = self.provider_var.get()
        key = self.key_var.get().strip()
        output_dir = self.folder_var.get().strip()

        if not idea:
            self._log("ERROR: Please enter an app idea.\n", "red")
            return

        if provider == "groq" and not key:
            self._log("ERROR: Groq API key required.\n", "red")
            return

        self.running = True
        self.gen_btn.config(state="disabled", bg=BORDER, fg=TEXT2)
        self.stop_btn.config(state="normal")
        self.progress.pack(fill="x")
        self.progress.start(10)
        self._set_status("Generating...", ACCENT)
        self._clear_log()
        self._log(f"Starting generation: {name}\n", "accent")
        self._log(f"Idea: {idea}\n", "dim")
        self._log(f"Output: {output_dir}/{name}\n\n", "dim")

        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        if key:
            env["GROQ_API_KEY"] = key

        engine_dir = Path(__file__).parent
        cli_path = engine_dir / "cli.py"

        cmd = [
            sys.executable, str(cli_path),
            "--fullstack", idea,
            "--name", name,
            "--provider", provider,
        ]

        def run():
            try:
                self.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    env=env,
                    cwd=str(output_dir),
                )
                for line in self.process.stdout:
                    self.root.after(0, self._handle_line, line)
                self.process.wait()
                rc = self.process.returncode
                self.root.after(0, self._done, rc)
            except Exception as e:
                self.root.after(0, self._log, f"ERROR: {e}\n", "red")
                self.root.after(0, self._done, 1)

        threading.Thread(target=run, daemon=True).start()

    def _handle_line(self, line):
        line = line.rstrip()
        if not line:
            self._log("\n")
            return
        tag = None
        if any(x in line for x in ["ERR", "Error", "error", "Failed", "FAIL"]):
            tag = "red"
        elif any(x in line for x in ["OK", "ready", "complete", "success", "AutoFix"]):
            tag = "green"
        elif any(x in line for x in ["Groq", "Pipeline", "step", "Writing", "Installing"]):
            tag = "accent"
        elif any(x in line for x in ["Rate limit", "waiting", "Retry"]):
            tag = "dim"
        self._log(line + "\n", tag)

    def _done(self, returncode):
        self.running = False
        self.process = None
        self.gen_btn.config(state="normal", bg=ACCENT, fg="#080808")
        self.stop_btn.config(state="disabled")
        self.progress.stop()
        self.progress.pack_forget()
        if returncode == 0:
            self._set_status("Done!", GREEN)
            self._log("\nGeneration complete!\n", "green")
        else:
            self._set_status("Failed", RED)
            self._log("\nGeneration failed. Check output above.\n", "red")

    def _stop(self):
        if self.process:
            self.process.terminate()
            self._log("\nStopped by user.\n", "dim")
        self._done(1)


if __name__ == "__main__":
    root = tk.Tk()
    app = ApexLauncher(root)
    root.mainloop()
