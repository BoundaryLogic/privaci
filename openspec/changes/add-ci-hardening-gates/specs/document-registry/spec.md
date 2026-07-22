## ADDED Requirements

### Requirement: Machine-readable code-to-docs registry
The repository MUST maintain `docs/registry.yaml` (or an equivalent path
documented in `docs/ci-gates.md`) that maps registry entry ids to code path
globs and required documentation paths. Every top-level package under
`src/privaci/` MUST appear in at least one entry, or MUST be explicitly
marked waived with an issue-linked waiver, except packages listed in the
registry meta exclude list (MUST include `spikes`).

#### Scenario: Registry loads and validates
- **WHEN** `scripts/check_doc_registry.py` runs against a valid registry
- **THEN** it exits 0 and reports no structural errors

#### Scenario: Unregistered package fails
- **WHEN** a new top-level package exists under `src/privaci/` with no
  registry entry and no waiver and is not meta-excluded
- **THEN** the checker exits non-zero

#### Scenario: Spikes package excluded
- **WHEN** only `src/privaci/spikes/` exists as an extra tree without a
  docs-bound entry
- **THEN** package coverage still passes because `spikes` is meta-excluded

### Requirement: Diff coupling between code and docs
The document-registry checker MUST fail when a commit or PR diff (per the
documented diff-base rules: staged for pre-commit; merge-base with main for
ci-local; PR base SHA on GitHub; coupling skipped on non-PR pushes to main)
touches any code path matching an entry's `code` globs without also touching
at least one of that entry's `docs` paths. The checker MUST require a
`CHANGELOG.md` touch only when the entry sets `changelog: required`. Entries
MUST default to `changelog: optional` unless the surface is operator-visible.
Issue-linked `DOC_REGISTRY_WAIVER` MUST suppress coupling for that entry.

#### Scenario: Code-only change fails
- **WHEN** a diff modifies a package with non-empty `docs:` binding without
  modifying any bound docs path
- **THEN** the document-registry check fails

#### Scenario: Changelog-required entry without CHANGELOG fails
- **WHEN** a diff modifies a `changelog: required` entry's code paths and
  docs but not `CHANGELOG.md`
- **THEN** the document-registry check fails

#### Scenario: Coupled change passes
- **WHEN** a diff modifies a bound code path and the corresponding docs
  (and CHANGELOG when required)
- **THEN** the document-registry coupling check passes

### Requirement: Generated reference freshness in default CI
Default local unit CI MUST run `python scripts/generate_docs.py --check`
without requiring `--docs`, and the GitHub `lint-and-test` job MUST do the
same, failing when generated reference docs are stale.

#### Scenario: Stale generated docs fail default ci-local
- **WHEN** CLI or config schema outputs would change generated docs but
  `docs/generated/` was not updated
- **THEN** default `./scripts/ci-local.sh` exits non-zero at the generate_docs
  check

### Requirement: Env-example keys documented
Every environment variable key listed in `.env.example` MUST appear in at
least one documentation file bound by a registry env-docs entry (string
presence check).

#### Scenario: Undocumented env key fails
- **WHEN** `.env.example` contains a key that appears in no bound env docs
  page
- **THEN** the document-registry check fails

### Requirement: Exit-code anchors stay in sync with errors module
The document-registry checker MUST collect every `PrivaCIError` subclass
`exit_code` and `default_doc_anchor` from `src/privaci/errors.py` and MUST
fail when `docs/error-codes.md` lacks a matching heading or anchor for that
code.

#### Scenario: Missing exit-code section fails
- **WHEN** a new `PrivaCIError` subclass with `exit_code = 7` and a
  `default_doc_anchor` is added without a corresponding section in
  `docs/error-codes.md`
- **THEN** the document-registry check fails

#### Scenario: Documented exit codes pass
- **WHEN** every error subclass anchor exists in `docs/error-codes.md`
- **THEN** the exit-code sync portion of the check passes

### Requirement: Pre-commit runs a fast coupling check
Pre-commit MUST run a document-registry check on staged changes that touch
registry `code` globs, `docs/`, or the registry file itself, so contributors
learn of coupling failures before push.

#### Scenario: Staged code without docs fails pre-commit
- **WHEN** only code under a bound glob is staged
- **THEN** pre-commit fails the document-registry hook
