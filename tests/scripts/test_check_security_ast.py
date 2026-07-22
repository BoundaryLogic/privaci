"""Tests for scripts/check_security_ast.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.scripts.conftest_helpers import ensure_scripts_path, write_py

_REPO_ROOT = Path(__file__).resolve().parents[2]

ensure_scripts_path()
import security_ast as _lib  # noqa: E402


def _empty_allowlist(root: Path) -> None:
    path = root / "scripts" / "security_ast_allowlist.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")


def test_collect_findings_flags_eval(tmp_path: Path) -> None:
    # Arrange
    write_py(
        tmp_path,
        "src/privaci/mask/evil.py",
        """
        def run_code(src: str) -> object:
            return eval(src)
        """,
    )
    _empty_allowlist(tmp_path)

    # Act
    findings = _lib.collect_findings(tmp_path)

    # Assert
    assert any(f.rule == "dynamic-exec" for f in findings)


def test_collect_findings_flags_subprocess_shell_true(tmp_path: Path) -> None:
    # Arrange
    write_py(
        tmp_path,
        "src/privaci/config/runner.py",
        """
        import subprocess

        def run_cmd(cmd: str) -> None:
            subprocess.run(cmd, shell=True)
        """,
    )
    _empty_allowlist(tmp_path)

    # Act
    findings = _lib.collect_findings(tmp_path)

    # Assert
    assert any(f.rule == "subprocess-shell" for f in findings)


def test_collect_findings_flags_subprocess_alias_shell_true(tmp_path: Path) -> None:
    # Arrange
    write_py(
        tmp_path,
        "src/privaci/config/runner.py",
        """
        import subprocess as sp

        def run_cmd(cmd: str) -> None:
            sp.run(cmd, shell=True)
        """,
    )
    _empty_allowlist(tmp_path)

    # Act
    findings = _lib.collect_findings(tmp_path)

    # Assert
    assert any(f.rule == "subprocess-shell" for f in findings)


def test_collect_findings_flags_sql_keyword_arg(tmp_path: Path) -> None:
    # Arrange
    write_py(
        tmp_path,
        "src/privaci/stream/query.py",
        """
        async def load(source, table: str) -> None:
            await source.execute(query=f"SELECT * FROM {table}")
        """,
    )
    _empty_allowlist(tmp_path)

    # Act
    findings = _lib.collect_findings(tmp_path)

    # Assert
    assert any(f.rule == "sql-concat" for f in findings)


def test_collect_findings_flags_subprocess_from_import_alias(
    tmp_path: Path,
) -> None:
    # Arrange
    write_py(
        tmp_path,
        "src/privaci/config/runner.py",
        """
        from subprocess import run as sp_run

        def run_cmd(cmd: str) -> None:
            sp_run(cmd, shell=True)
        """,
    )
    _empty_allowlist(tmp_path)

    # Act
    findings = _lib.collect_findings(tmp_path)

    # Assert
    assert any(f.rule == "subprocess-shell" for f in findings)


def test_collect_findings_flags_sql_concat(tmp_path: Path) -> None:
    # Arrange
    write_py(
        tmp_path,
        "src/privaci/stream/query.py",
        """
        async def load(source, table: str) -> None:
            query = f"SELECT * FROM {table}"
            await source.execute(query)
        """,
    )
    _empty_allowlist(tmp_path)

    # Act
    findings = _lib.collect_findings(tmp_path)

    # Assert
    assert any(f.rule == "sql-concat" for f in findings)


@pytest.mark.parametrize(
    "snippet",
    [
        'query = "SELECT " + table\n            await source.execute(query)',
        'query = "SELECT %s" % table\n            await source.execute(query)',
        'query = "SELECT {}".format(table)\n            await source.execute(query)',
        'await source.execute("SELECT " + table)',
    ],
)
def test_collect_findings_flags_non_fstring_sql(tmp_path: Path, snippet: str) -> None:
    # Arrange
    write_py(
        tmp_path,
        "src/privaci/stream/query.py",
        f"""
        async def load(source, table: str) -> None:
            {snippet}
        """,
    )
    _empty_allowlist(tmp_path)

    # Act
    findings = _lib.collect_findings(tmp_path)

    # Assert
    assert any(f.rule == "sql-concat" for f in findings)


def test_collect_findings_flags_article_i_http_import(tmp_path: Path) -> None:
    # Arrange
    write_py(
        tmp_path,
        "src/privaci/mask/client.py",
        """
        import httpx

        def fetch_model() -> None:
            return None
        """,
    )
    _empty_allowlist(tmp_path)

    # Act
    findings = _lib.collect_findings(tmp_path)

    # Assert
    assert any(f.rule == "article-i-import" for f in findings)


def test_secrets_urllib_parse_is_allowed(tmp_path: Path) -> None:
    # Arrange
    write_py(
        tmp_path,
        "src/privaci/secrets/parser.py",
        """
        from urllib.parse import urlparse

        def parse(url: str) -> str:
            return urlparse(url).scheme
        """,
    )
    _empty_allowlist(tmp_path)

    # Act
    findings = _lib.collect_findings(tmp_path)

    # Assert
    assert findings == []


def test_allowlist_suppresses_sql_concat(tmp_path: Path) -> None:
    # Arrange
    write_py(
        tmp_path,
        "src/privaci/stream/query.py",
        """
        async def load(source, table: str) -> None:
            query = f"SELECT * FROM {table}"
            await source.execute(query)
        """,
    )
    allowlist = tmp_path / "scripts" / "security_ast_allowlist.txt"
    allowlist.parent.mkdir(parents=True, exist_ok=True)
    allowlist.write_text(
        "src/privaci/stream/query.py:load # issue #100\n", encoding="utf-8"
    )

    # Act
    findings = _lib.collect_findings(tmp_path)

    # Assert
    assert findings == []


def test_collect_findings_flags_logging_interpolation(tmp_path: Path) -> None:
    # Arrange
    write_py(
        tmp_path,
        "src/privaci/mask/loggy.py",
        """
        import logging

        logger = logging.getLogger(__name__)

        def emit(email: str) -> None:
            logger.info(f"user={email}")
        """,
    )
    _empty_allowlist(tmp_path)

    # Act
    findings = _lib.collect_findings(tmp_path)

    # Assert
    assert any(f.rule == "logging-interpolation" for f in findings)


def test_collect_findings_flags_aiohttp_import(tmp_path: Path) -> None:
    # Arrange
    write_py(
        tmp_path,
        "src/privaci/pipeline/net.py",
        """
        import aiohttp

        def client() -> None:
            return None
        """,
    )
    _empty_allowlist(tmp_path)

    # Act
    findings = _lib.collect_findings(tmp_path)

    # Assert
    assert any(f.rule == "article-i-import" for f in findings)


def test_collect_findings_flags_urllib_parent_import(tmp_path: Path) -> None:
    # Arrange
    write_py(
        tmp_path,
        "src/privaci/mask/net.py",
        """
        import urllib

        def open_url() -> None:
            return None
        """,
    )
    _empty_allowlist(tmp_path)

    # Act
    findings = _lib.collect_findings(tmp_path)

    # Assert
    assert any(f.rule == "article-i-import" for f in findings)


def test_collect_findings_flags_packaging_import(tmp_path: Path) -> None:
    # Arrange
    write_py(
        tmp_path,
        "src/privaci/cli/leak.py",
        """
        import privaci_commercial

        def touch() -> None:
            return None
        """,
    )
    _empty_allowlist(tmp_path)

    # Act
    findings = _lib.collect_findings(tmp_path)

    # Assert
    assert any(f.rule == "packaging-import" for f in findings)


def test_collect_findings_flags_logging_extra_pii_key(tmp_path: Path) -> None:
    # Arrange
    write_py(
        tmp_path,
        "src/privaci/mask/loggy.py",
        """
        import logging

        logger = logging.getLogger(__name__)

        def emit(email: str) -> None:
            logger.info("masked", extra={"email": email})
        """,
    )
    _empty_allowlist(tmp_path)

    # Act
    findings = _lib.collect_findings(tmp_path)

    # Assert
    assert any(f.rule == "logging-pii-extra" for f in findings)


def test_invalid_allowlist_raises(tmp_path: Path) -> None:
    # Arrange
    allowlist = tmp_path / "scripts" / "security_ast_allowlist.txt"
    allowlist.parent.mkdir(parents=True, exist_ok=True)
    allowlist.write_text("bad-entry\n", encoding="utf-8")
    write_py(tmp_path, "src/privaci/mask/ok.py", "x = 1\n")

    # Act / Assert
    with pytest.raises(ValueError, match="invalid allowlist/waiver"):
        _lib.collect_findings(tmp_path)


def test_symbol_allowlist_does_not_hide_eval(tmp_path: Path) -> None:
    # Arrange
    write_py(
        tmp_path,
        "src/privaci/mask/evil.py",
        """
        def run_code(src: str) -> object:
            return eval(src)
        """,
    )
    allowlist = tmp_path / "scripts" / "security_ast_allowlist.txt"
    allowlist.parent.mkdir(parents=True, exist_ok=True)
    allowlist.write_text(
        "src/privaci/mask/evil.py:run_code # issue #100\n",
        encoding="utf-8",
    )

    # Act
    findings = _lib.collect_findings(tmp_path)

    # Assert
    assert any(f.rule == "dynamic-exec" for f in findings)


def test_collect_findings_flags_subprocess_kwargs_shell(tmp_path: Path) -> None:
    # Arrange
    write_py(
        tmp_path,
        "src/privaci/config/runner.py",
        """
        import subprocess

        def run_cmd(cmd: str) -> None:
            opts = {"shell": True}
            subprocess.run(cmd, **opts)
        """,
    )
    _empty_allowlist(tmp_path)

    # Act
    findings = _lib.collect_findings(tmp_path)

    # Assert
    assert any(f.rule == "subprocess-shell" for f in findings)


def test_collect_findings_flags_subprocess_star_import(tmp_path: Path) -> None:
    # Arrange
    write_py(
        tmp_path,
        "src/privaci/config/runner.py",
        """
        from subprocess import *

        def run_cmd(cmd: str) -> None:
            run(cmd, shell=True)
        """,
    )
    _empty_allowlist(tmp_path)

    # Act
    findings = _lib.collect_findings(tmp_path)

    # Assert
    assert any(f.rule == "subprocess-shell" for f in findings)


def test_collect_findings_flags_subprocess_shell_name(tmp_path: Path) -> None:
    # Arrange
    write_py(
        tmp_path,
        "src/privaci/config/runner.py",
        """
        import subprocess

        def run_cmd(cmd: str, use_shell: bool) -> None:
            subprocess.run(cmd, shell=use_shell)
        """,
    )
    _empty_allowlist(tmp_path)

    # Act
    findings = _lib.collect_findings(tmp_path)

    # Assert
    assert any(f.rule == "subprocess-shell" for f in findings)


def test_collect_findings_flags_sql_name_flow_across_stmts(tmp_path: Path) -> None:
    # Arrange
    write_py(
        tmp_path,
        "src/privaci/stream/query.py",
        """
        async def load(source, table: str) -> None:
            built = "SELECT " + table
            await source.execute(built)
        """,
    )
    _empty_allowlist(tmp_path)

    # Act
    findings = _lib.collect_findings(tmp_path)

    # Assert
    assert any(f.rule == "sql-concat" for f in findings)


def test_collect_findings_flags_sql_annassign_name_flow(tmp_path: Path) -> None:
    # Arrange
    write_py(
        tmp_path,
        "src/privaci/stream/query.py",
        """
        async def load(source, table: str) -> None:
            built: str = "SELECT " + table
            await source.execute(built)
        """,
    )
    _empty_allowlist(tmp_path)

    # Act
    findings = _lib.collect_findings(tmp_path)

    # Assert
    assert any(f.rule == "sql-concat" for f in findings)


def test_collect_findings_flags_importlib_http(tmp_path: Path) -> None:
    # Arrange
    write_py(
        tmp_path,
        "src/privaci/mask/dyn.py",
        """
        import importlib

        def load_client() -> object:
            return importlib.import_module("httpx")
        """,
    )
    _empty_allowlist(tmp_path)

    # Act
    findings = _lib.collect_findings(tmp_path)

    # Assert
    assert any(f.rule == "article-i-import" for f in findings)


def test_collect_findings_flags_importlib_non_constant(tmp_path: Path) -> None:
    # Arrange
    write_py(
        tmp_path,
        "src/privaci/mask/dyn.py",
        """
        import importlib

        def load_client(name: str) -> object:
            return importlib.import_module(name)
        """,
    )
    _empty_allowlist(tmp_path)

    # Act
    findings = _lib.collect_findings(tmp_path)

    # Assert
    assert any(f.rule == "article-i-import" for f in findings)


def test_collect_findings_flags_logging_pii_name(tmp_path: Path) -> None:
    # Arrange
    write_py(
        tmp_path,
        "src/privaci/mask/loggy.py",
        """
        import logging

        logger = logging.getLogger(__name__)

        def emit(user_email: str) -> None:
            logger.info(user_email)
        """,
    )
    _empty_allowlist(tmp_path)

    # Act
    findings = _lib.collect_findings(tmp_path)

    # Assert
    assert any(f.rule == "logging-pii-name" for f in findings)
