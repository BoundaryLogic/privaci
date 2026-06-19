## ADDED Requirements

### Requirement: S3 credential resolution

S3 connector credentials SHALL be resolved via the secrets resolver and
standard AWS credential chain. Config MAY specify:

- IAM role attached to the runtime (default on AWS Marketplace image)
- `env://AWS_ACCESS_KEY_ID` and `env://AWS_SECRET_ACCESS_KEY` indirection
- `aws-sm://` URI for access key material (JSON keys `access_key_id`,
  `secret_access_key`, optional `session_token`)

Optional `endpoint_url` SHALL support S3-compatible endpoints (e.g., MinIO)
for contributor testing. Resolved credentials SHALL be wrapped in `SecretStr`
and SHALL NOT appear in logs or exceptions.

#### Scenario: IAM role default

- **WHEN** no explicit keys are configured and the task role can access the
  bucket
- **THEN** the connector SHALL authenticate with the instance/task role
  without env vars.

#### Scenario: Secret URI for static keys

- **WHEN** `config.aws_credentials: aws-sm://prod/privaci-s3-keys`
- **THEN** the engine SHALL fetch keys at boot and use them for all S3
  operations in the run.

#### Scenario: Credential leak prevention

- **WHEN** an S3 `AccessDenied` error occurs
- **THEN** the error message surfaced to the operator SHALL NOT include
  access key or session token values.

### Requirement: S3 URI validation at boot

`s3://` URIs in source and sink configuration SHALL be validated for
well-formed bucket and key/prefix syntax at pre-flight. Invalid URIs SHALL
exit `3` with the offending config path.

#### Scenario: Malformed sink URI

- **WHEN** `sink.path` is `s3:///missing-bucket`
- **THEN** the engine SHALL exit `3` naming the config field.
