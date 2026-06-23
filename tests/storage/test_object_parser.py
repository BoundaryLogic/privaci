"""Tests for object URI parsing."""

from __future__ import annotations

import pytest

from privaci.errors import StorageError
from privaci.storage.parser import ObjectUriKind, parse_object_uri


def test_parse_local_bare_path() -> None:
    parsed = parse_object_uri("./reports/out.json")

    assert parsed.kind is ObjectUriKind.LOCAL
    assert parsed.path == "./reports/out.json"


def test_parse_file_uri() -> None:
    parsed = parse_object_uri("file:///tmp/report.json")

    assert parsed.kind is ObjectUriKind.FILE
    assert parsed.path == "/tmp/report.json"


def test_parse_s3_uri() -> None:
    parsed = parse_object_uri(
        "s3://evidence/privaci/run-1/report.json?region=us-east-1"
    )

    assert parsed.kind is ObjectUriKind.S3
    assert parsed.bucket == "evidence"
    assert parsed.key == "privaci/run-1/report.json"
    assert parsed.query_dict()["region"] == "us-east-1"


def test_parse_azure_blob_uri() -> None:
    parsed = parse_object_uri("azure-blob://acct/container/blob.json")

    assert parsed.kind is ObjectUriKind.AZURE_BLOB
    assert parsed.account == "acct"
    assert parsed.container == "container"
    assert parsed.blob == "blob.json"


def test_unknown_scheme_raises() -> None:
    with pytest.raises(StorageError, match="Unsupported object URI scheme"):
        parse_object_uri("ftp://host/path")
