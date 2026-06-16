## ADDED Requirements

### Requirement: Pattern-based PII column scanner

The system SHALL inspect every column's name, table name, column type,
and (when available) `pg_stats.avg_width`, matching against a built-in
pattern library to infer a likely PII classification and a default
masking action. Auto-detection SHALL be ON by default and SHALL run
regardless of whether a YAML config is supplied.

Each inspection SHALL produce a **detection finding** with:

- `confidence`: `high`, `medium`, or `low`
- `reasons`: human-readable strings explaining the score
- `action` / `provider`: proposed masking when confidence is sufficient

Only `high` confidence findings SHALL be applied automatically at run
time. `medium` findings SHALL appear in `dry-run --report` as uncertain;
`low` findings are passthrough unless YAML overrides.

Structured PII patterns (`email`, `ssn`, `phone`, …) SHALL receive
`high` confidence on column-name match alone. Freeform / L2 patterns
(`note*`, `comment*`, `description`, …) SHALL additionally require
column type (`text` or `varchar` with declared length ≥ 500) and SHALL
use `pg_stats.avg_width` plus table-name context to set confidence
(see ADR-0011).

Built-in patterns (case-insensitive substring or regex match against
column name) SHALL cover at minimum:

| Pattern (substring / regex) | Inferred provider | Default action |
|----------------------------|-------------------|----------------|
| `email`, `e_mail`, `*_email`, `email_*` | `email` | `fake` |
| `phone`, `mobile`, `tel`, `cell`, `*_phone` | `phone` | `fake` |
| `ssn`, `social_security`, `tax_id`, `national_id` | `ssn` | `fake` |
| `first_name`, `fname`, `given_name` | `first_name` | `fake` |
| `last_name`, `lname`, `surname`, `family_name` | `last_name` | `fake` |
| `full_name`, `display_name`, `^name$` | `full_name` | `fake` |
| `address`, `street`, `city`, `postcode`, `zip`, `country` | corresponding | `fake` |
| `dob`, `date_of_birth`, `birth_date`, `birthday` | `dob` | `fake` |
| `ip`, `ip_address`, `remote_ip`, `last_login_ip` | `ip_address` | `fake` |
| `credit_card`, `card_number`, `cc_number`, `pan` | `credit_card` | `fake` |
| `password`, `passwd`, `pwd`, `password_hash` | `password` | `static` (`privaci-test-pw`) |
| `token`, `api_key`, `secret`, `*_token`, `auth_*` | `token` | `hash` |
| `note*`, `comment*`, `description`, `bio`, `about` | _freeform_ | `ner_mask` (L2) |

#### Scenario: Standard `users.email` column

- **WHEN** auto-detect inspects a column named `email` of type `text`
- **THEN** it SHALL classify it as `email` and select action `fake` with
  provider `email`.

#### Scenario: Suffix-style naming

- **WHEN** a column is named `customer_email`
- **THEN** auto-detect SHALL match the `*_email` suffix and apply the
  same classification.

#### Scenario: Freeform text auto-detected for L2

- **WHEN** a column is named `agent_notes` with type `text`,
  `pg_stats.avg_width` ≥ 200, and the parent table name matches a
  sensitive-context prior (e.g. `support`, `patient`, `visit`)
- **THEN** auto-detect SHALL classify the finding as `high` confidence
  and apply `action: ner_mask` (L2).

#### Scenario: Freeform text down-ranked on catalog tables

- **WHEN** a column is named `description` on table `products` with
  type `text` and `pg_stats.avg_width` ≥ 200
- **THEN** auto-detect SHALL classify the finding as `medium`
  confidence (uncertain) and SHALL NOT auto-apply `ner_mask` without
  explicit YAML.

#### Scenario: Missing stats on freeform column

- **WHEN** a column matches a freeform name pattern and type checks pass
  but `pg_stats` has no `avg_width` for that column
- **THEN** auto-detect SHALL classify the finding as `medium` on
  sensitive tables and `low` on neutral/low-sensitivity tables.

### Requirement: Config overrides auto-detect on a per-column basis

The system SHALL treat any explicit per-column entry in `mask-rules.yaml`
as authoritative and SHALL NOT override it with an auto-detect action,
even when the explicit action is `passthrough`.

#### Scenario: Explicit passthrough wins

- **WHEN** auto-detect would mask `users.email` but config says
  `users.email: { action: passthrough }`
- **THEN** the engine SHALL not mask the column.

#### Scenario: Explicit fake_domain wins

- **WHEN** auto-detect would use the default email-domain list but
  config sets `users.email: { action: fake, provider: email, domains: ["test.org"] }`
- **THEN** the engine SHALL use `test.org`.

### Requirement: Strict mode

The system SHALL provide a `--strict-autodetect` CLI flag (and
`config.strict_autodetect: true` equivalent). In strict mode, any
column matching a PII pattern but NOT explicitly addressed by config
SHALL cause the engine to exit `3` at config validation, naming the
columns.

#### Scenario: Strict mode catches uncovered PII column

- **WHEN** `strict_autodetect` is on AND `users.email` is auto-matched
  but not in the YAML
- **THEN** the engine SHALL exit `3` with a list of uncovered columns
  and the line `Add 'users.email' to mask-rules.yaml or pass
  --no-strict-autodetect to acknowledge.`

#### Scenario: Strict mode permits explicit passthrough

- **WHEN** `strict_autodetect` is on AND `users.email` is configured
  `passthrough`
- **THEN** the engine SHALL accept the config and proceed.

### Requirement: Detection findings recorded in audit log

Every auto-detect classification (matched or not) SHALL be written to
`_privaci.audit_log` with the table, column, matched pattern, inferred
provider, and the action taken. This SHALL include cases where config
overrode the detection.

#### Scenario: Audit-log entries on first run

- **WHEN** an engine runs with no YAML config against a schema with 50
  columns
- **THEN** `_privaci.audit_log` SHALL contain one row per inspected
  column with the detection result.

### Requirement: `privaci dry-run --report` mode

`privaci dry-run --report <path>` SHALL write a human-readable
markdown summary listing, per table:

- Columns being masked (with inferred provider).
- Columns being passed through.
- Columns flagged but uncertain (recommend manual review).

#### Scenario: Reviewable report

- **WHEN** the user runs `privaci dry-run --report report.md`
- **THEN** a markdown file is written, and the engine exits `0` having
  written no rows.

### Requirement: Pattern library is extensible

The pattern library SHALL be data-driven (YAML or Python data
structure) and SHALL support contributed extensions via vertical config
packs (see `install-pack`).

#### Scenario: HIPAA pack extends patterns

- **WHEN** the HIPAA config pack is installed
- **THEN** patterns for `patient_id`, `mrn`, `diagnosis_code`,
  `provider_npi`, etc. SHALL be available for auto-detect.
