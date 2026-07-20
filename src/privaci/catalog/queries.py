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
    n.nspname AS schema_name,
    c.relname AS view_name,
    pg_catalog.pg_get_viewdef(c.oid, true) AS definition,
    COALESCE(
        (
            SELECT true
            FROM pg_catalog.pg_options_to_table(c.reloptions) opt
            WHERE opt.option_name = 'security_invoker'
              AND lower(opt.option_value) IN ('true', 'on', '1')
        ),
        false
    ) AS security_invoker
FROM pg_catalog.pg_class c
JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind = 'v'
  AND """
    + _SCHEMA_WHERE
    + """
ORDER BY n.nspname, c.relname
"""
)

MATVIEWS_SQL = (
    """
SELECT
    n.nspname AS schema_name,
    c.relname AS view_name,
    pg_catalog.pg_get_viewdef(c.oid, true) AS definition
FROM pg_catalog.pg_class c
JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind = 'm'
  AND """
    + _SCHEMA_WHERE
    + """
ORDER BY n.nspname, c.relname
"""
)

FUNCTIONS_SQL = (
    """
SELECT
    n.nspname AS schema_name,
    p.proname AS function_name,
    p.oid AS function_oid,
    p.prosecdef AS is_security_definer,
    l.lanname AS language,
    pg_catalog.pg_get_function_identity_arguments(p.oid) AS identity_args,
    pg_catalog.pg_get_functiondef(p.oid) AS create_sql
FROM pg_catalog.pg_proc p
JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
JOIN pg_catalog.pg_language l ON l.oid = p.prolang
WHERE p.prokind IN ('f', 'p')
  AND NOT EXISTS (
      SELECT 1
      FROM pg_catalog.pg_depend d
      WHERE d.objid = p.oid
        AND d.deptype = 'e'
        AND d.refclassid = 'pg_catalog.pg_extension'::pg_catalog.regclass
  )
  AND """
    + _SCHEMA_WHERE
    + """
ORDER BY n.nspname, p.proname, identity_args
"""
)

FUNCTION_DEPENDENCIES_SQL = (
    """
SELECT
    n.nspname AS schema_name,
    p.proname AS function_name,
    pg_catalog.pg_get_function_identity_arguments(p.oid) AS identity_args,
    ref_n.nspname AS ref_schema,
    ref_p.proname AS ref_function_name,
    pg_catalog.pg_get_function_identity_arguments(ref_p.oid) AS ref_identity_args
FROM pg_catalog.pg_depend d
JOIN pg_catalog.pg_proc p ON p.oid = d.objid
JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
JOIN pg_catalog.pg_proc ref_p ON ref_p.oid = d.refobjid
JOIN pg_catalog.pg_namespace ref_n ON ref_n.oid = ref_p.pronamespace
WHERE d.classid = 'pg_catalog.pg_proc'::pg_catalog.regclass
  AND d.refclassid = 'pg_catalog.pg_proc'::pg_catalog.regclass
  AND d.deptype IN ('n', 'a')
  AND p.prokind IN ('f', 'p')
  AND ref_p.prokind IN ('f', 'p')
  AND """
    + _SCHEMA_WHERE
    + """
"""
)

FUNCTION_TABLE_DEPENDENCIES_SQL = (
    """
SELECT
    n.nspname AS schema_name,
    p.proname AS function_name,
    pg_catalog.pg_get_function_identity_arguments(p.oid) AS identity_args,
    ref_n.nspname AS ref_schema,
    ref_c.relname AS ref_table
FROM pg_catalog.pg_depend d
JOIN pg_catalog.pg_proc p ON p.oid = d.objid
JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
JOIN pg_catalog.pg_class ref_c ON ref_c.oid = d.refobjid
JOIN pg_catalog.pg_namespace ref_n ON ref_n.oid = ref_c.relnamespace
WHERE d.classid = 'pg_catalog.pg_proc'::pg_catalog.regclass
  AND d.refclassid = 'pg_catalog.pg_class'::pg_catalog.regclass
  AND d.deptype IN ('n', 'a')
  AND p.prokind IN ('f', 'p')
  AND ref_c.relkind IN ('r', 'p')
  AND """
    + _SCHEMA_WHERE
    + """
"""
)

VIEW_DEPENDENCIES_SQL = (
    """
SELECT DISTINCT
    nv.nspname AS view_schema,
    cv.relname AS view_name,
    nr.nspname AS ref_schema,
    cr.relname AS ref_name,
    cr.relkind AS ref_kind
FROM pg_catalog.pg_rewrite r
JOIN pg_catalog.pg_class cv ON cv.oid = r.ev_class
JOIN pg_catalog.pg_namespace nv ON nv.oid = cv.relnamespace
JOIN pg_catalog.pg_depend d
    ON d.objid = r.oid AND d.refclassid = 'pg_catalog.pg_class'::pg_catalog.regclass
JOIN pg_catalog.pg_class cr ON cr.oid = d.refobjid
JOIN pg_catalog.pg_namespace nr ON nr.oid = cr.relnamespace
WHERE r.ev_type = '1'
  AND cv.relkind IN ('v', 'm')
  AND cr.oid <> cv.oid
  AND cr.relkind IN ('r', 'p', 'v', 'm')
  AND """
    + _SCHEMA_WHERE.replace("n.nspname", "nv.nspname")
    + """
"""
)

TRIGGERS_SQL = (
    """
SELECT
    n.nspname AS schema_name,
    c.relname AS table_name,
    t.tgname AS trigger_name,
    pg_catalog.pg_get_triggerdef(t.oid, true) AS create_sql,
    CASE
        WHEN pg_catalog.pg_get_function_identity_arguments(p.oid) = ''
        THEN pn.nspname || '.' || p.proname
        ELSE pn.nspname || '.' || p.proname || '(' ||
             pg_catalog.pg_get_function_identity_arguments(p.oid) || ')'
    END AS function_identity
FROM pg_catalog.pg_trigger t
JOIN pg_catalog.pg_class c ON c.oid = t.tgrelid
JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
JOIN pg_catalog.pg_proc p ON p.oid = t.tgfoid
JOIN pg_catalog.pg_namespace pn ON pn.oid = p.pronamespace
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
