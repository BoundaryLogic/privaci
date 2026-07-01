# JSONB structural masking

**Audience:** Developers masking nested JSON documents without corrupting structure.

**Status:** Config schema ships in v1; transform pipeline integration requires
public engine **v1.0.1+** and the commercial container image.

---

## Problem

Regex over serialized JSON breaks structure. Whole-column `fake` replaces valid
JSON with opaque strings.

## Config (`commercial-extensions.yaml`)

```yaml
version: "1.0"
json_mask:
  - column: public.events.payload
    paths:
      - path: $.user.email
        action: fake
        provider: email
      - path: $.user.phone
        action: hash
      - path: $.internal.debug
        action: remove
```

| Field / action | Effect |
| --- | --- |
| `fake` | Deterministic fake value at path |
| `fake` + `seed_alias` | Same fake as a scalar column sharing that alias (see below) |
| `hash` | Salted hash |
| `null` | Set JSON null |
| `remove` | Delete key from object |

### `seed_alias` for scalar ↔ JSON alignment

Scalar fakes in `mask-rules.yaml` and JSON path fakes hash with different
default paths (`public.users.email` vs `public.audit_events.payload:$.actor.email`),
so the same real email can mask to two different values. Set a shared
`seed_alias` on both rules when audit payloads copy identifiers from table
columns:

```yaml
# mask-rules.yaml
tables:
  - name: public.users
    columns:
      - name: email
        action: fake
        provider: email
        seed_alias: user_email

# commercial-extensions.yaml
json_mask:
  - column: public.audit_events.payload
    paths:
      - path: $.actor.email
        action: fake
        provider: email
        seed_alias: user_email
```

See the public engine [seed_alias docs](https://docs.boundarylogic.io/configuration/#seed_alias-for-foreign-keys)
for the scalar-column pattern.

**Alignment limits:**

- **Same normalized value required.** Seeding is value-based (NFC-normalized,
  case-preserving). `Jane@Acme.com` in a column and `jane@acme.com` in JSON
  produce different fakes even with the same `seed_alias`.
- **Scalar `is_unique` breaks alignment.** JSON path fakes do not apply
  uniqueness suffixing. If the scalar email column is on a UNIQUE constraint with
  `is_unique` enabled, the scalar fake may diverge from the JSON path fake after
  the base seed step. Prefer joining on stable IDs in JSON (`actor.user_id`) when
  uniqueness suffixing is in play.

## Related

- [Configuration](https://docs.boundarylogic.io/configuration/) — column-level actions
- [Subsetting](subsetting.md)
