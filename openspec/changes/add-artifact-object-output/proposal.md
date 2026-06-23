## Why

Compliance artifacts (`report --output`, `dry-run --report`, commercial
`preview --policy-diff` / `--sarif`) are written only to local paths today.
AWS demo and Marketplace buyers store evidence in S3 via task roles; shell
`aws s3 cp` workarounds bypass a single, testable write path and block a
future Azure Blob deployment without rework.

## What Changes

- **`ObjectWriter` plugin contract** — public ABC + community fallback (local
  paths only); commercial registers S3 (Azure Blob later). Same pattern as
  `RunEnhancer`.
- **`write_object(uri, bytes)`** — public dispatch via `load_plugins().object_writer`.
- **CLI integration** — artifact output flags accept `file://`, local paths, and
  cloud URIs when a plugin is installed.
- **Tier policy** — all commercial tiers get cloud artifact upload; community
  stays local-only unless a third party registers `object_writer`.
- **Non-breaking** — bare paths unchanged; `report` stdout default unchanged.

## Capabilities

### New Capabilities

- `object-output`: URI parsing and small-object write dispatch.

### Modified Capabilities

- `commercial-tier-contract`: add `ObjectWriter` ABC and plugin entry point.
- `engine-cli`: output flags accept object URIs.

## Impact

- **Public:** `privaci.contracts` (`ObjectWriter`), `src/privaci/storage/`,
  CLI call sites, docs.
- **Commercial:** `CommercialObjectWriter` (S3), `preview.py` wiring,
  `pyproject.toml` entry point.
- **Release:** v1.0.2 bundle with copy-pipe fix; bump commercial engine pin.
