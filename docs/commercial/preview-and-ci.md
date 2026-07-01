# CI preview and policy diff

**Audience:** DevOps running pre-merge CI checks before production masking.

**CLI:** `privaci preview` (public engine **v1.0.1+** and Marketplace
image). The legacy `privaci-preview` console script remains as an alias.

Public baseline unchanged: `privaci dry-run`, `privaci verify` — see public
[CLI reference](https://docs.boundarylogic.io/cli-reference/).

---

## Commands

### Policy diff JSON (26.2)

```bash
docker run --rm \
  -e SOURCE_DB_URL='…' -e TARGET_DB_URL='…' \
  -v "$(pwd)/mask-rules.yaml:/config/mask-rules.yaml:ro" \
  -v "$(pwd)/policy-diff:/output" \
  <marketplace-image> \
  privaci preview --config /config/mask-rules.yaml \
    --policy-diff /output/policy-diff.json
```

When `strict_autodetect: true`, preview **writes** `--policy-diff` (and `--sarif`
when requested), then exits **3** if uncovered high/medium columns remain. A
non-zero exit does **not** mean artifacts were skipped — inspect
`strict_passed` and `uncovered_strict` in the JSON.

Example CI gate (single command, artifact on failure):

```yaml
- name: Enforce masking policy
  run: |
    mkdir -p policy-diff
    docker run --rm \
      -e SOURCE_DB_URL=${{ secrets.PROD_READ_REPLICA_URL }} \
      -e TARGET_DB_URL=${{ secrets.PRIVACI_EMPTY_TARGET_URL }} \
      -v "$PWD/mask-rules.yaml:/config/mask-rules.yaml:ro" \
      -v "$PWD/policy-diff:/output" \
      ghcr.io/boundarylogic/privaci-commercial:1.0.1 \
      privaci preview --config /config/mask-rules.yaml \
        --policy-diff /output/policy-diff.json
- name: Upload policy diff
  if: always()
  uses: actions/upload-artifact@v4
  with:
    name: policy-diff
    path: policy-diff/policy-diff.json
```

Policy diff fields:

| Field | Meaning |
| --- | --- |
| `strict_autodetect` | Whether strict mode was enabled in config |
| `strict_passed` | `false` when `uncovered_strict` is non-empty under strict mode |
| `uncovered_strict` | Columns that require an explicit YAML rule or `passthrough` |

### SARIF for CI platforms (26.3)

```bash
privaci preview --config mask-rules.yaml \
  --sarif /tmp/privaci.sarif.json
```

### Sample preview (26.1)

```bash
privaci preview --config mask-rules.yaml --sample 5
```

Emits redacted before/after cell previews (never raw PII).

### Commercial extensions

When using `commercial-extensions.yaml`, preview validates config and fails
with a clear message if subsetting/JSONB rules are present but engine hooks
are unavailable:

```bash
privaci preview --config mask-rules.yaml \
  --commercial-extensions commercial-extensions.yaml
```

### Link preview to compliance report (26.4)

Run preview in CI, persist the policy diff, then pass it when rendering the signed
report:

```bash
privaci preview --config mask-rules.yaml --policy-diff /tmp/policy-diff.json
export PRIVACI_POLICY_DIFF_ARTIFACT=/tmp/policy-diff.json
privaci report --run-id …
```

Uncovered high/medium auto-detect columns and preview warnings appear under
`summary.attention_required.policy_diff_findings` and `preview_warnings` in the
signed JSON and Markdown summary.

---

## Related

- [Signed reports](signed-reports.md) — policy diff → `attention_required`
- [Compliance evidence mapping](compliance-evidence-mapping.md)
- Public [CLI — preview](https://docs.boundarylogic.io/cli-reference/)
