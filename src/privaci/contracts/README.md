# contracts

Stable abstract base classes for the ``privaci.plugins`` plugin layer. The public
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
