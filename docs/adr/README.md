# Architecture Decision Records

This directory captures every significant architectural decision made
for PrivaCI. Each ADR follows the template defined in
`.cursorrules` §6.

## How to use this directory

- **Read order:** ADRs are numbered chronologically by acceptance date.
  Newer ADRs may supersede or amend older ones; that relationship is
  documented in the **Status** section of each file.
- **Adding an ADR:** Copy `template.md`, increment the number, and fill
  in the sections. Submit as part of the change proposal that motivates
  the decision.
- **Superseding:** When a new ADR replaces an old one, set the old
  ADR's **Status** to `Superseded by ADR-NNNN` and link both ways.

## Index

| # | Title | Status |
|---|-------|--------|
| 0001 | [Use Elastic License 2.0 for the public engine](0001-elv2-license.md) | Accepted |
| 0002 | [Build the engine in Python 3.12](0002-python-3-12-runtime.md) | Accepted |
| 0003 | [Bill by unique source databases](0003-billing-dimension-source-dbs.md) | Relocated to `privaci-commercial` |
| 0004 | [Store run state in `_privaci` schema in the target DB](0004-state-in-target-database.md) | Accepted |
| 0005 | [Require an explicit user-supplied salt with no silent default](0005-salt-ux-no-silent-default.md) | Accepted |
| 0006 | [Stream via PostgreSQL `COPY ... (FORMAT BINARY)`](0006-copy-binary-streaming.md) | Accepted |
| 0007 | [Split into public engine + private commercial layer](0007-public-commercial-split.md) | Accepted |
| 0008 | [Topological-sort FK loading with deferred constraints for cycles](0008-fk-strategy-topo-sort-deferred.md) | Accepted |
| 0009 | [Support PostgreSQL native partitioning in MVP](0009-postgres-native-partitioning.md) | Accepted |
| 0010 | [Constant-memory streaming bounds](0010-constant-memory-streaming.md) | Accepted |
| 0011 | [Auto-detect confidence scoring and table context](0011-autodetect-confidence-scoring.md) | Accepted |
