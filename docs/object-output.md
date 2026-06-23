# Object output URIs

Compliance artifacts (`privaci report --output`, `dry-run --report`, and
`preview` artifact flags when a preview plugin is registered) accept local paths
and object URIs.

## Supported destinations

| Form | Community fallback | With `object_writer` plugin |
|------|-------------------|----------------------------|
| `./report.json`, `/tmp/out.md` | Yes | Yes |
| `file:///tmp/out.json` | Yes | Yes |
| `s3://bucket/prefix/report.json` | No (register plugin) | Yes |
| `azure-blob://account/container/blob` | No | Not yet |

Cloud uploads use the `object_writer` plugin (`privaci.plugins`). Register an
S3-capable writer via your plugin package entry point (see below).

## Examples

Local report:

```bash
privaci report --run "$RUN_ID" --format json --output ./evidence/report.json
```

S3 evidence path (ECS task role or `AWS_*` env vars):

```bash
privaci report --run "$RUN_ID" --output "s3://compliance-evidence/privaci/${RUN_ID}/report.json"
```

Dry-run detection report:

```bash
privaci dry-run --report "s3://compliance-evidence/privaci/preflight/detection.md"
```

Optional query params on `s3://` URIs:

- `?region=us-east-1` — bucket region
- `?endpoint_url=http://localhost:9000` — MinIO (contributor testing only)

## Custom plugin

Register your own writer for MinIO or Azure:

```toml
[project.entry-points."privaci.plugins"]
object_writer = "my_package.storage:MyObjectWriter"
```

Implement `privaci.contracts.ObjectWriter`.

## Related

- [CLI reference](cli-reference.md)
- [extending-privaci.md](extending-privaci.md)
