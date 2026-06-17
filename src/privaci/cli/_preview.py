"""``privaci preview`` — delegates to the commercial preview entry point."""

from __future__ import annotations

import importlib.metadata
from collections.abc import Callable
from pathlib import Path
from typing import Any

from privaci.cli.context import resolve_db_url
from privaci.errors import ConfigError

PLUGIN_GROUP = "privaci.plugins"
_PREVIEW_ENTRY = "cli.preview"


def _load_preview_command() -> Callable[..., None] | None:
    for ep in importlib.metadata.entry_points(group=PLUGIN_GROUP):
        if ep.name == _PREVIEW_ENTRY:
            loaded = ep.load()
            return loaded if callable(loaded) else None
    return None


def execute_preview(
    *,
    config: str,
    source: str | None,
    target: str | None,
    commercial_extensions: str | None = None,
    sample: int = 0,
    policy_diff: str | None = None,
    sarif: str | None = None,
) -> None:
    """Run commercial CI preview when the layer is installed."""
    preview_fn = _load_preview_command()
    if preview_fn is None:
        raise ConfigError(
            "CI preview",
            cause="The preview command requires the commercial layer.",
            remediation=(
                "Install privaci-commercial or use the Marketplace container image."
            ),
        )
    source_dsn = resolve_db_url(source, env_name="SOURCE_DB_URL", role="source")
    target_dsn = resolve_db_url(target, env_name="TARGET_DB_URL", role="target")
    kwargs: dict[str, Any] = {
        "config": Path(config),
        "source": source_dsn,
        "target": target_dsn,
        "sample": sample,
    }
    if commercial_extensions is not None:
        kwargs["commercial"] = Path(commercial_extensions)
    if policy_diff is not None:
        kwargs["policy_diff"] = Path(policy_diff)
    if sarif is not None:
        kwargs["sarif"] = Path(sarif)
    preview_fn(**kwargs)
