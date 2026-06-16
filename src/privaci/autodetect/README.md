# autodetect

Zero-config PII column scanner. Samples source tables, matches column names
and cell values against built-in patterns, and proposes `mask-rules.yaml`
actions with confidence scores.

## Public API

| Symbol | Role |
|--------|------|
| `scanner.scan_catalog` | Score all tables in a catalog snapshot |
| `resolve.build_detection` | Build a `DetectionResult` from config + catalog |
| `report.write_detection_report` | Write a markdown auto-detect report |

## Configuration

Controlled by top-level `auto_detect` and `strict_autodetect` in
`mask-rules.yaml`. See [`docs/configuration.md`](../../../docs/configuration.md).

## Example

```bash
privaci dry-run --report autodetect-report.md
```
