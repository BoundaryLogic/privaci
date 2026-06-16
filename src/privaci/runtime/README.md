# runtime

Process-level concerns: graceful shutdown on SIGTERM/SIGINT so in-flight
batches can checkpoint before exit.

## Public API

| Symbol | Role |
|--------|------|
| `signals.install_signal_handlers` | Register asyncio-friendly signal handlers |

## Configuration

No user-facing configuration. Used internally by the pipeline runner.

## Example

Installed automatically when `run_masking_pipeline` starts; operators do not
call this module directly.
