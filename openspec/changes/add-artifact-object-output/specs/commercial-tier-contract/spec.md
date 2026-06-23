## ADDED Requirements

### Requirement: ObjectWriter contract

The public engine SHALL expose an `ObjectWriter` ABC with
`write(uri: str, data: bytes, *, content_type: str | None = None) -> None`.
The commercial package SHALL register `object_writer` under
`privaci.plugins`. Community mode SHALL ship `CommunityObjectWriter` (local
paths only).

#### Scenario: Contract importable in community mode

- **WHEN** only the public engine is installed
- **THEN** `from privaci.contracts import ObjectWriter` SHALL succeed and
  `load_plugins().object_writer` SHALL be a `CommunityObjectWriter`.

#### Scenario: Commercial replaces writer

- **WHEN** the commercial wheel is installed
- **THEN** `load_plugins().object_writer` SHALL support `s3://` URIs for all
  valid commercial license tiers.
