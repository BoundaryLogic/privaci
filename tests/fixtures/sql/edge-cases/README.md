# Edge-case SQL fixtures

Small, isolated schemas for failure-mode tests. Each file is loaded only by
the tests that need it — they are **not** part of the Demo Corp dataset.

See `docs/test-fixtures.md` §2 ("Edge-case fixtures") for the failure mode
each file exercises.

| File | Failure mode |
|------|----------------|
| `non-deferrable-cycle.sql` | FK cycle with `NOT DEFERRABLE` constraints |
| `no-primary-key.sql` | Table without a primary key |
| `unsupported-types.sql` | Custom domain column (text-mode COPY fallback) |
| `permission-denied.sql` | `fixture_ro` role without schema `CREATE` |
| `dangling-fk-exclude.sql` | Excluded parent referenced by NOT NULL child FK |
| `composite-pk-only.sql` | Composite PK only, no single-column key |
| `adversarial-types.sql` | Deep FK chain + exotic types (4-byte UTF-8, large jsonb, max numeric, arrays, bytea, inet) |
