"""Validation helpers for keyed masking actions (license-gated)."""

from __future__ import annotations

import os
from collections.abc import Iterator

from privaci.config.models import Config
from privaci.contracts.plugins import load_plugins
from privaci.errors import LicenseError
from privaci.secrets.resolver import SecretResolutionError

KEYED_ACTIONS = frozenset({"hmac_hash", "pseudonym"})
# LicenseValidator.tier values that enable keyed actions (plugin-defined).
_KEYED_ACTION_LICENSES = frozenset({"growth", "business", "enterprise"})


def iter_keyed_columns(config: Config) -> Iterator[tuple[str, str]]:
    """Yield ``(table_id, column)`` for every keyed action in ``config``."""
    for table_id, table in config.tables.items():
        for column_name, action in table.columns.items():
            if action.action in KEYED_ACTIONS:
                yield table_id, column_name


def config_uses_keyed_actions(config: Config) -> bool:
    """Return whether ``config`` configures any keyed masking action."""
    return any(True for _ in iter_keyed_columns(config))


def pseudonym_key_configured(config: Config) -> bool:
    """Return whether a pseudonym key reference exists in config or env."""
    if config.pseudonym_key is not None:
        value = config.pseudonym_key.get_secret_value().strip()
        if value:
            return True
    return bool(os.environ.get("PSEUDONYM_KEY", "").strip())


def validate_keyed_actions(config: Config) -> None:
    """Reject keyed actions when license or key configuration is insufficient.

    Raises:
        LicenseError: When the installed license validator rejects keyed actions
            (exit 5).
        SecretResolutionError: When keyed actions lack a key reference (exit 4).
    """
    keyed = [
        f"tables.{table}.columns.{column}"
        for table, column in iter_keyed_columns(config)
    ]
    if not keyed:
        return

    license_tier = _normalize_license_tier(
        load_plugins().license_validator.validate().tier
    )
    if license_tier not in _KEYED_ACTION_LICENSES:
        raise LicenseError(
            "Validating keyed masking actions",
            cause=(
                "Actions hmac_hash and pseudonym are not enabled for the current "
                "license on: " + ", ".join(sorted(keyed))
            ),
            remediation=(
                "Install a plugin package whose LicenseValidator enables keyed "
                "pseudonymisation, or remove these actions from mask-rules.yaml. "
                "See docs/configuration.md."
            ),
        )

    if not pseudonym_key_configured(config):
        raise SecretResolutionError(
            "Validating pseudonym_key for keyed masking actions",
            exit_code=4,
            uri="<pseudonym_key>",
            cause=(
                "Columns use hmac_hash or pseudonym but no pseudonym_key is configured."
            ),
            remediation=(
                "Set pseudonym_key in mask-rules.yaml or export PSEUDONYM_KEY "
                "(minimum 32 bytes after resolution)."
            ),
        )


def _normalize_license_tier(tier: str) -> str:
    lowered = tier.lower()
    if lowered == "team":
        return "growth"
    if lowered in {"unlimited", "enterprise"}:
        return "enterprise"
    return lowered
