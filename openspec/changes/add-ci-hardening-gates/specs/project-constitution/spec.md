## ADDED Requirements

### Requirement: Constitution is the canonical non-negotiables document
The repository MUST publish a root `CONSTITUTION.md` that states articles
covering at least: trust boundary (customer environment / no PII phone-home),
fail closed, PII hygiene, memory and resource safety, correctness over
speed-to-merge, secure engineering defaults, integrity and honesty,
architecture discipline, amendment process, and documentation currency.
A short ADR MUST record adoption and point to `CONSTITUTION.md` as the
article source of truth.

#### Scenario: Contributor can find the constitution
- **WHEN** a contributor opens the repository root or CONTRIBUTING / SECURITY
  / docs index
- **THEN** they can navigate to `CONSTITUTION.md` within one link hop

#### Scenario: Amendment requires constitution update
- **WHEN** a PR changes the meaning of a constitution article
- **THEN** that PR MUST update `CONSTITUTION.md` (and the ADR if status
  changes) in the same change

### Requirement: Hard-gate policy for automatable articles
The project SHALL enforce every automatable constitution article with a named
hard CI or pre-commit gate documented in `docs/ci-gates.md`. Soft-fail
(ratchet) MUST be limited to at most one merge cycle with a tracking issue.
Review-only enforcement is permitted only where automation is impossible, and
MUST still appear as an explicit checklist item in PR guidance.

#### Scenario: Docs map articles to gates
- **WHEN** an operator or contributor opens `docs/ci-gates.md`
- **THEN** each constitution article lists its hard gate(s) and any
  review-only remainder

#### Scenario: Waiver cites article and issue
- **WHEN** a gate allowlist or waiver is added
- **THEN** the waiver MUST cite a GitHub issue number and the constitution
  article id it relaxes

### Requirement: Agents and humans are pointed at the constitution
The repository MUST include a Cursor rule that always applies and instructs
assistants to obey `CONSTITUTION.md` (no shortcuts that violate articles).

#### Scenario: Cursor rule present
- **WHEN** the change is merged
- **THEN** `.cursor/rules/constitution.mdc` exists with always-apply guidance
  referencing `CONSTITUTION.md`
