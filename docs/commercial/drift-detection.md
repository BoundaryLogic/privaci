# Drift detection

**Audience:** DevOps (CI gates) and developers (schema change workflow).

**When you are done:** You can detect production schema changes vs the last
stored snapshot and block staging refreshes when config is stale.

Drift detection is **commercial** — entry point `drift_detector`. Community
mode has no drift detector; see public
[Extending PrivaCI](https://docs.boundarylogic.io/extending-privaci/).

Complements public preflight [`strict_autodetect`](https://docs.boundarylogic.io/configuration/#top-level-options)
(exit **3**) which catches unmapped PII columns **at run time**. Drift compares
**catalog snapshots between runs** (exit **6** when wired to CLI).

**Engine requirement:** `privaci detect-drift` ships in public **v1.0.0+**
with commercial **v1.0.0+** (engine pin `v1.0.0`).

---

## What it detects

`CatalogDriftDetector` diffs the live source catalog against
`runs.source_schema_snapshot` on the target (public
[state schema](https://docs.boundarylogic.io/state-schema/)).

| Finding kind | Meaning |
| --- | --- |
| `table_added` / `table_removed` | Whole table appeared or disappeared |
| `column_added` / `column_removed` / `column_retyped` | Column schema change |
| `uncovered_pii_column` | New column name matches **no** built-in auto-detect pattern |

The last kind is the r/postgres nightmare case — a new column that would
**passthrough** silently on the next run.

---

## When to run drift detection

| Trigger | Recommendation |
| --- | --- |
| Before `privaci run` in CI | Fail if drift + config not updated |
| After production migration | Alert platform team |
| Scheduled (nightly) | Compare prod catalog to last staging snapshot |

---

## CLI (public engine v1.0.0+)

```bash
privaci detect-drift --source "$SOURCE_DB_URL" --target "$TARGET_DB_URL"
# Exit 6 when drift found; --accept-drift to emit findings only
```

Requires commercial installed (`privaci-commercial` provides `CatalogDriftDetector`).

---

## Python API

Same behaviour as the CLI — useful in custom scripts or before the CLI existed:

```python
import asyncio

import asyncpg

from privaci.catalog import introspect_catalog
from privaci.catalog.snapshot import load_latest_schema_snapshot
from privaci.state.fingerprints import source_db_hash
from privaci_commercial.drift import CatalogDriftDetector

SOURCE_DSN = "postgresql://…/production_source"
TARGET_DSN = "postgresql://…/staging_target"


async def main() -> None:
    detector = CatalogDriftDetector()
    source = await asyncpg.connect(SOURCE_DSN)
    target = await asyncpg.connect(TARGET_DSN)
    try:
        current = (await introspect_catalog(source)).to_snapshot_dict()
        previous = await load_latest_schema_snapshot(
            target, source_db_hash=source_db_hash(SOURCE_DSN)
        )
    finally:
        await source.close()
        await target.close()

    if previous is None:
        raise SystemExit("No baseline — run masking once to store a snapshot.")

    report = detector.detect(previous, current)
    if report.has_drift:
        for finding in report.findings:
            print(finding)
        raise SystemExit(6)


asyncio.run(main())
```

Exit **6** matches public
[error code 6 — drift](https://docs.boundarylogic.io/error-codes/#exit-code-6-drift-detected-commercial).

---

## CI/CD gate pattern

Run drift check as a one-shot container job (same Marketplace image) before
masking:

```yaml
- name: Schema drift check
  env:
    SOURCE_DB_URL: ${{ secrets.PROD_SOURCE_DB_URL }}
    TARGET_DB_URL: ${{ secrets.STAGING_TARGET_DB_URL }}
  run: |
    docker run --rm … <marketplace-image> privaci detect-drift \
      --source "$SOURCE_DB_URL" --target "$TARGET_DB_URL"
```

Or call the Python API from `scripts/check_drift.py` if you need custom output.

---

## Remediation workflow

1. Run drift check after production DDL
2. If exit **6**: review findings — add `mask-rules.yaml` entries for new PII columns
3. Re-run drift with `--accept-drift` to acknowledge non-blocking changes, or
   update config and re-run until clean
4. Proceed with staging refresh / `privaci run`

Treat `uncovered_pii_column` as **blocking**.

---

## Relationship to public `strict_autodetect`

| Mechanism | When | Blocks with |
| --- | --- | --- |
| `strict_autodetect: true` | Preflight on each run | Exit **3** — config error |
| Drift detector | Compare to last snapshot | Exit **6** (CLI) or your script |
| Auto-detect (default) | Preflight | Auto-applies high-confidence columns |

Use **both** for defense in depth. See public
[Auto-detect](https://docs.boundarylogic.io/configuration/#auto-detect).

---

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| No baseline snapshot | No succeeded run yet | Run `privaci run` once |
| Drift after intentional migration | Expected | Update config, then accept |
| `uncovered_pii_column` on `legacy_code` | No name pattern match | Add explicit column rule in YAML |
| False negative on `phone_number` | Name matches `phone` pattern | Auto-detect handles on next run; add YAML for strict mode |

---

## FAQ

**Does drift run automatically on `privaci run`?**  
Not as rich findings today. Resume compares binary snapshot equality. Use an
explicit drift check in CI.

**Where is the snapshot stored?**  
`_privaci.runs.source_schema_snapshot` on the **target** DB.

**Community mode?**  
`plugins.drift_detector is None` — drift API unavailable without commercial layer.

---

## Related

- [Compliance evidence mapping](compliance-evidence-mapping.md) — drift as optional CI gate
- Public [error codes](https://docs.boundarylogic.io/error-codes/#exit-code-6-drift-detected-commercial)
- OpenSpec task **21.5** — CLI shipped in engine **v1.0.0**
