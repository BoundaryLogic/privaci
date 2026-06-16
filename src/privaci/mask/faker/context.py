"""Request context for one deterministic fake invocation."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class FakeRequest:
    """Inputs for a single fake-value generation.

    Attributes:
        salt: The anonymization salt (never logged).
        column_path: ``schema.table.column`` path used for hashing.
        value: The original cell value.
        provider: Registered provider name (e.g. ``email``).
        seed_alias: Optional alternate path for FK consistency
            (e.g. ``users.email`` for an FK column).
        is_unique: When true, apply collision-resistant suffixing.
        params: Provider-specific string parameters from config.
    """

    salt: str
    column_path: str
    value: str
    provider: str
    seed_alias: str | None = None
    is_unique: bool = False
    params: dict[str, str] = field(default_factory=dict)

    @property
    def hash_path(self) -> str:
        """Return the column path used for seed computation."""
        return self.seed_alias or self.column_path
