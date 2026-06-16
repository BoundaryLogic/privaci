# Local Development & Testing

This document captures how a contributor develops and tests PrivaCI
locally. It is the day-1 reference for setting up a workstation,
running the test suites, and exercising the engine end-to-end against
real PostgreSQL databases.

The conventions here are derived from `.cursorrules`, the OpenSpec
change `init-privaci-engine`, and the deployment-artifacts spec.
Where this document and `.cursorrules` disagree, `.cursorrules` wins.

---

## 1. Workstation Prerequisites

| Tool | Minimum version | Notes |
|------|-----------------|-------|
| Python | **3.12 (exactly)** | Per ADR-0002. No 3.11 shims. SpaCy (`nlp` extra) has no wheels for 3.13/3.14 — a non-3.12 venv silently lacks SpaCy. Verify with `python --version`. |
| Docker **or** Podman + Compose v2 | recent | For compose fixtures and the demo run. Podman is the rootless Fedora-native option (see §4.4). On Windows use Docker Desktop (WSL2 backend) or WSL2 — see [`deployment.md` § Windows](deployment.md#windows). |
| `make` | any | Convenience targets only |
| `git` | recent | |
| `pre-commit` | recent | Installed via `pip install pre-commit` |

A working `psql` is helpful for ad-hoc inspection but not required —
tests use `asyncpg` directly.

---

## 2. First-Time Setup

```bash
# 1. Clone and enter the repo
git clone git@github.com:privaci/privaci.git
cd privaci

# 2. Create and activate a venv — MUST be Python 3.12
python3.12 -m venv .venv
source .venv/bin/activate
python --version            # verify: Python 3.12.x

# NOTE: The venv interpreter MUST be 3.12. The `nlp` extra (SpaCy 3.8.x) has
# no wheels for 3.13/3.14, so a 3.14 venv will silently skip SpaCy and the
# spikes will fail with "No module named spacy". If `python --version` is not
# 3.12, recreate the venv: `rm -rf .venv && python3.12 -m venv .venv`.

# 3. Install pinned dev dependencies (lockfile from pip-compile)
pip install -r requirements-dev.txt
pip install -e .                          # editable install of the engine

# 4. Initialize git (required for pre-commit) and install hooks
git init
pre-commit install

# 5. Create a local .env (never commit this file)
cp .env.example .env
# Edit .env to point at your local Postgres instances and salt source.

# 6. Generate a local salt
privaci gen-salt > .privaci-salt
chmod 600 .privaci-salt
# Add ANONYMIZATION_SALT=file:///$(pwd)/.privaci-salt to .env

# 7. Bring up local Postgres (Docker or Podman — see §4)
docker compose -f compose.dev.yml up -d
# Fedora/rootless alternative:
# podman compose -f compose.dev.yml up -d

# 8. Sanity-check
pytest -q -m "not integration"
```

After step 8 you should see all unit tests pass in seconds.

---

## 3. The Three Test Layers

Tests are organized so the fast layer runs in seconds and the slow
layer is opt-in. The CI default mirrors the fast layer exactly so
local and CI feedback loops are identical.

```
┌──────────────────────────────────────────────────────────────┐
│  Layer 1 — Unit (default `pytest`)                            │
│  • masking pipeline (purity, determinism, NULL preservation)  │
│  • deterministic faker (property tests via hypothesis)        │
│  • config validation, secrets URI parsing                     │
│  • CLI parsing via typer.testing.CliRunner                    │
│  • No network. No real DB. Runtime: seconds.                  │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│  Layer 2 — Integration (`pytest -m integration`)              │
│  • catalog introspection vs real schemas                      │
│  • schema replication (DDL clone)                             │
│  • COPY-binary streaming source→target                        │
│  • `_privaci` schema lifecycle, checkpoint atomicity        │
│  • resume after crash                                         │
│  • Backed by pytest-postgresql or compose Postgres            │
│  • Runtime: minutes.                                          │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│  Layer 3 — Smoke / End-to-End                                 │
│  • `docker compose up` against the demo dataset               │
│  • Full container, full CLI, full mask run                    │
│  • Validates packaging, image, image size, non-root user      │
│  • Runtime: ~60 seconds for the demo dataset                  │
└──────────────────────────────────────────────────────────────┘
```

### 3.1. Markers and Filtering

Per `.cursorrules` §2, any test that opens a real DB connection MUST
be marked `@pytest.mark.integration`. The CI gate runs:

```bash
pytest --cov=src --cov-fail-under=85 -m "not integration"
```

Integration tests are a separate CI job that runs less frequently
(every push, but in a parallel workflow) so the main feedback loop
is fast.

Useful invocations:

```bash
pytest                                       # unit only (default)
pytest -m integration                        # integration only (Demo Corp e2e, catalog, edge-case SQL)
pytest -m "integration and not slow"         # subset
pytest tests/masking/                        # one package
pytest tests/masking/test_faker.py::TestEmailFaker::test_determinism
pytest -k "deterministic"                    # name match
pytest --lf                                  # only failures from last run
pytest --cov=src/masking --cov-report=term-missing tests/masking/
```

### 3.2. Coverage

- **≥85% overall** (CI gate via `--cov-fail-under=85`).
- **100%** on `src/masking/`, `src/config/`, and the commercial
  `src/billing/` package when it exists.
- Every new function MUST have at least one positive and one
  negative/edge test.

To inspect coverage gaps locally:

```bash
pytest --cov=src --cov-report=term-missing -m "not integration"
pytest --cov=src --cov-report=html -m "not integration"
open htmlcov/index.html
```

### 3.3. Fixtures

- All shared setup uses `pytest.fixture`. Scope is explicit
  (`function` is the default; `module` / `session` when shared).
- DB fixtures use **`pytest-postgresql`** (preferred for per-test
  isolation) or a long-running compose Postgres (for performance
  tests). Tests SHALL NEVER point at a shared or production DB.
- Test constants live in `tests/fixtures/constants.py`. No magic
  strings inline in test bodies.
- Data generation uses `Faker` seeded with `Faker().seed_instance(42)`
  for repeatability.
- Mocking uses `pytest-mock` (the `mocker` fixture). Direct
  `monkeypatch` is reserved for env vars where `mocker.patch.dict`
  is clumsy.

### 3.4. Mutation testing (opt-in)

Coverage tells you which lines ran; **mutation testing** tells you whether the
tests would actually *catch a bug* in those lines. We use
[`cosmic-ray`](https://cosmic-ray.readthedocs.io/) against the masking core
(`src/privaci/mask/`), scoped by the committed `cosmic-ray.toml`.

```bash
# One-time per session DB (re-init after changing source or tests):
cosmic-ray init cosmic-ray.toml mutation.sqlite
cosmic-ray baseline cosmic-ray.toml          # tests must pass un-mutated
cosmic-ray exec cosmic-ray.toml mutation.sqlite
cr-rate mutation.sqlite                       # surviving-mutant % (lower is better)
cr-report mutation.sqlite                     # per-mutant detail
```

A surviving mutant is either a missing assertion (add a test) or an
*equivalent mutant* that cannot change observable behaviour (e.g. an
`lru_cache` capacity). Session files (`*.sqlite`) are git-ignored.

---

## 4. Local Postgres via Docker Compose

Two compose files coexist:

| File | Purpose |
|------|---------|
| `compose.dev.yml` | Long-running source + target Postgres for development and integration tests |
| `compose.yml` | Self-contained demo: source + target + engine; used for smoke runs and customer-facing evaluation |

### 4.1. `compose.dev.yml` (Development)

```yaml
services:
  source-pg:
    image: postgres:16
    environment:
      POSTGRES_PASSWORD: dev
      POSTGRES_DB: privaci_source
    ports:
      - "55432:5432"
    volumes:
      - source-pgdata:/var/lib/postgresql/data
      - ./tests/fixtures/sql/demo-corp:/docker-entrypoint-initdb.d:ro

  target-pg:
    image: postgres:16
    environment:
      POSTGRES_PASSWORD: dev
      POSTGRES_DB: privaci_target
    ports:
      - "55433:5432"
    volumes:
      - target-pgdata:/var/lib/postgresql/data

volumes:
  source-pgdata:
  target-pgdata:
```

Notable choices:

- **Ports 55432 / 55433** avoid clashing with a system Postgres on 5432.
- **Source** is auto-seeded from `tests/fixtures/sql/demo-corp/`
  via the `docker-entrypoint-initdb.d` convention on first volume
  creation. See [`docs/test-fixtures.md`](test-fixtures.md) for the
  schema, tiers, and regeneration commands (`make fixtures-generate`).
- **Target is empty** by default — this matches the engine's default
  `on_existing_data: fail`.

Environment vars for a contributor's `.env`:

```bash
SOURCE_DB_URL=postgresql://postgres:dev@localhost:55432/privaci_source
TARGET_DB_URL=postgresql://postgres:dev@localhost:55433/privaci_target
ANONYMIZATION_SALT=file:///absolute/path/to/.privaci-salt
PRIVACI_LOG_LEVEL=info
```

### 4.2. `compose.yml` (Demo / Smoke)

The demo compose file at the repo root is what a customer or evaluator runs:

```bash
export ANONYMIZATION_SALT="$(python -m privaci gen-salt)"
docker compose up
```

It builds the `Dockerfile` image, seeds source Postgres from
`deploy/demo-seed/`, and runs `privaci run` with
`examples/mask-rules.demo.yaml` under a read-only root filesystem.
Expected behaviour per the `deployment-artifacts` spec:

- Within 60 seconds the engine streams source → masked target.
- stdout emits a `run.end` event with `status: succeeded`.
- Container exits 0.

This file is part of release CI's smoke gate: every release pipeline
must successfully `docker compose up` against the published image
before the tag is promoted.

### 4.3. Resetting the Local Environment

```bash
docker compose -f compose.dev.yml down -v   # nukes volumes
docker compose -f compose.dev.yml up -d     # re-seed source
```

For a faster reset during integration test development:

```bash
pytest-postgresql --help    # one-shot ephemeral instances per test
```

### 4.4. Docker vs Podman (Fedora / rootless)

The compose file is engine-agnostic. Pick whichever is installed:

```bash
# Docker (rootful by default on Fedora): add yourself to the docker group once
sudo usermod -aG docker "$USER" && newgrp docker
docker compose -f compose.dev.yml up -d

# Podman (rootless, Fedora-native) — drop-in replacement
podman compose -f compose.dev.yml up -d
# If 'podman compose' is unavailable:
sudo dnf install -y podman-compose && podman-compose -f compose.dev.yml up -d
```

> If you see `permission denied while trying to connect to the docker API at
> unix:///var/run/docker.sock`, your user is not in the `docker` group — use
> the `usermod` line above or switch to Podman.

---

## 5. The Day-to-Day Loop

A typical inner loop while implementing a module:

```bash
# 1. Edit src/privaci/<module>/...

# 2. Fast unit tests for the package you touched
pytest tests/<module>/ -q

# 3. Lint + types incrementally
ruff check src/privaci/<module>/
mypy src/privaci/<module>/ --strict

# 4. Coverage check on the touched package
pytest --cov=src/privaci/<module> --cov-report=term-missing tests/<module>/

# 5. (when DB matters) integration tests
pytest -m integration tests/<module>/
```

When you're ready to push:

```bash
# Run exactly what CI runs (per .cursorrules §7)
black --check src/ tests/
isort --check-only --profile black src/ tests/
ruff check src/ tests/
mypy src/ --strict
pytest -m "not integration" --cov=src --cov-fail-under=85
pip-audit --requirement requirements.txt
```

Pre-commit hooks run a subset of these on `git commit` automatically.

---

## 6. Exercising the Engine Locally

With compose databases running and env vars set (`SOURCE_DB_URL`,
`TARGET_DB_URL`, `ANONYMIZATION_SALT`):

```bash
source .venv/bin/activate
export SOURCE_DB_URL=postgresql://postgres:dev@127.0.0.1:55432/privaci_source
export TARGET_DB_URL=postgresql://postgres:dev@127.0.0.1:55433/privaci_target
export ANONYMIZATION_SALT="$(privaci gen-salt)"

# Pre-flight only, no writes
privaci dry-run --config examples/mask-rules.example.yaml

# Actual masking run (same as bare `privaci` with default flags)
privaci run --config examples/mask-rules.example.yaml

# Inspect what the engine recorded
psql "$TARGET_DB_URL" -c "SELECT * FROM _privaci.runs ORDER BY started_at DESC LIMIT 5;"
psql "$TARGET_DB_URL" -c "SELECT event_type, count(*) FROM _privaci.audit_log GROUP BY 1;"

# Test the resume path (manual)
privaci run --config tests/fixtures/configs/demo-corp.yaml &
sleep 5
kill -9 %1
privaci resume --config tests/fixtures/configs/demo-corp.yaml
```

---

## 7. What You Do NOT Need Locally

| Capability | Why it's not needed for local dev |
|------------|------------------------------------|
| AWS account | Engine uses local Postgres + `env://` or `file://` secret URIs |
| Marketplace / metering | Community-mode `NoOpLicenseValidator` runs unrestricted |
| Bedrock / Azure OpenAI | L3 is commercial; L1+L2 are sufficient for local tests |
| Helm / Kubernetes | Compose covers local; Helm only for prod-shape verification |
| LocalStack | Only needed if you're modifying `aws-sm://` resolver code |
| Azurite | Only needed if you're modifying `azure-kv://` resolver code |
| Real production data | **Explicitly forbidden** — `.cursorrules` §2 / §3 |

---

## 8. Security Discipline for Test Code

These are non-negotiable per `.cursorrules` §3:

- **No real PII**, ever — not in fixtures, not in commit messages,
  not in test docstrings. Even synthetic-looking real data is
  prohibited.
- **No hardcoded secrets**. All test-time secrets are either
  generated at runtime (`secrets.token_hex`) or read from env vars
  that the contributor sets in their `.env`.
- **Tests must verify the original value is not present in output**
  for any masking test. The `assert original not in serialized_row`
  pattern is mandatory for masking unit tests.
- **`.env`, `.privaci-salt`, `*.pem`, `*.key`** are in
  `.gitignore`. Verify this is true before committing in any new
  branch.

---

## 9. Common Pitfalls

| Symptom | Likely cause |
|---------|--------------|
| `No module named spacy` | venv is not Python 3.12 (SpaCy has no 3.13/3.14 wheels). `python --version`; if not 3.12, `rm -rf .venv && python3.12 -m venv .venv` and reinstall. |
| `permission denied ... /var/run/docker.sock` | User not in `docker` group. `sudo usermod -aG docker $USER && newgrp docker`, or use Podman (§4.4). |
| `Connect call failed (... 55432)` | Postgres never started (usually a downstream effect of the docker.sock error). Bring compose up first. |
| Tests pass locally, fail in CI | Forgot to run pre-commit / different Python version. Re-create the venv with `python3.12`. |
| `_privaci` schema permission errors | Local target Postgres role lacks `CREATE SCHEMA`. Use the superuser `postgres` for dev. |
| Integration tests hang | Old compose volumes hold a partial run. `docker compose down -v` and retry. |
| Coverage falls below 85% | Find untested lines: `pytest --cov-report=term-missing` and read the report. Add tests, do not lower the gate. |
| `mypy` errors only locally | Stub package out of date. `pip install -U types-PyYAML types-...` or re-run `pip-compile`. |
| `pip-audit` fails | A dependency has a new CVE. Update the lockfile and review the changelog before bumping security-sensitive packages. |

---

## 10. Where to Look Next

- **`docs/README.md`** — the documentation index (start here).
- **`docs/error-codes.md`** — every exit code and the Context + Cause +
  Remediation message format.
- **`docs/architecture/memory-model.md`** — how RAM stays bounded on large
  databases (batch sizing, backpressure, K8s sizing).
- **`docs/test-fixtures.md`** — the representative "Demo Corp" source
  schema, generation strategy, and tier-1/2/3 dataset sizes.
- **`docs/spikes/`** — Week-1 architecture spikes and how to run them.
- **`docs/adr/`** — every load-bearing architectural decision with
  context and consequences.
- **`openspec/changes/init-privaci-engine/`** — the source of truth
  for what the MVP must do and how.
