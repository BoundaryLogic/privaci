## ADDED Requirements

### Requirement: Checkpoint durability outside cycle components
For load-plan layers that are not a single deferred-cycle component, the engine
SHALL commit progress such that a failure on table B does not roll back
checkpoints for already-completed table A in that layer.

#### Scenario: Sibling failure keeps prior checkpoint
- **WHEN** two independent tables share a layer and the second fails mid-stream
- **THEN** the first table’s checkpoint remains durable on the target
