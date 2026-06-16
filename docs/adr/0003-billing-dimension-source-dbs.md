# ADR-0003: Bill by unique source databases (relocated)

## Status

Accepted — 2026-05-28. Relocated to the private `privaci-commercial` repository
— 2026-06-11 (ADR-0007 placement policy; `init-privaci-engine` task §18.7.2).

## Summary

This decision covers the **commercial billing dimension** — how the proprietary
layer counts unique source databases and maps them to Marketplace pricing tiers.
That is business-model material, so per [ADR-0007](0007-public-commercial-split.md)
it lives in the private `privaci-commercial` repository, not in this public
engine repo. The ADR number is retained here as a tombstone for traceability.

## What stays in the public engine

The engine computes and persists a **stable** `source_db_hash`
(`sha256(host:port/dbname)`) on every run, recorded in `_privaci.runs`. This
supports run identity and resumability and is specified by the engine's
`state-and-audit` capability. How any commercial layer aggregates those hashes
for metering or tiering is out of scope for the public engine.

See [ADR-0004](0004-state-in-target-database.md) for why run state (including
`source_db_hash`) lives in the target database.
