"""Shared constants for the security AST gate."""

from __future__ import annotations

SCAN_PACKAGES = frozenset({"mask", "stream", "secrets", "config", "pipeline"})
ARTICLE_I_PACKAGES = frozenset({"mask", "stream", "pipeline"})
BANNED_DYNAMIC_CALLS = frozenset({"eval", "exec", "__import__"})
SUBPROCESS_CALLS = frozenset(
    {"run", "Popen", "call", "check_output", "check_call"},
)
DB_CALL_NAMES = frozenset({"execute", "executemany", "fetch", "fetchval", "fetchrow"})
LOGGER_METHODS = frozenset(
    {"debug", "info", "warning", "error", "critical", "exception", "log"},
)
BANNED_HTTP_MODULES = frozenset(
    {
        "httpx",
        "requests",
        "urllib",
        "urllib.request",
        "urllib3",
        "aiohttp",
        "http",
        "http.client",
    }
)
BANNED_PACKAGING_MODULES = frozenset({"privaci_commercial"})
PII_ISH_NAMES = frozenset(
    {
        "email",
        "ssn",
        "password",
        "phone",
        "address",
        "dob",
        "mrn",
        "plain",
        "secret",
        "token",
        "pii",
    }
)
# Symbol allowlists only suppress SQL heuristics (never dynamic-exec / shell / HTTP).
SYMBOL_ALLOWLIST_RULES = frozenset({"sql-concat"})
