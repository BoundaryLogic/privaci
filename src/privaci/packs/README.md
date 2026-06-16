# packs

Signed vertical config packs (HIPAA, PCI, GDPR starters). Fetches manifests,
verifies signatures, and merges pack rules into an existing `mask-rules.yaml`.

## Public API

| Symbol | Role |
|--------|------|
| `install.install_pack` | Fetch and merge a named pack |
| `verify.verify_pack_manifest` | Signature and schema checks |

## Configuration

`privaci install-pack` accepts `--registry-url` and `--local-pack-dir` for
offline installs.

## Example

```bash
privaci install-pack hipaa --config mask-rules.yaml --yes
```
