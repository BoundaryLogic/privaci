"""Commercial plugin contracts and community-mode fallbacks."""

from __future__ import annotations

from privaci.contracts.base import (
    CONTRACT_VERSION,
    ColumnContext,
    DriftDetector,
    DriftReport,
    LicenseStatus,
    LicenseValidator,
    LLMConnector,
    Notifier,
    ObjectWriter,
    RedactionResult,
    ReportRenderer,
    RunCompletionEvent,
    UsageMeter,
)
from privaci.contracts.fallbacks import (
    CommunityLicenseValidator,
    CommunityObjectWriter,
    JsonReportRenderer,
    NoOpLLMConnector,
    NoOpNotifier,
    NoOpUsageMeter,
)
from privaci.contracts.plugins import load_plugins
from privaci.mask.faker import FakeProvider, register_provider

__all__ = [
    "CONTRACT_VERSION",
    "ColumnContext",
    "CommunityLicenseValidator",
    "CommunityObjectWriter",
    "DriftDetector",
    "DriftReport",
    "FakeProvider",
    "JsonReportRenderer",
    "LLMConnector",
    "LicenseStatus",
    "LicenseValidator",
    "NoOpLLMConnector",
    "NoOpNotifier",
    "NoOpUsageMeter",
    "Notifier",
    "ObjectWriter",
    "RedactionResult",
    "ReportRenderer",
    "RunCompletionEvent",
    "UsageMeter",
    "load_plugins",
    "register_provider",
]
