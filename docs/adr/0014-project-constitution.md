# ADR-0014: Project Constitution

## Status

Accepted

## Context

Non-negotiables (customer-environment trust boundary, fail-closed behaviour,
PII hygiene, bounded memory, no merge shortcuts, documentation currency) lived
across ADRs, Cursor rules, and CONTRIBUTING prose. Agents and contributors
lacked a single citeable document, and most principles were honour-system
rather than CI-enforced.

## Decision

Adopt a root [`CONSTITUTION.md`](https://github.com/BoundaryLogic/privaci/blob/main/CONSTITUTION.md) as the canonical
article list (I–X). CI and pre-commit gates documented in
[`docs/ci-gates.md`](../ci-gates.md) enforce automatable articles. A Cursor
rule always points assistants at the constitution. Amendments follow Article
IX (ADR + PR updating `CONSTITUTION.md`).

Detailed gate design lives in OpenSpec change `add-ci-hardening-gates`.

## Consequences

- Humans and agents have one north-star document.
- New scanners map to article IDs; waivers cite article + issue.
- Runtime engine behaviour is unchanged by adopting the constitution itself.
