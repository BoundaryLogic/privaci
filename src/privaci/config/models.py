"""Top-level mask-rules.yaml models.

Defines the :class:`Config` root document and per-table :class:`TableConfig`.
Both forbid unknown keys so typos surface as path-attributed validation errors
rather than being silently ignored. See ``docs/configuration.md``.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    WithJsonSchema,
    field_validator,
    model_validator,
)

from privaci.config.actions import ColumnAction
from privaci.secrets.types import SecretStr

DEFAULT_BATCH_SIZE = 10_000

OnExistingData = Literal["fail", "truncate", "drop_create", "append"]
TableStrategy = Literal["transform", "exclude", "empty", "truncate"]

# ``SecretStr`` is a plain dataclass, so without this override pydantic emits the
# salt field as a ``{"_value": ...}`` object in the published JSON schema. The
# accepted input is a plain string (the before-validator wraps it), so present it
# as a nullable string and keep the secret type out of ``$defs``.
GlobalSalt = Annotated[
    SecretStr | None,
    WithJsonSchema(
        {"anyOf": [{"type": "string"}, {"type": "null"}], "title": "Global Salt"}
    ),
]

PseudonymKey = Annotated[
    SecretStr | None,
    WithJsonSchema(
        {
            "anyOf": [{"type": "string"}, {"type": "null"}],
            "title": "Pseudonym Key",
        }
    ),
]


class TableConfig(BaseModel):
    """Per-table masking configuration.

    Attributes:
        strategy: How the table is handled in the target. ``transform``
            (default) masks and copies rows; ``exclude`` drops the table;
            ``empty`` recreates it with no rows; ``truncate`` empties an
            existing target table before copy.
        columns: Mapping of column name to its masking action.
        batch_size: Optional per-table override of the global batch size.
        null_orphan_fks: When true, FK columns that lose their referent are
            set to NULL instead of failing the load.
    """

    model_config = ConfigDict(extra="forbid")

    strategy: TableStrategy = "transform"
    columns: dict[str, ColumnAction] = Field(default_factory=dict)
    batch_size: int | None = None
    null_orphan_fks: bool = False

    @field_validator("batch_size")
    @classmethod
    def _batch_size_positive(cls, value: int | None) -> int | None:
        """Reject non-positive per-table batch sizes."""
        if value is not None and value < 1:
            raise ValueError("batch_size must be >= 1")
        return value


class Config(BaseModel):
    """Root mask-rules.yaml document.

    Attributes:
        version: Config schema version. The MVP engine accepts ``"1.0"`` only.
        global_salt: Optional salt literal or secret URI; resolved at run time
            by the secrets resolver. Never logged.
        pseudonym_key: Optional HMAC key for ``hmac_hash`` and ``pseudonym``
            actions (Growth+ tier). Distinct from ``global_salt``.
        on_existing_data: Target-table collision policy. ``append`` is rejected
            in the MVP.
        strict_autodetect: Fail the run when auto-detect finds uncovered PII.
        replicate_all_indexes: Replicate every source index, not just unique
            and primary-key indexes.
        batch_size: Default streaming batch size in rows.
        audit_log: Write the per-run audit log to ``_privaci.audit_log``.
        auto_detect: Run the zero-config PII column scanner.
        implied_fk_ignore: Source column paths (``schema.table.column``) whose
            implied (soft) foreign-key warnings should be silenced.
        tables: Mapping of table identifier to its configuration.
    """

    model_config = ConfigDict(extra="forbid")

    version: str
    global_salt: GlobalSalt = None
    pseudonym_key: PseudonymKey = None
    on_existing_data: OnExistingData = "fail"
    strict_autodetect: bool = False
    replicate_all_indexes: bool = False
    batch_size: int = DEFAULT_BATCH_SIZE
    audit_log: bool = True
    auto_detect: bool = True
    implied_fk_ignore: list[str] = Field(default_factory=list)
    tables: dict[str, TableConfig] = Field(default_factory=dict)

    @field_validator("global_salt", mode="before")
    @classmethod
    def _wrap_global_salt(cls, value: str | SecretStr | None) -> SecretStr | None:
        """Wrap plaintext salt literals from YAML in :class:`SecretStr`."""
        return _wrap_secret_literal(value)

    @field_validator("pseudonym_key", mode="before")
    @classmethod
    def _wrap_pseudonym_key(cls, value: str | SecretStr | None) -> SecretStr | None:
        """Wrap plaintext pseudonym key literals from YAML in :class:`SecretStr`."""
        return _wrap_secret_literal(value)

    @field_validator("batch_size")
    @classmethod
    def _batch_size_positive(cls, value: int) -> int:
        """Reject non-positive global batch sizes."""
        if value < 1:
            raise ValueError("batch_size must be >= 1")
        return value

    @model_validator(mode="after")
    def _reject_append_in_mvp(self) -> Config:
        """Reject the unsupported ``append`` strategy in the MVP."""
        if self.on_existing_data == "append":
            raise ValueError(
                "append strategy is not supported in this version. "
                "Use truncate or drop_create."
            )
        return self


def _wrap_secret_literal(value: str | SecretStr | None) -> SecretStr | None:
    """Wrap a YAML secret literal in :class:`SecretStr` when non-empty."""
    if value is None:
        return None
    if isinstance(value, SecretStr):
        return value
    text = str(value).strip()
    if not text:
        return None
    return SecretStr(text)
