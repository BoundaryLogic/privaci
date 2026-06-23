# storage

URI-based writers for CLI compliance artifacts (`report --output`,
`dry-run --report`, commercial preview outputs).

## Public API

| Symbol | Role |
|--------|------|
| `write_object` | Write bytes via `load_plugins().object_writer` |
| `parse_object_uri` | Parse destination URIs |
| `redact_object_uri` | Safe URI string for logs |

Cloud schemes (`s3://`, `azure-blob://`) require a `privaci.plugins`
`object_writer` entry point (commercial package or custom plugin).

## Example

```python
from privaci.storage import write_object

write_object("./report.json", b'{"ok": true}', content_type="application/json")
```
