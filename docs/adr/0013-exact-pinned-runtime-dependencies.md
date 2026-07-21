# ADR-0013: Exact-pinned runtime dependencies

## Status

Accepted

## Context

The public engine is both a pip-installable library and the base of a
reproducible container image. Loose dependency ranges improve installability
into mixed environments but can break CI and container builds when upstream
releases shift. Exact pins in `pyproject.toml` / `requirements.txt` match the
container and CI posture today.

## Decision

Keep **exact pins** for production runtime dependencies in `pyproject.toml` and
the compiled `requirements.txt` lock used by CI and images. Document that
operators who need looser resolution should install into a dedicated venv or
use the published container. A future change may split library ranges from an
image lockfile; that is out of scope until we have evidence of install pain.

## Consequences

- Predictable CI and GHCR builds; `pip-audit` against the locked set is
  meaningful and must fail the build on known findings.
- Installing `privaci` into an environment with conflicting pins (especially
  pydantic) may require a dedicated virtualenv.
- Contributors update pins deliberately via `pip-compile` / PR review.
