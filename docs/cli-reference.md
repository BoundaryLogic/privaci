# PrivaCI CLI Reference

The `privaci` executable is the single entry point for every operation. This
page documents each subcommand, its options, and copy-pasteable examples. For
the `mask-rules.yaml` format see [`configuration.md`](configuration.md); for
exit codes see [`error-codes.md`](error-codes.md).

> Running `privaci` with no subcommand is identical to `privaci run`.

## Command summary

| Command | Purpose |
|---------|---------|
| [`run`](#privaci-run) | Execute a masking run against source → target |
| [`dry-run`](#privaci-dry-run) | Pre-flight checks and a per-table plan; no writes |
| [`resume`](#privaci-resume) | Continue an interrupted run from checkpoints |
| [`verify`](#privaci-verify) | Value-free audit of a completed run |
| [`validate`](#privaci-validate) | Validate `mask-rules.yaml` syntax/schema |
| [`gen-salt`](#privaci-gen-salt) | Emit a cryptographically random 64-char salt |
| [`generate-ci`](#privaci-generate-ci) | Write CI/CD workflow templates |
| [`install-pack`](#privaci-install-pack) | Fetch, verify, and merge a config pack |
| [`migrate-config`](#privaci-migrate-config) | Upgrade a config between schema versions |
| [`report`](#privaci-report) | Render a compliance report for a run |
| [`schema config`](#privaci-schema-config) | Print the `mask-rules.yaml` JSON Schema |
| [`catalog inspect`](#privaci-catalog-inspect) | Introspect the source schema |

## Global options

These apply to the default (no-subcommand) invocation:

| Option | Env var | Default | Description |
|--------|---------|---------|-------------|
| `--log-level` | `PRIVACI_LOG_LEVEL` | `info` | Logging level (`debug`, `info`, `warning`, `error`). |
| `--config` | — | `/config/mask-rules.yaml` | Path to `mask-rules.yaml`. |
| `--source` | `SOURCE_DB_URL` | — | Source DB URL or secret URI. |
| `--target` | `TARGET_DB_URL` | — | Target DB URL or secret URI. |
| `--dry-run` | — | `false` | Pre-flight only; do not write rows. |
| `--no-audit-table` | — | `false` | Skip `_privaci.audit_log` writes. |
| `--prometheus-port` | — | _off_ | Serve Prometheus metrics on this port. No port is opened unless set. |

All lifecycle output is emitted as JSON-lines on stdout; see
[`observability.md`](observability.md).

`--help` works at every level (`privaci --help`, `privaci run --help`).

---

## `privaci run`

Execute a masking run: resolve secrets, run pre-flight, replicate schema, and
stream masked rows to the target.

| Option | Env var | Default | Description |
|--------|---------|---------|-------------|
| `--config` | — | `/config/mask-rules.yaml` | Path to `mask-rules.yaml`. |
| `--source` | `SOURCE_DB_URL` | — | Source DB URL or secret URI. |
| `--target` | `TARGET_DB_URL` | — | Target DB URL or secret URI. |
| `--dry-run` | — | `false` | Pre-flight + plan only; no writes. |
| `--no-audit-table` | — | `false` | Skip `_privaci.audit_log` writes (run row still recorded). |
| `--prometheus-port` | — | _off_ | Serve Prometheus metrics on this port (off by default). |

```bash
export SOURCE_DB_URL=postgresql://postgres:dev@127.0.0.1:55432/privaci_source
export TARGET_DB_URL=postgresql://postgres:dev@127.0.0.1:55433/privaci_target
export ANONYMIZATION_SALT="$(privaci gen-salt)"

privaci run --config mask-rules.yaml
# Streaming public.users (~200 rows)
# Streamed public.users: 200 row(s)
# Run 019eaca5-… succeeded: 6 table(s), 900 row(s).
```

Interrupting with `Ctrl+C` (SIGINT) finishes the in-flight batch, marks the run
`interrupted`, and exits `130`. Continue with [`resume`](#privaci-resume).

---

## `privaci dry-run`

Run pre-flight checks and print the per-table action plan, including which
columns auto-detect will mask or flag for review. Never writes rows.

| Option | Env var | Default | Description |
|--------|---------|---------|-------------|
| `--config` | — | `/config/mask-rules.yaml` | Path to `mask-rules.yaml`. |
| `--source` | `SOURCE_DB_URL` | — | Source DB URL or secret URI. |
| `--target` | `TARGET_DB_URL` | — | Target DB URL or secret URI. |
| `--report` | — | — | Write a markdown auto-detect report to this path. |

```bash
privaci dry-run --config mask-rules.yaml
# Pre-flight OK (6 table(s) in source):
# Auto-detect: 12 column(s) to mask, 3 uncertain for review
#   public.users: strategy=transform (~200 rows)
#       mask: email -> fake/email (autodetect)

privaci dry-run --config mask-rules.yaml --report detection.md
```

---

## `privaci resume`

Continue an interrupted run from `_privaci.table_checkpoints`. Resumes only when
the config, source, and salt fingerprints match the interrupted run (the
five-condition gate); otherwise exits `2`.

| Option | Env var | Default | Description |
|--------|---------|---------|-------------|
| `--config` | — | `/config/mask-rules.yaml` | Path to `mask-rules.yaml`. |
| `--source` | `SOURCE_DB_URL` | — | Source DB URL or secret URI. |
| `--target` | `TARGET_DB_URL` | — | Target DB URL or secret URI. |
| `--no-audit-table` | — | `false` | Skip `_privaci.audit_log` writes. |

```bash
privaci resume --config mask-rules.yaml
# Skipping public.users (already done)
# Streaming clinical.visits (~300 rows)
# Run 019eaca5-… resumed: 5 table(s), 700 row(s).
```

Tables already marked `done` are skipped; in-progress tables restart from their
`last_pk_value`.

---

## `privaci verify`

Audit a completed run by comparing the target against the source. **Value-free**:
reports only counts, rates, and verdicts — never raw cell values — so it is safe
in any environment. Exits `1` on any failing check (warnings do not fail).

| Option | Env var | Default | Description |
|--------|---------|---------|-------------|
| `--config` | — | `/config/mask-rules.yaml` | Path to `mask-rules.yaml`. |
| `--source` | `SOURCE_DB_URL` | — | Source DB URL or secret URI. |
| `--target` | `TARGET_DB_URL` | — | Target DB URL or secret URI. |
| `--sample-size` | — | `1000` | Rows per table to sample for row-level checks. |

```bash
privaci verify --config mask-rules.yaml
# Verification: 77 passed, 0 warning(s), 0 failure(s).

privaci verify --config mask-rules.yaml --sample-size 5000
```

See [Verifying a run](configuration.md#verifying-a-run) for the full check list.

---

## `privaci validate`

Validate `mask-rules.yaml` against the schema. Connectivity checks run later
during `run`/`dry-run`. Exits `3` on invalid config.

| Option | Default | Description |
|--------|---------|-------------|
| `--config` | `/config/mask-rules.yaml` | Path to `mask-rules.yaml`. |

```bash
privaci validate --config mask-rules.yaml
# Config mask-rules.yaml is valid.
```

---

## `privaci gen-salt`

Emit one cryptographically random 64-character (256-bit) hex salt to stdout,
generated with the `secrets` module.

```bash
privaci gen-salt
# 3f9a…(64 hex chars)

export ANONYMIZATION_SALT="$(privaci gen-salt)"
```

Each invocation produces a distinct value. Never commit the salt; store it in a
secret manager.

---

## `privaci generate-ci`

Write ready-to-commit CI/CD workflow templates for a chosen platform.

| Option | Default | Description |
|--------|---------|-------------|
| `--platform` | *(required)* | `github-actions`, `gitlab-ci`, or `k8s-cronjob`. |
| `--output-dir` | `.` | Directory to write generated files into. |

```bash
privaci generate-ci --platform github-actions
# Wrote .github/workflows/privaci-refresh.yml
# Wrote docs/privaci-setup.md

privaci generate-ci --platform gitlab-ci
privaci generate-ci --platform k8s-cronjob --output-dir deploy/
```

| Platform | Files written |
|----------|---------------|
| `github-actions` | `.github/workflows/privaci-refresh.yml`, `docs/privaci-setup.md` |
| `gitlab-ci` | `.gitlab-ci.yml` |
| `k8s-cronjob` | `privaci-cronjob.yaml` |

An unknown platform exits `3`.

---

## `privaci install-pack`

Fetch a vertical config pack, verify its Ed25519 manifest signature, preview the
merge, and (after confirmation) merge it into the local config. Invalid
signatures exit `3`; no local file is modified until you confirm.

| Argument / Option | Default | Description |
|-------------------|---------|-------------|
| `NAME` (argument) | *(required)* | Pack name, e.g. `hipaa`. |
| `--config` | `/config/mask-rules.yaml` | Local config to merge into. |
| `--registry-url` | `https://raw.githubusercontent.com/boundarylogic/config-packs/main` | Base URL for pack manifests. |
| `--local-pack-dir` | — | Offline directory containing `<name>/manifest.json`. |
| `--yes` | `false` | Apply the merge without prompting. |

```bash
privaci install-pack hipaa --config mask-rules.yaml
# Pack would change:
#   top-level: strict_autodetect
#   add table: clinical.patients
# Apply this pack to the local config? [y/N]:

privaci install-pack hipaa --config mask-rules.yaml --yes
privaci install-pack hipaa --local-pack-dir ./packs --config mask-rules.yaml
```

---

## `privaci migrate-config`

Upgrade a config file between schema versions. Shipped from v1 even when no
migrations are defined; a no-op when `--from` equals `--to`.

| Argument / Option | Description |
|-------------------|-------------|
| `PATH` (argument) | Path to the config file to migrate. |
| `--from` | Current schema version. |
| `--to` | Target schema version. |

```bash
privaci migrate-config mask-rules.yaml --from 1.0 --to 1.0
# No migration needed.
```

A version the engine cannot satisfy exits `3` with the exact invocation needed.

---

## `privaci report`

Render a compliance report for a completed run. Community mode emits a JSON
stub; signed PDF reports require the commercial layer.

| Option | Default | Description |
|--------|---------|-------------|
| `--run` | *(required)* | Run UUID to report on. |
| `--format` | `json` | Output format (`json`; `pdf` is commercial). |
| `--output` | *(stdout)* | Write report bytes to a local path or object URI (`s3://` with commercial). |

```bash
privaci report --run 019eaca5-32d9-7957-9b00-43d088b7ec6e --format json
privaci report --run 019eaca5-… --format json --output report.json
privaci report --run 019eaca5-… --output "s3://evidence/privaci/run/report.json"
```

See [`object-output.md`](object-output.md) for URI forms.

---

## `privaci schema config`

Print the `mask-rules.yaml` JSON Schema to stdout. Useful for editor validation
or generating documentation.

```bash
privaci schema config > mask-rules.schema.json
```

---

## `privaci catalog inspect`

Introspect the source schema and print tables, the FK-aware load order, and any
warnings (e.g. cyclic or polymorphic FKs). Read-only.

| Option | Env var | Description |
|--------|---------|-------------|
| `--source` | `SOURCE_DB_URL` | Source DB URL or secret URI. |

```bash
privaci catalog inspect --source "$SOURCE_DB_URL"
# public.users (~200 rows)
# public.orders (~540 rows)
# Load plan: [public.users] -> [public.orders]
```

---

## Related

- [Configuration reference](configuration.md) — the `mask-rules.yaml` format.
- [Error codes](error-codes.md) — exit codes and message format.
- [State & audit schema](state-schema.md) — what `run`/`resume` write to `_privaci`.
