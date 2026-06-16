## ADDED Requirements

### Requirement: Connection-string passwords are redacted everywhere

The system SHALL strip the password from any PostgreSQL connection string before it
appears in logs, error messages, or object reprs. The parsed-URI type SHALL define
a `__repr__` that never exposes the raw DSN, and connection-string redaction SHALL
remove the password rather than retaining the `user:pass` userinfo segment.

#### Scenario: Parsed URI repr hides the password

- **WHEN** a parsed `postgresql://user:secret@host/db` URI is rendered via `repr()`
- **THEN** the output contains neither `secret` nor the full raw DSN

#### Scenario: Resolution error text hides the password

- **WHEN** resolving a postgres connection string fails and the URI appears in the
  error
- **THEN** the password does not appear in the error text

### Requirement: Log redaction does not skip short secrets

The secret log-redaction filter SHALL register every resolved secret value for
scrubbing regardless of length, so short database passwords are not emitted.

#### Scenario: A short password is scrubbed

- **WHEN** a resolved secret shorter than eight characters would otherwise appear in
  a log record
- **THEN** the filter replaces it with the redaction marker

### Requirement: Secret backends apply timeouts and fail loud

Each secret backend (AWS Secrets Manager, Azure Key Vault, HashiCorp Vault) SHALL
apply a bounded network timeout, release client resources deterministically, and log
the failure (without secret values) before raising on error.

#### Scenario: Backend network stall does not hang boot indefinitely

- **WHEN** a secret backend cannot reach its service
- **THEN** the call times out and raises a structured secret error with
  non-sensitive context

### Requirement: File secret backend constrains what it can read

The file secret backend SHALL only read from configured allowed roots, SHALL NOT
follow symlinks out of those roots, and SHALL enforce a maximum file size, so it
cannot be pointed at arbitrary sensitive files.

#### Scenario: Path outside the allowed root is rejected

- **WHEN** a file secret URI references a path outside the allowed root (directly or
  via symlink)
- **THEN** the backend refuses to read it and raises a secret error
