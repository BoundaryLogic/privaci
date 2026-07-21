"""Bounded regex substitution for regex_mask actions.

Protection against catastrophic backtracking (ReDoS) is layered:

1. Parse time: :func:`reject_redos_prone_pattern` rejects common pattern
   *shapes* that nest unbounded quantifiers inside a single-level group
   (for example ``(a+)+``). The screen uses a non-recursive regex and does
   **not** walk nested groups — shapes such as ``((a+)b)*`` may still pass.
2. Run time: :func:`safe_regex_sub` caps the input length per value (64 KiB).
   That bounds input size, not worst-case backtracking time on adversarial
   patterns that slip past layer 1.

The substitution runs in-process. An earlier thread-timeout approach could not
preempt CPython's GIL-bound ``re`` engine. Treat layer 1 as a best-effort
shape screen, not a complete ReDoS proof; prefer simple patterns.
"""

from __future__ import annotations

import re
from functools import lru_cache

from privaci.errors import MaskingError

_REGEX_MASK_MAX_INPUT_LEN = 65_536

# A group followed by an *unbounded* quantifier (``*``, ``+`` or ``{n,}``).
_QUANTIFIED_GROUP = re.compile(r"\(([^()]*)\)(?:[*+]|\{\d+,\})")
# Inside such a group, an unbounded quantifier or an alternation is the classic
# catastrophic-backtracking shape: ``(a+)+``, ``(a*)*``, ``(.*)*``, ``(a|a)*``.
_INNER_RISK = re.compile(r"[*+]|\{\d+,\}")


def reject_redos_prone_pattern(pattern: str) -> str:
    """Reject regex patterns whose shape risks catastrophic backtracking.

    Args:
        pattern: The user-supplied regular expression.

    Returns:
        The unchanged pattern when it passes the shape screen.

    Raises:
        ValueError: When the pattern matches a known backtracking-prone shape.
    """
    for match in _QUANTIFIED_GROUP.finditer(pattern):
        body = match.group(1)
        if _INNER_RISK.search(body) or "|" in body:
            msg = (
                "pattern applies an unbounded quantifier to a group containing a "
                "nested quantifier or alternation, which risks catastrophic "
                "backtracking"
            )
            raise ValueError(msg)
    return pattern


def safe_regex_sub(
    pattern: str,
    repl: str,
    value: str,
    *,
    flags: int = 0,
) -> str:
    """Apply ``re.sub`` with a per-value input-length bound.

    Args:
        pattern: Compiled pattern source string.
        repl: Replacement string.
        value: Cell value to transform.
        flags: Bitwise ``re`` flags.

    Returns:
        The substituted string.

    Raises:
        MaskingError: When the input exceeds the length cap.
    """
    _reject_oversized_input(value)
    return _compiled_pattern(pattern, flags).sub(repl, value)


def _reject_oversized_input(value: str) -> None:
    if len(value) <= _REGEX_MASK_MAX_INPUT_LEN:
        return
    raise MaskingError(
        "Applying regex_mask",
        cause=(
            f"Value length {len(value)} exceeds the {_REGEX_MASK_MAX_INPUT_LEN} "
            "character limit for regex_mask."
        ),
        remediation="Use hash or fake for very long text columns.",
    )


@lru_cache(maxsize=256)
def _compiled_pattern(pattern: str, flags: int) -> re.Pattern[str]:
    """Compile and cache a pattern so hot-path cells reuse the compiled form."""
    return re.compile(pattern, flags)
