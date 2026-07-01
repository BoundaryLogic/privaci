# Commercial layer quickstart

**Audience:** DevOps and platform engineers running PrivaCI **after subscribing
on AWS Marketplace**.

**When you are done:** You have run a masked job in your VPC using the official
commercial container image and generated a signed compliance report.

**Delivery model:** PrivaCI commercial ships as a **container image** bundled
with the public engine. You subscribe on AWS Marketplace, pull the image into
your registry or runtime, and run it as a **one-shot batch job** in your VPC.
You do **not** clone this repository or `pip install` anything in production.

Public engine concepts (salt, `mask-rules.yaml`, CLI): see the public docs first
if you are new to PrivaCI:

| Public doc | Why |
| --- | --- |
| [Deployment](https://docs.boundarylogic.io/deployment/) | Container model, Helm chart, read-only root |
| [Configuration](https://docs.boundarylogic.io/configuration/) | `mask-rules.yaml` reference |
| [CLI reference](https://docs.boundarylogic.io/cli-reference/) | All `privaci` subcommands |
| [Quickstart (evaluation)](https://docs.boundarylogic.io/quickstart/) | Try the engine locally with synthetic data |

---

## Prerequisites

- Active **AWS Marketplace subscription** (Starter, Growth, Business, or Unlimited)
- Network path from the job to **source** and **target** PostgreSQL (in-VPC)
- Container runtime (ECS, EKS, Batch, Kubernetes CronJob) or `docker run` for a
  smoke test
- `mask-rules.yaml` authored for your schema — start from public
  [examples/mask-rules.example.yaml](https://github.com/BoundaryLogic/privaci/blob/main/examples/mask-rules.example.yaml)
- Secrets for DB URLs, salt, and (optionally) report signing — see
  [Licensing](licensing-and-entitlement.md) and [Signed reports](signed-reports.md)

---

## 1. Get the container image

After subscribing, AWS Marketplace provides the **image URI** and entitlement
fulfillment instructions on your subscription page.

```bash
docker pull ghcr.io/boundarylogic/privaci-commercial:<tag>
```

Pin to a **stable** tag (not `:beta` or `:edge`) in production. The commercial
layer is baked into this image — no separate install step.

Image properties match the public engine container — see public
[Deployment — container image](https://docs.boundarylogic.io/deployment/#container-image):
Python 3.12, non-root user `privaci` (UID 10001), entrypoint `privaci`,
read-only root compatible.

---

## 2. Configure entitlement

Marketplace subscription validates at job start. Set entitlement env vars or
use the IAM role attached to your task — see
[Licensing & entitlement](licensing-and-entitlement.md).

Minimum for a Marketplace run:

```bash
export PRIVACI_MARKETPLACE_PRODUCT_CODE='<from-subscription>'
export AWS_REGION='us-east-1'   # region where you subscribed
# AWS credentials via task/instance role — no static keys in the image
```

Optional offline JWT (air-gapped or contract without live metering):

```bash
export PRIVACI_LICENSE_KEY='eyJ...'
export PRIVACI_LICENSE_PUBLIC_KEY="$(cat license-public.pem)"
```

`PRIVACI_COMMERCIAL_DEV_LICENSE` is for **BoundaryLogic internal CI only** —
never in customer production.

---

## 3. Run masking (one-shot batch job)

Mount your config read-only. Pass DB URLs and salt via env vars or your
secrets manager (never bake secrets into the image).

```bash
docker run --rm --read-only --tmpfs /tmp \
  -e SOURCE_DB_URL='postgresql://user:pass@source-host:5432/app' \
  -e TARGET_DB_URL='postgresql://user:pass@target-host:5432/staging' \
  -e ANONYMIZATION_SALT="$(openssl rand -hex 32)" \
  -e PRIVACI_MARKETPLACE_PRODUCT_CODE='…' \
  -e AWS_REGION='us-east-1' \
  -v "$(pwd)/mask-rules.yaml:/config/mask-rules.yaml:ro" \
  ghcr.io/boundarylogic/privaci-commercial:<tag> \
  run --config /config/mask-rules.yaml
```

Expected stdout ends with:

```text
Run <uuid> succeeded: N table(s), M row(s).
```

State is written to `_privaci` on the **target** database — see public
[state schema](https://docs.boundarylogic.io/state-schema/).

**Dry run first (no writes):**

```bash
docker run --rm --read-only --tmpfs /tmp \
  -e SOURCE_DB_URL='…' \
  -v "$(pwd)/mask-rules.yaml:/config/mask-rules.yaml:ro" \
  ghcr.io/boundarylogic/privaci-commercial:<tag> \
  dry-run --config /config/mask-rules.yaml --report /tmp/autodetect.md
```

**Kubernetes / scheduled runs:** use the public Helm chart — see
[Deployment — Helm chart](https://docs.boundarylogic.io/deployment/#helm-chart).
Set commercial env vars via `extraEnv` or Secret refs.

---

## 4. Generate a signed compliance report

Generate a signing keypair once per environment — see
[Signed reports](signed-reports.md#1-generate-a-signing-keypair-once-per-environment).
Store the private key in AWS Secrets Manager (or equivalent); mount or inject at
job runtime.

```bash
docker run --rm --read-only --tmpfs /tmp \
  -e TARGET_DB_URL='postgresql://…/staging' \
  -e PRIVACI_REPORT_SIGNING_KEY_PEM="$(aws secretsmanager get-secret-value …)" \
  -e PRIVACI_OPERATOR_ID='prod-nightly-cron' \
  -e PRIVACI_REPORT_SUMMARY_MD='/tmp/run-summary.md' \
  ghcr.io/boundarylogic/privaci-commercial:<tag> \
  report --run <run-uuid-from-step-3> --format json --output /tmp/report.json
```

Copy `/tmp/report.json` (and the Markdown sidecar) to your evidence store.

Details: [Signed reports](signed-reports.md) ·
[Compliance evidence workflow](compliance-evidence-mapping.md)

---

## 5. Verify the report

Run on a CI worker or auditor workstation — **public key only**, no private key:

```bash
python - <<'PY'
from pathlib import Path
from privaci_commercial.report_verify import verify_report_file

payload = verify_report_file(
    Path("report.json"),
    public_key_pem=Path("report-signing.pub.pem").read_bytes(),
)
print(payload["summary"]["verdict"]["status"])
PY
```

The verify helper ships in the commercial image. Auditors can also use a
BoundaryLogic-provided verify script without Marketplace subscription — contact
support for auditor tooling.

---

## FAQ

**Do I need to clone any GitHub repo?**  
No. Subscribe on AWS Marketplace, pull the image, configure env vars, run.

**Community vs commercial image?**  
The public GHCR image (`ghcr.io/boundarylogic/privaci`) runs in **community
mode** (no license enforcement, unsigned reports). The **Marketplace image**
includes the commercial layer. Production paid deployments use the Marketplace
image only.

**Where does data go?**  
Nowhere outside your VPC. The container reads source Postgres, writes masked
rows to target Postgres, and exits. See public
[architecture overview](https://docs.boundarylogic.io/architecture/overview/).

**Which salt env var?**  
Production uses `ANONYMIZATION_SALT` or `global_salt` in YAML — see public
[error code 4](https://docs.boundarylogic.io/error-codes/#exit-code-4-missing-or-invalid-salt).

---

## Next steps

| Goal | Doc |
| --- | --- |
| License tiers & exit 5 | [Licensing & entitlement](licensing-and-entitlement.md) |
| Signing keys & CI verify | [Signed reports](signed-reports.md) |
| Schema drift gate | [Drift detection](drift-detection.md) |
| Errors | [Troubleshooting](troubleshooting.md) |
| Helm / CronJob patterns | Public [Deployment](https://docs.boundarylogic.io/deployment/) |
