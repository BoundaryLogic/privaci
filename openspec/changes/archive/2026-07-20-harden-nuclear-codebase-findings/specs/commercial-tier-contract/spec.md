## ADDED Requirements

### Requirement: UsageMeter run id pairing
The UsageMeter plugin contract SHALL receive the same `run_id` on
`register_run` as on `final_meter` for a successful fresh run.

#### Scenario: Matching ids
- **WHEN** a fresh run completes successfully with a UsageMeter plugin
- **THEN** both lifecycle calls use the persisted `_privaci.runs` id

#### Scenario: Resume does not double-register
- **WHEN** a run is resumed
- **THEN** the engine does not call `register_run` again with a new random id

#### Scenario: Interrupted run does not finalize the meter
- **WHEN** a run is interrupted and later resumed to success
- **THEN** `final_meter` is called once on the successful terminal close, not on
  the interrupt
