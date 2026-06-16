"""Tests for config pack install and signature verification."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from privaci.cli.app import app
from privaci.errors import ConfigError
from privaci.packs.install import fetch_manifest, install_pack, merge_config
from privaci.packs.keys import PACK_PUBLIC_KEY_ENV
from privaci.packs.verify import verify_manifest_signature

runner = CliRunner()
FIXTURE_PACK_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "packs"


def test_fetch_local_manifest() -> None:
    # Act
    manifest = fetch_manifest("hipaa", local_dir=FIXTURE_PACK_DIR)

    # Assert
    assert manifest["name"] == "hipaa"
    verify_manifest_signature(manifest)


def test_invalid_signature_raises() -> None:
    # Arrange
    manifest = fetch_manifest("hipaa", local_dir=FIXTURE_PACK_DIR)
    manifest = dict(manifest)
    manifest["signature"] = "AAAA"

    # Act / Assert
    with pytest.raises(ConfigError, match="signature"):
        verify_manifest_signature(manifest)


def test_verify_fails_closed_without_trust_anchor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    monkeypatch.delenv(PACK_PUBLIC_KEY_ENV, raising=False)
    manifest = fetch_manifest("hipaa", local_dir=FIXTURE_PACK_DIR)

    # Act / Assert
    with pytest.raises(ConfigError, match="No trusted config-pack public key"):
        verify_manifest_signature(manifest)


def test_install_aborts_before_write_without_trust_anchor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    monkeypatch.delenv(PACK_PUBLIC_KEY_ENV, raising=False)
    config = tmp_path / "mask-rules.yaml"
    original = yaml.safe_dump({"version": "1.0", "tables": {}})
    config.write_text(original, encoding="utf-8")

    # Act / Assert: signature gate must fire before the config file is touched.
    with pytest.raises(ConfigError, match="No trusted config-pack public key"):
        install_pack(
            "hipaa",
            config_path=config,
            local_dir=FIXTURE_PACK_DIR,
            assume_yes=True,
        )
    assert config.read_text(encoding="utf-8") == original


def test_merge_config_deep_merges_tables() -> None:
    # Arrange
    base = {"version": "1.0", "tables": {"public.users": {"strategy": "transform"}}}
    fragment = {"tables": {"public.users": {"columns": {"email": {"action": "hash"}}}}}

    # Act
    merged = merge_config(base, fragment)

    # Assert
    assert merged["tables"]["public.users"]["strategy"] == "transform"
    assert merged["tables"]["public.users"]["columns"]["email"]["action"] == "hash"


def test_install_pack_cancelled_when_user_declines(tmp_path: Path) -> None:
    # Arrange
    config = tmp_path / "mask-rules.yaml"
    config.write_text(
        yaml.safe_dump({"version": "1.0", "tables": {}}), encoding="utf-8"
    )

    # Act
    runner.invoke(
        app,
        [
            "install-pack",
            "hipaa",
            "--config",
            str(config),
            "--local-pack-dir",
            str(FIXTURE_PACK_DIR),
        ],
        input="n\n",
    )

    # Assert
    data = yaml.safe_load(config.read_text())
    assert "strict_autodetect" not in data


def test_install_pack_applies_with_yes(tmp_path: Path) -> None:
    # Arrange
    config = tmp_path / "mask-rules.yaml"
    config.write_text(
        yaml.safe_dump({"version": "1.0", "tables": {}}), encoding="utf-8"
    )

    # Act
    install_pack(
        "hipaa",
        config_path=config,
        local_dir=FIXTURE_PACK_DIR,
        assume_yes=True,
    )

    # Assert
    data = yaml.safe_load(config.read_text())
    assert data["strict_autodetect"] is True
    assert "clinical.patients" in data["tables"]
