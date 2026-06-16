# MedicalHelpDesk Corp fixtures

Deterministic synthetic Postgres data for PrivaCI integration tests. See
[`docs/test-fixtures.md`](../../../docs/test-fixtures.md) for the full spec.

## Generate SQL

```bash
# Mini tier (committed for CI — all tables, small row counts)
python -m tests.fixtures.demo_corp.generate --tier mini \
    --out tests/fixtures/sql/demo-corp

# Full demo tier (large; not committed)
python -m tests.fixtures.demo_corp.generate --tier demo \
    --out /tmp/demo-corp-full
```

## Load into Postgres

```bash
SOURCE_DB_URL=postgresql://postgres:dev@127.0.0.1:55432/privaci_source \
    python -m scripts.load_sample_data
```
