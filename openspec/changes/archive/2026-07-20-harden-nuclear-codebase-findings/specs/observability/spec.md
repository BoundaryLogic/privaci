## ADDED Requirements

### Requirement: Structural PII redaction is non-reversible
String values redacted for observability SHALL use a non-reversible form
`***len={n}:{hex}` derived from a hash digest, not a plaintext character preview.

#### Scenario: Email-like value in event field
- **WHEN** an observability field subject to redaction contains an email-like
  string
- **THEN** the emitted value matches the hashed length+digest pattern and does
  not contain the original local-part prefix

### Requirement: commercial_layer_present reflects install state
`run.start` SHALL set `commercial_layer_present` from whether the plugin
package is installed, not a hardcoded false.

#### Scenario: Plugin installed
- **WHEN** the plugin package is importable
- **THEN** `run.start` reports `commercial_layer_present: true`

### Requirement: Free-text event fields are redacted by default
Observability free-text fields such as `message`, `detail`, and `cause` SHALL
be treated as untrusted for PII unless an event-specific allowlist marks them
structural.

#### Scenario: Unexpected PII in message
- **WHEN** an event includes a `message` containing an email address
- **THEN** the emitted message is redacted
