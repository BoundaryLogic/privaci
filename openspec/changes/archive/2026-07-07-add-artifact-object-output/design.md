## Context

Artifact outputs today use `Path.write_*` in public and commercial CLI code.
Phase 3 AWS demo needs `s3://` evidence paths. Phase C lake exports will share
the same URI vocabulary later.

## Goals / Non-Goals

**Goals:**

- `ObjectWriter` ABC registered via `privaci.plugins` (`object_writer`).
- Community fallback: local / `file://` only; cloud schemes fail with clear error.
- Commercial default: S3 via IAM role; all paid tiers (no intra-commercial gate).
- `azure-blob://` parsed in public; backend deferred in commercial.
- URI redaction in logs and error `cause` strings.

**Non-Goals:**

- Streaming/multipart (Phase C `ObjectStoreConnector`).
- boto3 in public ELv2 tree.
- Tier gating within commercial.

## Decisions

### D1. Plugin model (like `RunEnhancer`)

**Decision:** `write_object()` calls `load_plugins().object_writer.write(uri, data)`.
Commercial replaces the entire writer; third parties may register their own.

### D2. Local writes in public

**Decision:** `CommunityObjectWriter` handles `LOCAL` and `FILE` in public code.
Commercial delegates local paths to the same helper.

### D3. S3 in commercial only

**Decision:** `CommercialObjectWriter` uses lazy boto3 `put_object`; optional
`endpoint_url` query param for MinIO tests.

### D4. `StorageError` vs `ConfigError`

**Decision:** Malformed URIs → `StorageError`; missing plugin for cloud scheme
→ `ConfigError` (exit 3).

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Public release required for CLI hook | Bundle with copy-pipe in v1.0.2 |
| Azure re-architect | Parser accepts scheme; add commercial backend only |

## Migration Plan

Ship v1.0.2 public + commercial pin bump. Local paths unchanged.
