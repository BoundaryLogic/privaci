"""AST helpers shared by the security visitor."""

from __future__ import annotations

import ast

from security_ast.constants import PII_ISH_NAMES, SYMBOL_ALLOWLIST_RULES


def call_name(node: ast.Call) -> str | None:
    """Return the attribute or bare name of a call target."""
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return None


def module_banned(module: str, banned: frozenset[str]) -> bool:
    """Return True when ``module`` matches a banned root or prefix."""
    if module in banned:
        return True
    return any(module.startswith(f"{name}.") for name in banned)


def package_for_path(rel_path: str) -> str | None:
    """Return the top-level ``src/privaci/<pkg>`` name for a relative path."""
    parts = rel_path.replace("\\", "/").split("/")
    if len(parts) >= 3 and parts[0] == "src" and parts[1] == "privaci":
        return parts[2]
    return None


def is_interpolated(node: ast.expr) -> bool:
    """Return True when an expression is built via f-string, +, %, or .format()."""
    if isinstance(node, ast.JoinedStr):
        return True
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod | ast.Add):
        return True
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        return node.func.attr == "format"
    return False


def name_looks_pii(name: str) -> bool:
    """Return True when ``name`` is PII-ish (exact or ``*_email``-style suffix)."""
    lowered = name.lower()
    if lowered in PII_ISH_NAMES:
        return True
    return any(lowered.endswith(f"_{token}") for token in PII_ISH_NAMES)


def is_allowlisted(
    *,
    rel_path: str,
    line: int,
    symbol: str | None,
    rule: str,
    allowlist: set[str],
) -> bool:
    """Return True when this finding is waived.

    ``path:lineno`` waives every rule on that line.
    ``path:symbol`` waives only SQL-concat rules (never dynamic/shell/HTTP).
    """
    if f"{rel_path}:{line}" in allowlist:
        return True
    if (
        symbol
        and f"{rel_path}:{symbol}" in allowlist
        and rule in SYMBOL_ALLOWLIST_RULES
    ):
        return True
    return False
