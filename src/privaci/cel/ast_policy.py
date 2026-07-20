"""AST allowlist and complexity limits for CEL ``when:`` expressions."""

from __future__ import annotations

from typing import Any

from lark import Token, Tree

from privaci.errors import ConfigError

# Lark trees for typical comparisons sit around depth 12–25; paren bombs explode.
MAX_AST_DEPTH = 48
MAX_AST_NODES = 400

_ALLOWED_METHODS = frozenset({"contains", "startsWith", "endsWith"})
_ALLOWED_FUNCTIONS = frozenset({"has", "size"})


def assert_expression_policy(ast: Tree[Any], *, column_path: str) -> None:
    """Reject denied builtins and over-complex ASTs (exit 3).

    Args:
        ast: Compiled celpy Lark tree.
        column_path: YAML path for error attribution.

    Raises:
        ConfigError: When the expression uses a denied form or exceeds limits.
    """
    methods: set[str] = set()
    functions: set[str] = set()
    field_selects = 0
    node_count = 0
    max_depth = 0

    def walk(node: Tree[Any] | Token, depth: int) -> None:
        nonlocal node_count, max_depth, field_selects
        node_count += 1
        max_depth = max(max_depth, depth)
        if not isinstance(node, Tree):
            return
        rule = str(node.data)
        if rule == "member_dot_arg":
            _collect_method(node, methods)
        elif rule == "ident_arg":
            _collect_function(node, functions)
        elif rule == "member_dot":
            field_selects += 1
        for child in node.children:
            if isinstance(child, Tree | Token):
                walk(child, depth + 1)

    walk(ast, 0)
    _raise_if_over_budget(column_path, max_depth, node_count)
    _raise_if_field_select(column_path, field_selects)
    _raise_if_denied(column_path, methods, functions)


def referenced_idents(ast: Tree[Any]) -> frozenset[str]:
    """Return identifier names from ``ident`` nodes (not methods/functions)."""
    names: set[str] = set()

    def walk(node: Tree[Any] | Token) -> None:
        if not isinstance(node, Tree):
            return
        if str(node.data) == "ident":
            for child in node.children:
                if isinstance(child, Token) and child.type == "IDENT":
                    names.add(str(child.value))
        for child in node.children:
            if isinstance(child, Tree | Token):
                walk(child)

    walk(ast)
    return frozenset(names)


def _collect_method(node: Tree[Any], methods: set[str]) -> None:
    for child in node.children:
        if isinstance(child, Token) and child.type == "IDENT":
            methods.add(str(child.value))
            return


def _collect_function(node: Tree[Any], functions: set[str]) -> None:
    for child in node.children:
        if isinstance(child, Token) and child.type == "IDENT":
            functions.add(str(child.value))
            return


def _raise_if_over_budget(column_path: str, max_depth: int, node_count: int) -> None:
    if max_depth > MAX_AST_DEPTH:
        raise ConfigError(
            f"Validating {column_path}",
            cause=(f"when: AST depth {max_depth} exceeds limit {MAX_AST_DEPTH}."),
            remediation=(
                "Simplify the expression; see "
                "docs/configuration.md#conditional-masking-when."
            ),
        )
    if node_count > MAX_AST_NODES:
        raise ConfigError(
            f"Validating {column_path}",
            cause=(
                f"when: AST node count {node_count} exceeds limit " f"{MAX_AST_NODES}."
            ),
            remediation=(
                "Simplify the expression; see "
                "docs/configuration.md#conditional-masking-when."
            ),
        )


def _raise_if_field_select(column_path: str, field_selects: int) -> None:
    if field_selects <= 0:
        return
    raise ConfigError(
        f"Validating {column_path}",
        cause="when: field selection (e.g. col.field) is not allowed.",
        remediation=(
            "Compare whole columns only; see "
            "docs/configuration.md#conditional-masking-when."
        ),
    )


def _raise_if_denied(
    column_path: str,
    methods: set[str],
    functions: set[str],
) -> None:
    bad_methods = sorted(methods - _ALLOWED_METHODS)
    bad_funcs = sorted(functions - _ALLOWED_FUNCTIONS)
    if not bad_methods and not bad_funcs:
        return
    parts: list[str] = []
    if bad_methods:
        parts.append("methods " + ", ".join(bad_methods))
    if bad_funcs:
        parts.append("functions " + ", ".join(bad_funcs))
    raise ConfigError(
        f"Validating {column_path}",
        cause="when: uses disallowed CEL " + " and ".join(parts) + ".",
        remediation=(
            "Use comparisons, logic, has(), size(), contains/startsWith/"
            "endsWith only; see docs/configuration.md#conditional-masking-when."
        ),
    )
