# ADR-0009: Support PostgreSQL native partitioning in MVP

## Status

Accepted — 2026-05-29

## Context

PostgreSQL has shipped declarative (native) partitioning since 10
(`PARTITION BY RANGE / LIST / HASH`). In 2026, it is the default
choice for high-volume event, audit, and time-series tables in
real customer schemas. Customers expecting PrivaCI to "just clone
my Postgres database" will almost always have at least one
partitioned table — typically the events table they need most.

Deferring partitioning support to v1.x means:

- The flagship MedicalHelpDesk Corp test fixture (which includes
  `public.raw_events` partitioned monthly and
  `clinical.patient_visits` partitioned by region) would not
  represent a real customer database.
- Early Marketplace customers with partitioned event tables would
  hit a hard fail on day 1, generating support tickets and
  refund requests.
- The retrofitting cost later (when the engine has shipped) is
  higher than building it in now: streaming, checkpointing, and
  config-validation all have partition-aware code paths.

The decision space is: do we model partitioned tables as a
**single virtual table** at the streaming layer, or as **N
independent tables** that share a parent's masking config?

Alternatives considered:

- **Stream from parent only.** Simplest. Postgres routes inserts to
  the right partition on the target. But checkpointing granularity
  is the whole table, so a 24-partition crash at partition 23
  restarts all 24. Unacceptable for the resumability promise.
- **Treat partitioned parents as one virtual table everywhere.**
  Hides reality. The catalog already shows the structure;
  pretending otherwise leaks complexity into many places (e.g.,
  the audit log would lie about which "table" was being processed).
- **Per-child streaming, parent supplies masking config.** Each
  partition child is a streaming unit. The masking pipeline
  resolves config from the parent. Best resumability, honest
  about catalog reality, modest extra code. Accepted.

Sub-partitioning (a partition that is itself partitioned) is a
PostgreSQL feature but is rare in practice. Supporting it
correctly requires recursive resolution of bound expressions and
config inheritance. Deferred to v1.x.

## Decision

Native partitioning is a **first-class MVP capability**.

### Catalog layer

- Each partitioned-parent table records
  `is_partitioned = true`, the strategy (`RANGE`, `LIST`, `HASH`),
  the partition-key column list, and the ordered children.
- Each partition child records its parent ID and its bound
  expression as a verbatim string.
- Multi-level partitioning is detected at pre-flight and refused
  with exit `2` and a clear error message.

### Schema replication

- The partitioned parent is created on the target first, with its
  original `PARTITION BY <strategy> (<keys>)` clause.
- Each partition child is created with its
  `PARTITION OF <parent> <bound>` clause.
- Per-partition `strategy` config is rejected at config validation
  with exit `3`. The user configures the parent; all children
  inherit.

### Streaming

- Partition children are independent streaming units. The parent
  itself has no rows and is not streamed.
- Target-side writes go directly into the child via
  `COPY <child> FROM STDIN ...`, bypassing the parent's tuple
  routing. This is faster (no per-row routing overhead) and
  guarantees we write to the partition we expect.
- The masking pipeline resolves per-column actions from the
  parent's config.

### State

- Each partition child has its own row in
  `_privaci.table_checkpoints`.
- Resumability is per-partition. A 24-partition crash at
  partition 23 resumes 23 and starts 24, leaving 1-22 untouched.
- A new partition added to the source between runs is treated as
  a new table on the next run and emits a `new_table` audit event.

## Consequences

### What this enables

- Realistic test coverage on the MedicalHelpDesk Corp fixture (24
  monthly partitions on `raw_events`, 4 list partitions on
  `patient_visits`).
- "Just point me at your Postgres" actually works for real
  customer schemas in 2026.
- Future per-partition parallelism: because partitions are
  independent streaming units, post-MVP parallelism work just
  schedules N children concurrently in the topo-sort layer.

### What this rules out

- **Per-partition config overrides** in MVP. Customers who need
  partition-specific masking (rare) must configure the parent.
- **Sub-partitioning** in MVP. Detected, refused, documented as
  a future change.
- **Cross-partition resume semantics.** A partition that has
  partially completed but whose checkpoint is corrupted forces a
  restart of only that partition, not the whole table.

### Operational implications

- The audit log is slightly chattier on partitioned tables (one
  `table.start` / `table.end` event per partition child).
  Documented; customers who don't want it can grep the audit log
  by partition-parent name.
- A "new partition appeared mid-run" race is impossible because
  introspection happens at run start; new partitions appearing
  between runs are picked up cleanly on the next run.

### Risks

- **Bound-expression replication fidelity.** `FOR VALUES FROM (...)
  TO (...)` and `FOR VALUES IN (...)` cover the common cases;
  expression bounds (e.g., a function call) are rare but possible
  and may require special handling. Integration-tested.
- **Per-child streaming = N COPY commands.** For tables with
  hundreds of small partitions, the per-COPY overhead may
  dominate. Mitigation: introspection can group small adjacent
  partitions into bulk COPYs in a v1.x optimization if it ever
  matters in production.

### Decision review triggers

- If sub-partitioning becomes common in customer support tickets,
  revisit deferral.
- If per-COPY overhead on hundred-partition tables becomes a real
  bottleneck, implement child-grouping.
- If customers ask for per-partition config (e.g., "the 2024
  partition is older data, mask it differently"), reconsider.
