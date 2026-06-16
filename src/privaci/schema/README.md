# schema

Target DDL replication: schemas, tables, indexes, sequences, extensions, and
table strategies (`exclude`, `empty`, `truncate`).

## Public API

| Symbol | Role |
|--------|------|
| `replicate.replicate_schema` | Create target objects from catalog snapshot |
| `strategies.apply_table_strategy` | Handle exclude/empty/truncate before streaming |
| `sequences.sync_sequences` | Advance identity/serial sequences after load |

## Configuration

Per-table `strategy` and global `replicate_all_indexes` in `mask-rules.yaml`.

## Example

Schema replication runs automatically during `privaci run` after preflight
succeeds. Inspect planned tables with `privaci dry-run`.
