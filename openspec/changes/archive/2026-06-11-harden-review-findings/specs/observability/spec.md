## ADDED Requirements

### Requirement: Event redaction is safe-by-default

The event redaction layer SHALL redact value-bearing fields by default and SHALL
only emit a field's raw content when that field is explicitly classified as
structural/non-sensitive. Adding a new value-bearing event field SHALL NOT leak its
value merely because it was omitted from an allowlist.

#### Scenario: A new value-bearing field is redacted

- **WHEN** an event carries a value-bearing field that is not in the structural
  allowlist
- **THEN** its value is redacted rather than emitted raw

### Requirement: Value previews cannot reconstruct short PII

Any preview the system emits for a possibly-sensitive value SHALL NOT reveal enough
of the original to reconstruct short PII (for example a social-security number, name,
or short email local-part). Previews SHALL be non-reversible (for example a length
indicator plus a salted hash prefix) rather than the leading characters of the raw
value.

#### Scenario: SSN preview does not leak the number

- **WHEN** a value such as `123-45-6789` is previewed for a DEBUG log or event
- **THEN** the emitted preview does not contain the leading digits of the SSN
