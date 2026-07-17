"""Implementation of ``privaci report``."""

from __future__ import annotations

import sys
import uuid

import typer

from privaci.contracts import load_plugins
from privaci.storage import write_object

_BINARY_REPORT_FORMATS = frozenset({"pdf"})


def _emit_report_payload(payload: bytes, *, output_format: str) -> None:
    """Write report bytes to stdout (binary-safe for PDF)."""
    if output_format in _BINARY_REPORT_FORMATS:
        sys.stdout.buffer.write(payload)
        sys.stdout.buffer.flush()
        return
    typer.echo(payload.decode())


def execute_report(
    *,
    run_id: str,
    output_format: str,
    output: str | None,
) -> None:
    """Render a compliance report for a completed run."""
    plugins = load_plugins()
    payload = plugins.report_renderer.render(
        uuid.UUID(run_id), output_format=output_format
    )
    if output is None:
        _emit_report_payload(payload, output_format=output_format)
        return
    write_object(output, payload)
    typer.echo(f"Wrote report to {output}")
