---
title: "Configuration guide"
description: "Author mask-rules.yaml — table rules, masking actions, regex, NER, and strict validation."
---

# Configuring PrivaCI (`mask-rules.yaml`)

PrivaCI is driven by a single declarative YAML file, mounted in the container at
`/config/mask-rules.yaml` (override with `--config`). The engine validates this
file strictly on boot: unknown keys, misspelled actions, and unsupported
versions fail fast with [exit code 3](error-codes.md#exit-code-3-config-validation-failure)
before any database connection is opened.

This page is the operator reference for every field. The same schema is
available machine-readable for editor auto-completion:

```bash
privaci schema config > mask-rules.schema.json
```

## Quickstart

**Generate a starter config** from your source schema (no target required):

```bash
export SOURCE_DB_URL=postgresql://user:pass@source-host:5432/app

privaci init --source "$SOURCE_DB_URL" --output mask-rules.yaml
privaci plan --config mask-rules.yaml --source "$SOURCE_DB_URL"
```

Then set `ANONYMIZATION_SALT` and review/edit the YAML before production runs.

A minimal hand-authored config that masks two columns on one table:

```yaml
version: "1.0"
global_salt: "${ANONYMIZATION_SALT}"

tables:
  public.users:
    strategy: transform
    columns:
      first_name: { action: fake, provider: first_name }
      email:      { action: fake, provider: email }
```

Validate it without running a masking job:

```bash
privaci validate --config mask-rules.yaml
# Config mask-rules.yaml is valid.
```

A failing example — a misspelled action — exits `3` and names the column path:

```bash
privaci validate --config mask-rules.yaml
# Context: Validating mask-rules.yaml
# Cause: Config does not satisfy the schema:
#   - tables.users.columns.email: ...
# Remediation: Fix the fields listed above; see docs/configuration.md.
```

## Top-level options

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `version` | string | _required_ | Config schema version. The v1.x engine accepts `"1.0"` only. |
| `global_salt` | string \| secret URI | _none_ | Salt literal or secret URI; resolved at run time. Never logged. |
| `pseudonym_key` | string \| secret URI | _none_ | HMAC key for `hmac_hash` / `pseudonym` (required when the `keyed_actions` capability is granted). Distinct from `global_salt`. |
| `on_existing_data` | enum | `fail` | Target collision policy: `fail`, `truncate`, `drop_create`. Under `assume_existing`, `fail` allows empty prebuilt tables but refuses rows; see [assume_existing](#schema_mode-assume_existing). `append` is rejected in the MVP. |
| `schema_mode` | enum | `replicate` | Who owns target DDL: `replicate` (engine clones schema) or `assume_existing` (validate prebuilt target, then load). |
| `passthrough_copy` | enum | `auto` | Binary COPY for unmasked tables: `auto` (binary when column order matches, else named batch), `require_binary` (fail if ineligible), `batch` (always named batch). |
| `replicate_views` | bool | `true` | Replicate non-elevated plain views in `replicate` mode (**post-data**). |
| `replicate_functions` | bool | `true` | Replicate non-elevated functions/procedures (**post-data**, except DEFAULT/CHECK deps which hoist to **pre-data**). |
| `replicate_triggers` | bool | `true` | Create user triggers in **post-data** (do not fire during mask load). Set `false` to skip. Ignored under `assume_existing`. |
| `replicate_materialized_views` | bool | `false` | Create materialized-view shells with `WITH NO DATA` in **post-data** (never copy source storage). Rejected under `assume_existing`. |
| `refresh_materialized_views` | bool | `false` | After masked loads, `REFRESH MATERIALIZED VIEW` in dependency order (requires `replicate_materialized_views`; `replicate` mode only). Rejected under `assume_existing`. |
| `elevated_objects` | map | `{}` | Explicit `replicate` or `skip` for elevated views/functions. Unresolved elevated objects fail preflight. |
| `strict_autodetect` | bool | `false` | Fail the run when auto-detect finds uncovered PII columns. |
| `replicate_all_indexes` | bool | `false` | Replicate every source index (non-unique indexes in **post-data**), not just unique/PK indexes. |
| `batch_size` | int | `10000` | Default streaming batch size in rows (must be ≥ 1). |
| `audit_log` | bool | `true` | Write the per-run audit log to `_privaci.audit_log`. |
| `auto_detect` | bool | `true` | Run the zero-config PII column scanner. |
| `implied_fk_ignore` | list[string] | `[]` | Source column paths (`schema.table.column`) whose [implied FK warnings](#implied-soft-foreign-keys) are silenced. |
| `tables` | mapping | `{}` | Table identifier → [table config](#table-configuration). Keys must match the catalog (`schema.table`, e.g. `public.users`). |

Target DDL that must interpolate schema/table names (truncate, drop schema,
`search_path`, and similar) always runs those identifiers through
`quote_pg_identifier` first. Semgrep `auto` SQL-concatenation findings on those
paths are calibrated with `nosemgrep` next to the SECURITY comments.

## Auto-detect

When `auto_detect: true` (default), PrivaCI inspects every column name against a
built-in pattern library and assigns a **confidence** score:

| Confidence | Run-time behaviour |
|------------|-------------------|
| `high` | Auto-apply the inferred action (e.g. `fake` for `email`, `ner_mask` for long clinical notes). |
| `medium` | Flag for manual review in `privaci dry-run --report`; passthrough unless YAML overrides. |
| `low` | Passthrough. |

Explicit YAML column entries always win, including `passthrough`. Structured
patterns (`email`, `ssn`, `phone`, …) are `high` on name match alone. Freeform
patterns (`note*`, `description`, …) additionally require column type (`text`
or `varchar` ≥ 500) and use `pg_stats.avg_width` plus table-name context — see
[ADR-0011](adr/0011-autodetect-confidence-scoring.md).

Review detections without writing data:

```bash
privaci dry-run --config mask-rules.yaml --report review.md
```

With `strict_autodetect: true`, any `high` or `medium` finding not explicitly
listed under `tables.<id>.columns` fails validation (exit `3`).

`privaci preview` and `privaci dry-run --report` write their review artifacts
**before** applying the strict check, so CI can upload a policy diff or markdown
report even when the job exits `3`. Production `privaci run` still fails at
preflight with no writes.

> **Version policy.** A config whose `version` is not `"1.0"` is rejected by the
> v1.x engine. A future engine reading an older config will direct you to
> `privaci migrate-config --from <old> --to <new> <path>`. When `--from` equals
> `--to`, `migrate-config` is a no-op and exits `0`.

## Table configuration

Each entry under `tables` accepts:

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `strategy` | enum | `transform` | `transform` (mask + copy), `exclude` (drop in target), `empty` (recreate, no rows), `truncate` (empty before copy). |
| `columns` | mapping | `{}` | Column name → [action](#actions). |
| `batch_size` | int | _inherits global_ | Per-table override (must be ≥ 1). |
| `null_orphan_fks` | bool | `false` | When a nullable FK references an **excluded** (or otherwise non-created) parent, set those FK columns to `NULL` on every streamed row instead of leaving dangling values. Forces the batch/cell path for that table (binary COPY is ineligible). Conflicts with `passthrough_copy: require_binary` at preflight. |

`empty` creates the table DDL on the target but streams zero rows and marks the
table checkpoint `done`. `truncate` does the same after `TRUNCATE` on an
existing target table — useful when you need the schema but not the data.

When `null_orphan_fks: true`, `privaci plan` / `privaci dry-run` still list the
child table as streamable; the FK DDL to the excluded parent is omitted either
way. Review exclude graphs before production runs.

### Idempotent replicated DDL

In `schema_mode: replicate`, index creation uses `IF NOT EXISTS` and foreign
keys are checked by constraint name before creation. PostgreSQL's
`CREATE INDEX IF NOT EXISTS` compares the object name only, and the FK guard
also compares constraint names. PrivaCI does not silently replace a same-name
index or constraint whose definition differs. Use schema drift review or
remove/rename the conflicting target object before retrying.

### Object replication (pg_dump-style phases)

In `schema_mode: replicate`, DDL is applied in three phases (same names as
`pg_dump` sections):

| Phase | Objects |
| --- | --- |
| **pre-data** | Schemas, extensions, sequences, tables, partition children, PRIMARY KEY / UNIQUE indexes, foreign keys; functions required by column `DEFAULT` / `CHECK` expressions |
| **data** | Masked/passthrough row stream; per-table sequence `setval` |
| **post-data** | Remaining functions/procedures, plain views, optional matview shells, optional non-unique indexes (`replicate_all_indexes`), triggers (`replicate_triggers`, default on), optional matview `REFRESH` |

`RunStatus.SUCCEEDED` means all three phases completed. Phase membership is
fixed (not configurable); use include/skip flags and `assume_existing` when you
own target DDL.

- **Elevated** objects still require an explicit disposition (see below).
- **Materialized views** remain opt-in definition-only shells (see below).
- **Rules** and **publications** remain skipped.

Each created object is recorded as `created_object` (or
`definition_only_object`) with `ddl_phase`. Skipped objects use
`skipped_object` with a `kind` and `reason`.

Triggers created in post-data apply to **subsequent** DML on the target; they
do **not** fire against rows inserted during the mask COPY/load. Set
`replicate_triggers: false` to skip (audit `skipped_object` with
`reason: flag_disabled`). When the trigger function is not replicated
(elevated skip or `replicate_functions: false`), the trigger is skipped with
`reason: dependency_excluded`.

### Elevated objects

An object is **elevated** when it is a `SECURITY DEFINER` function/procedure, or
a view that does **not** use invoker rights (`security_invoker`). Elevated
objects are deny-by-default:

```yaml
elevated_objects:
  clinical.admin_v: skip
  reporting.privileged_fn(bigint): replicate
```

- `replicate` — create on the target; audit `created_object` with `elevated: true`.
- `skip` — do not create; audit `skipped_object` with
  `reason: elevated_object_skipped`.
- Missing entry → preflight exit **2** naming the object.

`privaci init` scaffolds `elevated_objects: {}` and prints **ACTION REQUIRED**
listing unresolved elevated objects. `privaci plan` prints the same reminder
and a pre-data / post-data phase summary.

### Objects still not replicated

Rules and logical-replication publications are never copied. Each is recorded
as `skipped_object` (`kind`: `rule` or `publication`). Triggers are skipped when
`replicate_triggers: false` (`reason: flag_disabled`) or when their function is
not replicated (`reason: dependency_excluded`).

### Materialized views (opt-in, definition-only)

```yaml
version: "1.0"
replicate_materialized_views: true   # CREATE … WITH NO DATA (default false)
refresh_materialized_views: true     # REFRESH after masked table loads
```

When `replicate_materialized_views: true`, PrivaCI creates the matview shell from
`pg_get_viewdef` and audits `definition_only_object` with `contents_copied: false`
(and `refreshed: false` until an optional refresh completes). It never copies stored
rows from the source matview. Optional `refresh_materialized_views: true` re-derives
contents from the masked base tables after streaming completes (`schema_mode:
replicate` only) and sets `refreshed: true` on the audit row. Setting refresh without
replicate is rejected at config load. Both matview flags are rejected under
`schema_mode: assume_existing` — pre-create and refresh shells out of band, or use
`replicate`.

Chained matviews are dropped in reverse dependency order before recreate so truncate
re-runs stay idempotent without `CASCADE`. Plain views that depend on a matview are
not yet ordered after matview shells; prefer table-backed matviews or create those
views out of band.

### Source database trust boundary

Function bodies, index definitions, DEFAULT expressions, and similar catalog
text are copied from the source as-is when replication is enabled. Treat the
source database as a trust boundary: elevated-object dispositions
(`elevated_objects`) are the control plane for SECURITY DEFINER / invoker-rights
risks. PrivaCI does not rewrite or sanitize function/index bodies beyond those
gates.

### `schema_mode: assume_existing`

Use when DBAs (or Flyway/Liquibase) already own the target schema and PrivaCI
should validate-and-load only:

```yaml
version: "1.0"
schema_mode: assume_existing
on_existing_data: truncate   # typical for prebuilt staging
passthrough_copy: auto       # auto | require_binary | batch
```

Preflight checks every in-scope table exists on the target with compatible
column **names and types** (physical order is not required). Extra target
columns are allowed. On success the engine writes `schema.validated` to
`_privaci.audit_log`; on refusal it writes `schema.validation_failed` (identifiers
and declared types only — never cell values) and exits **2**.

`passthrough_copy` controls whole-table binary COPY for unmasked tables:

| Value | Behaviour |
|-------|-----------|
| `auto` (default) | Prefer binary when source and target column names, types, and order match; otherwise use the named batch path. |
| `require_binary` | Fail preflight if any passthrough table is not binary-eligible. |
| `batch` | Never use binary COPY; always use the named batch path. |

`on_existing_data: drop_create` is rejected with `assume_existing`: deleting
customer-managed DDL would leave no schema for PrivaCI to load. Use `truncate`
or `fail`.

Loads are **full reloads of source values**, including primary keys and
identity/`SERIAL` columns (explicit insert + post-load `setval`). That means:

| Target state | `on_existing_data: fail` | `on_existing_data: truncate` |
|--------------|--------------------------|------------------------------|
| In-scope tables empty | Allowed | Truncate (no-op) then load |
| In-scope tables have rows | Preflight exit **2** | Truncate then load |

Missing identity/`SERIAL` columns does **not** make a populated target safe without
truncate — source keys still collide on unique constraints. Use `truncate` for
re-runs into staging; `append` / upsert is not supported in this version.

## Actions

Every column action is selected by its `action` discriminator. Unknown action
names and extra keys are rejected with the offending YAML path.

| Action | Required params | Optional params | Notes |
|--------|-----------------|-----------------|-------|
| `fake` | `provider` | `seed_alias`, `params` | Deterministic synthetic value from a registered provider. Unknown provider names fail validation (exit 3). |
| `regex_mask` | `pattern`, `replace` | `flags` | `pattern` must compile; unknown `flags` are rejected. |
| `hash` | — | — | Salted SHA-256 of raw `salt` concatenated with `value` (no delimiter between them; no column path). Same value hashes the same across tables/columns — useful when you intentionally want join/linkability. Prefer `hmac_hash` when column-scoped digests are required. Low-entropy inputs (phone, SSN) with a known salt are dictionary-reversible; do not treat `hash` as irreversible anonymization for those fields. |
| `hmac_hash` | — | `encoding` | Keyed HMAC-SHA256 using `pseudonym_key`, scoped by column path. Requires a plugin granting the `keyed_actions` capability; rejected in community mode (exit 5). |
| `pseudonym` | `provider` | `seed_alias`, `params` | Keyed deterministic fake (same providers as `fake`). Requires the `keyed_actions` capability; rejected in community mode (exit 5). |
| `passthrough` | — | — | Copy the value unchanged. |
| `null` | — | — | Write `NULL`. Rejected at pre-flight on `NOT NULL` columns. |
| `static` | `value` | — | Replace every value with a constant. |
| `ner_mask` | — | `entities` | Level-2 SpaCy NER. `entities` defaults to `PERSON, ORG, GPE, LOC`. **Requires** `pip install 'privaci[nlp]'` and the `en_core_web_sm` model. Missing SpaCy fails at config validate (exit **3**, explicit YAML), preflight (exit **2**, including auto-detect), or runtime ``MaskingError`` (exit **1**) — never silent passthrough of source text. |
| `ai_refine` | `provider`, `model` | `params` | **Level-3 (not implemented / not wired).** Rejected in community mode at config validate (exit 3). With a plugin package installed, config may accept the action, but mask time still raises ``L3NotInstalledError`` (exit 3) until connectors are wired and implemented. Do not use in production configs yet. |

### Conditional masking (`when:`)

Every column action may include an optional CEL expression:

```yaml
tables:
  public.tickets:
    columns:
      notes:
        action: fake
        provider: company
        when: "status == 'closed'"
```

- When `when` is omitted or empty, the action runs for every row (unchanged).
- When present, the action runs only if the expression evaluates to **true**;
  otherwise the cell is left unchanged (auto-detect does not override).
- Requires the `conditional_masking` license capability (plugin package).
  Without it, config validation exits **5**.
- Tables with any `when` use the batch/row path (not whole-table binary COPY).
  `passthrough_copy: require_binary` plus `when` fails preflight (exit **2**).
- Unsupported column types in the expression (e.g. `jsonb`, arrays) fail at
  preflight (exit **3**). Prefer bool/int/float/text/uuid/timestamp/bytea.
- Unknown column identifiers in `when:` fail at catalog type-check (exit **3**).
- Allowed forms: comparisons, logic, `size()`, and string
  `contains` / `startsWith` / `endsWith`. Use `col != null` for null checks
  (`has()` is rejected — activation always binds columns, so it would be
  always-true). Regex (`matches`), comprehensions (`map` / `filter`), field
  selection, indexing (`col[i]`), and `timestamp`/`duration` are rejected at
  compile (exit **3**).
- Audit rollup: one `column.conditional_skip` per guarded column with
  `expression_hash`, `skipped_rows`, and `evaluated_rows` (no cell values).
- Expression length max 512 characters; evaluation enforces a cooperative
  **5 ms elapsed budget** per row per guarded column (celpy cannot hard-preempt;
  overrun fails the run with exit **1**). AST depth/node limits also apply.

### Built-in `fake` providers

| Provider | Output shape |
|----------|--------------|
| `first_name`, `last_name`, `full_name` | Synthetic person names |
| `email` | `local@domain` using fake domains (`fakedom.net`, `example.test`, `tryvault.dev` by default); `params.domain` overrides |
| `phone` | E.164 test number; preserves a leading country code when detectable |
| `street`, `city`, `postcode`, `country`, `address` | Synthetic postal components or a one-line address |
| `dob` | ISO-8601 date within ±5 years of the input age bracket |
| `ip_address` | RFC 5737 TEST-NET address |
| `ssn` | `000-099-XXXX` SSA advertising test range |
| `credit_card` | Luhn-valid number from documented test BINs |
| `uuid` | Deterministic UUIDv4 layout |
| `company`, `job_title`, `username` | Synthetic org / role / handle |
| `password` | Always the fixed placeholder `privaci-test-pw` (never a real-looking hash) |

Register custom providers from plugins via `privaci.contracts.register_provider`.

### Examples

```yaml
tables:
  public.users:
    columns:
      first_name: { action: fake, provider: first_name }
      email:      { action: fake, provider: email, seed_alias: user_email }
      ssn:        { action: regex_mask, pattern: "^\\d{3}-\\d{2}-\\d{4}$", replace: "000-00-0000" }
      password_hash: { action: hash }
      notes:      { action: ner_mask }            # masks PERSON/ORG/GPE/LOC

  audit_internal.audit_log_events:
    strategy: exclude                              # table omitted in target
```

### `seed_alias` for foreign keys

Salt-hashed faking already keeps the same input → same output across columns.
When two columns hold the *same logical value under different column names*
(for example an FK `orders.customer_email` pointing at `users.email`), give them
a shared `seed_alias` so they fake to the same value and the relationship
survives:

```yaml
tables:
  public.users:
    columns:
      email: { action: fake, provider: email, seed_alias: user_email }
  public.orders:
    columns:
      customer_email: { action: fake, provider: email, seed_alias: user_email }
```

### Implied (soft) foreign keys

Postgres only enforces relationships you declare. Many real schemas carry
*soft* references — a column like `clinical.patient_documents.referring_provider_email`
that informally points at `clinical.providers.email` with no `FOREIGN KEY`
constraint. PrivaCI cannot see these in the catalog, so it would fake the two
columns independently and silently break the link.

During introspection PrivaCI flags these. A column whose name ends in a known
suffix (`_email`, `_username`, `_user_id`, `_mrn`) is matched against
single-column **UNIQUE** columns elsewhere in the source. When a match is
found and no catalog FK exists, the engine emits one `implied_fk_warning`
naming both columns and suggesting a `seed_alias`:

```text
Warning: [implied_fk_warning] Table clinical.patient_documents column
referring_provider_email looks like a soft reference to
clinical.providers.email (UNIQUE) but no catalog foreign key exists. Add
'seed_alias: clinical.providers.email' on
clinical.patient_documents.referring_provider_email to keep masked values
consistent across both columns.
```

The warning never blocks the run. Apply the fix by giving both the referenced
column and the soft reference a shared `seed_alias` (see above). To silence a
warning you have reviewed and accepted, list its source column path under
`implied_fk_ignore`:

```yaml
implied_fk_ignore:
  - clinical.patient_documents.referring_provider_email
```

## Running a mask job

`privaci run` (or bare `privaci`) loads this file, resolves secrets, runs
pre-flight checks, then streams masked rows to the target:

```bash
export SOURCE_DB_URL=postgresql://postgres:dev@127.0.0.1:55432/privaci_source
export TARGET_DB_URL=postgresql://postgres:dev@127.0.0.1:55433/privaci_target
export ANONYMIZATION_SALT="$(privaci gen-salt)"

privaci run --config mask-rules.yaml
privaci dry-run --config mask-rules.yaml   # pre-flight only (no target wipe)
```

| Flag | Description |
|------|-------------|
| `--config` | Path to this file (default: `/config/mask-rules.yaml`). |
| `--source` | Source DB URL or secret URI (default: `SOURCE_DB_URL`). |
| `--target` | Target DB URL or secret URI (default: `TARGET_DB_URL`). |
| `--dry-run` | On `run` only: pre-flight + per-table summary, no writes. |
| `--no-audit-table` | Skip `_privaci.audit_log` writes for this run. |

Salt resolution: `global_salt` in this file (supports `${ANONYMIZATION_SALT}`
and secret URIs), else the `ANONYMIZATION_SALT` environment variable.

Secret URIs (`aws-sm://`, `azure-kv://`, `vault://`, `env://`, `file://`) use
bounded connect/read timeouts and fail closed on backend errors. The `file://`
backend only reads regular files under allowed roots (default:
`/run/secrets`, `/var/run/secrets`); override with a `:`-separated list in
`PRIVACI_SECRET_FILE_ROOTS`. Symlinks and paths outside those roots are rejected.

## Verifying a run

`privaci verify` audits a completed run by comparing the target against the
source. It is **value-free**: it reports only counts, rates, and verdicts —
never raw cell values — so it is safe to run in any environment, including CI.
Cell equality uses string forms (`str(src)` vs `str(tgt)`), so float formatting
or timestamp precision differences can produce false FAIL/WARN verdicts — treat
verify as a leak/passthrough screen, not a typed equality oracle.

```bash
privaci verify --config mask-rules.yaml
# Verification: 77 passed, 0 warning(s), 0 failure(s).
```

It samples rows (default 1,000 per table, `--sample-size`) and runs these checks:

| Check | Verdict on failure | Catches |
|-------|--------------------|---------|
| `column.change_rate` | FAIL if 0% changed, WARN if partial | A masked column whose values didn't change (mask not applied) |
| `column.passthrough_drift` | FAIL | A passthrough column that changed unexpectedly |
| `table.row_count` | FAIL | Rows dropped or duplicated vs source |
| `table.uniqueness` | FAIL | Faker collisions breaking a PK/UNIQUE constraint |
| `table.fk_integrity` | FAIL | Orphaned foreign keys after masking |

`verify` exits `1` when any check FAILs (warnings do not fail the command), so
it can gate a pipeline. Tables without a single-column primary key skip the
row-level checks (reported as a WARN) but still get structural checks.

| Flag | Description |
|------|-------------|
| `--config` | Path to this file (default: `/config/mask-rules.yaml`). |
| `--source` / `--target` | DB URLs or secret URIs (default: `SOURCE_DB_URL` / `TARGET_DB_URL`). |
| `--sample-size` | Rows per table to sample for row-level checks (default: `1000`). |

## Resuming an interrupted run

After a SIGINT/SIGTERM (exit `130`), checkpoints in `_privaci.table_checkpoints`
record per-table progress. Resume only when config, source URL, and salt are
unchanged:

```bash
privaci resume --config mask-rules.yaml
```

If identity fields drift, resume exits `2` with a structured message. Tables
already marked `done` in checkpoints are skipped; in-progress tables continue
from `last_pk_value`.

## Generating CI workflows

```bash
privaci generate-ci --platform github-actions
# Writes .github/workflows/privaci-refresh.yml and docs/privaci-setup.md

privaci generate-ci --platform gitlab-ci
privaci generate-ci --platform k8s-cronjob
```

Use `--output-dir` to write files somewhere other than the current directory.

## Installing a config pack

```bash
privaci install-pack hipaa --config mask-rules.yaml
# Preview merge, prompt for confirmation

privaci install-pack hipaa --config mask-rules.yaml --yes
privaci install-pack hipaa --local-pack-dir ./packs --config mask-rules.yaml
```

Manifests are verified against a trusted Ed25519 public key before any local
file is modified. Invalid signatures exit `3`.

The engine ships **no** built-in key. You must provide the official release key
through the `PRIVACI_PACK_PUBLIC_KEY` environment variable (a hex-encoded 32-byte
Ed25519 public key). When it is unset, verification fails closed and
`install-pack` aborts before touching your config:

```bash
# Official trust anchor (v0.1.0-beta.1 and later, until rotated):
export PRIVACI_PACK_PUBLIC_KEY="cd965cb6dadcecefd508ae84a000684f431490c3d3ddae006ad5f89bf2c25978"
privaci install-pack hipaa --config mask-rules.yaml
```

| Situation | Result |
| --- | --- |
| `PRIVACI_PACK_PUBLIC_KEY` unset or invalid | Exit `3`, no files modified |
| Key set, signature invalid/tampered | Exit `3`, no files modified |
| Key set, signature valid | Merge proceeds after preview/confirmation |

The release pipeline provisions this key; operators installing official packs
copy it from the published release notes. See the
[pack-signing runbook](runbooks/pack-signing.md) for how the key is generated
and rotated.

## Compliance reports

```bash
privaci report --run <run-uuid> --format json
privaci report --run <run-uuid> --format json --output report.json
```

Community mode emits a JSON stub; signed PDF reports require a
``report_renderer`` plugin.

## Validation rules at a glance

All violations below exit `3` and name the YAML path:

- Unknown top-level or per-action keys (`extra = forbid`).
- Missing or unsupported `version`.
- Misspelled `action` (lists the valid action tags).
- `regex_mask` with a non-compilable `pattern` or an unknown flag.
- `on_existing_data: append` (unsupported in the MVP).
- `batch_size < 1` (global or per-table).
- `action: ai_refine` without an LLM connector plugin installed, **or** with a
  plugin installed but Level-3 not yet wired into the masking path (mask time
  still raises ``L3NotInstalledError``, exit 3).
- `action: null` on a `NOT NULL` column (checked during pre-flight against the
  live catalog).
- Configured table names absent from the source catalog (pre-flight exit `3`).

## Related

- [CLI reference](cli-reference.md) — every `privaci` subcommand and its options.
- [Error codes](error-codes.md) — exit codes and message format.
- [Extending PrivaCI](extending-privaci.md) — the `privaci.plugins` entry-point
  model (including reserved `ai_refine` connectors — not implemented yet).

<!-- registry: secrets StrEnum (ruff UP042) sync -->
