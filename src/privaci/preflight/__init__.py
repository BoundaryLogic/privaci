"""Pre-flight checks before any database writes."""

from __future__ import annotations

from privaci.preflight.runner import PreflightReport, run_preflight
from privaci.preflight.salt import resolve_run_salt

__all__ = ["PreflightReport", "resolve_run_salt", "run_preflight"]
