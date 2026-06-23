## MODIFIED Requirements

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

Output destination flags (`report --output`, `dry-run --report`, commercial
`preview --policy-diff`, `preview --sarif`) SHALL accept local paths,
`file://`, and cloud URIs when an `ObjectWriter` plugin supports them.

#### Scenario: Default subcommand

- **WHEN** the user runs `privaci` with no subcommand and a valid env
- **THEN** the engine SHALL behave identically to `privaci run`.

#### Scenario: Unknown subcommand

- **WHEN** the user runs `privaci nonexistent`
- **THEN** the engine SHALL exit with code `1` and print the usage line.

#### Scenario: `--help` works at every level

- **WHEN** the user runs `privaci --help` or `privaci <subcommand> --help`
- **THEN** the engine SHALL print help and exit with code `0`.

#### Scenario: Report to object URI

- **WHEN** the user runs `privaci report --run <uuid> --output s3://bucket/key.json`
  with commercial installed and valid AWS credentials
- **THEN** the engine SHALL upload the report and exit `0`.

#### Scenario: Dry-run report to local path

- **WHEN** the user runs `privaci dry-run --report ./detection.md`
- **THEN** the engine SHALL write the markdown report locally as before.
