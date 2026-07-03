---
title: "ADR-0012: Capability tiers and stateless entitlement"
description: "Tombstone — capability-based commercial tiers live in the private repo."
---

# ADR-0012: Capability-based tiers and stateless entitlement (relocated)

## Status

Accepted — 2026-07-03. Recorded in the private `privaci-commercial` repository
(ADR-0007 placement policy). Supersedes [ADR-0003](0003-billing-dimension-source-dbs.md).

## Summary

This decision replaces the source-database-count / data-volume billing dimension
(ADR-0003) with **capability-based flat tiers** and **stateless entitlement** derived
once per process from a signed license. It removes in-customer usage counting and
usage-metering calls. All of that is **business-model and commercial-layer material**,
so per [ADR-0007](0007-public-commercial-split.md) it lives in the private
`privaci-commercial` repository, not in this public engine repo. The ADR number is
retained here as a tombstone for traceability.

## What stays in the public engine

The engine still computes and persists a stable `source_db_hash` for run identity and
resumability (see `state-and-audit`). The only new public surface is an additive
capability-token field on `LicenseStatus` (`capabilities: frozenset[str]`); the engine
checks capability **membership** and never interprets license-tier names. See the change
`add-license-capabilities`.

See [ADR-0004](0004-state-in-target-database.md) for why run state (including
`source_db_hash`) lives in the target database.
