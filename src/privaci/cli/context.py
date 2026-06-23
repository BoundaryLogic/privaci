"""Shared CLI run preparation and database URL resolution."""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, TypeVar

from privaci.config import load_config
from privaci.config.models import Config
from privaci.contracts import load_plugins
from privaci.errors import CatalogError, LicenseError
from privaci.preflight import resolve_run_salt
from privaci.preflight.pseudonym_key import resolve_run_pseudonym_key
from privaci.runtime.signals import clear_interrupt, install_handlers, restore_handlers
from privaci.secrets import SecretKind, resolve_secret
from privaci.state.fingerprints import salt_fingerprint

logger = logging.getLogger(__name__)

_T = TypeVar("_T")


@dataclass(frozen=True, slots=True)
class RunContext:
    """Validated inputs shared by ``run`` and ``resume`` CLI commands."""

    config: Config
    source_dsn: str
    target_dsn: str
    salt: str
    salt_fingerprint: str
    pseudonym_key: str | None = None


def prepare_cli_run(
    *,
    config_path: str,
    source: str | None,
    target: str | None,
) -> RunContext:
    """Load config, validate license, and resolve DSNs plus salt."""
    config = load_config(config_path)
    _validate_license()
    source_dsn = resolve_db_url(source, env_name="SOURCE_DB_URL", role="source")
    target_dsn = resolve_db_url(target, env_name="TARGET_DB_URL", role="target")
    salt = resolve_run_salt(config)
    pseudonym_key = resolve_run_pseudonym_key(config)
    fingerprint = salt_fingerprint(salt)
    logger.info("Resolved salt fingerprint", extra={"salt_fingerprint": fingerprint})
    return RunContext(
        config=config,
        source_dsn=source_dsn,
        target_dsn=target_dsn,
        salt=salt,
        salt_fingerprint=fingerprint,
        pseudonym_key=pseudonym_key,
    )


def _validate_license() -> None:
    plugins = load_plugins()
    license_status = plugins.license_validator.validate()
    if license_status.is_valid:
        return
    raise LicenseError(
        "Validating license",
        cause=license_status.message or "License validation failed.",
        remediation="Install a valid license or use the community tier.",
    )


def resolve_db_url(
    explicit: str | None,
    *,
    env_name: str,
    role: str,
) -> str:
    """Resolve a database URL from CLI flag or environment.

    Raises:
        CatalogError: When no URL is provided or resolution fails.
    """
    raw = explicit or os.environ.get(env_name)
    if raw is None or not raw.strip():
        raise CatalogError(
            f"Resolving the {role} database URL",
            cause=f"No {role} connection string was provided.",
            remediation=(
                f"Pass --{role} or export {env_name}, e.g. "
                f"{env_name}=postgresql://postgres:dev@127.0.0.1:55432/privaci_source"
            ),
        )
    secret = resolve_secret(raw.strip(), required=True, kind=SecretKind.DB_URL)
    if secret is None:  # pragma: no cover - required=True never returns None
        raise CatalogError(
            f"Resolving the {role} database URL",
            cause=f"The {role} connection string could not be resolved.",
            remediation=f"Verify --{role} or {env_name}.",
        )
    return secret.get_secret_value()


def run_with_signal_handlers(
    coro_factory: Callable[[], Coroutine[Any, Any, _T]],
) -> _T:
    """Run an async coroutine with SIGINT/SIGTERM handlers installed."""
    clear_interrupt()
    install_handlers()
    try:
        return asyncio.run(coro_factory())
    finally:
        restore_handlers()
