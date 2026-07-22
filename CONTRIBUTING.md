# Contributing to PrivaCI

Thanks for your interest in contributing. This repository is the public
**ELv2** masking engine. Product tiers and paid packaging live in a
separate private repository.

## Before you start

1. Read [`CONSTITUTION.md`](CONSTITUTION.md) — project non-negotiables (CI
   enforces automatable articles; see [`docs/ci-gates.md`](docs/ci-gates.md)).
2. Read [`docs/quality-evidence.md`](docs/quality-evidence.md) — threat model
   before code, regression tests, nuclear as checkpoint (not proof).
3. Read [`SECURITY.md`](SECURITY.md) for vulnerability reporting (do not open
   public issues for security bugs).
4. Skim [`docs/local-development.md`](docs/local-development.md) for the
   Python 3.12, Docker, and fixture workflow.
5. Open an issue or discussion before large design changes.

## Development workflow

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
pre-commit install --hook-type commit-msg
./scripts/ci-local.sh   # required before every commit that touches src/tests/scripts
```

Default `./scripts/ci-local.sh` also runs the jscpd duplicate-code gate and
needs **Node.js 20+** (`npx`) on `PATH`, plus `typos` and `gitleaks` (via
`pre-commit install` or standalone CLIs). See
[`docs/ci-gates.md`](docs/ci-gates.md) and
[`docs/local-development.md`](docs/local-development.md).

- Use a feature branch (`feat/…`, `fix/…`, `docs/…`) — do not push directly to
  `main`.
- Match existing Google-style docstrings, type hints, and black/isort/ruff.
- Add tests next to the code you change (`tests/` mirroring `src/`).
- Public-repo language (ADR-0007): do not add product tier names in
  `src/`, operator docs, CHANGELOG, or commit messages.

## Pull requests

- Keep PRs focused; update docs and `CHANGELOG.md` `[Unreleased]` when behaviour
  changes.
- Maintainers merge; do not expect auto-merge.

## Maintenance commitment

BoundaryLogic maintains this engine for production use with an optional
plugin package. Security reports are acknowledged within two business days
(see `SECURITY.md`). Feature work is prioritized via OpenSpec changes under
`openspec/`. We welcome high-quality PRs; response times vary with capacity.
