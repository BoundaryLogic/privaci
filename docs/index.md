# PrivaCI

**One command. Sanitized staging data. No data leaves your VPC.**

PrivaCI is a stateless batch engine that reads from a PostgreSQL source
(typically a production replica), masks PII with a three-tier pipeline, and
writes realistic synthetic data to a staging database with referential
integrity preserved.

## Start here

| Goal | Page |
|------|------|
| Run your first mask in under five minutes | [Quickstart](quickstart.md) |
| Every CLI flag and subcommand | [CLI reference (generated)](generated/cli-reference.md) |
| Author `mask-rules.yaml` | [Configuration guide](configuration.md) |
| Deploy with Docker or Helm | [Deployment](deployment.md) |
| Extend the engine with plugins | [Building a plugin](extending-privaci.md) |

## How it works

1. **Introspect** the source schema (tables, FKs, partitions, implied keys).
2. **Replicate** DDL to an empty target database.
3. **Stream** rows through COPY-binary, mask in memory, and load in FK order.
4. **Checkpoint** every batch so a crashed run can resume.
5. **Audit** every decision in `_privaci` tables on the target.

See the [architecture overview](architecture/overview.md) for design rationale.

## License

The engine is licensed under the [Elastic License 2.0](https://github.com/BoundaryLogic/privaci/blob/main/LICENSE).
Optional paid features ship as a separate [plugin layer](extending-privaci.md).
