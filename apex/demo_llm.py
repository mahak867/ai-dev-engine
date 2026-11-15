"""
Deterministic stand-in LLM ("fake/canned" model).

Used by the dashboard's no-key **demo replay**, by ``eval/run_eval.py
--self-test`` and by the tests. Outputs are canned, so nothing produced with
it says anything about real model quality; every surface labels it.
"""
from __future__ import annotations

import json

_APP = '''import os
import sqlite3
from flask import Flask, jsonify, request

app = Flask(__name__)
DB = os.environ.get("DB_PATH", ":memory:")
_conn = sqlite3.connect(DB, check_same_thread=False)
_conn.execute("CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY, title TEXT NOT NULL)")


@app.post("/items")
def create():
    data = request.get_json(silent=True) or {}
    title = str(data.get("title", "")).strip()
    if not title or len(title) > 200:
        return jsonify(error="title required (1-200 chars)"), 400
    cur = _conn.execute("INSERT INTO items (title) VALUES (?)", (title,))
    return jsonify(id=cur.lastrowid, title=title), 201


@app.get("/items")
def list_items():
    rows = _conn.execute("SELECT id, title FROM items ORDER BY id").fetchall()
    return jsonify([{"id": r[0], "title": r[1]} for r in rows])


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")))
'''

_TEST = '''import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import app


def test_create_and_list():
    c = app.test_client()
    assert c.post("/items", json={"title": "a"}).status_code == 201
    assert any(i["title"] == "a" for i in c.get("/items").get_json())


def test_validation():
    assert app.test_client().post("/items", json={}).status_code == 400
'''

_SINGLE_APP = '''from flask import Flask, request
import sqlite3, os

app = Flask(__name__)
SECRET_KEY = "dev-secret-key-123456"
db = sqlite3.connect("app.db", check_same_thread=False)
db.execute("CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY, title TEXT)")


@app.route("/items", methods=["POST"])
def create():
    title = request.json["title"]
    db.execute("INSERT INTO items (title) VALUES ('%s')" % title)
    return {"ok": True}


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
'''


def _block(path: str, body: str, lang: str = "python") -> str:
    return f"```{lang}\n# file: {path}\n{body}```\n"


def respond(messages: list[dict]) -> str:
    system = messages[0]["content"] if messages else ""
    if "Output ONLY valid JSON, zero prose" in system:            # Planner
        return json.dumps({"tech_stack": {"backend": "flask"}, "files": ["backend/app.py"],
                           "features": ["crud"], "api_routes": ["/items"], "db_schema": {},
                           "security_notes": ["validate input"], "complexity": "low"})
    if system.startswith("You are an elite software architect"):  # Architect
        return "Flask app in backend/, SQLite, pytest tests in backend/tests."
    if "senior code reviewer" in system:                          # Reviewer
        return json.dumps({"score": 92, "critical": [], "warnings": [], "suggestions": [],
                           "security_issues": [], "fixed_files": {}})
    if "elite full-stack engineer" in system:                     # Coder / revise
        return (_block("backend/app.py", _APP) + _block("backend/tests/test_app.py", _TEST)
                + _block("backend/requirements.txt", "flask>=3.0\n", "text"))
    if "README" in system:                                        # DocWriter
        return "# Generated app\n\nRun `python backend/app.py`.\n"
    if "=== filename.ext ===" in system:                          # single-agent baseline
        return f"=== app.py ===\n{_SINGLE_APP}\n=== requirements.txt ===\nflask\n"
    return "No issues found."                                     # SelfHealer / Debugger
