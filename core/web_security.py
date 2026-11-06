"""
HTTP / WebSocket access control shared by server.py and mcp_server.py.

Defaults are safe for a laptop: bind 127.0.0.1, accept only localhost Host
headers (DNS-rebinding protection, per the MCP transport security guidance),
and only same-machine browser Origins. Set ``APEX_API_TOKEN`` to require a
bearer token on every /api and /mcp route and on the WebSocket. Binding to a
non-loopback address without a token is refused at startup.

Environment:
  APEX_HOST                 bind address (default 127.0.0.1)
  APEX_PORT                 port (default 8000; MCP standalone uses APEX_MCP_PORT/8001)
  APEX_API_TOKEN            shared secret; required for non-loopback binds
  APEX_ALLOWED_HOSTS        comma list of acceptable Host header names
  APEX_ALLOWED_ORIGINS      comma list of acceptable browser Origins
  APEX_MAX_CONCURRENT_JOBS  generation jobs allowed at once (default 2)
  APEX_MAX_TASK_CHARS       max task prompt length (default 500)
  APEX_MAX_SESSIONS         in-memory session records kept (default 200)
  APEX_PUBLIC_DEMO          1 = public demo (e.g. Hugging Face Space): visitors bring
                            their own API key or watch a no-LLM replay; the server
                            holds no provider keys, shares no sessions or memory
  APEX_RUNS_PER_HOUR        per-client run limit in public demo mode (default 6)
  APEX_TRUST_PROXY          1 = take the client IP from X-Forwarded-For
  APEX_FRAME_ANCESTORS      allow embedding (e.g. "https://huggingface.co")
"""
from __future__ import annotations

import hmac
import ipaddress
import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Iterable

LOOPBACK_NAMES = {"localhost", "127.0.0.1", "::1", "[::1]"}
PROVIDER_KEY_VARS = ("QWEN_API_KEY", "DASHSCOPE_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY",
                     "TOGETHER_API_KEY", "MISTRAL_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY")


def _csv(name: str, default: Iterable[str]) -> list[str]:
    raw = os.environ.get(name)
    if raw is None:
        return list(default)
    return [x.strip() for x in raw.split(",") if x.strip()]


def is_loopback_host(host: str) -> bool:
    h = host.strip("[]").lower()
    if h == "localhost":
        return True
    try:
        return ipaddress.ip_address(h).is_loopback
    except ValueError:
        return False


@dataclass
class Settings:
    host: str = "127.0.0.1"
    port: int = 8000
    api_token: str = ""
    allowed_hosts: list[str] = field(default_factory=list)
    allowed_origins: list[str] = field(default_factory=list)
    max_concurrent_jobs: int = 2
    max_task_chars: int = 500
    max_sessions: int = 200
    max_ws_message_bytes: int = 16 * 1024
    max_tool_input_chars: int = 20_000
    public_demo: bool = False
    runs_per_hour: int = 6
    trust_proxy: bool = False
    frame_ancestors: str = ""

    @property
    def auth_required(self) -> bool:
        return bool(self.api_token)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    host = os.environ.get("APEX_HOST", "127.0.0.1")
    port = int(os.environ.get("APEX_PORT", "8000"))
    default_hosts = ["localhost", "127.0.0.1", "::1"]
    if not is_loopback_host(host) and host not in ("0.0.0.0", "::"):
        default_hosts.append(host)
    default_origins = [f"http://localhost:{port}", f"http://127.0.0.1:{port}"]
    return Settings(
        host=host,
        port=port,
        api_token=os.environ.get("APEX_API_TOKEN", "").strip(),
        allowed_hosts=[h.lower() for h in _csv("APEX_ALLOWED_HOSTS", default_hosts)],
        allowed_origins=[o.rstrip("/").lower() for o in _csv("APEX_ALLOWED_ORIGINS", default_origins)],
        max_concurrent_jobs=max(1, int(os.environ.get("APEX_MAX_CONCURRENT_JOBS", "2"))),
        max_task_chars=max(1, int(os.environ.get("APEX_MAX_TASK_CHARS", "500"))),
        max_sessions=max(1, int(os.environ.get("APEX_MAX_SESSIONS", "200"))),
        public_demo=os.environ.get("APEX_PUBLIC_DEMO", "") == "1",
        runs_per_hour=max(1, int(os.environ.get("APEX_RUNS_PER_HOUR", "6"))),
        trust_proxy=os.environ.get("APEX_TRUST_PROXY", "") == "1",
        frame_ancestors=os.environ.get("APEX_FRAME_ANCESTORS", "").strip(),
    )


def assert_safe_bind(host: str, settings: Settings | None = None) -> None:
    """Refuse to listen beyond loopback unless a token is configured."""
    s = settings or get_settings()
    if s.public_demo:
        leaked = [k for k in PROVIDER_KEY_VARS if os.environ.get(k)]
        if leaked:
            raise SystemExit(
                f"APEX_PUBLIC_DEMO=1 but provider keys are set ({', '.join(leaked)}). A public demo must "
                f"not spend the operator's quota: remove them — visitors bring their own key.")
        return
    if not is_loopback_host(host) and not s.auth_required:
        raise SystemExit(
            f"Refusing to bind {host!r} without APEX_API_TOKEN. Set a long random token "
            f"(e.g. `python -c \"import secrets;print(secrets.token_urlsafe(32))\"`) and put "
            f"TLS in front of the server, or bind 127.0.0.1."
        )


# ── checks ─────────────────────────────────────────────────────────────────────
def host_allowed(host_header: str | None, s: Settings) -> bool:
    if not host_header:
        return False
    host = host_header.strip().lower()
    if host.startswith("["):
        name = host.split("]")[0] + "]"
    else:
        name = host.rsplit(":", 1)[0] if host.count(":") == 1 else host
    if "*" in s.allowed_hosts:
        return True
    if name in s.allowed_hosts or name.strip("[]") in s.allowed_hosts:
        return True
    # ".hf.space" / "*.hf.space" entries allow any subdomain of that suffix
    return any(name.endswith(h.lstrip("*")) and h.lstrip("*").startswith(".")
               for h in s.allowed_hosts if h.startswith((".", "*.")))


def origin_allowed(origin: str | None, s: Settings) -> bool:
    """Absent Origin = non-browser client (curl, MCP client) → allowed; host+token still apply."""
    if origin is None:
        return True
    o = origin.rstrip("/").lower()
    if o in s.allowed_origins:
        return True
    # "https://*.hf.space" entries allow any subdomain over that scheme
    for a in s.allowed_origins:
        if "://*." in a:
            scheme, suffix = a.split("://*", 1)
            if o.startswith(scheme + "://") and o.endswith(suffix):
                return True
    return False


def token_ok(presented: str | None, s: Settings) -> bool:
    if not s.auth_required:
        return True
    if not presented:
        return False
    return hmac.compare_digest(presented.encode(), s.api_token.encode())


def extract_token(headers, query_params) -> str | None:
    auth = headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    if headers.get("x-api-key"):
        return headers.get("x-api-key").strip()
    # Browsers cannot set headers on WebSocket handshakes or download links.
    return query_params.get("token")


PUBLIC_PATHS = {"/", "/api/health", "/mcp/health", "/favicon.ico"}

SECURITY_HEADERS = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
    (b"cross-origin-opener-policy", b"same-origin"),
]


class SecurityMiddleware:
    """
    Pure-ASGI middleware: Host allowlist (DNS rebinding), Origin allowlist
    (CSRF/CSWSH from browsers), bearer token on protected HTTP routes, and
    baseline security headers. WebSocket auth is enforced in the endpoint
    (see ``ws_reject_reason``) so the client gets a proper close code.
    """

    def __init__(self, app, settings_factory=get_settings):
        self.app = app
        self.settings_factory = settings_factory

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        from starlette.datastructures import Headers, QueryParams
        from starlette.responses import JSONResponse

        s = self.settings_factory()
        headers = Headers(scope=scope)
        path = scope.get("path", "")

        if not host_allowed(headers.get("host"), s):
            return await JSONResponse({"error": "invalid host"}, status_code=403)(scope, receive, send)
        if not origin_allowed(headers.get("origin"), s):
            return await JSONResponse({"error": "origin not allowed"}, status_code=403)(scope, receive, send)
        protected = (
            (path.startswith("/api/") or path.startswith("/mcp/"))
            and path not in PUBLIC_PATHS
            and scope.get("method") != "OPTIONS"  # CORS preflight carries no credentials
        )
        if protected and not token_ok(extract_token(headers, QueryParams(scope.get("query_string", b""))), s):
            return await JSONResponse(
                {"error": "authentication required"}, status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )(scope, receive, send)

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                hdrs = list(message.get("headers", []))
                existing = {k.lower() for k, _ in hdrs}
                for k, v in SECURITY_HEADERS:
                    if k == b"x-frame-options" and s.frame_ancestors:
                        continue
                    if k not in existing:
                        hdrs.append((k, v))
                if s.frame_ancestors and b"content-security-policy" not in existing:
                    hdrs.append((b"content-security-policy",
                                 f"frame-ancestors 'self' {s.frame_ancestors}".encode()))
                if path.startswith("/api/") and b"cache-control" not in existing:
                    hdrs.append((b"cache-control", b"no-store"))
                message = {**message, "headers": hdrs}
            await send(message)

        return await self.app(scope, receive, send_with_headers)


def client_ip(conn, s: Settings | None = None) -> str:
    s = s or get_settings()
    if s.trust_proxy:
        xff = conn.headers.get("x-forwarded-for", "")
        if xff:
            return xff.split(",")[0].strip()
    return conn.client.host if conn.client else "unknown"


class RateLimiter:
    """Sliding one-hour window per key (client IP)."""

    def __init__(self):
        import threading
        self._hits: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int, window: float = 3600.0) -> bool:
        import time
        now = time.time()
        with self._lock:
            hits = [t for t in self._hits.get(key, []) if now - t < window]
            if len(hits) >= limit:
                self._hits[key] = hits
                return False
            hits.append(now)
            self._hits[key] = hits
            if len(self._hits) > 10_000:
                self._hits = {k: v for k, v in self._hits.items() if v and now - v[-1] < window}
            return True


def ws_reject_reason(websocket, s: Settings | None = None) -> tuple[int, str] | None:
    """Return (close_code, reason) if the WebSocket handshake must be refused."""
    s = s or get_settings()
    if not host_allowed(websocket.headers.get("host"), s):
        return 4403, "invalid host"
    if not origin_allowed(websocket.headers.get("origin"), s):
        return 4403, "origin not allowed"
    if not token_ok(extract_token(websocket.headers, websocket.query_params), s):
        return 4401, "authentication required"
    return None


def install(app, settings_factory=get_settings) -> None:
    """Attach security middleware + strict CORS to a FastAPI app."""
    from fastapi.middleware.cors import CORSMiddleware

    s = settings_factory()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.allowed_origins,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-API-Key"],
        allow_credentials=False,
    )
    # Added last => runs first (outermost).
    app.add_middleware(SecurityMiddleware, settings_factory=settings_factory)
