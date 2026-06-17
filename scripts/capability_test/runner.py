"""Execute pytest for one capability and capture results."""

from __future__ import annotations

import os
import resource
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from scripts.capability_test.compose_dev import (
    DEFAULT_SOURCE,
    DEFAULT_TARGET,
    engine_root,
)
from scripts.capability_test.insights import (
    CapabilityMetrics,
    collect_capability_metrics,
    masking_metrics_issues,
    masking_metrics_status,
)
from scripts.capability_test.registry import Capability
from scripts.capability_test.validators import ValidationResult, run_post_validate

_METRICS_NEED_TARGET = frozenset({"demo-corp", "autodetect", "json-mask", "subsetting"})

_CHILD_AS_BYTES = 2 * 1024 * 1024 * 1024  # 2 GiB virtual memory cap per pytest


@dataclass(frozen=True, slots=True)
class CapabilityResult:
    """Outcome of running one capability."""

    capability_id: str
    label: str
    repo: str
    status: str
    duration_sec: float
    pytest_exit_code: int | None
    pytest_output: str
    validations: tuple[ValidationResult, ...] = field(default_factory=tuple)
    issues: tuple[str, ...] = field(default_factory=tuple)
    metrics: CapabilityMetrics | None = None


def commercial_root() -> Path:
    sibling = engine_root().parent / "privaci-commercial"
    if sibling.is_dir():
        return sibling
    msg = "privaci-commercial repo not found beside PrivaCI (expected ../privaci-commercial)."
    raise FileNotFoundError(msg)


def repo_root(cap: Capability) -> Path:
    return engine_root() if cap.repo == "public" else commercial_root()


def _uses_integration_tests(cap: Capability) -> bool:
    return any(path.startswith("tests/integration/") for path in cap.test_paths)


def build_env(cap: Capability) -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("SOURCE_DB_URL", DEFAULT_SOURCE)
    env.setdefault("TARGET_DB_URL", DEFAULT_TARGET)
    env.setdefault("PRIVACI_TEST_SALT", "a" * 64)
    if cap.requires_postgres or cap.requires_commercial_env:
        _ensure_commercial_dev_license(env)
    if cap.requires_commercial_env:
        env.setdefault("PRIVACI_COMMERCIAL_DEV_LICENSE", "1")
    env.pop("PRIVACI_REPORT_SIGNING_KEY_PEM", None)
    env.pop("PRIVACI_REPORT_SIGNING_KEY", None)
    if cap.repo == "commercial":
        engine = str(engine_root())
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = f"{engine}{os.pathsep}{existing}" if existing else engine
    return env


def _ensure_commercial_dev_license(env: dict[str, str]) -> None:
    """Public integration runs hit the commercial meter when the plugin is installed."""
    try:
        import importlib.metadata

        eps = importlib.metadata.entry_points(group="privaci.plugins")
        if any(ep.name == "usage_meter" for ep in eps):
            env.setdefault("PRIVACI_COMMERCIAL_DEV_LICENSE", "1")
    except (ImportError, AttributeError, TypeError):
        return


def _limit_child_memory() -> None:
    """Cap pytest child process virtual memory (Linux)."""
    try:
        resource.setrlimit(resource.RLIMIT_AS, (_CHILD_AS_BYTES, _CHILD_AS_BYTES))
    except OSError:
        return


def run_capability(
    cap: Capability,
    *,
    timeout_sec: int = 300,
    skip_validate: bool = False,
) -> CapabilityResult:
    """Run pytest for ``cap`` and optional post-validation."""
    root = repo_root(cap)
    missing = [p for p in cap.test_paths if not (root / p).exists()]
    issues: list[str] = []
    if missing:
        issues.extend(f"Missing test file: {p}" for p in missing)
        return CapabilityResult(
            capability_id=cap.id,
            label=cap.label,
            repo=cap.repo,
            status="error",
            duration_sec=0.0,
            pytest_exit_code=None,
            pytest_output="",
            issues=tuple(issues),
        )

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        *cap.test_paths,
        "-q",
        "--tb=short",
        "-ra",
    ]
    env = build_env(cap)
    if cap.requires_postgres or _uses_integration_tests(cap):
        # Repo pyproject.toml defaults to `-m 'not integration'`; override for
        # integration capability modules under tests/integration/.
        cmd.extend(["-m", "integration"])
        env["PYTEST_ADDOPTS"] = ""
    if cap.post_validate or cap.metrics_scope in _METRICS_NEED_TARGET:
        # Metrics and post-validators query the target after pytest exits.
        env["CAPABILITY_PRESERVE_TARGET"] = "1"
    if cap.id == "commercial-subsetting":
        env["CAPABILITY_SUBSETTING_PROFILE"] = "subsetting-demo"
    started = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
            preexec_fn=_limit_child_memory if not cap.requires_postgres else None,
        )
    except subprocess.TimeoutExpired as exc:
        elapsed = time.monotonic() - started
        output = (exc.stdout or "") + (exc.stderr or "")
        issues.append(f"Timed out after {timeout_sec}s")
        return CapabilityResult(
            capability_id=cap.id,
            label=cap.label,
            repo=cap.repo,
            status="failed",
            duration_sec=elapsed,
            pytest_exit_code=None,
            pytest_output=output,
            issues=tuple(issues),
        )

    elapsed = time.monotonic() - started
    output = proc.stdout + proc.stderr
    validations: list[ValidationResult] = []

    if proc.returncode == 0 and cap.post_validate and not skip_validate:
        try:
            validations.append(
                run_post_validate(
                    cap.post_validate,
                    source_dsn=env["SOURCE_DB_URL"],
                    target_dsn=env["TARGET_DB_URL"],
                )
            )
        except (OSError, TimeoutError, ValueError) as exc:
            issues.append(f"Post-validation error: {exc}")
        except Exception as exc:
            # asyncpg and other DB errors — report without aborting the harness
            issues.append(f"Post-validation error: {type(exc).__name__}: {exc}")

    status = _derive_status(proc.returncode, validations, issues)
    if proc.returncode != 0:
        issues.append(f"pytest exit code {proc.returncode}")

    metrics: CapabilityMetrics | None = None
    try:
        metrics = collect_capability_metrics(
            cap,
            source_dsn=env["SOURCE_DB_URL"],
            target_dsn=env["TARGET_DB_URL"],
            pytest_exit_code=proc.returncode,
            pytest_output=output,
        )
    except (OSError, ValueError, RuntimeError) as exc:
        issues.append(f"Metrics collection error: {exc}")

    metrics_issue_list = masking_metrics_issues(cap, metrics)
    if metrics_issue_list:
        issues = (*issues, *metrics_issue_list)
    metrics_status = masking_metrics_status(cap, metrics)
    if metrics_status and proc.returncode == 0:
        status = metrics_status
    elif proc.returncode != 0:
        status = "failed"
    elif any(not v.passed for v in validations):
        status = "failed"
    elif issues and status == "passed":
        status = "error"

    return CapabilityResult(
        capability_id=cap.id,
        label=cap.label,
        repo=cap.repo,
        status=status,
        duration_sec=round(elapsed, 2),
        pytest_exit_code=proc.returncode,
        pytest_output=output,
        validations=tuple(validations),
        issues=tuple(issues),
        metrics=metrics,
    )


def _derive_status(
    exit_code: int,
    validations: list[ValidationResult],
    issues: list[str],
) -> str:
    if exit_code != 0:
        return "failed"
    if any(not v.passed for v in validations):
        return "failed"
    if issues:
        return "error"
    return "passed"


def summarize_results(results: list[CapabilityResult]) -> dict[str, Any]:
    """Build aggregate counts for reporting."""
    counts = {"passed": 0, "failed": 0, "warn": 0, "error": 0}
    for result in results:
        key = result.status if result.status in counts else "error"
        counts[key] += 1
    return counts
