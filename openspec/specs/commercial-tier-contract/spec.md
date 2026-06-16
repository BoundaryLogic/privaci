# commercial-tier-contract Specification

## Purpose
TBD - created by archiving change init-privaci-engine. Update Purpose after archive.
## Requirements
### Requirement: Stable ABC contracts in `privaci.contracts`

The public engine SHALL expose stable Python ABCs in
`privaci.contracts` that the closed commercial layer plugs into. The
public engine SHALL remain fully functional ("community mode") when no
commercial implementations are registered.

Defined contracts:

- `LicenseValidator` — `validate(self) -> LicenseStatus`.
- `UsageMeter` — `register_run(...)`, `report_usage(...)`,
  `final_meter(...)`.
- `LLMConnector` — `name()`, `redact_entities(text, *, salt, context)
  -> RedactionResult`.
- `ReportRenderer` — `render(self, run_id: UUID, format: str) ->
  bytes`.
- `Notifier` — `notify(self, event: RunCompletionEvent) -> None`.
- `DriftDetector` — `detect(self, previous_snapshot, current_snapshot)
  -> DriftReport`.

Each contract SHALL be:

- An `abc.ABC` with `@abstractmethod` declarations.
- Importable from `privaci.contracts.<name>` and re-exported from
  `privaci.contracts`.
- Versioned via a `CONTRACT_VERSION` module-level constant. Changes
  that break the contract SHALL bump the major version.

#### Scenario: Contract module importable in community mode

- **WHEN** the public engine is installed with no commercial layer
- **THEN** `from privaci.contracts import LicenseValidator,
  UsageMeter, LLMConnector, ReportRenderer, Notifier, DriftDetector`
  SHALL succeed.

#### Scenario: Contract version exposed

- **WHEN** code reads `privaci.contracts.CONTRACT_VERSION`
- **THEN** the value SHALL be a semver string matching the engine's
  major version (e.g., `"1.0"`).

### Requirement: Plugin discovery via entry points

The system SHALL discover commercial implementations via Python entry
points under the group `privaci.plugins`. The commercial package SHALL
register implementations under expected entry-point names:
`license_validator`, `usage_meter`, `llm_connector.aws_bedrock`,
`llm_connector.azure_openai`, `report_renderer.json`,
`report_renderer.pdf`, `notifier.slack`, `notifier.webhook`,
`drift_detector`.

#### Scenario: Commercial package installed

- **WHEN** the commercial wheel is installed in the same Python
  environment as the public engine
- **THEN** `importlib.metadata.entry_points(group='privaci.plugins')`
  SHALL include the commercial implementations, and the engine SHALL
  use them automatically.

#### Scenario: No commercial package

- **WHEN** the commercial package is not installed
- **THEN** the engine SHALL use built-in fallbacks (no-op `Notifier`,
  no-op `UsageMeter`, `NoOpLicenseValidator`, `NoOpLLMConnector`,
  JSON-only `ReportRenderer`, no `DriftDetector`).

### Requirement: Community-mode behavior of fallbacks

- **`NoOpLicenseValidator`** SHALL return `LicenseStatus(tier="community",
  is_valid=True)`. Community mode is unrestricted in the public engine.
- **No-op `UsageMeter`** SHALL be a silent no-op (no metering reported).
- **`NoOpLLMConnector`** SHALL raise `L3NotInstalledError` if invoked.
  Config validation SHALL surface this earlier (see `config-yaml`).
- **No-op `Notifier`** SHALL silently drop notifications.
- **JSON `ReportRenderer`** SHALL be present in the public engine — it
  produces a structured-JSON dump from `_privaci.runs` + `audit_log`.
  PDF rendering SHALL only be available via the commercial package.
- **No `DriftDetector`** in the community mode — `privaci detect-drift`
  SHALL exit `1` with the message "detect-drift requires the commercial
  layer."

#### Scenario: Community report

- **WHEN** the user runs `privaci report --run <id> --format json` in
  community mode
- **THEN** the engine SHALL produce a JSON document; **WHEN** the
  request is `--format pdf`
- **THEN** the engine SHALL exit `1` with the message "PDF rendering
  requires the commercial layer."

#### Scenario: Detect-drift in community mode

- **WHEN** the user runs `privaci detect-drift` without the commercial
  package installed
- **THEN** the engine SHALL exit `1` with the documented message.

### Requirement: License-mode behavior is enforced by the commercial layer only

The public engine SHALL NOT call home, SHALL NOT phone any boundarylogic.io
endpoint, and SHALL NOT enforce tier limits. All license-bound behavior
(source-DB count limits, feature gating beyond what's defined in the
ABCs) SHALL live in the commercial layer.

#### Scenario: Public engine is fully offline-capable

- **WHEN** the public engine runs with no network access to the
  internet
- **THEN** masking SHALL succeed against the customer's local source
  and target databases.

#### Scenario: Commercial layer enforces source-DB limit

- **WHEN** the commercial layer detects that the customer's rolling
  30-day distinct `source_db_hash` count exceeds the tier limit
- **THEN** the engine SHALL exit `5` with a message naming the tier and
  the count.

### Requirement: Contract surface area is documented

Every ABC SHALL ship with a docstring covering:

- The expected lifecycle of the implementation.
- Thread-safety / re-entrancy expectations.
- Failure-mode expectations (raise, return-null, etc.).
- Performance constraints (e.g., `LLMConnector.redact_entities` will
  be called once per row containing freeform text — should be batched
  internally where possible).

#### Scenario: Public docs reference contract module

- **WHEN** the published docs are rendered
- **THEN** there SHALL be a "Building a PrivaCI Plugin" page deriving
  examples from the `contracts` module.

### Requirement: Backwards-compatible contract evolution

Once a major contract version is published, additions to ABCs SHALL be
done via default-implementing mixins to preserve compatibility with
older commercial builds. Breaking changes SHALL bump the major version
of the public engine.

#### Scenario: New optional method added in a minor release

- **WHEN** a minor engine release adds a new method to `Notifier` with
  a default no-op implementation
- **THEN** an older commercial-layer install SHALL continue to work
  (the default kicks in).

