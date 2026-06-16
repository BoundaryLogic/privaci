"""Abstract base for deterministic fake providers."""

from __future__ import annotations

import abc


class FakeProvider(abc.ABC):
    """Generate a deterministic fake value from a salted seed.

    Implementations MUST be pure: no I/O, no wall-clock randomness, no logging
    of raw PII. The engine supplies a 16-byte seed derived from
    ``sha256(salt || column_path || normalized_input)``.

    Attributes:
        name: Registry key referenced by ``provider`` in mask-rules.yaml.
    """

    name: str

    @abc.abstractmethod
    def generate(self, seed: bytes, value: str, *, params: dict[str, str]) -> str:
        """Return a fake replacement for ``value``.

        Args:
            seed: 16-byte deterministic seed for this column and input.
            value: The normalized original value (may inform format hints).
            params: Optional provider-specific string parameters from config.

        Returns:
            A synthetic value that must not resemble production PII.
        """
