# telegram_bot.py — APEX AI Dev Engine Telegram Interface
# Full remote control: generate apps, chat, plan, check status

import os
import sys
import asyncio
import re
from pathlib import Path
from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

BOT_TOKEN  = os.getenv("TELEGRAM_BOT_TOKEN", "")
ENGINE_DIR = Path(__file__).parent
PROVIDER   = "groq" if os.getenv("GROQ_API_KEY", "").strip() else "ollama"

BANNER = """
╔═══════════════════════════════════╗
║  APEX AI Dev Engine               ║
║  Powered by Kimi K2 + Qwen3-32B   ║
║  Type /help to see commands       ║
╚═══════════════════════════════════╝
"""

# ── Intent Parser ──────────────────────────────────────────────────────────────

def parse_intent(text: str) -> dict:
    t  = text.strip()
    tl = t.lower()

    # Raw CLI passthrough
    if t.startswith("--"):
        return {"mode": "cli", "raw": t}

    # Status checks
    if any(w in tl for w in ["check", "status", "models", "ping"]):
        return {"mode": "check"}

    # Explicit modes
    if tl.startswith(("chat ", "ask ")):
        return {"mode": "chat", "prompt": t.split(" ", 1)[1]}
    if tl.startswith(("plan ", "design ", "architect ")):
        return {"mode": "plan", "prompt": t}
    if tl.startswith(("code ", "write code", "generate code")):
        return {"mode": "code", "prompt": t}

    # Parse flags
    dry      = "--dry-run" in tl or "dry run" in tl
    no_tests = "--no-tests" in tl or "no test" in tl

    # Extract project name
    nm = re.search(r"(?:called|named|name it|call it)\s+([a-zA-Z0-9_\-]+)", tl)
    if nm:
        name = nm.group(1).lower().replace("-", "_")
    else:
        words = re.sub(r"[^a-z0-9 ]", "", tl).split()
        skip  = {"build","create","make","generate","a","an","the","with","and",
                 "for","using","app","application","frontend","backend","full","stack",
                 "me","please","i","want","need"}
        name = "_".join([w for w in words if w not in skip][:3]) or "my_app"

    # Detect fullstack build intent
    build_kw = ["build", "create", "make", "generate", "develop",
                "fullstack", "full stack", "website", "web app", "saas",
                "api", "flask", "react", "vue", "fastapi", "dashboard",
                "platform", "system", "app", "tool", "tracker", "manager"]

    if any(w in tl for w in build_kw):
        return {
            "mode": "fullstack",
            "prompt": t,
            "name": name,
            "dry_run": dry,
            "no_tests": no_tests,
        }

    return {"mode": "chat", "prompt": t}


def build_cmd(intent: dict) -> list:
    base     = [sys.executable, str(ENGINE_DIR / "cli.py")]
    provider = ["--provider", PROVIDER]
    m        = intent.get("mode")

    if m == "cli":
        import shlex
        return base + shlex.split(intent["raw"])
    if m == "check":
        return base + ["--check"] + provider
    if m == "chat":
        return base + ["--chat", intent["prompt"]] + provider
    if m == "plan":
        return base + ["--plan", intent["prompt"]] + provider
    if m == "code":
        return base + ["--code", intent["prompt"]] + provider
    if m == "fullstack":
        cmd = base + ["--fullstack", intent["prompt"], "--name", intent["name"]] + provider
        if intent.get("dry_run"):   cmd += ["--dry-run"]
        if intent.get("no_tests"):  cmd += ["--no-tests"]
        return cmd
    return base + ["--help"]


# ── Engine Runner ──────────────────────────────────────────────────────────────

async def run_engine(update: Update, intent: dict):
    chat_id = update.effective_chat.id
    bot     = update.get_bot()
    cmd     = build_cmd(intent)
    name    = intent.get("name", "")
    mode    = intent.get("mode", "?")
    prov    = PROVIDER.upper()

    # Send start message
    start_msgs = {
        "fullstack": f"🚀 *Building: {name}*\nProvider: {prov}\n\nThis takes 3-5 minutes. Updates incoming...",
        "check":     f"🔍 Checking {prov} connection...",
        "chat":      f"💬 Thinking...",
        "plan":      f"🏗️ Designing architecture...",
        "code":      f"⚡ Generating code...",
        "cli":       f"⚙️ Running: `{' '.join(cmd[2:])}`",
    }
    await bot.send_message(
        chat_id=chat_id,
        text=start_msgs.get(mode, "⚙️ Running..."),
        parse_mode=ParseMode.MARKDOWN
    )

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(ENGINE_DIR),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        buffer    = []
        last_sent = asyncio.get_event_loop().time()
        step_msgs = []  # collect pipeline step completions

        async for line in proc.stdout:
            text = line.decode("utf-8", errors="ignore").rstrip()
            if not text:
                continue

            # Send pipeline step completions immediately
            if any(kw in text for kw in ["Pipeline step", "responded.", "Writing", "Installing", "AutoFix", "Project ready"]):
                if buffer:
                    try:
                        await bot.send_message(chat_id=chat_id, text="\n".join(buffer[-15:]))
                    except Exception:
                        pass
                    buffer = []
                try:
                    await bot.send_message(chat_id=chat_id, text=text)
                except Exception:
                    pass
                last_sent = asyncio.get_event_loop().time()
                continue

            buffer.append(text)
            now = asyncio.get_event_loop().time()

            if len(buffer) >= 15 or (now - last_sent) > 8:
                chunk = "\n".join(buffer[-15:])
                try:
                    await bot.send_message(chat_id=chat_id, text=chunk)
                except Exception:
                    pass
                buffer    = []
                last_sent = now

        await proc.wait()

        # Send remaining buffer
        if buffer:
            try:
                await bot.send_message(chat_id=chat_id, text="\n".join(buffer))
            except Exception:
                pass

        # Final message
        if proc.returncode == 0:
            if name and mode == "fullstack":
                msg = (
                    f"✅ *{name} is ready!*\n\n"
                    f"*Run Backend (Terminal 1):*\n"
                    f"`cd {name}\\backend`\n`py app.py`\n\n"
                    f"*Run Frontend (Terminal 2):*\n"
                    f"`cd {name}\\frontend`\n`npm install && npm run dev`\n\n"
                    f"🌐 http://localhost:5173"
                )
                if os.path.exists(ENGINE_DIR / name / "frontend" / ".env"):
                    msg += "\n\n⚠️ Add Clerk key to `frontend/.env`"
            else:
                msg = "✅ Done!"
            await bot.send_message(chat_id=chat_id, text=msg, parse_mode=ParseMode.MARKDOWN)
        else:
            await bot.send_message(chat_id=chat_id, text="❌ Generation failed. Check output above.")

    except Exception as e:
        await bot.send_message(chat_id=chat_id, text=f"❌ Error: {e}")


# ── Command Handlers ───────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prov = PROVIDER.upper()
    await update.message.reply_text(
        f"*APEX AI Dev Engine* [{prov}]\n\n"
        "*Generate a full app:*\n"
        "  `build a todo app with React and Flask`\n"
        "  `build a SaaS dashboard with auth`\n"
        "  `build an e-commerce store`\n\n"
        "*Single model:*\n"
        "  `chat what is JWT?`\n"
        "  `plan a microservices system`\n"
        "  `code a Flask auth route`\n\n"
        "*Utilities:*\n"
        "  /check — test connection\n"
        "  /models — list available models\n"
        "  /help — show this message\n\n"
        f"Provider: {prov} ({'cloud ⚡' if PROVIDER == 'groq' else 'local 🖥️'})",
        parse_mode=ParseMode.MARKDOWN
    )

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_start(update, context)

async def cmd_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await run_engine(update, {"mode": "check"})

async def cmd_models(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "*Current Model Stack:*\n\n"
        "🧠 *Reasoner:* Kimi K2 Instruct\n"
        "   → Architecture, system design\n\n"
        "⚡ *Coder:* Qwen3-32B\n"
        "   → Backend, frontend, DB schema\n\n"
        "📦 *Decoder:* Llama 3.3 70B\n"
        "   → Config, deployment files\n\n"
        "All running on Groq LPUs 🚀",
        parse_mode=ParseMode.MARKDOWN
    )

async def cmd_build(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        prompt = " ".join(context.args)
        intent = parse_intent(f"build {prompt}")
        await run_engine(update, intent)
    else:
        await update.message.reply_text(
            "Usage: `/build <description>`\n"
            "Example: `/build a task manager with React`",
            parse_mode=ParseMode.MARKDOWN
        )

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    await run_engine(update, parse_intent(update.message.text))


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    token = BOT_TOKEN
    if not token or token == "YOUR_TOKEN_HERE":
        print("❌ Set TELEGRAM_BOT_TOKEN environment variable first")
        print("   setx TELEGRAM_BOT_TOKEN your_token_here")
        sys.exit(1)

    print(BANNER)
    print(f"Provider: {PROVIDER.upper()}")
    print(f"Engine:   {ENGINE_DIR}")
    print(f"Token:    {token[:10]}...")
    print("\nBot is running. Open Telegram and send /start\n")

    app = Application.builder().token(token).build()

    # Register commands
    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("help",   cmd_help))
    app.add_handler(CommandHandler("check",  cmd_check))
    app.add_handler(CommandHandler("models", cmd_models))
    app.add_handler(CommandHandler("build",  cmd_build))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))

    app.run_polling(
        stop_signals=None,
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    asyncio.set_event_loop(asyncio.new_event_loop())
    main()
