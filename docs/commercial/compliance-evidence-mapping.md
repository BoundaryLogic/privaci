# Compliance evidence mapping

PrivaCI produces **technical evidence** for database anonymization runs. Your
organization remains the controller/processor for GDPR, the covered entity or
business associate for HIPAA, and the accountable party for SOC 2 and ISO 27001
certifications. This document describes how to collect and verify PrivaCI
artifacts and maps report fields to frameworks **your compliance team** may
reference — it is not audit advice.

> **Marketing alignment:** PrivaCI supports *audit-ready reports for SOC 2,
> ISO 27001, GDPR, and HIPAA reviews*. It does not replace organizational
> certification, control design, or legal determinations. Framework mappings
> below are illustrative; validate scope with your auditor or counsel.

## How to use this document

| Audience | Start here |
| --- | --- |
| Platform / data engineering | [Evidence collection workflow](#evidence-collection-workflow) |
| Compliance / GRC | [Field → framework mapping](#field-framework-mapping) and [Evidence artifact checklist](#evidence-artifact-checklist) |
| Legal / DPO | [ROPA snippet](#ropa-snippet-customer-template) and [Retention starter template](#retention-starter-template) |

---

## Evidence collection workflow

Run this sequence after each production-source anonymization job (or on a
schedule aligned with your change-management cadence).

### 1. Execute and record the run

```bash
export SOURCE_DB_URL='postgresql://…/production_source'
export TARGET_DB_URL='postgresql://…/staging_target'
export ANONYMIZATION_SALT='…'   # ≥32 chars; never commit
export PRIVACI_OPERATOR_ID='platform-team-ci-42'  # optional; appears in report

privaci run --config mask-rules.yaml
# Note the run_id printed in the summary (also in _privaci.runs).
```

The run writes immutable state to `_privaci.runs` and `_privaci.audit_log` on the
target database. Partial runs can be resumed; interrupted runs exit `130`.

### 2. Generate a signed compliance report

See [Signed reports](signed-reports.md) for key generation, env vars, and verify.

```bash
export PRIVACI_REPORT_SIGNING_KEY_PEM='…'
export PRIVACI_OPERATOR_ID='ci-pipeline-42'
export PRIVACI_REPORT_SUMMARY_MD='/var/evidence/run-summary.md'

privaci report --run <run-uuid> --format json --output "evidence/report-<run-uuid>.json"
```

For S3 evidence buckets (all commercial tiers), use an object URI — see public
[Object output URIs](https://docs.boundarylogic.io/object-output/):

```bash
privaci report --run <run-uuid> --format json \
  --output "s3://compliance-evidence/privaci/<year>/<run-uuid>/report.json"
```

Archive both the JSON report and the Markdown sidecar (if generated).

### 3. Verify signature and integrity (CI or auditor workstation)

See [Signed reports — verify](signed-reports.md#4-verify-ci-or-auditor-workstation).

```bash
export PRIVACI_REPORT_VERIFY_PUBLIC_KEY_PEM="$(cat report-signing.pub.pem)"

python - <<'PY'
from pathlib import Path
from privaci_commercial.report_verify import verify_report_file

payload = verify_report_file(
    Path("evidence/report-<run-uuid>.json"),
    public_key_pem=Path("report-signing.pub.pem").read_bytes(),
)
print(payload["summary"]["verdict"]["status"])
PY
```

### 4. Check schema drift (optional gate before the next run)

See [Drift detection](drift-detection.md) for the Python API and CI gate pattern.

### 5. File evidence

Store under a stable path, e.g. `s3://compliance-evidence/privaci/<year>/<run_id>/`:

| Artifact | Retention |
| --- | --- |
| Signed `report-<run_id>.json` | ≥12–18 months (see [Retention](#retention-guidance)) |
| `run-summary.md` sidecar | Same as JSON |
| Verification log (stdout / CI job URL) | Same as JSON |
| `mask-rules.yaml` hash (from `summary.provenance.config_hash`) | Version-controlled separately |
| Drift report JSON (if collected) | Same as JSON |

---

## Report structure

Signed JSON reports (commercial layer) contain:

| Section | Purpose |
| --- | --- |
| `summary` | One-screen verdict, coverage, exceptions — start here |
| `run` | Raw run metadata from `_privaci.runs` |
| `audit_events` | Full drill-down audit trail |
| Envelope `signature` | Ed25519 tamper evidence over canonical JSON |

Generate a report:

```bash
export TARGET_DB_URL='postgresql://postgres:dev@127.0.0.1:55433/privaci_target'
export PRIVACI_REPORT_SIGNING_KEY_PEM='…'   # optional; signs envelope
export PRIVACI_OPERATOR_ID='ci-pipeline-42' # optional; provenance
export PRIVACI_REPORT_SUMMARY_MD='/tmp/run-summary.md'  # optional sidecar

privaci report --run <run-uuid> --format json --output report.json
```

S3 (ECS task role or `AWS_*` credentials):

```bash
privaci report --run <run-uuid> --format json \
  --output "s3://compliance-evidence/privaci/<run-uuid>/report.json"
```

See public [Object output URIs](https://docs.boundarylogic.io/object-output/)
for URI forms, MinIO testing, and custom plugins.

Verify a signed report:

```python
from pathlib import Path

from privaci_commercial.report_verify import verify_report_file

public_pem = Path("report-signing.pub.pem").read_bytes()
payload = verify_report_file(Path("report.json"), public_key_pem=public_pem)
print(payload["summary"]["verdict"])
```

Or set ``PRIVACI_REPORT_VERIFY_PUBLIC_KEY_PEM`` and use
:func:`privaci_commercial.report_verify.verify_report_bytes` in CI.

Markdown-only export (commercial `ReportRenderer`, format `summary-md`):

```python
from uuid import UUID
from privaci_commercial.reports import SignedJsonReportRenderer

md = SignedJsonReportRenderer().render(
    UUID("019ed1bf-97be-730a-8bb0-e019cea366c9"),
    output_format="summary-md",
)
print(md.decode())
```

## Field → framework mapping

Illustrative mapping only — customers decide which controls and frameworks apply.

| Summary field | SOC 2 TSC | ISO 27001 | GDPR | HIPAA de-ID |
| --- | --- | --- | --- | --- |
| `verdict.status`, timestamps, `duration_ms` | PI1.2 processing integrity | A.8.15 logging | Art 30 ops record | Processing log (when, outcome) |
| `provenance.run_id`, `config_hash`, versions | CC8.1 change/config traceability | A.8.11 documented techniques | Art 32 measures | Rule/version binding |
| `provenance.salt_fingerprint` | C1.1 confidentiality | A.8.11 pseudonymisation key governance | Art 32 pseudonymisation | Tokenization key controls |
| `provenance.operator` | CC6.1 logical access | A.8.2 user identification | Accountability | Certifier identity |
| `controls_applied.techniques` | C1.1 / PI1.3 | A.8.11 masking techniques | Art 32 technical measures | Field transformation inventory |
| `coverage.*` | PI1.4 completeness | A.8.11 effectiveness | Risk mitigation evidence | QA / sampling support |
| `attention_required.*` | PI1.4 exceptions | Nonconformity / risk register | Art 32 residual risk | Residual PHI review |
| `attention_required.policy_diff_findings` | Pre-run CI gate evidence | Policy drift before masking | Residual risk from preview | Preview-before-run QA |
| `processing_scope.personal_data_categories_inferred` | — | A.8.11 data inventory (partial) | Art 30 ROPA categories | Identifier categories |
| `audit_rollup` + `audit_events` | CC7.2 monitoring | A.8.15 event logging | Integrity (Art 32) | Audit trail |
| Ed25519 `signature` | CC7.2 integrity | A.8.15 log protection | Integrity (Art 32) | Tamper-evident record |

---

## Evidence artifact checklist

Product-focused list of what to collect per anonymization run. Your org owns
control design, policy wording, and how evidence maps to certification scope.

| Artifact | Source | Notes |
| --- | --- | --- |
| Signed compliance report | `privaci report --format json` | Primary technical evidence |
| Signature verification output | `report_verify` (see workflow step 3) | Proves payload unchanged since signing |
| Markdown summary sidecar | `PRIVACI_REPORT_SUMMARY_MD` or `summary-md` | Human-readable; same run as JSON |
| `mask-rules.yaml` commit | Version control | Tie to `summary.provenance.config_hash` |
| Operator / runner identity | `PRIVACI_OPERATOR_ID` or CI role | Optional; set in your pipeline |
| Drift review output | Drift Python API (see step 4) | When schema may have changed |
| Run exit code / CI job URL | Shell / orchestrator | `0` = succeeded |

Example index for your evidence store:

```markdown
## PrivaCI run evidence — <run_id>

| Item | Location |
| --- | --- |
| Signed report | evidence/report-<uuid>.json |
| Verify log | ci/job-<id> or manual output |
| Config | git:<sha> (config_hash: …) |
| Drift (if run) | drift-<date>.json |
```

---

## Retention starter template

Starter text for **your** internal policy — adjust periods and roles to match
your obligations. PrivaCI does not host or retain customer reports.

```markdown
## PrivaCI compliance report retention

**Purpose:** Preserve tamper-evident evidence of database anonymization runs.

**Scope:** All production-source → non-production anonymization jobs using PrivaCI.

**Retention period:** Minimum 18 months from report generation date.

**Storage:** [Customer bucket / GRC system]. Encryption at rest required.

**Access:** Compliance, Internal Audit, and Platform Engineering (read-only).

**Deletion:** Automated lifecycle rule after retention period; deletion logged.

**Verification:** Re-run signature verification annually on a sample of archived reports.

**Related artifacts:** mask-rules.yaml (version control, indefinite);
signing public key (until key rotation + overlap period ends).
```

## ROPA snippet (customer template)

```markdown
## Processing activity: non-production database anonymization

- **Purpose:** Realistic staging/test data without production PII
- **Lawful basis / role:** [customer completes]
- **Categories of data subjects:** See `summary.processing_scope.data_subject_categories_inferred`
- **Categories of personal data:** See `summary.processing_scope.personal_data_categories_inferred`
- **Recipients:** Internal non-production environments (in-VPC)
- **Retention:** Target DB per customer policy; signed report retained ≥12–18 months
- **Technical measures:** PrivaCI in-VPC masking; evidence: signed report `{run_id}`
```

---

## Control ownership matrix

| Area | Customer owns | PrivaCI provides |
| --- | --- | --- |
| Certification scope & policies | ✓ | Guidance only (this doc) |
| Database credentials & network | ✓ | Connection via standard Postgres |
| Salt / signing key custody | ✓ | Fingerprint + signature mechanics |
| Mask rule authoring | ✓ | Validation + execution |
| Run execution & scheduling | ✓ | CLI / container |
| Tamper-evident report | — | ✓ Signed JSON + verify helpers |
| In-run audit trail | — | ✓ `_privaci.audit_log` + report export |
| Report hosting & retention | ✓ | — |
| Organizational SOC 2 / ISO cert | ✓ | Product evidence, not vendor cert |

---

## Retention guidance

Store signed reports for at least **12–18 months** to cover typical SOC 2 Type II
observation windows. PrivaCI does not retain customer reports — reports live in
your environment.

## Gaps and roadmap

| Gap | Impact | Mitigation |
| --- | --- | --- |
| Preflight catalog warnings not in audit log | Incomplete exception register | Engine batch: write warnings to `_privaci.audit_log` |
| No `config_version` in summary | Weaker config traceability | Add when config artifact ID is stored on run row |
| `passed_through` events not emitted by engine yet | Passthrough counts from PII detections only | Engine batch: emit `column.passed_through` |
| Organizational SOC 2 / ISO certs | Vendor trust vs product evidence | BoundaryLogic vendor audit (separate from product) |
| `privaci detect-drift` CLI | Requires engine **v1.0.0+** and commercial **v1.0.0+** | Use [drift CLI](drift-detection.md#cli-public-engine-v100) or [Python API](#4-check-schema-drift-optional-gate-before-the-next-run) in CI |

---

## Related documentation

### Commercial

- [Signed reports](signed-reports.md) — signing, verify, Markdown export
- [Drift detection](drift-detection.md) — schema drift CI gate
- [Troubleshooting](troubleshooting.md) — exit codes

### Public engine

- [Error codes](https://docs.boundarylogic.io/error-codes/) — exit codes for run/report failures
- [State schema](https://docs.boundarylogic.io/state-schema/) — `_privaci` tables referenced in reports
- [Configuration](https://docs.boundarylogic.io/configuration/) — `mask-rules.yaml`

## Disclaimer

This mapping is guidance for customer compliance teams, not legal advice. Consult
counsel for certification scope and HIPAA de-identification determinations.
