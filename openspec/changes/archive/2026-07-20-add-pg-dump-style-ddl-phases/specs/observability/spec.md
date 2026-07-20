## MODIFIED Requirements

### Requirement: Object replication audit events

Structured logging and `_privaci.audit_log` SHALL support three object disposition
event types in addition to existing run events:

- `created_object` — DDL applied on target (`view`, `function`, `trigger`, etc.);
  payload SHALL include `ddl_phase` of `pre-data` or `post-data` when applicable.
- `definition_only_object` — shell created without copying source bytes (materialized
  views); payload SHALL include `contents_copied: false` and `ddl_phase`.
- `skipped_object` — intentionally not replicated; payload SHALL include `kind` and
  `reason`.

#### Scenario: Replicated view emits created_object

- **WHEN** a plain view is replicated in `schema_mode: replicate`
- **THEN** stdout and audit_log SHALL contain `created_object` with `schema_name`,
  `object_name`, `payload.kind = view`, and `ddl_phase = post-data`.

#### Scenario: Materialized view emits definition_only_object

- **WHEN** a materialized view definition is replicated with `WITH NO DATA`
- **THEN** audit_log SHALL contain `definition_only_object` with
  `payload.contents_copied = false` and `ddl_phase = post-data`.

#### Scenario: Trigger emits created_object when replicated

- **WHEN** a trigger is replicated in post-data
- **THEN** audit_log SHALL contain `created_object` with `payload.kind = trigger`
  and `ddl_phase = post-data`.

#### Scenario: Trigger emits skipped_object with reason when disabled

- **WHEN** `replicate_triggers: false` and a trigger is skipped during replication
- **THEN** audit_log SHALL contain `skipped_object` with `payload.kind = trigger`
  and a non-empty `reason`.
