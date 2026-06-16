"""Fetch, verify, preview, and merge vertical config packs."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

import typer
import yaml

from privaci.errors import ConfigError
from privaci.packs.verify import verify_manifest_signature

logger = logging.getLogger(__name__)

DEFAULT_REGISTRY_URL = (
    "https://raw.githubusercontent.com/boundarylogic/config-packs/main"
)


def fetch_manifest(
    pack_name: str,
    *,
    registry_url: str = DEFAULT_REGISTRY_URL,
    local_dir: Path | None = None,
) -> dict[str, Any]:
    """Load a pack manifest from the registry or a local directory."""
    if local_dir is not None:
        path = local_dir / pack_name / "manifest.json"
        if not path.is_file():
            raise ConfigError(
                "Fetching config pack manifest",
                cause=f"Pack {pack_name!r} not found under {local_dir}.",
                remediation="Check the pack name or --local-pack-dir path.",
            )
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        return data

    url = f"{registry_url.rstrip('/')}/packs/{pack_name}/manifest.json"
    try:
        with urlopen(url, timeout=30) as response:  # noqa: S310 — registry URL
            payload = response.read()
    except URLError as exc:
        raise ConfigError(
            "Fetching config pack manifest",
            cause=f"Could not download pack manifest from registry ({url}).",
            remediation=(
                "Check network access or pass --local-pack-dir for offline use."
            ),
        ) from exc
    remote: dict[str, Any] = json.loads(payload.decode("utf-8"))
    return remote


def merge_config(base: dict[str, Any], fragment: dict[str, Any]) -> dict[str, Any]:
    """Shallow-merge ``fragment`` into a copy of ``base`` (tables deep-merged)."""
    merged = dict(base)
    for key, value in fragment.items():
        if key == "tables" and isinstance(value, dict):
            tables = dict(merged.get("tables", {}))
            for table_id, table_cfg in value.items():
                existing = tables.get(table_id, {})
                if isinstance(existing, dict) and isinstance(table_cfg, dict):
                    tables[table_id] = {**existing, **table_cfg}
                else:
                    tables[table_id] = table_cfg
            merged["tables"] = tables
        else:
            merged[key] = value
    return merged


def preview_merge(base: dict[str, Any], fragment: dict[str, Any]) -> str:
    """Return a human-readable diff summary (value-free, keys only)."""
    merged = merge_config(base, fragment)
    added_tables = sorted(set(merged.get("tables", {})) - set(base.get("tables", {})))
    changed_top = sorted(
        key for key in fragment if key != "tables" and merged.get(key) != base.get(key)
    )
    lines = ["Pack would change:"]
    for key in changed_top:
        lines.append(f"  top-level: {key}")
    for table_id in added_tables:
        lines.append(f"  add table: {table_id}")
    if len(lines) == 1:
        lines.append("  (no visible changes — pack may reinforce existing settings)")
    return "\n".join(lines)


def install_pack(
    pack_name: str,
    *,
    config_path: Path,
    registry_url: str = DEFAULT_REGISTRY_URL,
    local_dir: Path | None = None,
    assume_yes: bool = False,
) -> None:
    """Verify, preview, and optionally merge a config pack into ``config_path``."""
    fragment = _load_pack_fragment(
        pack_name, registry_url=registry_url, local_dir=local_dir
    )
    base = _load_base_config(config_path)
    typer.echo(preview_merge(base, fragment))
    if not _confirm_pack_install(assume_yes):
        return
    _write_merged_pack(config_path, pack_name, base, fragment)


def _load_pack_fragment(
    pack_name: str,
    *,
    registry_url: str,
    local_dir: Path | None,
) -> dict[str, Any]:
    manifest = fetch_manifest(pack_name, registry_url=registry_url, local_dir=local_dir)
    verify_manifest_signature(manifest)
    fragment = manifest.get("config_fragment")
    if not isinstance(fragment, dict):
        raise ConfigError(
            "Installing config pack",
            cause="Manifest config_fragment is missing or not an object.",
            remediation="Use a pack published for this engine version.",
        )
    return fragment


def _load_base_config(config_path: Path) -> dict[str, Any]:
    if not config_path.is_file():
        raise ConfigError(
            "Installing config pack",
            cause=f"Config file {config_path} does not exist.",
            remediation="Create mask-rules.yaml first or pass --config.",
        )
    base = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(base, dict):
        raise ConfigError(
            "Installing config pack",
            cause="Config file root must be a mapping.",
            remediation="Fix mask-rules.yaml syntax before installing a pack.",
        )
    return base


def _confirm_pack_install(assume_yes: bool) -> bool:
    if assume_yes:
        return True
    confirmed = typer.confirm("Apply this pack to the local config?", default=False)
    if not confirmed:
        typer.echo("Install cancelled; no files modified.")
        return False
    return True


def _write_merged_pack(
    config_path: Path,
    pack_name: str,
    base: dict[str, Any],
    fragment: dict[str, Any],
) -> None:
    merged = merge_config(base, fragment)
    config_path.write_text(
        yaml.safe_dump(merged, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    typer.echo(f"Merged pack {pack_name!r} into {config_path}")
    logger.info(
        "Config pack installed",
        extra={"event": "pack.installed", "pack": pack_name},
    )
