# PrivaCI Documentation Index

PrivaCI is an in-VPC PostgreSQL batch masking and anonymization engine. This
folder is the canonical documentation set. Start here, then follow the links.

> **Doc conventions:** see [`.cursor/rules/documentation.mdc`](../.cursor/rules/documentation.mdc).
> Docs are updated in the same change as the code, are written customer-first
> with examples, and use stable headings/anchors so tooling can link into them.

## Getting started

| Doc | What it covers |
|-----|----------------|
| [`quickstart.md`](quickstart.md) | Zero to first masked row (evaluation compose or your own DBs) |
| [`local-development.md`](local-development.md) | Workstation setup (Python 3.12 venv, Docker/Podman), test layers, capability harness (§6.1), day-to-day loop |
| [`test-fixtures.md`](test-fixtures.md) | The "MedicalHelpDesk Corp" source schema and dataset tiers |
| [`spikes/README.md`](spikes/README.md) | Week-1 architecture spikes and how to run them |

### Documentation site (MkDocs)

Browse locally:

```bash
pip install -e ".[dev]"
make docs-serve
```

Build static HTML:

```bash
make docs-build
```

Auto-generated reference pages (regenerate with `make docs-generate`):

| Generated | Source |
|-----------|--------|
| [`generated/cli-reference.md`](generated/cli-reference.md) | Typer CLI in `src/privaci/cli/app.py` |
| [`generated/configuration-reference.md`](generated/configuration-reference.md) | pydantic `Config` JSON Schema |
| [`generated/mask-rules.schema.json`](generated/mask-rules.schema.json) | Raw JSON Schema |

## Operating PrivaCI

| Doc | What it covers |
|-----|----------------|
| [`cli-reference.md`](cli-reference.md) | Every `privaci` subcommand, its options, and copy-pasteable examples |
| [`configuration.md`](configuration.md) | The `mask-rules.yaml` reference: top-level options, table strategies, and every masking action |
| [`state-schema.md`](state-schema.md) | The `_privaci` run-state & audit schema: required grant, tables, fingerprints, audit opt-out |
| [`observability.md`](observability.md) | The JSON-lines stdout event stream, event catalog, PII redaction, log levels, and optional Prometheus metrics |
| [`deployment.md`](deployment.md) | Container image, evaluation `docker compose`, Helm chart, and release publishing |
| [`error-codes.md`](error-codes.md) | Every exit code + the Context + Cause + Remediation message format |
| [`runbooks/pack-signing.md`](runbooks/pack-signing.md) | Generating, provisioning (`PRIVACI_PACK_PUBLIC_KEY`), and rotating the config-pack signing key |
| [`runbooks/release-infrastructure.md`](runbooks/release-infrastructure.md) | Secrets, environments, GHCR/PyPI/Pages setup after a fresh repo |
| [`runbooks/git-history-privacy.md`](runbooks/git-history-privacy.md) | Keeping personal emails out of git history (CI guard remediation) |
| [`architecture/overview.md`](architecture/overview.md) | MVP architecture summary (streaming, FKs, state, masking tiers) |
| [`architecture/memory-model.md`](architecture/memory-model.md) | How RAM stays bounded on large databases (batch sizing, backpressure, sizing guidance) |

## Extending PrivaCI

| Doc | What it covers |
|-----|----------------|
| [`extending-privaci.md`](extending-privaci.md) | Plugin/contract model for the commercial layer |

## Architecture decisions

[`adr/`](adr/) holds numbered Architecture Decision Records. Highlights:

| ADR | Decision |
|-----|----------|
| [0001](adr/0001-elv2-license.md) | Elastic License 2.0 for the public engine |
| [0002](adr/0002-python-3-12-runtime.md) | Python 3.12 runtime |
| [0011](adr/0011-autodetect-confidence-scoring.md) | Auto-detect confidence scoring and table context |
| [0004](adr/0004-state-in-target-database.md) | `_privaci` state schema in the target DB |
| [0005](adr/0005-salt-ux-no-silent-default.md) | User-supplied salt, no silent default |
| [0006](adr/0006-copy-binary-streaming.md) | COPY-binary streaming |
| [0010](adr/0010-constant-memory-streaming.md) | Constant-memory streaming bounds |
| [0008](adr/0008-fk-strategy-topo-sort-deferred.md) | Topo-sort + deferred-constraint FK strategy |
| [0009](adr/0009-postgres-native-partitioning.md) | Native partitioning support |

## Source of truth for the MVP

The OpenSpec change `openspec/changes/init-privaci-engine/` (proposal,
design, specs, tasks) defines what the MVP must do and tracks implementation
progress.
