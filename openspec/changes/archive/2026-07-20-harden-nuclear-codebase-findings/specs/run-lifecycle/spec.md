## ADDED Requirements

### Requirement: Run open/stream/close seam
The engine SHALL expose a run-lifecycle module that opens a run (state schema,
start or resume, schema prepare, audit writer, UsageMeter register with the
persisted run id), streams tables, and closes the run (finish/abort, UsageMeter
final, run.end emit) so CLI fresh and resume paths share one policy surface.

#### Scenario: Fresh run uses one run id for meter start and end
- **WHEN** a fresh masking run starts with a UsageMeter plugin installed
- **THEN** `register_run` and `final_meter` receive the same `run_id` as
  `_privaci.runs`

#### Scenario: Dual audit and observability recording
- **WHEN** the lifecycle records a catalog object event
- **THEN** a single helper writes the audit row and emits the observability
  event with aligned field names
