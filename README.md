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

See the [quickstart](https://docs.boundarylogic.io/quickstart/) for the full walkthrough.

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

Start with the [documentation site](https://docs.boundarylogic.io/) or
[quickstart](https://docs.boundarylogic.io/quickstart/).
Key pages:

**Using PrivaCI**

- [CLI reference](https://docs.boundarylogic.io/cli-reference/) — every command, its options, and examples
- [Configuration reference](https://docs.boundarylogic.io/configuration/) — the `mask-rules.yaml` format
- [Error codes](https://docs.boundarylogic.io/error-codes/) — exit codes and message format
- [State & audit schema](https://docs.boundarylogic.io/state-schema/) — what runs write to `_privaci`
- [Extending PrivaCI](https://docs.boundarylogic.io/extending-privaci/) — the plugin contract model

**Developing PrivaCI**

- [Local development & testing](https://docs.boundarylogic.io/local-development/)
- [Test fixtures — MedicalHelpDesk Corp](https://docs.boundarylogic.io/test-fixtures/)
- [Architecture decision records](https://docs.boundarylogic.io/adr/)

## License

The engine is licensed under the [Elastic License 2.0](LICENSE). Optional
paid features ship as a separate plugin layer via the
[plugin contracts](https://docs.boundarylogic.io/extending-privaci/).

## Commercial

Optional paid capabilities — signed compliance reports, schema-drift detection,
FK-aware subsetting, JSONB path masking, and more — ship as a separate plugin
layer on top of this engine, still entirely in your VPC. Learn more at
[BoundaryLogic](https://boundarylogic.io/commercial).
