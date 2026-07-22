"""Glob matching helpers for registry code and doc paths.

Supports exact paths, ``dir/**`` recursive prefixes, and simple ``*`` / ``?``
segments via ``fnmatch``. Mid-path ``**`` (for example ``src/**/foo.py``) is
rejected at validation time — it never matched and must not fail open.
"""

from __future__ import annotations

import fnmatch


def unsupported_glob_reason(pattern: str) -> str | None:
    """Return an error message when ``pattern`` uses unsupported ``**`` placement."""
    normalized = pattern.replace("\\", "/")
    if "**" not in normalized:
        return None
    if normalized.endswith("/**") and normalized.count("**") == 1:
        return None
    return (
        f"unsupported glob {pattern!r}: only exact paths, simple *?[] globs, "
        "or trailing 'dir/**' prefixes are allowed (mid-path ** never matches)"
    )


def path_matches_glob(rel_path: str, pattern: str) -> bool:
    """Return True when ``rel_path`` matches a registry glob."""
    if unsupported_glob_reason(pattern) is not None:
        return False
    normalized = rel_path.replace("\\", "/").lstrip("./")
    normalized_pattern = pattern.replace("\\", "/")

    if "**" not in normalized_pattern and any(
        ch in normalized_pattern for ch in "*?[]"
    ):
        return fnmatch.fnmatchcase(normalized, normalized_pattern)

    if normalized_pattern.endswith("/**"):
        prefix = normalized_pattern[:-3]
        return normalized == prefix or normalized.startswith(f"{prefix}/")

    return normalized == normalized_pattern
