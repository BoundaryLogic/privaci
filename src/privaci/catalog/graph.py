"""Foreign-key dependency graph and topological load ordering."""

from __future__ import annotations

from privaci.catalog.identifiers import qualify, quote_pg_identifier
from privaci.catalog.models import (
    DeferredEdge,
    ForeignKeyInfo,
    LoadLayer,
    LoadPlan,
    TableInfo,
    parse_table_id,
)
from privaci.catalog.partitions import should_skip_fk_edge
from privaci.errors import CatalogError

Edge = tuple[str, str, ForeignKeyInfo]  # referenced, referencing, fk


def build_load_plan(tables: dict[str, TableInfo]) -> LoadPlan:
    """Build a layered load plan with cycle-deferral metadata.

    Args:
        tables: Introspected tables keyed by schema-qualified id.

    Returns:
        A :class:`LoadPlan` with topological layers and deferred edges.

    Raises:
        CatalogError: When a cycle requires deferring a non-deferrable FK.
    """
    edges = _collect_edges(tables)
    layers, deferred, non_deferrable, remaining = _resolve_layered_plan(edges, tables)

    if remaining:  # pragma: no cover - defensive: termination is proven above
        raise CatalogError(
            "Building foreign-key load order",
            cause="The dependency resolver did not converge.",
            remediation="File a bug with the source schema's FK structure.",
        )

    if non_deferrable:
        raise CatalogError(
            "Building foreign-key load order",
            cause="; ".join(non_deferrable),
            remediation=(
                "Make the listed constraints DEFERRABLE INITIALLY IMMEDIATE "
                "or remove the cyclic dependency."
            ),
        )

    layers = _merge_deferred_tables(layers, deferred)
    return LoadPlan(layers=tuple(layers), deferred_edges=tuple(deferred))


def _resolve_layered_plan(
    edges: list[Edge],
    tables: dict[str, TableInfo],
) -> tuple[list[LoadLayer], list[DeferredEdge], list[str], set[str]]:
    """Topologically layer tables, deferring cycle-breaking edges as needed."""
    deferred: list[DeferredEdge] = []
    non_deferrable: list[str] = []
    working = list(edges)
    remaining = set(tables)
    layers: list[LoadLayer] = []
    max_iterations = len(tables) + len(edges) + 1
    for _ in range(max_iterations):
        if not remaining:
            break
        layer = _ready_tables(remaining, working)
        if layer:
            layers.append(LoadLayer(table_ids=tuple(sorted(layer))))
            remaining -= layer
            working = [edge for edge in working if edge[0] not in layer]
            continue
        edge = _select_cycle_edge(working, tables)
        if not edge[2].deferrable:
            non_deferrable.append(_non_deferrable_message(edge))
        deferred.append(
            DeferredEdge(
                referencing_table=edge[1],
                foreign_key_name=edge[2].name,
                referenced_table=edge[0],
            )
        )
        working = [item for item in working if item != edge]
    return layers, deferred, non_deferrable, remaining


def _collect_edges(tables: dict[str, TableInfo]) -> list[Edge]:
    """Build FK edges for load ordering.

    Partition children inherit dependency edges from their parent so each
    child streams only after referenced tables are loaded. Parent-level FK
    rows are not duplicated per child in catalog introspection.
    """
    edges: list[Edge] = []
    for info in tables.values():
        if should_skip_fk_edge(info):
            continue
        for referencing_id in _fk_referencing_units(info):
            for fk in info.foreign_keys:
                if fk.referenced_id == referencing_id:
                    continue
                if fk.referenced_id not in tables:
                    continue
                edges.append((fk.referenced_id, referencing_id, fk))
    return edges


def _fk_referencing_units(table: TableInfo) -> tuple[str, ...]:
    """Return table ids that need FK dependency edges for load ordering."""
    if table.is_partitioned and table.partition_children:
        return table.partition_children
    return (table.identifier,)


def _ready_tables(remaining: set[str], edges: list[Edge]) -> set[str]:
    """Return unassigned tables with no remaining unloaded dependency.

    A table is blocked while it still references (as the ``referencing`` side
    of an edge) a table that has not yet been loaded.
    """
    blocked = {referencing for _referenced, referencing, _fk in edges}
    return {tid for tid in remaining if tid not in blocked}


def _select_cycle_edge(edges: list[Edge], tables: dict[str, TableInfo]) -> Edge:
    return min(edges, key=lambda edge: _edge_cost(edge, tables))


def _edge_cost(edge: Edge, tables: dict[str, TableInfo]) -> tuple[int, float, str]:
    _referenced, referencing, fk = edge
    table = tables[referencing]
    nullable_penalty = 0
    for column_name in fk.source_columns:
        column = table.column_by_name(column_name)
        if column is not None and column.not_null:
            nullable_penalty = 1_000_000
            break
    rows = table.estimated_rows if table.estimated_rows >= 0 else 1000.0
    return (nullable_penalty, rows, fk.name)


def _non_deferrable_message(edge: Edge) -> str:
    _referenced, referencing, fk = edge
    schema_name, table_name = parse_table_id(referencing)
    table_ref = qualify(schema_name, table_name)
    constraint_ref = quote_pg_identifier(fk.name)
    return (
        f"{referencing} constraint {fk.name} is not DEFERRABLE; run: "
        f"ALTER TABLE {table_ref} ALTER CONSTRAINT {constraint_ref} "
        "DEFERRABLE INITIALLY IMMEDIATE;"
    )


def _merge_deferred_tables(
    layers: list[LoadLayer], deferred: list[DeferredEdge]
) -> list[LoadLayer]:
    """Co-locate only the tables linked by deferred edges into one layer.

    A deferred edge means two tables form (or are part of) a cycle and must load
    in the same transaction. Only those specific tables are moved together — the
    rest of their original layers keep their topological position. Merging whole
    layers would drag unrelated tables (which merely shared a layer with a cycle
    member) into the cycle layer and break their own FK ordering.
    """
    if not deferred:
        return layers

    layer_sets = [set(layer.table_ids) for layer in layers]
    for component in _deferred_components(deferred):
        member_indices = [
            index for index, layer in enumerate(layer_sets) if layer & component
        ]
        if len(member_indices) < 2:
            continue
        target_index = min(member_indices)
        for index in member_indices:
            if index == target_index:
                continue
            moved = layer_sets[index] & component
            layer_sets[target_index] |= moved
            layer_sets[index] -= moved

    return [LoadLayer(table_ids=tuple(sorted(layer))) for layer in layer_sets if layer]


def _deferred_components(deferred: list[DeferredEdge]) -> list[set[str]]:
    """Group tables connected (transitively) by deferred edges."""
    components: list[set[str]] = []
    for edge in deferred:
        pair = {edge.referenced_table, edge.referencing_table}
        touching = [c for c in components if c & pair]
        if not touching:
            components.append(pair)
            continue
        merged = set(pair)
        for component in touching:
            merged |= component
            components.remove(component)
        components.append(merged)
    return components
