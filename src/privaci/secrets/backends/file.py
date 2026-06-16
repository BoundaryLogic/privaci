"""Resolve file:// secret URIs."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from privaci.errors import SecretError
from privaci.secrets.backends.constants import MAX_SECRET_FILE_BYTES
from privaci.secrets.parser import ParsedSecretUri

logger = logging.getLogger(__name__)

_FILE_ROOTS_ENV = "PRIVACI_SECRET_FILE_ROOTS"
_DEFAULT_ROOTS = ("/run/secrets", "/var/run/secrets")


def _allowed_roots() -> tuple[Path, ...]:
    """Return resolved directory roots that file:// paths must stay under."""
    raw = os.environ.get(_FILE_ROOTS_ENV, "").strip()
    if raw:
        entries = [entry.strip() for entry in raw.split(":") if entry.strip()]
        return tuple(Path(entry).resolve() for entry in entries)
    return tuple(Path(entry).resolve() for entry in _DEFAULT_ROOTS)


def _is_under_allowed_root(path: Path) -> bool:
    resolved = path.resolve()
    for root in _allowed_roots():
        try:
            resolved.relative_to(root)
        except ValueError:
            continue
        return True
    return False


def resolve_file_uri(parsed: ParsedSecretUri) -> str:
    """Read a secret from a file on disk.

    Args:
        parsed: Parsed file:// URI (absolute path required).

    Returns:
        File contents with trailing newlines stripped.

    Raises:
        SecretError: If the path is unsafe, outside allowed roots, or unreadable.
    """
    path = Path(parsed.file_path)
    resolved = _validate_file_path(parsed, path)
    return _read_secret_file(parsed, resolved)


def _validate_file_path(parsed: ParsedSecretUri, path: Path) -> Path:
    if not path.is_absolute():
        raise SecretError(
            f"file:// URI must use an absolute path, got {parsed.file_path!r}",
        )
    if path.is_symlink():
        raise SecretError(
            "Reading a file:// secret",
            cause="Symlink paths are not allowed for secret files.",
            remediation="Use a regular file under an allowed secrets directory.",
        )
    resolved = path.resolve()
    if not _is_under_allowed_root(resolved):
        raise SecretError(
            "Reading a file:// secret",
            cause=f"Path {parsed.file_path!r} is outside allowed secret roots.",
            remediation=(
                f"Place secrets under {_FILE_ROOTS_ENV} directories "
                "(default: /run/secrets, /var/run/secrets)."
            ),
        )
    if not resolved.is_file():
        raise SecretError(f"Secret file does not exist: {parsed.file_path!r}")
    size = resolved.stat().st_size
    if size > MAX_SECRET_FILE_BYTES:
        raise SecretError(
            "Reading a file:// secret",
            cause=f"Secret file exceeds {MAX_SECRET_FILE_BYTES} byte limit.",
            remediation="Store large material elsewhere; secrets must be small.",
        )
    return resolved


def _read_secret_file(parsed: ParsedSecretUri, resolved: Path) -> str:
    try:
        text = resolved.read_text(encoding="utf-8")
    except OSError as exc:
        logger.error(
            "Secret file read failed",
            extra={"path": parsed.file_path},
        )
        raise SecretError(f"Cannot read secret file {parsed.file_path!r}") from exc
    if not text.strip():
        raise SecretError(f"Secret file is empty: {parsed.file_path!r}")
    return text.strip()
