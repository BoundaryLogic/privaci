"""Memory and heavy-work guards for capability-test (user + agent runs)."""

from __future__ import annotations

import os
from pathlib import Path


class ResourceGuardError(RuntimeError):
    """Raised when the machine cannot safely start a heavy job."""


def mem_available_mb() -> int:
    """Return Linux MemAvailable in megabytes."""
    text = Path("/proc/meminfo").read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("MemAvailable:"):
            kb = int(line.split()[1])
            return kb // 1024
    msg = "MemAvailable not found in /proc/meminfo"
    raise ResourceGuardError(msg)


def swap_used_pct() -> int:
    """Return swap used as an integer percentage (0 when no swap)."""
    text = Path("/proc/meminfo").read_text(encoding="utf-8")
    total_kb = 0
    free_kb = 0
    for line in text.splitlines():
        if line.startswith("SwapTotal:"):
            total_kb = int(line.split()[1])
        elif line.startswith("SwapFree:"):
            free_kb = int(line.split()[1])
    if total_kb == 0:
        return 0
    used_kb = total_kb - free_kb
    return int((used_kb * 100) / total_kb)


def check_memory_or_raise(
    *,
    min_avail_mb: int | None = None,
    max_swap_pct: int | None = None,
) -> None:
    """Refuse when the host is under memory pressure.

    Swap usage alone does not block the run when MemAvailable is high — Linux
    often keeps cold pages in swap after pressure eases. Set
    ``CAPABILITY_IGNORE_SWAP=1`` to skip the swap check entirely.
    """
    min_mb = (
        min_avail_mb
        if min_avail_mb is not None
        else _env_int("CAPABILITY_MIN_AVAIL_MB", 4096)
    )
    max_swap = (
        max_swap_pct
        if max_swap_pct is not None
        else _env_int("CAPABILITY_MAX_SWAP_PCT", 80)
    )
    stale_swap_ok_mb = _env_int("CAPABILITY_STALE_SWAP_OK_MB", 8192)
    avail = mem_available_mb()
    swap_pct = swap_used_pct()
    if avail < min_mb:
        raise ResourceGuardError(
            f"Only {avail}MB MemAvailable (need {min_mb}MB). "
            "Close apps or wait for memory to recover before running tests."
        )
    if _env_truthy("CAPABILITY_IGNORE_SWAP"):
        return
    if avail >= stale_swap_ok_mb:
        return
    if swap_pct > max_swap:
        raise ResourceGuardError(
            f"Swap is {swap_pct}% used and MemAvailable is {avail}MB "
            f"(need {stale_swap_ok_mb}MB to treat swap as stale-only). "
            "Free RAM, run `sudo swapoff -a && sudo swapon -a`, or set "
            "CAPABILITY_IGNORE_SWAP=1 if you accept the risk."
        )


def heavy_work_confirmed() -> bool:
    """Return True when the operator explicitly opted into heavy work."""
    return os.environ.get("CAPABILITY_ALLOW_HEAVY", "").strip() in {
        "1",
        "yes",
        "true",
    }


def require_heavy_confirmation(*, reason: str) -> None:
    """Require ``--allow-heavy`` (or CAPABILITY_ALLOW_HEAVY=1) for heavy jobs."""
    if heavy_work_confirmed():
        return
    raise ResourceGuardError(
        f"{reason}\n"
        "This script will NOT start heavy work unless you pass --allow-heavy "
        "(or export CAPABILITY_ALLOW_HEAVY=1). "
        "For quick checks use unit capabilities only, e.g. "
        "--cap public-detect-drift,commercial-jsonb-transform"
    )


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    return int(raw)


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "yes", "true"}
