"""Spin up ``compose.dev.yml`` Postgres for capability tests."""

from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

DEFAULT_SOURCE = "postgresql://postgres:dev@127.0.0.1:55432/privaci_source"
DEFAULT_TARGET = "postgresql://postgres:dev@127.0.0.1:55433/privaci_target"


def engine_root() -> Path:
    return Path(__file__).resolve().parents[2]


def resolve_compose_cmd() -> list[str]:
    """Return argv prefix for compose (e.g. ``['docker', 'compose']``)."""
    if cmd := shutil.which("docker"):
        try:
            subprocess.run(
                [cmd, "compose", "version"],
                check=True,
                capture_output=True,
            )
            subprocess.run([cmd, "info"], check=True, capture_output=True)
            return [cmd, "compose"]
        except (subprocess.CalledProcessError, OSError):
            pass
    if cmd := shutil.which("podman"):
        try:
            subprocess.run(
                [cmd, "compose", "version"],
                check=True,
                capture_output=True,
            )
            return [cmd, "compose"]
        except (subprocess.CalledProcessError, OSError):
            pass
    if cmd := shutil.which("podman-compose"):
        return [cmd]
    if cmd := shutil.which("docker-compose"):
        return [cmd]
    msg = "No compose engine found (docker compose, podman compose, podman-compose)."
    raise RuntimeError(msg)


def compose_dev_up(*, reset_volumes: bool = False) -> list[str]:
    """Start dev Postgres stack; return log lines describing steps."""
    root = engine_root()
    compose_file = root / "compose.dev.yml"
    cmd_base = resolve_compose_cmd()
    logs: list[str] = []

    if reset_volumes:
        down_cmd = [*cmd_base, "-f", str(compose_file), "down", "-v"]
        logs.append(f"$ {' '.join(down_cmd)}")
        subprocess.run(down_cmd, cwd=root, check=True)

    up_cmd = [*cmd_base, "-f", str(compose_file), "up", "-d"]
    logs.append(f"$ {' '.join(up_cmd)}")
    subprocess.run(up_cmd, cwd=root, check=True)
    return logs


def compose_dev_down(*, volumes: bool = False) -> list[str]:
    """Stop dev Postgres stack."""
    root = engine_root()
    compose_file = root / "compose.dev.yml"
    cmd_base = resolve_compose_cmd()
    down_cmd = [*cmd_base, "-f", str(compose_file), "down"]
    if volumes:
        down_cmd.append("-v")
    logs = [f"$ {' '.join(down_cmd)}"]
    subprocess.run(down_cmd, cwd=root, check=True)
    return logs


def wait_postgres_ready(
    source_dsn: str,
    target_dsn: str,
    *,
    timeout_sec: float = 90.0,
) -> list[str]:
    """Poll until both databases accept connections."""
    import asyncio

    import asyncpg

    logs: list[str] = []
    deadline = time.monotonic() + timeout_sec
    last_error = "unknown"

    async def _probe() -> None:
        nonlocal last_error
        for dsn in (source_dsn, target_dsn):
            conn = await asyncpg.connect(dsn, timeout=5)
            await conn.close()

    while time.monotonic() < deadline:
        try:
            asyncio.run(_probe())
            logs.append("Postgres source and target are reachable.")
            return logs
        except (OSError, asyncpg.PostgresError) as exc:
            last_error = str(exc)
            time.sleep(2.0)

    msg = f"Postgres not ready after {timeout_sec}s: {last_error}"
    raise TimeoutError(msg)
