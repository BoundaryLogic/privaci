---
title: "Building a plugin"
description: "Extend PrivaCI with entry-point plugins for custom maskers, drift detectors, and report renderers."
---

# Building a PrivaCI Plugin

The engine defines stable contracts in `privaci.contracts`. Any plugin —
your own or the proprietary commercial layer — implements these contracts and
registers them via Python entry points under the group `privaci.plugins`.

## Entry points

| Name | ABC | Purpose |
|------|-----|---------|
| `license_validator` | `LicenseValidator` | Marketplace entitlement |
| `usage_meter` | `UsageMeter` | Billing heartbeat |
| `llm_connector.aws_bedrock` | `LLMConnector` | Level 3 Bedrock |
| `llm_connector.azure_openai` | `LLMConnector` | Level 3 Azure OpenAI |
| `report_renderer.json` | `ReportRenderer` | Signed JSON reports |
| `report_renderer.pdf` | `ReportRenderer` | PDF reports (commercial) |
| `notifier.slack` | `Notifier` | Slack webhook |
| `notifier.webhook` | `Notifier` | Generic HTTP webhook |
| `drift_detector` | `DriftDetector` | Schema drift detection |
| `run_enhancer` | `RunEnhancer` | Subsetting and JSONB transforms |
| `object_writer` | `ObjectWriter` | Compliance artifact upload (`s3://`, local) |

## Community mode

Without the commercial package installed, `privaci` uses built-in
fallbacks: unrestricted community license, silent metering, JSON report
stub, no LLM connector, no drift detector.

## License capabilities

A `LicenseValidator` returns a `LicenseStatus`. Beyond `tier` and `is_valid`, it
carries `capabilities: frozenset[str]` — opaque capability tokens the engine
checks by **membership only**. The engine never interprets tier names, so a
plugin is free to name its tiers however it likes; it grants a feature by
adding the corresponding token.

Tokens the engine reads today:

| Token | Enables |
|-------|---------|
| `keyed_actions` | `hmac_hash` and `pseudonym` masking actions |

Grant a token by including it in the returned set:

```python
from privaci.contracts import LicenseStatus, LicenseValidator


class MyValidator(LicenseValidator):
    def validate(self) -> LicenseStatus:
        return LicenseStatus(
            tier="my-plan",
            is_valid=True,
            capabilities=frozenset({"keyed_actions"}),
        )
```

Community mode returns an empty capability set, so keyed actions are fail-closed
in the open-source engine. Additional tokens may be defined and enforced
entirely by your plugin without any engine change.

## Contract version

`privaci.contracts.CONTRACT_VERSION` is currently `"1.0"`. Query it with
`privaci --contract-version` or the OCI label `io.boundarylogic.contract_version`
on release images. Breaking
changes to ABCs require a major version bump in both repositories.

## Registering a plugin

Add an entry in your commercial package's `pyproject.toml`:

```toml
[project.entry-points."privaci.plugins"]
license_validator = "privaci_commercial.license:MarketplaceValidator"
usage_meter = "privaci_commercial.meter:HeartbeatMeter"
```

Implement the ABC from `privaci.contracts` and call `load_plugins()` at
runtime — the CLI does this automatically before `run` and `report`.

## Registering a fake provider

Community and commercial code can add deterministic fakers without touching
core engine code:

```python
from privaci.contracts import register_provider
from privaci.mask.faker import FakeProvider, FakeRequest

class AcmeEmployeeId(FakeProvider):
    name = "acme_employee_id"

    def fake(self, request: FakeRequest) -> str:
        return f"EMP-{request.stable_hash[:8].upper()}"

register_provider(AcmeEmployeeId())
```

Then reference `provider: acme_employee_id` in `mask-rules.yaml`.

## Testing a plugin locally

```python
from privaci.contracts import load_plugins

plugins = load_plugins()
assert plugins.license_validator.validate() is not None
```

Integration tests in the commercial repo should install the package editable
and run `privaci run` against a throwaway Postgres (see
[`local-development.md`](local-development.md)).
