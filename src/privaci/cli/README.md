# cli

Typer-based command-line interface. All user-facing operations (`run`,
`validate`, `resume`, …) are registered in `app.py` and executed through the
centralized error boundary in `_errors.py`.

## Public API

| Symbol | Role |
|--------|------|
| `app.main` | Setuptools entry point (`privaci` executable) |
| `generate_ci.generate_ci_files` | `privaci generate-ci` backend |

## Configuration

Global options (`--config`, `--source`, `--target`, `--log-level`) accept
environment variable overrides. See
[`docs/cli-reference.md`](../../../docs/cli-reference.md).

## Example

```bash
privaci run --config mask-rules.yaml --dry-run
```
