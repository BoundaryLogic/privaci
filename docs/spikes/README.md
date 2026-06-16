# Week-1 Architecture Spikes

These spikes validate core assumptions before locking the streaming and
masking architecture. They map to OpenSpec tasks **§2.1–§2.5** in
`openspec/changes/init-privaci-engine/tasks.md`.

## Prerequisites

```bash
# venv MUST be Python 3.12 — SpaCy has no 3.13/3.14 wheels
python --version            # expect 3.12.x; else: rm -rf .venv && python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,nlp]"
python -m spacy download en_core_web_sm   # SpaCy spike only

# Docker or Podman (rootless, Fedora-native):
docker compose -f compose.dev.yml up -d
# podman compose -f compose.dev.yml up -d
# Wait until both healthchecks pass (~10s on first start)
```

Optional: set `SOURCE_DB_URL` / `TARGET_DB_URL` in `.env` (defaults match
`compose.dev.yml` ports **55432** / **55433**).

> Troubleshooting: `No module named spacy` → venv isn't 3.12.
> `permission denied ... docker.sock` → add yourself to the `docker` group or
> use Podman. See `docs/local-development.md` §4.4.

## Run all spikes

```bash
export SOURCE_DB_URL=postgresql://postgres:dev@localhost:55432/privaci_source
export TARGET_DB_URL=postgresql://postgres:dev@localhost:55433/privaci_target
python scripts/spikes/run_week1_spikes.py
```

Or via pytest (integration + spike markers):

```bash
pytest tests/spikes -m "integration and spike" -v
pytest tests/spikes -m "spike and not integration" -v   # SpaCy only
```

## Spike documents

| Task | Document | Code |
|------|----------|------|
| 2.1 COPY-binary round-trip | [2.1-copy-binary.md](2.1-copy-binary.md) | `privaci.spikes.copy_binary` |
| 2.2 SpaCy throughput | [2.2-spacy-throughput.md](2.2-spacy-throughput.md) | `privaci.spikes.spacy_throughput` |
| 2.3 Cyclic FK deferred | [2.3-cyclic-fk-deferred.md](2.3-cyclic-fk-deferred.md) | `privaci.spikes.cyclic_fk` |

> Spike 2.4 (AWS Marketplace) was a commercial process spike and has been
> relocated to the private `privaci-commercial` repository (ADR-0007).

After running spikes locally, update the per-spike markdown files with your
machine's metrics and any blockers found.
