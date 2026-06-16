# engine-cli Specification

## Purpose
TBD - created by archiving change init-privaci-engine. Update Purpose after archive.
## Requirements
### Requirement: CLI surface and default invocation

The system SHALL expose a single executable, `privaci`, implemented with
the `typer` library. Running `privaci` with no subcommand SHALL invoke
`run` with the default configuration discovery (config file at
`/config/mask-rules.yaml`, env-var-based DB URLs and salt).

The CLI SHALL provide the following subcommands:

- `run` — execute a masking run.
- `dry-run` — perform pre-flight checks only, no writes.
- `validate` — validate config and verify connectivity, no run.
- `gen-salt` — emit a cryptographically random 64-character salt to stdout.
- `generate-ci` — emit CI/CD workflow files for a chosen platform.
- `install-pack` — fetch and merge a vertical config pack.
- `migrate-config` — upgrade a YAML config from an older schema version.
- `resume` — resume an in-progress run from its checkpoints.
- `report` — render a compliance report from a completed run (commercial).

#### Scenario: Default subcommand

- **WHEN** the user runs `privaci` with no subcommand and a valid env
- **THEN** the engine SHALL behave identically to `privaci run`.

#### Scenario: Unknown subcommand

- **WHEN** the user runs `privaci nonexistent`
- **THEN** the engine SHALL exit with code `1` and print the usage line.

#### Scenario: `--help` works at every level

- **WHEN** the user runs `privaci --help` or `privaci <subcommand> --help`
- **THEN** the engine SHALL print help and exit with code `0`.

### Requirement: Exit codes

The system SHALL use a stable set of exit codes so CI scripts can branch
on outcome.

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Generic error (unexpected) |
| `2` | Pre-flight failure (target not empty, schema mismatch, missing privileges) |
| `3` | Config validation failure |
| `4` | Missing or invalid salt |
| `5` | License / Marketplace entitlement failure (commercial only) |
| `6` | Drift detected (commercial only) |
| `130` | Interrupted by signal (SIGINT/SIGTERM) |

#### Scenario: Config file is missing required field

- **WHEN** `mask-rules.yaml` lacks a required field
- **THEN** the engine SHALL exit with code `3` and a pydantic-style error
  pointing to the offending field.

#### Scenario: Salt is shorter than 32 characters

- **WHEN** the resolved salt has length < 32
- **THEN** the engine SHALL exit with code `4` and instruct the user to
  generate a new salt with `privaci gen-salt`.

#### Scenario: Target has user tables and on_existing_data is `fail`

- **WHEN** the target database contains any user tables outside the
  `_privaci` schema and `on_existing_data` is `fail` (the default)
- **THEN** the engine SHALL exit with code `2` before any writes occur.

#### Scenario: SIGINT during a run

- **WHEN** the engine receives SIGINT mid-run
- **THEN** it SHALL flush in-flight checkpoints, close DB connections,
  emit a `run.end` event with status `interrupted`, and exit `130`.

### Requirement: Pre-flight checks run before any writes

The system SHALL execute a pre-flight phase before any `INSERT`, `COPY`,
`TRUNCATE`, `DROP`, or `CREATE` is sent to the target. Pre-flight SHALL
verify:

1. Source DB reachable, read perms confirmed on `pg_catalog`.
2. Target DB reachable, write perms confirmed.
3. `CREATE SCHEMA` privilege on target (or `_privaci` already exists).
4. Target is empty OR the configured `on_existing_data` permits writes.
5. Estimated row count vs target disk capacity (warn if > 80% projected).
6. Config validates against the JSON Schema.
7. Every table referenced in config exists in source.
8. No `exclude` strategy creates an unsatisfiable FK from a non-excluded
   table.
9. Salt is resolved, length-validated, fingerprint logged (not value).
10. Marketplace entitlement check passes (commercial only).

#### Scenario: All pre-flight checks pass

- **WHEN** every check above succeeds
- **THEN** the engine SHALL emit a single `preflight.ok` event with
  per-check status and proceed.

#### Scenario: Any pre-flight check fails

- **WHEN** any pre-flight check fails
- **THEN** the engine SHALL exit with the corresponding exit code and
  emit a `preflight.fail` event naming the failed check; no writes
  SHALL have occurred.

#### Scenario: `--dry-run` flag

- **WHEN** the user passes `--dry-run`
- **THEN** the engine SHALL run pre-flight, print a per-table summary of
  intended actions, and exit `0` without writing any rows.

### Requirement: `gen-salt` produces a usable salt

`privaci gen-salt` SHALL emit to stdout exactly one line containing a
cryptographically random salt of length 64 (256 bits hex) generated with
the `secrets` module.

#### Scenario: Generated salt is usable

- **WHEN** the user runs `privaci gen-salt > .salt && export ANONYMIZATION_SALT=$(cat .salt) && privaci validate`
- **THEN** the engine SHALL accept the salt and report `validate` as
  successful.

#### Scenario: Salt is not predictable

- **WHEN** `gen-salt` is invoked 1000 times
- **THEN** the engine SHALL produce 1000 distinct outputs.

### Requirement: `generate-ci` emits ready-to-commit workflows

The system SHALL provide a `generate-ci --platform
<github-actions|gitlab-ci|k8s-cronjob>` subcommand that writes a
workflow file and (where applicable) a least-privilege IAM policy file
to the current directory.

#### Scenario: GitHub Actions output

- **WHEN** the user runs `privaci generate-ci --platform github-actions`
- **THEN** the engine SHALL write `.github/workflows/privaci-refresh.yml`
  with a weekly schedule, env-var-driven secrets, and the official
  privaci image reference; AND a sibling
  `docs/privaci-setup.md` describing the required GitHub secrets.

#### Scenario: K8s CronJob output

- **WHEN** the user runs `privaci generate-ci --platform k8s-cronjob`
- **THEN** the engine SHALL write a CronJob manifest using the official
  Helm-chart-compatible secret names.

### Requirement: `migrate-config` is shipped from v1

`privaci migrate-config --from <old> --to <new> <path>` SHALL be
present from the first release, even if no migrations are yet defined.

#### Scenario: No migration needed

- **WHEN** `--from` and `--to` are equal
- **THEN** the engine SHALL print "no migration needed" and exit `0`.

#### Scenario: Engine v2 reads a v1 config

- **WHEN** an engine v2 boots with a `version: "1.0"` config and no
  `--migrate` flag
- **THEN** the engine SHALL exit `3` and print the exact
  `migrate-config` invocation required.

### Requirement: `install-pack` is sandboxed

`privaci install-pack <name>` SHALL fetch from a configured registry
URL (default: `https://github.com/boundarylogic/config-packs`), verify a
manifest signature, preview the merge result, and prompt for confirmation
before writing to the local config.

#### Scenario: Pack signature invalid

- **WHEN** the pack manifest's signature does not verify against the
  public key shipped with the engine
- **THEN** the engine SHALL refuse to install and exit `1`.

#### Scenario: User declines merge preview

- **WHEN** the user answers "no" to the merge preview
- **THEN** the engine SHALL not modify any local file.

