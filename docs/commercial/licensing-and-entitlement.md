# Licensing & entitlement

**Audience:** DevOps configuring PrivaCI commercial on AWS Marketplace.

**When you are done:** You know how Marketplace entitlement flows into each
batch job, which env vars to set, what each tier allows, and why a run exits **5**.

PrivaCI commercial is sold via **AWS Marketplace SaaS Contract**. Customers
subscribe, run the **official container image** in their VPC, and entitlement
is validated at job start — no git clone, no separate license server in your
network.

The commercial plugin `MarketplaceLicenseValidator` (entry point
`license_validator`) is called by the public engine before every `privaci run`.
See public [Extending PrivaCI — Community mode](https://docs.boundarylogic.io/extending-privaci/#community-mode)
for the plugin boundary.

---

## How licensing works

```text
Marketplace subscription
  → customer pulls commercial container image
  → privaci run (batch job in customer VPC)
  → load_plugins().license_validator.validate()
  → (if valid) UsageMeter.register_run → pipeline
  → (at run start) enforce_source_db_limit() against _privaci.runs
  → (optional) RegisterUsage / MeterUsage to AWS Marketplace
```

| Check | When | Exit code |
| --- | --- | --- |
| Marketplace / JWT license valid | Run start (preflight) | [5](https://docs.boundarylogic.io/error-codes/#exit-code-5-license--entitlement-failure-commercial) |
| Source-DB count within tier | Before recording new run | [5](https://docs.boundarylogic.io/error-codes/#exit-code-5-license--entitlement-failure-commercial) |
| Calendar-month data within tier | Before starting a new run | [5](https://docs.boundarylogic.io/error-codes/#exit-code-5-license--entitlement-failure-commercial) |

Billing dimension: ADR-0003 (commercial).

Billing dimension semantics (source DB count, monthly data allocation) are
summarized in [Tier limits](#tier-limits) below. Internal ADR-0003 stays in the
private repo.

---

## Marketplace subscription flow

1. **Subscribe** on AWS Marketplace (Starter / Growth / Business / Unlimited).
2. **Register** — AWS POSTs to the fulfillment URL; complete setup at
   [boundarylogic.io/marketplace/register](https://boundarylogic.io/marketplace/register)
   to obtain `LicenseArn` and product code.
3. **Run in VPC** — attach an IAM role to your ECS task / EKS pod / Batch job
   that can call `aws-marketplace:GetEntitlements`.
4. **Entitlement at job start** — with `PRIVACI_MARKETPLACE_PRODUCT_CODE`,
   `PRIVACI_LICENSE_ARN`, and IAM `GetEntitlements`, the commercial layer
   resolves your subscribed tier. Alternatively use offline `PRIVACI_LICENSE_KEY` (JWT).

No BoundaryLogic-hosted license server. Entitlement checks use AWS APIs from
inside your account/VPC.

---

## Configuration

### Environment variables

| Variable | Required | Description |
| --- | --- | --- |
| `PRIVACI_MARKETPLACE_PRODUCT_CODE` | Marketplace runs | Product code from registration / subscription |
| `PRIVACI_LICENSE_ARN` | Marketplace runs (Concurrent Agreements) | License ARN from registration; scopes `GetEntitlements` |
| `AWS_REGION` | Marketplace runs | Region for Marketplace APIs (default `us-east-1`) |
| AWS credentials | Marketplace runs | Via task/instance role — **never** static keys in the image |
| `PRIVACI_LICENSE_KEY` | Offline / air-gap | Signed JWT license (EdDSA) when live metering is unavailable |
| `PRIVACI_LICENSE_PUBLIC_KEY` | With JWT | PEM Ed25519 public key that verifies the JWT |
| `TARGET_DB_URL` | Entitlement check | Required for rolling 30-day source-DB counting on `_privaci.runs` |
| `PRIVACI_COMMERCIAL_DEV_LICENSE` | **Contributors only** | Set to `1` for Growth-tier dev bypass. **Never in customer production.** |

Copy from [Deployment environment variables](https://docs.boundarylogic.io/deployment/) (reference for all vars).

### Production (Marketplace — recommended)

Configure via your orchestrator's secret/env mechanism:

```yaml
# Kubernetes Secret / ECS task definition — illustrative
env:
  - name: PRIVACI_MARKETPLACE_PRODUCT_CODE
    value: "<from-registration>"
  - name: PRIVACI_LICENSE_ARN
    value: "<from-registration>"
  - name: AWS_REGION
    value: "us-east-1"
  - name: TARGET_DB_URL
    valueFrom:
      secretKeyRef:
        name: privaci-target-creds
        key: url
# IAM task role grants marketplace-metering:* — no access keys in env
```

### Offline JWT (contract without live metering)

1. Obtain a signed JWT from BoundaryLogic (tier claim inside token).
2. Inject at runtime:

```bash
export PRIVACI_LICENSE_PUBLIC_KEY="$(cat license-public.pem)"
export PRIVACI_LICENSE_KEY='eyJ...'
```

JWT claims:

| Claim | Values |
| --- | --- |
| `tier` | `starter` · `growth` · `business` · `enterprise` · `unlimited` (legacy `team` → `growth`) |
| `exp` | Standard JWT expiry |

---

## Tier limits

Rolling **30-day distinct `source_db_hash`** count on the target's
`_privaci.runs` table (see public
[state schema](https://docs.boundarylogic.io/state-schema/)).

| Tier | Source DBs (30-day) | Monthly data (GiB) | Price |
| --- | --- | --- | --- |
| `starter` | 2 | 100 | $99/mo |
| `growth` | 5 | 500 | $349/mo |
| `business` | 15 | 5 TiB | $899/mo |
| Unlimited (`enterprise` / `unlimited`) | Unlimited | Unlimited | $1,499/mo |

Monthly data-volume enforcement sums ``summary.bytes`` from succeeded runs in the
**UTC calendar month** on the target's ``_privaci.runs`` table.

| Dimension | Enforcement model |
| --- | --- |
| **Source databases** | Hard gate at run start — exit **5** when the rolling 30-day distinct count would exceed the tier. |
| **Data processed** | Pre-run gate on the **next** job — exit **5** when month-to-date bytes are already at or above the tier GiB ceiling. Does **not** estimate or cap bytes for the run about to start; a job that begins under the ceiling may still push month-to-date usage over the tier. Over-limit usage is logged after completion so the following run is blocked until the UTC month rolls or the tier is upgraded. |

Either ceiling breached at run start → exit **5**.

### GetEntitlements failures fail closed

When ``PRIVACI_MARKETPLACE_PRODUCT_CODE`` is set but ``GetEntitlements`` fails
(bad IAM policy, wrong region, network error), the commercial layer logs a
warning and returns **no** tier. Without a valid ``PRIVACI_LICENSE_KEY``, ``validate()``
returns ``is_valid=False`` and the run exits **5** — entitlement API errors do not
grant a free tier.

---

## AWS Marketplace metering

When `PRIVACI_MARKETPLACE_PRODUCT_CODE` and AWS credentials are configured,
`HeartbeatMeter` calls `RegisterUsage` / `MeterUsage` at job boundaries.

| Scenario | Behaviour |
| --- | --- |
| Marketplace task role configured | Live metering calls |
| No AWS credentials | Client is a **no-op** (dev/CI only — not valid for production) |
| Job crashes before end metering | See Marketplace spike FAQ |

Spike notes: AWS Marketplace spike.

---

## CI/CD integration (customer pipeline)

Run the **Marketplace image** as a one-shot job in your CI cluster or runner
with the same env vars as production:

```yaml
- name: Mask staging from prod snapshot
  env:
    PRIVACI_MARKETPLACE_PRODUCT_CODE: ${{ secrets.PRIVACI_MARKETPLACE_PRODUCT_CODE }}
    AWS_REGION: us-east-1
    SOURCE_DB_URL: ${{ secrets.STAGING_SOURCE_DB_URL }}
    TARGET_DB_URL: ${{ secrets.STAGING_TARGET_DB_URL }}
    ANONYMIZATION_SALT: ${{ secrets.ANONYMIZATION_SALT }}
  run: |
    docker run --rm … <marketplace-image> run --config /config/mask-rules.yaml
    test $? -ne 5   # fail pipeline on entitlement error
```

Schema drift gate: [Drift detection](drift-detection.md).

---

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| Exit **5** — no license | Subscription not linked; missing product code | Confirm active Marketplace subscription; set `PRIVACI_MARKETPLACE_PRODUCT_CODE` |
| Exit **5** — tier exceeded | Too many distinct source DBs in 30 days | Upgrade tier on Marketplace or reduce source databases |
| Exit **5** — invalid JWT | Bad signature or expired `exp` | Re-issue token; check `PRIVACI_LICENSE_PUBLIC_KEY` |
| Exit **5** — metering unreachable | Task role lacks Marketplace API access | Attach IAM policy for `aws-marketplace:RegisterUsage` |
| Entitlement skipped | `TARGET_DB_URL` unset | Set target DSN for counting |

Full exit code reference: [Troubleshooting](troubleshooting.md) · public
[Error codes](https://docs.boundarylogic.io/error-codes/).

---

## FAQ

**Does community mode (public GHCR image, no commercial layer) exit 5?**  
No. Community `LicenseValidator` always returns valid. Unsigned reports only.

**Is `PRIVACI_COMMERCIAL_DEV_LICENSE` for customers?**  
No. Internal BoundaryLogic CI and contributor local dev only. Block it in
customer deploy templates.

**Where is `source_db_hash` defined?**  
Public engine fingerprints `host:port/dbname` of the source DSN — see
[state schema — runs](https://docs.boundarylogic.io/state-schema/).

**Do I need this private GitHub repo?**  
No. Everything ships in the Marketplace container image.
