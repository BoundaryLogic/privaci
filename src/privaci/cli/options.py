"""Shared Typer option aliases for the PrivaCI CLI."""

from __future__ import annotations

from typing import Annotated

import typer

ConfigPathOption = Annotated[
    str,
    typer.Option(
        "--config",
        help="Path to mask-rules.yaml.",
    ),
]

SourceDbOption = Annotated[
    str | None,
    typer.Option(
        "--source",
        envvar="SOURCE_DB_URL",
        help="Source database URL or secret URI.",
    ),
]

TargetDbOption = Annotated[
    str | None,
    typer.Option(
        "--target",
        envvar="TARGET_DB_URL",
        help="Target database URL or secret URI.",
    ),
]

DryRunOption = Annotated[
    bool,
    typer.Option(
        "--dry-run",
        help="Run pre-flight checks only; do not write rows.",
    ),
]

NoAuditTableOption = Annotated[
    bool,
    typer.Option(
        "--no-audit-table",
        help="Disable writes to _privaci.audit_log for this run.",
    ),
]

PrometheusPortOption = Annotated[
    int | None,
    typer.Option(
        "--prometheus-port",
        help="Serve Prometheus metrics on this port (off by default).",
    ),
]

LogLevelOption = Annotated[
    str,
    typer.Option(
        "--log-level",
        envvar="PRIVACI_LOG_LEVEL",
        help="Logging level.",
    ),
]
