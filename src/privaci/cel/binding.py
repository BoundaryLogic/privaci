"""Catalog-typed annotation binding for CEL ``when:`` expressions."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import celpy
from lark import Tree

from privaci.cel.ast_policy import assert_expression_policy, referenced_idents
from privaci.cel.pg_types import CelBindingError, cel_annotation_for_pg_type
from privaci.errors import ConfigError

_REMEDIATION = (
    "Reference only existing bindable columns; see "
    "docs/configuration.md#conditional-masking-when."
)


def annotations_for_when(
    expression: str,
    *,
    column_path: str,
    column_types: Mapping[str, str],
) -> dict[str, type]:
    """Resolve CEL annotations for idents referenced by ``expression``.

    Walks the compiled AST (string literals are ignored). Every referenced
    identifier must exist on the table and map to a supported PostgreSQL type.

    Args:
        expression: CEL source from ``when:``.
        column_path: YAML path for error attribution.
        column_types: Column name → PostgreSQL type string for the table.

    Returns:
        Annotation map for referenced columns only.

    Raises:
        ConfigError: Unknown column, disallowed AST, or unsupported type.
    """
    text = expression.strip()
    ast = _compile_ast(text, column_path=column_path)
    assert_expression_policy(ast, column_path=column_path)
    annotations: dict[str, type] = {}
    for name in sorted(referenced_idents(ast)):
        pg_type = column_types.get(name)
        if pg_type is None:
            raise ConfigError(
                f"Type-checking CEL when for {column_path}",
                cause=f"when: references unknown column {name!r}.",
                remediation=_REMEDIATION,
            )
        bind_path = f"{column_path} (binding {name})"
        try:
            annotations[name] = cel_annotation_for_pg_type(
                pg_type, column_path=bind_path
            )
        except CelBindingError:
            raise CelBindingError(
                f"Type-checking CEL when for {column_path}",
                cause=(
                    f"Column {name!r} has unsupported type {pg_type!r} "
                    "for when: expressions."
                ),
                remediation=_REMEDIATION,
            ) from None
    return annotations


def _compile_ast(text: str, *, column_path: str) -> Tree[Any]:
    """Compile CEL to a Lark tree without catalog annotations."""
    env = celpy.Environment(annotations={})
    try:
        return env.compile(text)
    except Exception as exc:
        raise ConfigError(
            f"Compiling {column_path}",
            cause=f"Invalid CEL: {exc}",
            remediation=(
                "Fix the when: expression; see "
                "docs/configuration.md#conditional-masking-when."
            ),
        ) from None
