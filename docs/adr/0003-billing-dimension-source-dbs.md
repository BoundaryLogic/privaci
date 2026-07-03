---
title: "ADR-0003: Source DB billing"
description: "Bill commercial usage by rolling distinct source database count."
---

# ADR-0003: Bill by unique source databases (relocated)

## Status

**Superseded** by ADR-0012 (private `privaci-commercial`) — 2026-07-03. The
source-database-count / data-volume billing dimension is no longer used; the
commercial layer moved to capability-based flat tiers with stateless
entitlement. See the tombstone at
[`0012-capability-tiers-and-license-manager.md`](0012-capability-tiers-and-license-manager.md).

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
