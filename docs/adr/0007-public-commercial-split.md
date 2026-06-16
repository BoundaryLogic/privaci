# ADR-0007: Split into public engine + private commercial layer

## Status

Accepted — 2026-05-28. Amended 2026-06-11: extended the placement policy to
`openspec/` artifacts and reconciled it with keeping a scrubbed public engine
proposal; relocated commercial design detail to `privaci-commercial`. This ADR
remains public by design as the transparent statement of the licensing model.

## Context

The business model funds development through a flat-rate Marketplace
listing. The product must satisfy two seemingly competing requirements:

1. **Be source-available** so security-conscious customers can audit
   the masking pipeline. This is central to the "trust us with your
   PII" positioning.
2. **Have a defensible commercial wedge** that funds full-time
   maintenance and is not displaced by a free fork.

Approaches considered:

- **One repo, paywalled directories** — Confusing license terms,
  invites accidental redistribution, scares enterprise legal review.
- **True open-core with a community fork** — Operationally brutal for
  a small team. Two release cadences, duplicate bug-fix porting,
  community confusion about which version is "real."
- **Two repos, public engine + private commercial layer, with a stable
  ABC contract between them** — Accepted.

## Decision

There are two git repositories with two different licenses.

### Public (`privaci`, ELv2)

A self-contained, fully-functional engine. Anyone can clone, build,
and run it inside their VPC indefinitely. Includes:

- Streaming engine, COPY pipeline, catalog introspection, schema
  replication, L1 regex + L2 SpaCy masking, deterministic faker,
  audit log, resumability, auto-detect, config, CLI, Docker/Compose/
  Helm packaging, vertical-config-pack loader.
- All the `privaci.contracts` ABCs declared but using community-mode
  no-op fallbacks: `NoOpLicenseValidator`, no-op `UsageMeter`, no-op
  `Notifier`, JSON-only `ReportRenderer`, no `DriftDetector`.

### Private (`privaci-commercial`, proprietary)

A thin Python package that registers via entry points and replaces the
no-op fallbacks. Includes:

- AWS Marketplace metering integration.
- License-key validation + tier enforcement (source-DB count).
- L3 LLM connectors (AWS Bedrock, Azure OpenAI).
- PDF compliance reports + signed-JSON reports.
- Slack/webhook notifier.
- Drift detection.

The commercial package is bundled into the official Marketplace
container image; customers who pull the image get both layers
simultaneously and transparently.

### Mechanism

The boundary is defined by:

- `privaci.contracts.*` — six `abc.ABC` interfaces. Versioned via
  `CONTRACT_VERSION`.
- Python entry points under the group `privaci.plugins`. The engine
  loads commercial implementations via `importlib.metadata.entry_points`.
- The public engine ships built-in fallbacks for every contract so it
  works without any commercial layer installed.

## Documentation & repository placement

The code split (above) is an *addition*, not an extraction: this repo is
already the public engine. The remaining decision is which **documents**
are public and **when** the boundary is enforced.

### Timing — two triggers

1. **Stand up the private repo** when commercial work begins (tracked by the
   `add-commercial-layer` change, which lives in `privaci-commercial` — formerly
   `init-privaci-engine` §19–22). No documents need to move for this; the
   `privaci.contracts` ABCs already live here.
2. **Scrub business/GTM material from the public repo** before the public
   beta gate (tasks §18.7), i.e. before the first Marketplace listing.

### Placement policy

| Content | Repo | Rationale |
| --- | --- | --- |
| CLI reference, configuration, error codes, state/audit schema, extending/plugin model, local development | Public | "Set up, modify, use." Core to operators and to the audit-trust story. |
| Engine ADRs (masking, streaming, memory model, salt UX, FK strategy, partitioning, ELv2 licensing) | Public | Architecture decisions *are* the auditability feature; security-conscious buyers read them. |
| Engine OpenSpec change (`openspec/changes/<engine-change>/` proposal, design, specs, tasks) | Public (scrubbed) | Engine spec is part of the audit-trust story; GTM/pricing/competitor content is removed and relocated. |
| Pricing, tiers, GTM, competitor analysis, business plan | Private | Pure strategy with no operator value; not for competitors. |
| Commercial OpenSpec changes (`add-commercial-layer`) and website changes (`add-marketing-site`, `add-docs-ai-assistant`) | Private (`privaci-commercial` / `boundarylogic-web`) | Business-model and web-property planning; not engine material. |
| Commercial ADRs (metering, license enforcement, billing dimension `0003`) | Private | Describe the proprietary layer. |
| `privaci-commercial` setup/license/metering docs | Private | Commercial-only. |

Rule of thumb: a document is public if it helps someone **run, audit, or
extend the engine**, and private if it only serves the **business model**.
ADR-0007 itself stays public as a transparent statement of the licensing
model.

### Git history

Personal emails can appear in two places that a mailmap alone does not fix:

1. **Author/committer fields** — rewrite with `git filter-repo` and a mailmap.
2. **Commit message bodies** — GitHub squash-merges inject `Co-authored-by:`
   trailers with the account's commit email. Rewrite message text with
   `git filter-repo --replace-message`.

Before the public beta gate (tasks §18.7.6–18.7.7):

- Scrub all personal emails from fields and messages; keep real names if desired.
- Set local `user.email` to the GitHub noreply address
  (`<id>+<username>@users.noreply.github.com`).
- Enable GitHub **Keep my email addresses private** and **Block command-line
  pushes that expose my email** so future squash-merges do not reintroduce
  personal addresses.

**GitHub caveat:** closed pull requests retain `refs/pull/*` refs pointing at
pre-rewrite commit SHAs. Those old URLs can remain reachable on GitHub even
after `main` is rewritten. For a private repo this is low risk; before the
repo goes public, either publish from a **fresh repository** with clean history
or ask GitHub Support to garbage-collect cached views.

## Consequences

### What the public engine provides on its own

- A complete masking solution for community users.
- Auditable source for any customer's compliance review, regardless
  of whether they pay for the commercial layer.
- Easy local development and testing — contributors don't need any
  commercial credentials.

### What the commercial layer adds

- Plumbing (metering, license enforcement) that has no customer-facing
  value individually but is essential to the business model.
- High-cognitive-load features (LLM connectors, signed reports, drift
  detection) that customers expect to pay for and get support on.

### Compatibility commitments

- Once `CONTRACT_VERSION` is bumped past `1.0`, the public engine
  MUST maintain backward-compatible ABCs across minor versions. New
  methods added in minor releases ship with default implementations
  (mixin patterns) so older commercial builds keep working.
- A breaking ABC change is a major version bump for both repos.

### Release channels and cadence

The two repos do **not** release in lockstep; they are decoupled by release
channel and a deliberate, bounded lag:

- The public engine publishes a **beta channel** (`vX.Y.Z-beta.N` pre-releases
  off `main`) for fast iteration and early-warning, and a **stable channel**
  (`vX.Y.Z` releases) that is the contract downstream consumers depend on.
- The official Marketplace image is built **only from a tagged stable engine
  release** — never from `main` or a beta. This is what makes the commercial
  layer trail the open-source engine by design.
- `privaci-commercial` pins the engine with a major-bounded range
  (`privaci>=X.0,<(X+1).0`) and promotes to a newer engine stable release only
  after its own integration suite passes (target: within ~2 weeks of each engine
  stable, unless tests block it).
- Maintenance is **forward-only**. A critical engine fix ships as a new engine
  stable patch; the commercial layer bumps its pin. No long-lived commercial
  backport branches against old engine versions (the open-core maintenance trap
  this ADR exists to avoid).

### Risks and mitigations

- **A motivated competitor could reimplement the commercial layer
  against the public ABCs.** Accepted. The license forbids it for
  managed-service competition (ELv2). Business-model mitigations are
  tracked in the private `privaci-commercial` strategy doc.
- **The engine could accidentally become tightly coupled to commercial
  internals.** Mitigation: CI in the public repo must build and test
  without the commercial package installed.

### Decision review triggers

- If a contract proves too narrow (e.g., we need to add a method that
  cannot be defaulted), revisit the major-version boundary policy.
- If the commercial layer's surface area exceeds ~30% of total LOC,
  reconsider whether some commercial features should be open-sourced
  for community goodwill.
