"""Detect functions that must exist before table DDL (DEFAULT / CHECK deps)."""

from __future__ import annotations

import re

from privaci.catalog.models import CatalogResult, FunctionInfo, TableInfo
from privaci.catalog.routines import functions_in_dependency_order
from privaci.config.models import Config
from privaci.schema.table_policy import is_excluded_table

# Matches schema.func( or func( in DEFAULT/CHECK text (best-effort).
_CALL_PATTERN = re.compile(
    r"(?P<qual>(?:[A-Za-z_][\w$]*|\"(?:[^\"]|\"\")+\")\s*\.\s*)?"
    r"(?P<name>[A-Za-z_][\w$]*|\"(?:[^\"]|\"\")+\")\s*\(",
    re.VERBOSE,
)

# SQL keywords / type constructors that look like calls but are not UDFs.
_NON_UDF_CALLS = frozenset(
    {
        "array",
        "check",
        "coalesce",
        "currval",
        "greatest",
        "least",
        "nextval",
        "nullif",
        "numeric",
        "row",
        "substring",
        "trim",
        "varchar",
        "char",
        "character",
        "decimal",
        "double",
        "float",
        "int",
        "integer",
        "bigint",
        "smallint",
        "text",
        "timestamp",
        "timestamptz",
        "date",
        "time",
        "interval",
        "bool",
        "boolean",
        "json",
        "jsonb",
        "uuid",
    }
)


def functions_required_for_pre_data(
    catalog: CatalogResult,
    config: Config,
) -> tuple[FunctionInfo, ...]:
    """Return functions that DEFAULT/CHECK expressions reference, in dep order.

    Includes the full transitive function dependency closure. Non-elevated
    DEFAULT/CHECK deps are hoisted even when ``replicate_functions`` is false
    (that flag only gates remaining post-data functions). Elevated functions
    still require an explicit ``elevated_objects: replicate`` disposition.
    """
    mentioned = _mentioned_function_keys(catalog, config)
    if not mentioned:
        return ()
    by_id = {fn.identifier: fn for fn in catalog.functions}
    selected: set[str] = set()
    for function in catalog.functions:
        if not _hoist_allowed(function, config):
            continue
        if _function_matches(function, mentioned):
            selected.add(function.identifier)
    _expand_dependency_closure(selected, by_id, config)
    ordered = [
        function
        for function in functions_in_dependency_order(catalog.functions)
        if function.identifier in selected
    ]
    return tuple(ordered)


def _expand_dependency_closure(
    selected: set[str],
    by_id: dict[str, FunctionInfo],
    config: Config,
) -> None:
    """BFS-expand ``selected`` through ``depends_on_functions`` to a fixed point."""
    frontier = list(selected)
    while frontier:
        current_id = frontier.pop()
        current = by_id.get(current_id)
        if current is None:
            continue
        for dep_id in current.depends_on_functions:
            dep = by_id.get(dep_id)
            if dep is None or dep_id in selected:
                continue
            if not _hoist_allowed(dep, config):
                continue
            selected.add(dep_id)
            frontier.append(dep_id)


def _hoist_allowed(function: FunctionInfo, config: Config) -> bool:
    """Return whether a function may be created in pre-data for DEFAULT/CHECK."""
    if function.is_elevated:
        return config.elevated_objects.get(function.identifier) == "replicate"
    return True


def _mentioned_function_keys(
    catalog: CatalogResult, config: Config
) -> frozenset[tuple[str | None, str]]:
    """Collect (schema_or_None, bare_name) pairs referenced in table DDL text."""
    found: set[tuple[str | None, str]] = set()
    for table in catalog.tables.values():
        if is_excluded_table(table, config):
            continue
        for text in _table_expression_texts(table):
            found.update(_parse_call_sites(text))
    return frozenset(found)


def _table_expression_texts(table: TableInfo) -> list[str]:
    texts: list[str] = []
    for column in table.columns:
        if column.default_expression and not column.uses_serial:
            texts.append(column.default_expression)
    for check in table.check_constraints:
        texts.append(check.definition)
    return texts


def _parse_call_sites(text: str) -> set[tuple[str | None, str]]:
    sites: set[tuple[str | None, str]] = set()
    for match in _CALL_PATTERN.finditer(text):
        qual = match.group("qual")
        name = _unquote(match.group("name"))
        if name.lower() in _NON_UDF_CALLS:
            continue
        schema = _unquote(qual.rstrip(".").strip()) if qual else None
        sites.add((schema, name))
    return sites


def _unquote(token: str) -> str:
    token = token.strip()
    if len(token) >= 2 and token[0] == '"' and token[-1] == '"':
        return token[1:-1].replace('""', '"')
    return token


def _function_matches(
    function: FunctionInfo, mentioned: frozenset[tuple[str | None, str]]
) -> bool:
    for schema, name in mentioned:
        if name != function.function_name:
            continue
        if schema is None or schema == function.schema_name:
            return True
    return False
