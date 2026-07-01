# Signed compliance reports

**Audience:** DevOps (signing keys, CI verify) and GRC (tamper evidence).

**When you are done:** You can generate, sign, verify, and archive compliance
JSON reports for a completed run.

Reports are a **commercial** capability registered as `report_renderer.json`.
The public engine's community fallback emits unsigned JSON — see
[Extending PrivaCI](https://docs.boundarylogic.io/extending-privaci/).

GRC workflow (evidence filing): [Compliance evidence mapping](compliance-evidence-mapping.md).

---

## What you get

| Output | Format | Signed? |
| --- | --- | --- |
| Full compliance JSON | `privaci report --format json` | Yes, when signing key set |
| Markdown summary sidecar | `PRIVACI_REPORT_SUMMARY_MD` or `summary-md` | Sidecar is derived from signed payload |
| Unsigned JSON | Same command, no signing key | No |

Report body includes:

- `summary` — verdict, coverage, attention register (commercial)
- `run` — row from `_privaci.runs`
- `audit_events` — drill-down trail

Data is read from the **target** database (`TARGET_DB_URL`) — see public
[state schema](https://docs.boundarylogic.io/state-schema/).

---

## Configuration

| Variable | Required | Description |
| --- | --- | --- |
| `TARGET_DB_URL` | Yes | Target Postgres holding `_privaci` state |
| `PRIVACI_REPORT_SIGNING_KEY_PEM` | For signing | Ed25519 **private** key PEM |
| `PRIVACI_REPORT_VERIFY_PUBLIC_KEY_PEM` | For verify | Ed25519 **public** key PEM (auditors/CI) |
| `PRIVACI_OPERATOR_ID` | No | Operator identity in `summary.provenance` |
| `PRIVACI_REPORT_SUMMARY_MD` | No | Write Markdown sidecar when rendering JSON |

Legacy alias: `PRIVACI_REPORT_SIGNING_KEY` (same as `_PEM`).

---

## Quickstart

### 1. Generate a signing keypair (once per environment)

```bash
openssl genpkey -algorithm Ed25519 -out report-signing.pem
openssl pkey -in report-signing.pem -pubout -out report-signing.pub.pem
```

Store `report-signing.pem` in your secrets manager. Distribute
`report-signing.pub.pem` to auditors and CI verify jobs.

### 2. Run masking (public engine CLI inside the container)

After a successful `privaci run` batch job, note the run UUID from stdout.

```bash
export SOURCE_DB_URL='postgresql://…/source'
export TARGET_DB_URL='postgresql://…/target'
export ANONYMIZATION_SALT='…'   # 64 hex chars — see public configuration

docker run --rm --read-only --tmpfs /tmp \
  -e SOURCE_DB_URL -e TARGET_DB_URL -e ANONYMIZATION_SALT \
  -e PRIVACI_MARKETPLACE_PRODUCT_CODE='…' \
  -v "$(pwd)/mask-rules.yaml:/config/mask-rules.yaml:ro" \
  <marketplace-image-uri>:<tag> \
  run --config /config/mask-rules.yaml
```

CLI reference: public [privaci run](https://docs.boundarylogic.io/cli-reference/).
Deployment patterns: public [Deployment](https://docs.boundarylogic.io/deployment/).

### 3. Render signed report

Run a second one-shot container (or the same image in your orchestrator) with
the signing key injected from Secrets Manager:

```bash
docker run --rm --read-only --tmpfs /tmp \
  -e TARGET_DB_URL='postgresql://…/target' \
  -e PRIVACI_REPORT_SIGNING_KEY_PEM="$(aws secretsmanager get-secret-value …)" \
  -e PRIVACI_OPERATOR_ID='ci-pipeline-42' \
  -e PRIVACI_REPORT_SUMMARY_MD='/tmp/run-summary.md' \
  <marketplace-image-uri>:<tag> \
  report --run <run-uuid> --format json --output /tmp/report.json
```

Signed envelope shape:

```json
{
  "algorithm": "ed25519",
  "payload": { "report_version": "1", "run_id": "…", "summary": { … } },
  "signature": "<base64>"
}
```

Without a signing key, output is unsigned canonical JSON (still valid for dev).

### 4. Verify (CI or auditor workstation)

```bash
export PRIVACI_REPORT_VERIFY_PUBLIC_KEY_PEM="$(cat report-signing.pub.pem)"

python - <<'PY'
from pathlib import Path
from privaci_commercial.report_verify import verify_report_file

payload = verify_report_file(
    Path("report.json"),
    public_key_pem=Path("report-signing.pub.pem").read_bytes(),
)
print("verdict:", payload["summary"]["verdict"]["status"])
PY
```

Or set `PRIVACI_REPORT_VERIFY_PUBLIC_KEY_PEM` and use
`verify_report_bytes()` in your pipeline.

Verification confirms:

- Valid UTF-8 JSON
- Ed25519 signature matches canonical payload bytes
- Byte-for-byte reproducible re-serialization

---

## Markdown summary export

Human-readable one-screen summary for reviewers:

```bash
# Sidecar on JSON render (env var above), or programmatically:
python - <<'PY'
from uuid import UUID
from privaci_commercial.reports import SignedJsonReportRenderer

md = SignedJsonReportRenderer().render(
    UUID("019ed1bf-97be-730a-8bb0-e019cea366c9"),
    output_format="summary-md",
)
print(md.decode())
PY
```

---

## CI/CD integration

```yaml
- name: Generate signing key (ephemeral — dev/CI pattern)
  run: |
    openssl genpkey -algorithm Ed25519 -out /tmp/sign.pem
    echo "PRIVACI_REPORT_SIGNING_KEY_PEM<<EOF" >> "$GITHUB_ENV"
    cat /tmp/sign.pem >> "$GITHUB_ENV"
    echo "EOF" >> "$GITHUB_ENV"

- name: Render and verify report
  env:
    TARGET_DB_URL: ${{ secrets.TARGET_DB_URL }}
  run: |
    privaci report --run "${RUN_ID}" --format json -o report.json
    python -c "
    from pathlib import Path
    from privaci_commercial.report_verify import verify_report_file
    verify_report_file(Path('report.json'), public_key_pem=Path('/tmp/sign.pem').read_bytes())
    "
```

Production: use a stable key from secrets manager, not ephemeral CI keys.

---

## Security notes

- Never commit private signing keys or log report payloads containing PII.
- `PRIVACI_OPERATOR_ID` should identify a role or pipeline — not a person's email.
- Public key rotation: keep overlap period where both keys verify; document in your
  key-management runbook.

---

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `CommercialConfigError` on signing key | Malformed PEM or non-Ed25519 key | Regenerate with `openssl genpkey -algorithm Ed25519` |
| Unsigned output | `PRIVACI_REPORT_SIGNING_KEY_PEM` unset | Set key or accept unsigned for dev |
| Verify fails | Report edited after signing | Re-render; investigate tampering |
| `TARGET_DB_URL is required` | Env not set for `report` | Export target DSN |
| Empty `audit_events` | Run failed or audit disabled | Check run status; see public [configuration — audit_log](https://docs.boundarylogic.io/configuration/#top-level-options) |

---

## FAQ

**Does verify need the private key?**  
No. Auditors use the **public** key only.

**Relationship to `privaci verify`?**  
Public [`privaci verify`](https://docs.boundarylogic.io/cli-reference/)
checks masking *quality* (value-free stats). Report verify checks *document integrity*
(signature). Use both.

**PDF reports?**  
Not yet — JSON + Markdown summary today (OpenSpec task 27.3 in public archive).
