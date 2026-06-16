# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| `0.1.x` (public beta) | Yes |

## Reporting a vulnerability

**Do not open a public GitHub issue for security bugs.**

Email **security@boundarylogic.io** with:

- A description of the issue and its impact
- Steps to reproduce (or a proof of concept)
- Affected versions and configuration
- Your contact information for follow-up

We aim to acknowledge reports within **2 business days** and provide a
remediation timeline within **7 business days** for confirmed issues.

## Scope

In scope:

- The `privaci` engine (`src/privaci/`), container image, and Helm chart in
  this repository
- PII leakage via logs, error messages, audit tables, or masked output
- Authentication bypass of secret backends when misconfigured by the operator
- SQL injection or privilege escalation in database interaction code

Out of scope:

- Misconfiguration by the operator (e.g., mounting production credentials into
  a shared staging cluster, using a weak salt, disabling TLS on database URLs)
- Vulnerabilities in PostgreSQL itself
- The proprietary commercial layer (report to the same address; handled under
  a separate disclosure process)
- Denial-of-service from intentionally large source databases within documented
  memory bounds

## Safe harbor

We support good-faith security research on your own deployments. Do not access
customer data you do not own, and do not exfiltrate real PII during testing —
use the synthetic fixtures under `deploy/demo-seed/` or `tests/fixtures/`.

## Security-related configuration

- Set `ANONYMIZATION_SALT` to a cryptographically random value (≥ 32 chars).
  Generate with `privaci gen-salt`.
- Run the container as the packaged non-root user (UID 10001).
- Use read-only root filesystem and mount config as `:ro`.
- Never commit `.env`, salts, or database credentials to version control.

See [`docs/error-codes.md`](docs/error-codes.md) and
[`docs/deployment.md`](docs/deployment.md) for operational hardening.
