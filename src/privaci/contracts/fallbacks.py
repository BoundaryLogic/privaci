"""Community-mode fallbacks for plugin contracts."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from privaci.contracts.base import (
    ColumnContext,
    DriftReport,
    LicenseStatus,
    LicenseValidator,
    LLMConnector,
    Notifier,
    ObjectWriter,
    RedactionResult,
    ReportRenderer,
    RunCompletionEvent,
    RunEnhancements,
    RunEnhancer,
    UsageMeter,
)
from privaci.errors import ConfigError, L3NotInstalledError
from privaci.storage.backends.file import write_local_object
from privaci.storage.parser import ObjectUriKind, parse_object_uri


class CommunityLicenseValidator(LicenseValidator):
    """Unrestricted community tier — no license check."""

    def validate(self) -> LicenseStatus:
        """Return a valid community license."""
        return LicenseStatus(tier="community", is_valid=True)


class NoOpUsageMeter(UsageMeter):
    """Silent metering — no external UsageMeter calls."""

    def register_run(self, *, source_db_hash: str, run_id: UUID) -> None:
        return None

    def report_usage(self, *, source_db_hash: str, run_id: UUID) -> None:
        return None

    def final_meter(self, *, source_db_hash: str, run_id: UUID) -> None:
        return None


class NoOpLLMConnector(LLMConnector):
    """Placeholder when no LLM connector plugin is installed."""

    def name(self) -> str:
        return "noop"

    def redact_entities(
        self,
        text: str,
        *,
        salt: str,
        context: ColumnContext,
    ) -> RedactionResult:
        raise L3NotInstalledError(
            "Level 3 LLM connectors require the commercial layer. "
            "See docs/extending-privaci.md."
        )


class JsonReportRenderer(ReportRenderer):
    """Minimal JSON report from run metadata (community mode)."""

    def render(self, run_id: UUID, *, output_format: str) -> bytes:
        if output_format != "json":
            msg = "PDF rendering requires the commercial layer."
            raise L3NotInstalledError(msg)
        payload: dict[str, Any] = {
            "run_id": str(run_id),
            "format": "json",
            "note": "community report stub — full report requires commercial layer",
        }
        return json.dumps(payload, indent=2).encode()


class NoOpNotifier(Notifier):
    """Drop notifications silently."""

    def notify(self, event: RunCompletionEvent) -> None:
        return None


class NoOpDriftDetector:
    """Drift detection requires a DriftDetector plugin; exposed for plugin loading."""

    def detect(
        self,
        previous_snapshot: dict[str, Any],
        current_snapshot: dict[str, Any],
    ) -> DriftReport:
        return DriftReport(has_drift=False)


class CommunityRunEnhancer(RunEnhancer):
    """No-op run enhancements in community mode."""

    def build_enhancements(self, catalog: Any) -> RunEnhancements:
        _ = catalog
        return RunEnhancements()


class CommunityObjectWriter(ObjectWriter):
    """Local artifact writes only; cloud URIs require a plugin."""

    def write(
        self,
        uri: str,
        data: bytes,
        *,
        content_type: str | None = None,
    ) -> None:
        _ = content_type
        parsed = parse_object_uri(uri)
        if parsed.kind in {ObjectUriKind.S3, ObjectUriKind.AZURE_BLOB}:
            raise ConfigError(
                "Writing compliance artifact",
                cause=(
                    f"Cloud object URIs such as {parsed.kind.value}:// are not "
                    "available in community mode."
                ),
                remediation=(
                    "Install the commercial layer, register a privaci.plugins "
                    "object_writer entry point, or use a local path."
                ),
            )
        write_local_object(parsed, data)
