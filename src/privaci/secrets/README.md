# secrets

Resolves database URLs, salts, and other credentials from plain env vars or
secret URIs (`env://`, `file://`, AWS Secrets Manager, Azure Key Vault,
HashiCorp Vault).

## Public API

| Symbol | Role |
|--------|------|
| `resolver.resolve_secret` | Fetch a secret value from a URI |
| `parser.parse_secret_uri` | Parse `scheme://` references |
| `SecretRedactionFilter` | Logging filter that redacts resolved secrets |

## Configuration

`SOURCE_DB_URL`, `TARGET_DB_URL`, `ANONYMIZATION_SALT`, and `global_salt` in
config may use secret URIs.

## Example

```bash
export SOURCE_DB_URL="aws-sm://prod/replica-url"
export ANONYMIZATION_SALT="file:///run/secrets/salt"
```
