# PrivaCI Error Codes & Message Format

This page is the authoritative reference for every exit code PrivaCI can
return and the format of every error message it prints. It is written for two
audiences:

- **Operators / customers** running PrivaCI in CI or Kubernetes who need to
  branch on exit codes and act on failures.
- **AI tooling and contributors** that parse errors, generate runbooks, or add
  new error sites in the code.

> **Where this is enforced:** the base exception
> [`PrivaCIError`](https://github.com/BoundaryLogic/privaci/blob/main/src/privaci/errors.py)
> renders every error in the
> Context + Cause + Remediation format below and carries the matching
> `exit_code`. Tests live in `tests/test_errors.py`.

---

## 1. Message format: Context + Cause + Remediation

Every operator-facing error follows this structure:

```text
Context: <what the engine was doing>
Cause: <why it failed — never contains PII or secret values>
Remediation: <the exact next step to take>
See: docs/error-codes.md#<anchor>
```

### Example

```text
Context: Validating the resolved anonymization salt
Cause: Resolved salt has length 5, minimum is 32.
Remediation: Generate a new salt with `privaci gen-salt`.
See: docs/error-codes.md#exit-code-4-missing-or-invalid-salt
```

> **How the CLI emits this:** all commands raise `PrivaCIError` subclasses and
> let the centralized boundary (`privaci.cli._errors.run_cli`) print the block
> to stderr and exit with the error's `exit_code`. Commands never call
> `sys.exit` directly.

### Rules

1. **Context** names the operation, not the function. ("Loading
   mask-rules.yaml", not "in `load_config`").
2. **Cause** is factual and PII-free. Never echo column values, salts, rows,
   or full connection strings. Redact to `<redacted>`.
3. **Remediation** is a concrete command or config change, and links back here.
4. Terse internal raises MAY pass only a context string; the structured format
   activates as soon as a `cause` or `remediation` is supplied.

### Raising a structured error (contributors)

```python
from privaci.errors import ConfigError

raise ConfigError(
    "Loading mask-rules.yaml",
    cause="Unknown action type 'shuffle' on column users.email",
    remediation="Use a supported action; see docs/configuration.md#actions.",
)
```

---

## 2. Exit code catalogue

| Code | Name | Meaning | Writes occurred? |
|------|------|---------|------------------|
| `0` | Success | Run (or `--dry-run`) completed successfully | Maybe (run) / No (dry-run) |
| `1` | Generic error | Unexpected/uncategorized failure | Maybe |
| `2` | Pre-flight failure | Target not empty, schema mismatch, missing privileges, catalog error | **No** |
| `3` | Config validation failure | `mask-rules.yaml` invalid or commercial-only action requested | No |
| `4` | Missing or invalid salt | Salt unresolved or shorter than 32 chars | No |
| `5` | License / entitlement failure | Marketplace entitlement check failed (commercial) | No |
| `6` | Drift detected | Schema/config drift detected (commercial) | No |
| `130` | Interrupted | SIGINT/SIGTERM; checkpoints flushed | Partial (checkpointed) |

CI scripts SHOULD treat `2`, `3`, and `4` as "operator must fix input" and `1`
as "open a bug or check logs".

---

## Exit code 0: Success

The run completed. For `run`, the target holds masked data and a `run.end`
event with `status: succeeded` was emitted. For `dry-run`, pre-flight passed
and no rows were written.

**Remediation:** none.

---

## Exit code 1: Generic error

An unexpected error not covered by a specific code. Raised by
`PrivaCIError`, `MaskingError`, and `StateError` by default.

**Common causes**

- A bug in the engine or a plugin.
- An unhandled database or network condition mid-run.
- `privaci verify` found at least one failing check (a masked column that did
  not change, passthrough drift, row-count mismatch, duplicate unique values, or
  an orphaned foreign key). Failing checks are printed to stderr; warnings alone
  do not trigger this exit.

**Remediation**

1. Re-run with `--log-level debug`.
2. Capture the full `Context/Cause/Remediation` block.
3. For `verify` failures, fix the offending rule in `mask-rules.yaml` (see
   [Verifying a run](configuration.md#verifying-a-run)) and re-run the mask job.
4. File an issue with the redacted error and engine version (`privaci --version`).

---

## Exit code 2: Pre-flight failure

A pre-flight check failed **before any writes**. Raised by `PreflightError`
and `CatalogError`.

**Common causes**

- Target database contains user tables and `on_existing_data: fail` (default).
- Source or target unreachable, or insufficient privileges.
- Missing `CREATE SCHEMA` privilege for `_privaci`.
- A table referenced in config does not exist in the source.
- `privaci resume` found no resumable run, or the config, source database, or
  salt changed since the interrupted run. The error names which one drifted; a
  run is resumable while its status is `in_progress`, `interrupted`, or
  `failed`. Restore the original input or start a fresh run with `privaci run`.

**Remediation**

```bash
# Inspect what pre-flight objected to:
privaci dry-run --config mask-rules.yaml

# If the target legitimately has data, choose an explicit policy:
#   on_existing_data: truncate   # wipe target user tables first
# (append is rejected in the MVP — see docs/configuration.md)
```

Grant schema creation if needed:

```sql
GRANT CREATE ON DATABASE privaci_target TO privaci_role;
```

---

## Exit code 3: Config validation failure

`mask-rules.yaml` failed schema validation, or a commercial-only action
(`ai_refine`) was requested without the commercial layer. Raised by
`ConfigError` and `L3NotInstalledError`.

**Common causes**

- Unknown field (configs use `extra = forbid`).
- Unknown `action` type or missing required field for an action.
- `action: ai_refine` without the commercial layer installed.
- Engine v2 reading a `version: "1.0"` config without `migrate-config`.

**Remediation**

```bash
# Validate and see the offending field (pydantic-style path):
privaci validate --config mask-rules.yaml

# Export the JSON Schema your editor can lint against:
privaci schema config > privaci.schema.json
```

---

## Exit code 4: Missing or invalid salt

The anonymization salt could not be resolved, or the resolved value is shorter
than 32 characters. Raised by `SecretError` / `SecretResolutionError`.

**Common causes**

- `ANONYMIZATION_SALT` unset or points at a missing secret.
- Resolved salt is too short.

**Remediation**

```bash
# Generate a strong 64-char salt and store it safely:
privaci gen-salt > .privaci-salt
chmod 600 .privaci-salt
export ANONYMIZATION_SALT=file://$(pwd)/.privaci-salt
```

See [`configuration.md`](configuration.md) (`global_salt`, database URLs) for
`aws-sm://`, `azure-kv://`, `vault://`, `env://`, and `file://` URI schemes.

> **Important:** changing the salt changes every deterministic fake value. Store
> it like a production secret and rotate deliberately.

---

## Exit code 5: License / entitlement failure (commercial)

The commercial layer could not validate a Marketplace entitlement.

**Remediation**

- Confirm the container can reach the AWS Marketplace metering endpoint.
- Verify the subscription is active in AWS Marketplace.
- Community mode (no commercial layer) never returns this code.

---

## Exit code 6: Drift detected (commercial)

The commercial drift detector found schema or config drift versus the last
recorded run.

**Remediation**

- Review the drift report.
- Re-run with `--accept-drift` (commercial) once changes are intentional.

---

## Exit code 130: Interrupted by signal

The engine received SIGINT/SIGTERM. It flushed in-flight checkpoints, closed
connections, emitted `run.end` with `status: interrupted`, and exited.

**Remediation**

```bash
# Resume from the last committed checkpoint (same source + config):
privaci resume --config mask-rules.yaml
```

---

## 3. Quick reference for CI

```bash
privaci run --config mask-rules.yaml
code=$?
case "$code" in
  0)   echo "ok" ;;
  2)   echo "pre-flight failed — see target state / privileges"; exit 2 ;;
  3)   echo "config invalid — run 'privaci validate'"; exit 3 ;;
  4)   echo "salt problem — run 'privaci gen-salt'"; exit 4 ;;
  130) echo "interrupted — run 'privaci resume'"; exit 130 ;;
  *)   echo "unexpected error $code — check logs"; exit "$code" ;;
esac
```
