# ADR-0001: Use Elastic License 2.0 (ELv2) for the public engine

## Status

Accepted — 2026-05-28

## Context

PrivaCI is a security-sensitive in-VPC tool. Customers must be able to
audit the masking pipeline (the entire pitch is "trust this with your PII").
That argues for the source being publicly visible. At the same time, the
business model funds development through a flat-rate Marketplace listing
backed by a closed commercial layer (metering, L3 LLM, signed reports,
drift). The license must:

1. Permit customer self-hosting — without it, the product is unusable
   (data never leaves the VPC is the central guarantee).
2. Block a competitor from packaging the engine as a hosted or managed
   service in competition with the maintainer.
3. Allow internal forks, contributions, and audit reads.
4. Be familiar to enterprise procurement and legal review so customer
   onboarding is fast.

Alternatives considered: BSL (Business Source License), FSL (Functional
Source License), AGPL, Apache 2.0, fully closed source.

## Decision

The public repository (`privaci`) is licensed under the **Elastic
License 2.0 (ELv2)**.

The private repository (`privaci-commercial`) is proprietary, closed
source. It is distributed only as part of the commercial Marketplace
container image. The boundary between the two is the
`privaci.contracts` Python ABCs and entry-point plugin discovery
mechanism documented in the `commercial-tier-contract` spec.

## Consequences

### Trade-offs accepted

- **Some communities will not consider ELv2 "open source"** in the
  OSI-purist sense. This is technically correct. For the target buyer
  (DevOps / backend engineer at a scale-up), it is rarely a concern;
  procurement legal teams have already reviewed ELv2 for Elastic, Redis
  Labs, and Sentry.
- **A motivated competitor can still reverse-engineer the closed
  commercial layer.** The license is a speed bump, not a wall. Real
  defensive moats are: Marketplace distribution, compliance audit
  trail, execution velocity, customer relationships, and the closed
  ~40% of total product value. See `design.md` Risk R12.

### Operational implications

- The public repo must ship with a `LICENSE` file containing the
  unmodified ELv2 text and a brief plain-English summary in `README.md`.
- The private repo must be visibly separate (different git remote,
  different access controls). Distribution channel is the Marketplace
  container image, not git.
- Contribution flow: external PRs are accepted under the same ELv2
  license, with an inbound=outbound license grant (no separate CLA
  unless legal requires one later).

### Open considerations

- If ELv2 ever causes a deal-loss with a specific customer because of
  procurement-team objections, consider a **dual-license** offer (ELv2
  plus a commercial license grant negotiated 1:1). MongoDB takes this
  approach with SSPL.
- A future major-version bump to a different license is possible but
  expensive — communicate with users at least one minor release in
  advance.
