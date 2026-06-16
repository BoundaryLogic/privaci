# ADR-0002: Build the engine in Python 3.12

## Status

Accepted — 2026-05-28

## Context

PrivaCI's masking pipeline depends on SpaCy (`en_core_web_sm`) for
Level 2 NER. SpaCy is Python-only; there is no comparable mature NER
toolkit in Go, Rust, or any other language likely to ship in a single
binary as of 2026.

The choice of runtime sets:

- Cold-start latency (irrelevant for batch jobs, relevant for tests).
- Container image size (not a constraint for container-based distribution).
- Streaming throughput ceiling (matters for large source DBs).
- Developer velocity (the most important factor for a small team with a
  tight scope).
- Ecosystem (mature async-Postgres support, mature pydantic/typer/
  YAML, mature `boto3` / Azure / Vault SDKs).

Alternatives considered: Go (no SpaCy peer), hybrid Go-core + Python
NER sidecar (complex), Rust via `pyo3` extensions (premature
optimization for MVP).

## Decision

Target **Python 3.12** exclusively. Use:

- `asyncio` for all I/O.
- `asyncpg` for PostgreSQL.
- `spacy` + `en_core_web_sm` for L2 NER.
- `pydantic` v2 for config / state models.
- `typer` for the CLI.
- `cryptography` for hashing and signature verification.
- `pytest` + `pytest-postgresql` + `hypothesis` for tests.

Container base image: `python:3.12-slim` pinned to a digest.

The package targets only 3.12+. No 3.11 compatibility shims. Use of
modern features (`type` alias syntax, `Self`, `Unpack`, exception
groups) is allowed.

## Consequences

### Trade-offs accepted

- **Image size ~400 MB** (vs ~20 MB for an equivalent Go binary). Not a
  concern for a container-based batch job.
- **Cold start ~1–2 seconds.** Irrelevant for batch jobs that run for
  minutes.
- **Throughput ceiling likely 50–100k rows/sec** with L1 only, dropping
  below 10k rows/sec on L2-heavy tables. An early spike must validate
  these numbers; if L2 is far slower than expected, the masking layer
  may batch text columns or fall back to a separate-process pool.

### Operational implications

- The SpaCy model is downloaded at image build, not container start.
  This makes the image deterministic and offline-capable.
- Locked Python dependencies via `pip-compile` (per `.cursorrules` §1).
- `mypy --strict` is a CI gate.

### Future revisit triggers

- If `asyncpg` + COPY-binary cannot meet 50k rows/sec on representative
  workloads, consider rewriting the streaming hot path as a `pyo3`
  Rust extension. Estimate: 4-6 engineering weeks. Defer to v1.5.
- If a Go-native SpaCy peer ever matures (currently nothing on the
  horizon), revisit the choice.
