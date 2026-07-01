# Troubleshooting (commercial layer)

**Audience:** DevOps, developers, and on-call engineers.

**When you are done:** You can map a failure to an exit code, the responsible
layer (public vs commercial), and the next fix.

The **authoritative exit code list** lives in the public engine:

[Error codes](https://docs.boundarylogic.io/error-codes/)

This page covers commercial-specific failures and points to public docs for the
rest.

---

## Exit code quick reference

| Code | Layer | Commercial? | Doc |
| --- | --- | --- | --- |
| 0 | Public | — | Success |
| 1 | Public | — | [Generic error](https://docs.boundarylogic.io/error-codes/#exit-code-1-generic-error) |
| 2 | Public | — | [Pre-flight failure](https://docs.boundarylogic.io/error-codes/#exit-code-2-pre-flight-failure) |
| 3 | Public | — | [Config validation](https://docs.boundarylogic.io/error-codes/#exit-code-3-config-validation-failure) |
| 4 | Public | — | [Invalid salt](https://docs.boundarylogic.io/error-codes/#exit-code-4-missing-or-invalid-salt) |
| **5** | **Commercial** | License / entitlement | [Licensing](licensing-and-entitlement.md) |
| **6** | **Commercial** | Drift detected | [Drift detection](drift-detection.md) |
| 130 | Public | — | [Interrupted](https://docs.boundarylogic.io/error-codes/#exit-code-130-interrupted-by-signal) |

Message format (all codes): **Context + Cause + Remediation** — see public doc.

---

## Commercial failures

### Exit 5 — license / entitlement

| Cause | Remediation |
| --- | --- |
| No `PRIVACI_LICENSE_KEY` and no dev bypass | Set JWT or `PRIVACI_COMMERCIAL_DEV_LICENSE=1` (local only) |
| Expired or invalid JWT | Re-issue license; verify `PRIVACI_LICENSE_PUBLIC_KEY` |
| Tier source-DB limit exceeded | Upgrade tier or reduce distinct source databases |

Details: [Licensing & entitlement](licensing-and-entitlement.md)

### Exit 6 — drift (when CLI or your script uses it)

| Cause | Remediation |
| --- | --- |
| Schema changed since last run | Review findings; update `mask-rules.yaml` |
| `uncovered_pii_column` | Add masking rule before next run |

Details: [Drift detection](drift-detection.md)

### Report signing / verify errors

| Symptom | Remediation |
| --- | --- |
| `CommercialConfigError` — bad PEM | Regenerate Ed25519 key — [Signed reports](signed-reports.md) |
| Verify signature mismatch | Report tampered or wrong public key |
| `TARGET_DB_URL` missing for report | Set target DSN |

### Plugins not active

| Symptom | Remediation |
| --- | --- |
| Unsigned reports only | Confirm you are running the **Marketplace image**, not the public community GHCR image |
| Exit **5** on every run | Check Marketplace subscription and `PRIVACI_MARKETPLACE_PRODUCT_CODE` — [Licensing](licensing-and-entitlement.md) |
| `drift_detector is None` | Commercial layer not in the image — contact support; verify image URI from subscription |

**Contributors:** verify plugins after editable install:

```bash
python -c "from privaci.contracts import load_plugins as l; p=l(); print(type(p.report_renderer).__name__)"
# Expect: SignedJsonReportRenderer (not JsonReportRenderer)
```

See public [Extending PrivaCI](https://docs.boundarylogic.io/extending-privaci/).

---

## Public engine failures (pointers)

| Symptom | Public doc |
| --- | --- |
| Config rejected | [Configuration](https://docs.boundarylogic.io/configuration/) |
| Connection / catalog errors | [CLI reference](https://docs.boundarylogic.io/cli-reference/) |
| Masking quality concerns | [`privaci verify`](https://docs.boundarylogic.io/cli-reference/) |
| Resume / interrupted run | [Error 130](https://docs.boundarylogic.io/error-codes/#exit-code-130-interrupted-by-signal) + `privaci resume` |
| `_privaci` schema / grants | [State schema](https://docs.boundarylogic.io/state-schema/) |

---

## FAQ

**Where do I start debugging a failed run?**  
1. Note exit code → public [error codes](https://docs.boundarylogic.io/error-codes/)  
2. Check `_privaci.runs.status` on target  
3. Re-run with `privaci dry-run --report /tmp/review.md`

**Logs contain PII?**  
They should not. Public engine redacts PII in observability — see
[Observability](https://docs.boundarylogic.io/observability/).
File an issue if you see raw values.

**Commercial support boundary?**  
Engine bugs → public repo. License, reports, drift, metering → commercial layer
(this repo).
