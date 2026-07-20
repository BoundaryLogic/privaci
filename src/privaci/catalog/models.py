"""Typed representations of PostgreSQL catalog introspection results."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from privaci.catalog.identifiers import qualify


def table_id(schema_name: str, table_name: str) -> str:
    """Return the canonical schema-qualified table identifier."""
    return f"{schema_name}.{table_name}"


def parse_table_id(identifier: str) -> tuple[str, str]:
    """Split a schema-qualified table id into ``(schema, table)``.

    Uses the rightmost ``.`` as the delimiter so schema names may contain dots
    (e.g. ``analytics.prod.events`` → ``analytics.prod``, ``events``).
    """
    if "." not in identifier:
        raise ValueError(f"invalid table id: {identifier!r}")
    schema_name, _, table_name = identifier.rpartition(".")
    if not schema_name or not table_name:
        raise ValueError(f"invalid table id: {identifier!r}")
    return schema_name, table_name


@dataclass(frozen=True, slots=True)
class ColumnInfo:
    """One column on a source table."""

    name: str
    data_type: str
    not_null: bool
    default_expression: str | None = None
    is_identity: bool = False
    identity_generation: str | None = None
    uses_serial: bool = False
    sequence_name: str | None = None
    avg_width: float | None = None

    def __repr__(self) -> str:
        return (
            f"ColumnInfo(name={self.name!r}, data_type={self.data_type!r}, "
            f"not_null={self.not_null}, avg_width={self.avg_width})"
        )


@dataclass(frozen=True, slots=True)
class ViewInfo:
    """A view or materialized view discovered during introspection."""

    schema_name: str
    view_name: str
    kind: str
    definition: str | None = None
    is_elevated: bool = False
    depends_on: tuple[str, ...] = ()

    @property
    def identifier(self) -> str:
        """Schema-qualified view name."""
        return table_id(self.schema_name, self.view_name)

    def __repr__(self) -> str:
        return (
            f"ViewInfo({self.identifier!r}, kind={self.kind!r}, "
            f"elevated={self.is_elevated})"
        )


@dataclass(frozen=True, slots=True)
class FunctionInfo:
    """A user-defined function or procedure discovered during introspection."""

    schema_name: str
    function_name: str
    identity_args: str
    create_sql: str
    language: str
    is_elevated: bool
    depends_on_functions: tuple[str, ...] = ()
    depends_on_tables: tuple[str, ...] = ()

    @property
    def identifier(self) -> str:
        """Schema-qualified name; appends args when present."""
        base = table_id(self.schema_name, self.function_name)
        args = self.identity_args.strip()
        if args:
            return f"{base}({args})"
        return base

    def __repr__(self) -> str:
        return (
            f"FunctionInfo({self.identifier!r}, elevated={self.is_elevated}, "
            f"lang={self.language!r})"
        )


@dataclass(frozen=True, slots=True)
class SkippedObjectInfo:
    """A non-replicated catalog object (rule or publication)."""

    schema_name: str
    object_name: str
    kind: str
    parent_table: str | None = None

    def __repr__(self) -> str:
        return (
            f"SkippedObjectInfo({self.object_name!r}, kind={self.kind!r}, "
            f"parent={self.parent_table!r})"
        )


@dataclass(frozen=True, slots=True)
class TriggerInfo:
    """A user trigger with enough metadata to emit post-data DDL."""

    schema_name: str
    table_name: str
    trigger_name: str
    create_sql: str
    function_identity: str | None = None

    @property
    def identifier(self) -> str:
        """Schema-qualified trigger id ``schema.table.trigger``."""
        return f"{self.schema_name}.{self.table_name}.{self.trigger_name}"

    def __repr__(self) -> str:
        return (
            f"TriggerInfo({self.identifier!r}, " f"function={self.function_identity!r})"
        )


@dataclass(frozen=True, slots=True)
class ForeignKeyInfo:
    """A catalog foreign-key constraint."""

    name: str
    source_columns: tuple[str, ...]
    referenced_schema: str
    referenced_table: str
    referenced_columns: tuple[str, ...]
    on_delete: str
    on_update: str
    deferrable: bool
    initially_deferred: bool

    @property
    def referenced_id(self) -> str:
        """Schema-qualified referenced table id."""
        return table_id(self.referenced_schema, self.referenced_table)

    def __repr__(self) -> str:
        return (
            f"ForeignKeyInfo(name={self.name!r}, "
            f"source={self.source_columns!r} -> {self.referenced_id!r})"
        )


@dataclass(frozen=True, slots=True)
class CheckConstraintInfo:
    """A check constraint recorded verbatim for DDL replication."""

    name: str
    definition: str

    def __repr__(self) -> str:
        return f"CheckConstraintInfo(name={self.name!r})"


@dataclass(frozen=True, slots=True)
class IndexInfo:
    """An index on a source table."""

    name: str
    is_unique: bool
    definition: str
    columns: tuple[str, ...]

    def __repr__(self) -> str:
        return f"IndexInfo(name={self.name!r}, unique={self.is_unique})"


@dataclass(frozen=True, slots=True)
class TableInfo:
    """Introspected metadata for one source table."""

    schema_name: str
    table_name: str
    columns: tuple[ColumnInfo, ...]
    primary_key: tuple[str, ...] = ()
    unique_constraints: tuple[tuple[str, ...], ...] = ()
    foreign_keys: tuple[ForeignKeyInfo, ...] = ()
    check_constraints: tuple[CheckConstraintInfo, ...] = ()
    indexes: tuple[IndexInfo, ...] = ()
    estimated_rows: float = -1.0
    self_cycle: bool = False
    is_partitioned: bool = False
    partition_strategy: str | None = None
    partition_key_def: str | None = None
    partition_children: tuple[str, ...] = ()
    parent_partition: str | None = None
    partition_bound: str | None = None

    @property
    def identifier(self) -> str:
        """Schema-qualified table id."""
        return table_id(self.schema_name, self.table_name)

    @property
    def sql_ref(self) -> str:
        """Safely-quoted ``"schema"."table"`` reference for dynamic SQL."""
        return qualify(self.schema_name, self.table_name)

    def column_by_name(self, name: str) -> ColumnInfo | None:
        """Return a column by name, or ``None`` if absent."""
        for column in self.columns:
            if column.name == name:
                return column
        return None

    def __repr__(self) -> str:
        return (
            f"TableInfo({self.identifier!r}, columns={len(self.columns)}, "
            f"fks={len(self.foreign_keys)})"
        )


@dataclass(frozen=True, slots=True)
class DeferredEdge:
    """An FK edge selected for deferral during a cyclic load."""

    referencing_table: str
    foreign_key_name: str
    referenced_table: str

    def __repr__(self) -> str:
        return (
            f"DeferredEdge({self.referencing_table!r} -[{self.foreign_key_name}]-> "
            f"{self.referenced_table!r})"
        )


@dataclass(frozen=True, slots=True)
class CatalogWarning:
    """A non-blocking catalog warning (polymorphic FK, never-analyzed table)."""

    code: str
    message: str
    table_id: str | None = None

    def __repr__(self) -> str:
        return f"CatalogWarning(code={self.code!r}, table_id={self.table_id!r})"


@dataclass(frozen=True, slots=True)
class LoadLayer:
    """One topological layer of tables with no unresolved in-layer dependencies."""

    table_ids: tuple[str, ...]

    def __repr__(self) -> str:
        return f"LoadLayer({list(self.table_ids)!r})"


@dataclass(frozen=True, slots=True)
class LoadPlan:
    """Topological load order with cycle-deferral metadata."""

    layers: tuple[LoadLayer, ...]
    deferred_edges: tuple[DeferredEdge, ...] = ()

    def __repr__(self) -> str:
        deferred = len(self.deferred_edges)
        return f"LoadPlan(layers={len(self.layers)}, deferred={deferred})"


@dataclass(frozen=True, slots=True)
class CatalogResult:
    """Full introspection output for a source database."""

    tables: dict[str, TableInfo]
    load_plan: LoadPlan
    warnings: tuple[CatalogWarning, ...] = ()
    views: tuple[ViewInfo, ...] = ()
    functions: tuple[FunctionInfo, ...] = ()
    triggers: tuple[TriggerInfo, ...] = ()
    skipped_objects: tuple[SkippedObjectInfo, ...] = ()

    def to_snapshot_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable snapshot dict with stable ordering."""
        from privaci.catalog.snapshot import catalog_to_snapshot_dict

        return catalog_to_snapshot_dict(self)
