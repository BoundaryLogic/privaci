"""Load, validate, and version-check mask-rules.yaml.

Turns a YAML file into a validated :class:`~privaci.config.models.Config`,
mapping every failure onto a :class:`~privaci.errors.ConfigError` (exit code 3)
in Context + Cause + Remediation form. Pure functions here never touch a
database; cross-checks that need catalog metadata (e.g. ``null`` on a
``NOT NULL`` column) are exposed as standalone helpers for pre-flight to call.
"""

from __future__ import annotations

import importlib.metadata
import json
from collections.abc import Iterator
from pathlib import Path

import yaml
from pydantic import ValidationError

from privaci.config.actions import ACTION_TAGS
from privaci.config.keyed import validate_keyed_actions
from privaci.config.models import Config
from privaci.errors import ConfigError
from privaci.mask.faker.registry import validate_fake_providers

SUPPORTED_VERSION = "1.0"
ENGINE_VERSION_LABEL = "v1.x"
PLUGIN_GROUP = "privaci.plugins"
CONFIG_DOC = "docs/configuration.md"


def load_config(
    path: str | Path,
    *,
    commercial_installed: bool | None = None,
) -> Config:
    """Load and fully validate a mask-rules.yaml file.

    Args:
        path: Filesystem path to the YAML config.
        commercial_installed: Override commercial-layer detection. When
            ``None`` (default), detection runs via entry-point discovery.

    Returns:
        The validated :class:`Config`.

    Raises:
        ConfigError: On a missing file, malformed YAML, unsupported version,
            schema violation, or an ``ai_refine`` action without the
            commercial layer. Always carries ``exit_code == 3``.
    """
    config_path = Path(path)
    raw = _read_file(config_path)
    data = _parse_yaml(raw, config_path)
    _check_version(data, config_path)
    config = _validate_model(data, config_path)
    if commercial_installed is None:
        commercial_installed = is_commercial_installed()
    _reject_ai_refine_without_commercial(config, commercial_installed)
    validate_keyed_actions(config)
    validate_fake_providers(config)
    return config


def _read_file(path: Path) -> str:
    """Read the config file, mapping I/O failures to ConfigError."""
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ConfigError(
            f"Loading {path}",
            cause="Config file does not exist.",
            remediation=f"Create {path} or pass --config; see {CONFIG_DOC}.",
        ) from exc
    except OSError as exc:
        raise ConfigError(
            f"Loading {path}",
            cause="Config file could not be read.",
            remediation="Check file permissions and retry.",
        ) from exc


def _parse_yaml(raw: str, path: Path) -> dict[str, object]:
    """Parse YAML into a mapping, attributing syntax errors to line/column."""
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ConfigError(
            f"Parsing {path}",
            cause=f"Invalid YAML syntax{_yaml_location(exc)}.",
            remediation="Fix the YAML syntax and retry.",
        ) from exc
    if not isinstance(data, dict):
        raise ConfigError(
            f"Parsing {path}",
            cause="Top-level config must be a mapping of keys to values.",
            remediation=f'Start the file with `version: "{SUPPORTED_VERSION}"`.',
        )
    return data


def _yaml_location(exc: yaml.YAMLError) -> str:
    """Render a ' at line L, column C' suffix when the marker is available."""
    mark = getattr(exc, "problem_mark", None)
    if mark is None:
        return ""
    return f" at line {mark.line + 1}, column {mark.column + 1}"


def _check_version(data: dict[str, object], path: Path) -> None:
    """Validate the required ``version`` field before model construction."""
    version = data.get("version")
    if version is None:
        raise ConfigError(
            f"Loading {path}",
            cause="Missing required field 'version'.",
            remediation=f'Add `version: "{SUPPORTED_VERSION}"` to the top of the file.',
        )
    if str(version) != SUPPORTED_VERSION:
        raise ConfigError(
            f"Loading {path}",
            cause=(
                f"Config version {version} is not supported by engine "
                f"{ENGINE_VERSION_LABEL}."
            ),
            remediation=(
                "Pin the engine to a matching major version or downgrade the "
                f"config to version {SUPPORTED_VERSION}."
            ),
        )


def _validate_model(data: dict[str, object], path: Path) -> Config:
    """Construct the Config model, rendering pydantic errors as a path list."""
    try:
        return Config.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(
            f"Validating {path}",
            cause="Config does not satisfy the schema:\n" + _format_errors(exc),
            remediation=f"Fix the fields listed above; see {CONFIG_DOC}.",
        ) from exc


def _format_errors(exc: ValidationError) -> str:
    """Render pydantic errors as ``  - path: message`` lines."""
    lines = []
    for err in exc.errors():
        path = _error_path(err["loc"])
        lines.append(f"  - {path}: {err['msg']}")
    return "\n".join(lines)


def _error_path(loc: tuple[object, ...]) -> str:
    """Join a pydantic ``loc`` into a dotted YAML path, dropping union tags."""
    parts = [str(part) for part in loc if str(part) not in ACTION_TAGS]
    return ".".join(parts) if parts else "<root>"


def _reject_ai_refine_without_commercial(
    config: Config, commercial_installed: bool
) -> None:
    """Reject ``ai_refine`` actions when the commercial layer is absent."""
    if commercial_installed:
        return
    offenders = [
        f"tables.{table}.columns.{column}"
        for table, column, action in _iter_actions(config)
        if action == "ai_refine"
    ]
    if not offenders:
        return
    raise ConfigError(
        "Validating ai_refine actions",
        cause=(
            "Action 'ai_refine' requires the commercial layer, which is not "
            "installed: " + ", ".join(offenders)
        ),
        remediation=(
            "Install privaci-commercial, or switch these columns to a Level-1/2 "
            f"action; see {CONFIG_DOC}#actions."
        ),
    )


def _iter_actions(config: Config) -> Iterator[tuple[str, str, str]]:
    """Yield ``(table, column, action_tag)`` for every configured column."""
    for table_name, table in config.tables.items():
        for column_name, action in table.columns.items():
            yield table_name, column_name, action.action


def check_null_actions(config: Config, not_null_columns: dict[str, set[str]]) -> None:
    """Reject ``null`` actions on ``NOT NULL`` columns (pre-flight helper).

    Args:
        config: The validated config.
        not_null_columns: Mapping of table name to the set of its ``NOT NULL``
            column names, as discovered by the catalog.

    Raises:
        ConfigError: When any column with a ``null`` action is ``NOT NULL``.
    """
    offenders = [
        f"tables.{table}.columns.{column}"
        for table, column, action in _iter_actions(config)
        if action == "null" and column in not_null_columns.get(table, set())
    ]
    if not offenders:
        return
    raise ConfigError(
        "Validating null actions",
        cause="Action 'null' targets NOT NULL columns: " + ", ".join(offenders),
        remediation=(
            "Use a non-null action (fake, static, hash) or alter the source "
            f"column to be nullable; see {CONFIG_DOC}#actions."
        ),
    )


def is_commercial_installed() -> bool:
    """Return True when a plugin package is registered via entry points."""
    eps = importlib.metadata.entry_points(group=PLUGIN_GROUP)
    return any(
        ep.name == "license_validator" or ep.name.startswith("llm_connector.")
        for ep in eps
    )


def export_json_schema() -> str:
    """Return the Config JSON Schema as an indented JSON string."""
    return json.dumps(Config.model_json_schema(), indent=2, sort_keys=True)


def migrate_config(source: str, target: str) -> str:
    """Compute a config migration message for the ``migrate-config`` command.

    Args:
        source: The ``--from`` schema version.
        target: The ``--to`` schema version.

    Returns:
        A human-readable result message when no migration is needed.

    Raises:
        ConfigError: When a migration between distinct versions is requested;
            no migration paths are defined in this release.
    """
    if source == target:
        return f"No migration needed: config is already version {target}."
    raise ConfigError(
        f"Migrating config from {source} to {target}",
        cause="No migration path is defined between these versions.",
        remediation=f"Only version {SUPPORTED_VERSION} is supported in this release.",
    )
