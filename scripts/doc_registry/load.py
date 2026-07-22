"""Load and parse ``docs/registry.yaml``."""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover — PyYAML is a project dependency
    yaml = None  # type: ignore[assignment]

from doc_registry.models import REGISTRY_PATH, Registry, RegistryEntry


class RegistryLoadError(Exception):
    """Raised when ``docs/registry.yaml`` cannot be read or parsed."""


def _parse_entry(item: dict[str, Any]) -> RegistryEntry:
    entry_id = item.get("id")
    if not isinstance(entry_id, str) or not entry_id:
        raise ValueError("registry entry missing non-empty id")
    code = item.get("code") or []
    docs = item.get("docs") or []
    if not isinstance(code, list) or not isinstance(docs, list):
        raise ValueError(f"entry {entry_id!r}: code and docs must be lists")
    changelog = item.get("changelog", "optional")
    if changelog not in {"optional", "required"}:
        raise ValueError(f"entry {entry_id!r}: changelog must be optional or required")
    waiver = item.get("waiver")
    if waiver is not None and not isinstance(waiver, str):
        raise ValueError(f"entry {entry_id!r}: waiver must be a string")
    return RegistryEntry(
        id=entry_id,
        code=tuple(str(c) for c in code),
        docs=tuple(str(d) for d in docs),
        changelog=str(changelog),
        waiver=str(waiver) if waiver else None,
    )


def _parse_registry(raw: object) -> Registry:
    if not isinstance(raw, dict):
        raise ValueError("registry root must be a mapping")
    meta = raw.get("meta") or {}
    excludes = meta.get("exclude_packages") or []
    if not isinstance(excludes, list):
        raise ValueError("meta.exclude_packages must be a list")
    entries_raw = raw.get("entries")
    if not isinstance(entries_raw, list):
        raise ValueError("entries must be a list")
    entries: list[RegistryEntry] = []
    for item in entries_raw:
        if not isinstance(item, dict):
            raise ValueError("each registry entry must be a mapping")
        entries.append(_parse_entry(item))
    return Registry(
        exclude_packages=frozenset(str(x) for x in excludes),
        entries=tuple(entries),
    )


def load_registry(path: Path = REGISTRY_PATH) -> Registry:
    """Load and minimally parse the registry YAML.

    Raises:
        RegistryLoadError: On missing PyYAML, I/O failure, invalid YAML, or
            schema validation failure.
    """
    if yaml is None:
        raise RegistryLoadError("PyYAML is required to load docs/registry.yaml")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RegistryLoadError(f"cannot read registry: {exc}") from exc
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise RegistryLoadError(f"invalid registry YAML: {exc}") from exc
    try:
        return _parse_registry(raw)
    except ValueError as exc:
        raise RegistryLoadError(str(exc)) from exc
