# ADR-0011: Auto-detect confidence scoring and table context

## Status

Accepted — 2026-06-09

## Context

Zero-config PII auto-detection (OpenSpec §9) matches column names against
a pattern library and applies masking actions without explicit YAML entries.
Column-name matching alone produces false positives (`products.description`
is not clinical notes) and false negatives (`patients.narrative` does not
match any name pattern).

The MVP must ship a boolean “mask or passthrough” outcome for operators,
but the detection layer should not hard-code a single signal. Future
improvements (table-context priors, value-shape stats, semantic embeddings)
need a stable finding model.

## Decision

1. **Finding objects, not bare actions.** Every detection pass returns a
   `DetectionFinding` with `action`, `provider`, `confidence`
   (`high` | `medium` | `low`), and `reasons[]` explaining the score.

2. **Auto-mask only on `high`.** `medium` findings are surfaced in
   `privaci dry-run --report` as “uncertain — manual review” and are left
   as passthrough at run time unless explicitly configured in YAML.
   `low` is passthrough.

3. **Table context as a confidence modifier (not a primary matcher).**
   Structured PII patterns (`email`, `ssn`, `phone`, …) remain
   column-name driven with `high` confidence regardless of table name.
   Freeform / L2 (`ner_mask`) candidates additionally consider:
   - column type (`text` or `varchar` ≥ 500),
   - `pg_stats.avg_width` (≥ 200 → eligible for `high`),
   - table-name priors (`patient`, `user`, `product`, …) that raise or
     lower confidence without replacing the column-name match.

4. **Semantic / embedding analysis is deferred.** No value sampling or
   external model calls in the MVP. A future scorer term
   (`w_semantic · embedding_similarity`) will plug into the same finding
   model; see revisit triggers below.

## Consequences

- Operators get a reviewable middle tier instead of silent wrong masks on
  ambiguous columns.
- `products.description` with long marketing copy may land in `medium`
  rather than auto-`ner_mask`, prompting explicit YAML.
- Clinical `visit_notes` with stats present stays `high` and auto-masks.
- Strict mode (`strict_autodetect`) treats any `high` or `medium` finding
  not explicitly addressed in YAML as a validation failure (exit `3`).
- Catalog introspection gains a read of `pg_stats.avg_width`; missing
  stats (never-`ANALYZE` tables) yield `medium` for freeform candidates
  on sensitive tables, `low` otherwise.
- **Revisit when:** we add config packs with table-scoped patterns,
  ship value-shape sampling, or integrate an on-prem embedding model for
  semantic column classification.
