"""Optional Prometheus metrics endpoint.

Off by default: no network ports are opened unless ``--prometheus-port`` (or the
equivalent config) is supplied. ``prometheus_client`` is imported lazily so the
core engine has no hard dependency on it (see ``observability/spec.md``).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from privaci.errors import ConfigError

if TYPE_CHECKING:  # pragma: no cover - typing only
    pass

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class MetricsHandles:
    """References to the registered Prometheus collectors.

    Held by the caller for the duration of a run so counters/gauges can be
    updated. The concrete collector objects are ``prometheus_client`` types,
    typed as ``Any`` to keep the dependency optional.
    """

    rows_processed: Any
    run_duration: Any
    run_errors: Any
    table_progress: Any


def start_metrics_server(port: int) -> MetricsHandles:
    """Start the Prometheus exposition endpoint on ``port``.

    Args:
        port: TCP port to serve ``/metrics`` on.

    Returns:
        Handles to the registered collectors.

    Raises:
        ConfigError: When ``prometheus_client`` is not installed.
    """
    client = _import_prometheus_client()
    handles = MetricsHandles(
        rows_processed=client.Counter(
            "privaci_run_rows_processed_total",
            "Rows processed per table.",
            labelnames=("table",),
        ),
        run_duration=client.Histogram(
            "privaci_run_duration_seconds",
            "Masking run duration in seconds.",
        ),
        run_errors=client.Counter(
            "privaci_run_errors_total",
            "Errors encountered during a run.",
            labelnames=("type",),
        ),
        table_progress=client.Gauge(
            "privaci_table_progress_ratio",
            "Per-table completion ratio (0..1).",
            labelnames=("table",),
        ),
    )
    client.start_http_server(port)
    logger.info(
        "Prometheus metrics endpoint started",
        extra={"event": "metrics.started", "port": port},
    )
    return handles


def _import_prometheus_client() -> Any:
    """Import ``prometheus_client`` or raise an actionable config error."""
    try:
        import prometheus_client
    except ImportError as exc:
        raise ConfigError(
            "Starting the Prometheus metrics endpoint",
            cause="The optional 'prometheus-client' package is not installed.",
            remediation=(
                "Install it with `pip install prometheus-client`, or omit "
                "--prometheus-port to run without metrics."
            ),
        ) from exc
    return prometheus_client
