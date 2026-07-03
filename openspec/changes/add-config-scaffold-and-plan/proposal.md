## Why

The biggest post-subscribe friction is not deployment — it is authoring
`mask-rules.yaml` for an unknown schema. Customers must copy examples, guess column
actions, or run `dry-run` only after both source **and** target DBs exist.

`catalog inspect` and auto-detect already exist but do not produce a starter config or a
source-only “what will we mask?” view. New-subscriber onboarding needs:

1. **`privaci init`** — connect to source, emit a reviewable starter `mask-rules.yaml`.
2. **`privaci plan`** — source-only preview of tables, columns, and proposed actions (no
   target write, no target connection required).

This is the largest activation lever for new subscribers and worth a **public minor
release** (e.g. v1.1.0); the plugin repo picks it up via engine pin.

## What Changes

- New CLI command **`privaci init`** (`src/privaci/cli/_init.py` or equivalent).
- New CLI command **`privaci plan`** — source-only masking plan; optional `--format json`.
- Reuse **`catalog`**, **`autodetect`**, and **`config`** — no duplicate PII logic.
- Docs: quickstart, configuration, CLI reference, CHANGELOG.
- Tests: init output shape, plan without target, strict_autodetect warnings in output.

## Capabilities

### New Capabilities

- `config-scaffold-and-plan`: `init` + `plan` commands and docs.

### Modified Capabilities

- `engine-cli`: new subcommands; `dry-run` unchanged (full source+target preflight).

## Impact

- **Public repo only** — no plugin-layer code in this change.
- **Security:** init/plan are read-only on source; generated YAML must be reviewed before
  production `run`.
- **Release:** public v1.1.0 recommended.

## Non-goals

- Auto-run masking from `init` without human review.
- Replacing `dry-run` (target preflight stays separate).
- Plugin tier gating on `init`/`plan`.
- LLM-generated mask rules (future; out of scope).
