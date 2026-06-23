# contracts

Stable abstract base classes for the commercial plugin layer. The public
engine loads implementations from the `privaci.plugins` entry-point group;
community fallbacks are used when no plugin is installed.

## Public API

| ABC | Purpose |
|-----|---------|
| `LicenseValidator` | Entitlement checks |
| `UsageMeter` | Billing heartbeat |
| `LLMConnector` | Level-3 AI refinement |
| `ReportRenderer` | Signed compliance reports |
| `Notifier` | Run-completion webhooks |
| `DriftDetector` | Schema drift detection |
| `RunEnhancer` | Subsetting and JSONB transforms |
| `ObjectWriter` | Compliance artifact destinations |
| `load_plugins` | Resolve all registered plugins |
| `CONTRACT_VERSION` | Semver string for ABI compatibility |

## Configuration

Plugins are discovered at import time; no `mask-rules.yaml` keys.

## Example

See [`docs/extending-privaci.md`](../../../docs/extending-privaci.md).

```python
from privaci.contracts import load_plugins

plugins = load_plugins()
plugins.usage_meter.record_run_complete(event)
```
