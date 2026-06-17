"""Discover commercial plugins via entry points."""

from __future__ import annotations

import importlib.metadata
import logging
from dataclasses import dataclass
from typing import Any, cast

from privaci.contracts.base import (
    DriftDetector,
    LicenseValidator,
    LLMConnector,
    Notifier,
    ReportRenderer,
    RunEnhancer,
    UsageMeter,
)
from privaci.contracts.fallbacks import (
    CommunityLicenseValidator,
    CommunityRunEnhancer,
    JsonReportRenderer,
    NoOpLLMConnector,
    NoOpNotifier,
    NoOpUsageMeter,
)

logger = logging.getLogger(__name__)

PLUGIN_GROUP = "privaci.plugins"


@dataclass(frozen=True, slots=True)
class PluginBundle:
    """Resolved plugin implementations for a run."""

    license_validator: LicenseValidator
    usage_meter: UsageMeter
    llm_connectors: dict[str, LLMConnector]
    report_renderer: ReportRenderer
    notifier: Notifier
    drift_detector: DriftDetector | None
    run_enhancer: RunEnhancer


def _load_entry(name: str) -> Any | None:
    """Load a single entry point by name, or None if missing."""
    eps = importlib.metadata.entry_points(group=PLUGIN_GROUP)
    for ep in eps:
        if ep.name == name:
            return ep.load()
    return None


def load_plugins() -> PluginBundle:
    """Load commercial plugins or fall back to community implementations."""
    license_cls = _load_entry("license_validator")
    meter_cls = _load_entry("usage_meter")
    report_cls = _load_entry("report_renderer.json")
    notifier_cls = _load_entry("notifier.slack") or _load_entry("notifier.webhook")
    drift_cls = _load_entry("drift_detector")
    enhancer_cls = _load_entry("run_enhancer")

    license_validator: LicenseValidator = (
        license_cls() if license_cls else CommunityLicenseValidator()
    )
    usage_meter: UsageMeter = meter_cls() if meter_cls else NoOpUsageMeter()
    report_renderer: ReportRenderer = (
        report_cls() if report_cls else JsonReportRenderer()
    )
    notifier: Notifier = notifier_cls() if notifier_cls else NoOpNotifier()
    drift_detector: DriftDetector | None = drift_cls() if drift_cls else None
    run_enhancer: RunEnhancer = (
        cast(RunEnhancer, enhancer_cls()) if enhancer_cls else CommunityRunEnhancer()
    )

    llm_connectors: dict[str, LLMConnector] = {}
    for ep in importlib.metadata.entry_points(group=PLUGIN_GROUP):
        if ep.name.startswith("llm_connector."):
            connector = ep.load()()
            llm_connectors[connector.name()] = connector
    if not llm_connectors:
        llm_connectors["noop"] = NoOpLLMConnector()

    logger.debug("Loaded plugins", extra={"llm_count": len(llm_connectors)})
    return PluginBundle(
        license_validator=license_validator,
        usage_meter=usage_meter,
        llm_connectors=llm_connectors,
        report_renderer=report_renderer,
        notifier=notifier,
        drift_detector=drift_detector,
        run_enhancer=run_enhancer,
    )
