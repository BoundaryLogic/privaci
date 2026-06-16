# secrets-resolver Specification

## Purpose
TBD - created by archiving change harden-review-findings. Update Purpose after archive.
## Requirements
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

### Requirement: URI-based secret resolution

The system SHALL resolve secret-bearing string fields via a URI scheme
at boot. Supported URI schemes:

- `aws-sm://<secret-id>[?region=<region>&key=<json-key>&version=<id>]`
- `azure-kv://<vault-name>/<secret-name>[?version=<id>]`
- `vault://<mount>/<path>#<key>`
- `env://<VAR_NAME>`
- `file://<absolute-path>`
- Literal `postgres://...`, `postgresql://...` — accepted for DB URLs
  only.
- Plain string — accepted as a literal value (for non-prod convenience).

The resolver SHALL be invoked for:

- `SOURCE_DB_URL`, `TARGET_DB_URL`
- `ANONYMIZATION_SALT` / `config.global_salt`
- L3 LLM credentials (commercial)
- Any other field tagged as `SecretField` in the pydantic model

#### Scenario: AWS Secrets Manager resolution

- **WHEN** `SOURCE_DB_URL=aws-sm://prod/db-creds?key=connection_string`
- **THEN** the engine SHALL fetch the secret using the container's
  attached IAM role, extract the `connection_string` JSON key, and use
  the resolved value as the source DB URL.

#### Scenario: Azure Key Vault resolution

- **WHEN** `ANONYMIZATION_SALT=azure-kv://acme-prod-vault/privaci-salt`
- **THEN** the engine SHALL fetch the secret via `DefaultAzureCredential`
  and use the result as the salt.

#### Scenario: HashiCorp Vault resolution

- **WHEN** `TARGET_DB_URL=vault://kv/data/staging-db#connection_url`
- **THEN** the engine SHALL fetch the KV-v2 secret at `kv/data/staging-db`
  and use the `connection_url` field.

#### Scenario: File-based secret (K8s secret mounts)

- **WHEN** `ANONYMIZATION_SALT=file:///run/secrets/privaci-salt`
- **THEN** the engine SHALL read the file (in text mode, strip
  trailing newlines) and use the contents as the salt.

#### Scenario: Env var indirection

- **WHEN** `config.global_salt = "env://PRIVACI_SALT"`
- **THEN** the engine SHALL resolve via `os.environ["PRIVACI_SALT"]`.

### Requirement: Secret values are redacted in logs and errors

The engine SHALL wrap all resolved secrets in a `SecretStr` type whose
`__repr__` and `__str__` return `"<redacted>"`. A logging filter SHALL
strip any known secret values from log records.

#### Scenario: Exception logged with secret in scope

- **WHEN** an asyncpg connection error includes the password in its
  message
- **THEN** the logged message SHALL have the password replaced with
  `<redacted>`.

#### Scenario: Salt printed by accident

- **WHEN** any code path tries to `str()` a salt SecretStr
- **THEN** the output SHALL be `<redacted>`, not the salt value.

### Requirement: Resolution failure handling

The system SHALL classify each secret URI as either required or
optional. If an optional secret URI fails to resolve, the engine SHALL
emit a `warning` event and continue with the dependent feature
disabled. If a required secret URI fails to resolve, the engine SHALL
exit with the appropriate code (`2` for DB URLs, `4` for salt).

#### Scenario: Missing AWS Secrets Manager secret

- **WHEN** `SOURCE_DB_URL=aws-sm://missing/secret`
- **THEN** the engine SHALL exit `2` with an error naming the secret
  and the underlying AWS error.

#### Scenario: Missing optional webhook secret

- **WHEN** the optional `notify.slack_webhook_url` resolves to a missing
  secret
- **THEN** the engine SHALL warn and disable Slack notifications, but
  the run SHALL proceed.

### Requirement: Resolution happens once, at boot

Secrets SHALL be resolved during the configuration/preflight phase. The
engine SHALL NOT re-fetch secrets mid-run. Rotated secrets require a
new container run.

#### Scenario: Rotation mid-run

- **WHEN** an AWS Secrets Manager secret is rotated mid-run
- **THEN** the engine SHALL continue using the originally-resolved
  value until the current run ends.

### Requirement: Salt URI is length-validated post-resolution

After resolving the salt URI, the system SHALL verify the resolved
value's length is ≥ 32 characters before any masking begins.

#### Scenario: Short salt in Secrets Manager

- **WHEN** the resolved salt is `"short"`
- **THEN** the engine SHALL exit `4` with the message "Resolved salt
  has length 5, minimum is 32. Generate a new salt with `privaci
  gen-salt`."

