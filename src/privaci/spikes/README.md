# spikes

Week-1 architecture validation scripts (COPY-binary throughput, cyclic FK
deferred constraints, SpaCy throughput). Not part of the production CLI.

## Public API

Runnable modules under `privaci.spikes.*`; documented in
[`docs/spikes/`](../../../docs/spikes/README.md).

## Configuration

Uses spike-specific env vars; see each spike's doc page.

## Example

```bash
pytest -m spike --run-spike
```

Spikes are marked `@pytest.mark.spike` and excluded from default CI.
