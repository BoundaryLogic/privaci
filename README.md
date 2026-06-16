# PrivaCI

**One command. Sanitized staging data. No data leaves your VPC.**

PrivaCI is a stateless batch engine that reads from a PostgreSQL source
(typically a production replica), masks PII with a three-tier pipeline, and
writes realistic synthetic data to a staging database with referential
integrity preserved.

## Prerequisites

- Python **3.12+**, or the official container image
  (`ghcr.io/boundarylogic/privaci`)
- A PostgreSQL **source** (typically a production replica) and an empty
  **target** database

## Quickstart

**Fastest path** — self-contained evaluation stack (~60 s):

```bash
export ANONYMIZATION_SALT="$(openssl rand -hex 32)"
make eval-up
```

See [`docs/quickstart.md`](docs/quickstart.md) for the full walkthrough.

**Your own databases:**

```bash
pip install -e .
privaci gen-salt > .privaci-salt && chmod 600 .privaci-salt
export ANONYMIZATION_SALT=$(cat .privaci-salt)
export SOURCE_DB_URL=postgresql://user:pass@source-host:5432/app
export TARGET_DB_URL=postgresql://user:pass@target-host:5432/staging

privaci validate && privaci dry-run && privaci run && privaci verify
```

Browse the docs site locally: `pip install -e ".[dev]" && make docs-serve`

## Documentation

Start with the [documentation index](docs/README.md) or [quickstart](docs/quickstart.md).
Key pages:

**Using PrivaCI**

- [CLI reference](docs/cli-reference.md) — every command, its options, and examples
- [Configuration reference](docs/configuration.md) — the `mask-rules.yaml` format
- [Error codes](docs/error-codes.md) — exit codes and message format
- [State & audit schema](docs/state-schema.md) — what runs write to `_privaci`
- [Extending PrivaCI](docs/extending-privaci.md) — the plugin contract model

**Developing PrivaCI**

- [Local development & testing](docs/local-development.md)
- [Test fixtures — MedicalHelpDesk Corp](docs/test-fixtures.md)
- [Architecture decision records](docs/adr/README.md)

## License

The engine is licensed under the [Elastic License 2.0](LICENSE). Optional
paid features ship as a separate plugin layer via the
[plugin contracts](docs/extending-privaci.md).
