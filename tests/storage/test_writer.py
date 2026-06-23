"""Tests for object write dispatch."""

from __future__ import annotations

from pathlib import Path

import pytest

from privaci.contracts.fallbacks import CommunityObjectWriter
from privaci.errors import ConfigError
from privaci.storage import write_object
from privaci.storage.writer import redact_object_uri


def test_community_writes_local_file(tmp_path: Path) -> None:
    destination = tmp_path / "report.json"
    writer = CommunityObjectWriter()

    writer.write(str(destination), b'{"ok": true}', content_type="application/json")

    assert destination.read_bytes() == b'{"ok": true}'


def test_community_rejects_s3_uri() -> None:
    writer = CommunityObjectWriter()

    with pytest.raises(ConfigError, match="Cloud object URIs"):
        writer.write("s3://bucket/key.json", b"{}")


def test_write_object_uses_plugin(mocker: pytest.Mock, tmp_path: Path) -> None:
    destination = tmp_path / "out.json"
    fake_writer = mocker.Mock()
    bundle = mocker.patch("privaci.storage.writer.load_plugins").return_value
    bundle.object_writer = fake_writer

    write_object(str(destination), b"data")

    fake_writer.write.assert_called_once_with(
        str(destination), b"data", content_type=None
    )


def test_redact_object_uri_hides_s3_key() -> None:
    assert redact_object_uri("s3://bucket/secret/path.json") == "s3://<redacted>"
