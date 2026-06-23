## 1. Public contracts & storage

- [x] 1.1 Add `ObjectWriter` ABC to `privaci.contracts.base`
- [x] 1.2 Add `CommunityObjectWriter` fallback and wire `PluginBundle.object_writer`
- [x] 1.3 Implement `storage/parser.py` and `storage/backends/file.py`
- [x] 1.4 Implement `storage/writer.py` (`write_object`, `redact_object_uri`)

## 2. Public CLI integration

- [x] 2.1 Wire `report --output` through `write_object`
- [x] 2.2 Wire `dry-run --report` through `write_object`
- [x] 2.3 Pass URI strings from `_preview.py` to commercial preview

## 3. Commercial layer

- [x] 3.1 Implement `CommercialObjectWriter` (S3) in `privaci-commercial`
- [x] 3.2 Register `object_writer` entry point; wire `preview.py`

## 4. Tests & docs

- [x] 4.1 Public tests: parser, community writer, plugin dispatch, CLI regression
- [x] 4.2 Commercial tests: S3 write with mocked boto3
- [x] 4.3 Docs + CHANGELOG (both repos); update `extending-privaci.md`
