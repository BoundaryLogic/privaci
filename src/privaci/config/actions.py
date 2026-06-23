"""Column-action models for mask-rules.yaml.

Each masking action is a strict pydantic model carrying a ``action`` literal
discriminator. The public :data:`ColumnAction` discriminated union lets the
config loader surface a clear, path-attributed error when an unknown or
misspelled action is supplied. See ``docs/configuration.md#actions``.
"""

from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from privaci.mask.regex_safe import reject_redos_prone_pattern

DEFAULT_NER_ENTITIES: tuple[str, ...] = ("PERSON", "ORG", "GPE", "LOC")

_ALLOWED_REGEX_FLAGS: frozenset[str] = frozenset(
    {
        "ASCII",
        "DEBUG",
        "DOTALL",
        "IGNORECASE",
        "LOCALE",
        "MULTILINE",
        "TEMPLATE",
        "UNICODE",
        "VERBOSE",
    }
)

# Action tags used both as discriminator values and to strip pydantic's
# injected union-tag segments from error paths in the loader.
ACTION_TAGS: frozenset[str] = frozenset(
    {
        "fake",
        "regex_mask",
        "hash",
        "hmac_hash",
        "pseudonym",
        "passthrough",
        "null",
        "static",
        "ner_mask",
        "ai_refine",
    }
)


class _ActionBase(BaseModel):
    """Base for all column actions; forbids unknown keys."""

    model_config = ConfigDict(extra="forbid")


class FakeAction(_ActionBase):
    """Replace the value with a deterministic synthetic from ``provider``.

    Attributes:
        provider: Name of the registered fake provider (e.g. ``first_name``).
        seed_alias: Optional shared seed key so two columns (e.g. an FK and its
            referenced column) fake to the same value across tables.
        params: Optional provider-specific string parameters.
    """

    action: Literal["fake"]
    provider: str
    seed_alias: str | None = None
    params: dict[str, str] = Field(default_factory=dict)


class RegexMaskAction(_ActionBase):
    """Substitute matches of ``pattern`` with ``replace``.

    Attributes:
        pattern: A Python-compatible regular expression. Validated at parse
            time; a non-compilable pattern fails config validation (exit 3).
        replace: The replacement string.
        flags: Optional list of regex flag names (e.g. ``IGNORECASE``).
    """

    action: Literal["regex_mask"]
    pattern: str
    replace: str
    flags: list[str] = Field(default_factory=list)

    @field_validator("pattern")
    @classmethod
    def _pattern_must_compile(cls, value: str) -> str:
        """Reject patterns that the ``re`` module cannot compile."""
        try:
            re.compile(value)
        except re.error as exc:
            raise ValueError(f"invalid regex: {exc}") from exc
        return reject_redos_prone_pattern(value)

    @field_validator("flags")
    @classmethod
    def _flags_must_be_known(cls, value: list[str]) -> list[str]:
        """Reject regex flag names that are not valid ``re`` compile flags."""
        for flag in value:
            normalized = flag.upper()
            if normalized not in _ALLOWED_REGEX_FLAGS:
                raise ValueError(f"unknown regex flag: {flag}")
        return value


class HashAction(_ActionBase):
    """Replace the value with a salted, deterministic hash."""

    action: Literal["hash"]


class HmacHashAction(_ActionBase):
    """Replace the value with an HMAC-SHA256 digest using ``pseudonym_key``.

    Attributes:
        encoding: ``hex`` (default) or ``base64url`` output form.
    """

    action: Literal["hmac_hash"]
    encoding: Literal["hex", "base64url"] = "hex"


class PseudonymAction(_ActionBase):
    """Keyed deterministic fake using the same providers as ``fake``.

    Attributes:
        provider: Registered fake provider name (e.g. ``email``).
        seed_alias: Optional shared seed path for FK consistency.
        params: Optional provider-specific string parameters.
    """

    action: Literal["pseudonym"]
    provider: str
    seed_alias: str | None = None
    params: dict[str, str] = Field(default_factory=dict)


class PassthroughAction(_ActionBase):
    """Copy the value unchanged into the target."""

    action: Literal["passthrough"]


class NullAction(_ActionBase):
    """Write SQL ``NULL``; rejected during pre-flight on ``NOT NULL`` columns."""

    action: Literal["null"]


class StaticAction(_ActionBase):
    """Replace every value with a single constant ``value``."""

    action: Literal["static"]
    value: str


class NerMaskAction(_ActionBase):
    """Mask named entities found by the Level-2 SpaCy NER model.

    Attributes:
        entities: Entity labels to mask. Defaults to ``PERSON``, ``ORG``,
            ``GPE``, ``LOC``.
    """

    action: Literal["ner_mask"]
    entities: list[str] = Field(default_factory=lambda: list(DEFAULT_NER_ENTITIES))


class AiRefineAction(_ActionBase):
    """Level-3 LLM refinement; requires the commercial layer.

    Attributes:
        provider: LLM backend identifier (e.g. ``aws_bedrock``).
        model: Provider model identifier.
        params: Optional provider-specific string parameters.
    """

    action: Literal["ai_refine"]
    provider: str
    model: str
    params: dict[str, str] = Field(default_factory=dict)


ColumnAction = Annotated[
    FakeAction
    | RegexMaskAction
    | HashAction
    | HmacHashAction
    | PseudonymAction
    | PassthroughAction
    | NullAction
    | StaticAction
    | NerMaskAction
    | AiRefineAction,
    Field(discriminator="action"),
]
