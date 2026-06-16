"""Parameterized SQL for PostgreSQL catalog introspection.

All queries are static strings with no user input concatenation. Schema
filtering is applied in the WHERE clause via fixed system-schema exclusions.
"""

from __future__ import annotations

# ruff: noqa: S608
# SECURITY: static catalog queries only — never interpolate table/schema names.
_SCHEMA_WHERE = """
    n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
    AND n.nspname NOT LIKE 'pg\\_%' ESCAPE '\\'
"""

TABLES_SQL = (
    """
SELECT
    n.nspname AS schema_name,
    c.relname AS table_name,
    c.reltuples::float8 AS estimated_rows
FROM pg_catalog.pg_class c
JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind IN ('r', 'p')
  AND """
    + _SCHEMA_WHERE
    + """
ORDER BY n.nspname, c.relname
"""
)

PARTITIONED_PARENTS_SQL = (
    """
SELECT
    n.nspname AS schema_name,
    c.relname AS parent_table,
    pt.partstrat AS partition_strategy,
    pg_catalog.pg_get_partkeydef(c.oid) AS partition_key_def
FROM pg_catalog.pg_partitioned_table pt
JOIN pg_catalog.pg_class c ON c.oid = pt.partrelid
JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
WHERE """
    + _SCHEMA_WHERE
    + """
ORDER BY n.nspname, c.relname
"""
)

PARTITION_CHILDREN_SQL = (
    """
SELECT
    n.nspname AS schema_name,
    parent.relname AS parent_table,
    child.relname AS child_table,
    pg_catalog.pg_get_expr(child.relpartbound, child.oid, true) AS partition_bound,
  EXISTS (
      SELECT 1
      FROM pg_catalog.pg_partitioned_table sub
      WHERE sub.partrelid = child.oid
  ) AS is_sub_partitioned
FROM pg_catalog.pg_inherits inh
JOIN pg_catalog.pg_class parent ON parent.oid = inh.inhparent
JOIN pg_catalog.pg_class child ON child.oid = inh.inhrelid
JOIN pg_catalog.pg_namespace n ON n.oid = parent.relnamespace
WHERE """
    + _SCHEMA_WHERE
    + """
ORDER BY n.nspname, parent.relname, child.relname
"""
)

VIEWS_SQL = (
    """
SELECT
    v.schemaname AS schema_name,
    v.viewname AS view_name
FROM pg_catalog.pg_views v
WHERE """
    + _SCHEMA_WHERE.replace("n.nspname", "v.schemaname")
    + """
ORDER BY v.schemaname, v.viewname
"""
)

MATVIEWS_SQL = (
    """
SELECT
    mv.schemaname AS schema_name,
    mv.matviewname AS view_name
FROM pg_catalog.pg_matviews mv
WHERE """
    + _SCHEMA_WHERE.replace("n.nspname", "mv.schemaname")
    + """
ORDER BY mv.schemaname, mv.matviewname
"""
)

TRIGGERS_SQL = (
    """
SELECT
    n.nspname AS schema_name,
    c.relname AS table_name,
    t.tgname AS trigger_name
FROM pg_catalog.pg_trigger t
JOIN pg_catalog.pg_class c ON c.oid = t.tgrelid
JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
WHERE NOT t.tgisinternal
  AND c.relkind IN ('r', 'p')
  AND """
    + _SCHEMA_WHERE
    + """
ORDER BY n.nspname, c.relname, t.tgname
"""
)

RULES_SQL = (
    """
SELECT
    n.nspname AS schema_name,
    c.relname AS table_name,
    r.rulename AS rule_name
FROM pg_catalog.pg_rewrite r
JOIN pg_catalog.pg_class c ON c.oid = r.ev_class
JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
WHERE r.rulename <> '_RETURN'
  AND c.relkind IN ('r', 'p')
  AND """
    + _SCHEMA_WHERE
    + """
ORDER BY n.nspname, c.relname, r.rulename
"""
)

PUBLICATIONS_SQL = """
SELECT pubname AS publication_name
FROM pg_catalog.pg_publication
WHERE pubname NOT LIKE 'pg\\_%' ESCAPE '\\'
ORDER BY pubname
"""

COLUMNS_SQL = (
    """
SELECT
    n.nspname AS schema_name,
    c.relname AS table_name,
    a.attname AS column_name,
    pg_catalog.format_type(a.atttypid, a.atttypmod) AS data_type,
    a.attnotnull AS not_null,
    pg_catalog.pg_get_expr(ad.adbin, ad.adrelid) AS default_expression,
    a.attidentity AS identity,
    pg_catalog.pg_get_serial_sequence(
        quote_ident(n.nspname) || '.' || quote_ident(c.relname),
        a.attname
    ) AS sequence_name
FROM pg_catalog.pg_attribute a
JOIN pg_catalog.pg_class c ON c.oid = a.attrelid
JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
LEFT JOIN pg_catalog.pg_attrdef ad
    ON ad.adrelid = a.attrelid AND ad.adnum = a.attnum
WHERE a.attnum > 0
  AND NOT a.attisdropped
  AND c.relkind IN ('r', 'p')
  AND """
    + _SCHEMA_WHERE
    + """
ORDER BY n.nspname, c.relname, a.attnum
"""
)

CONSTRAINTS_SQL = (
    """
SELECT
    n.nspname AS schema_name,
    c.relname AS table_name,
    con.conname AS constraint_name,
    con.contype AS constraint_type,
    pg_catalog.pg_get_constraintdef(con.oid, true) AS definition,
    con.condeferrable AS deferrable,
    con.condeferred AS initially_deferred,
    con.conkey AS source_attnums,
    con.confkey AS referenced_attnums,
    con.confrelid AS referenced_relid,
    ref_n.nspname AS referenced_schema,
    ref_c.relname AS referenced_table
FROM pg_catalog.pg_constraint con
JOIN pg_catalog.pg_class c ON c.oid = con.conrelid
JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
LEFT JOIN pg_catalog.pg_class ref_c ON ref_c.oid = con.confrelid
LEFT JOIN pg_catalog.pg_namespace ref_n ON ref_n.oid = ref_c.relnamespace
WHERE c.relkind IN ('r', 'p')
  AND """
    + _SCHEMA_WHERE
    + """
ORDER BY n.nspname, c.relname, con.conname
"""
)

INDEXES_SQL = (
    """
SELECT
    n.nspname AS schema_name,
    c.relname AS table_name,
    i.relname AS index_name,
    ix.indisunique AS is_unique,
    pg_catalog.pg_get_indexdef(ix.indexrelid) AS definition,
    ix.indkey AS index_attnums
FROM pg_catalog.pg_index ix
JOIN pg_catalog.pg_class c ON c.oid = ix.indrelid
JOIN pg_catalog.pg_class i ON i.oid = ix.indexrelid
JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind IN ('r', 'p')
  AND NOT ix.indisprimary
  AND """
    + _SCHEMA_WHERE
    + """
ORDER BY n.nspname, c.relname, i.relname
"""
)

COLUMN_STATS_SQL = (
    """
SELECT
    s.schemaname AS schema_name,
    s.tablename AS table_name,
    s.attname AS column_name,
    s.avg_width::float8 AS avg_width
FROM pg_catalog.pg_stats s
WHERE """
    + _SCHEMA_WHERE.replace("n.nspname", "s.schemaname")
    + """
"""
)

COLUMN_NAMES_SQL = (
    """
SELECT
    n.nspname AS schema_name,
    c.relname AS table_name,
    a.attnum AS attnum,
    a.attname AS column_name
FROM pg_catalog.pg_attribute a
JOIN pg_catalog.pg_class c ON c.oid = a.attrelid
JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
WHERE a.attnum > 0
  AND NOT a.attisdropped
  AND c.relkind IN ('r', 'p')
  AND """
    + _SCHEMA_WHERE
    + """
"""
)
