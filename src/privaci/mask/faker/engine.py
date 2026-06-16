"""Orchestrate seed computation, provider dispatch, and uniqueness suffixing."""

from __future__ import annotations

from privaci.errors import MaskingError
from privaci.mask.faker.context import FakeRequest
from privaci.mask.faker.hash import compute_seed, normalize_input
from privaci.mask.faker.registry import get_provider
from privaci.mask.faker.uniqueness import apply_uniqueness


def generate_fake(request: FakeRequest) -> str:
    """Generate one deterministic fake value for a cell.

    Args:
        request: Salt, column path, value, provider, and uniqueness flags.

    Returns:
        The fake replacement string. Empty inputs return unchanged.

    Raises:
        MaskingError: When the provider name is not registered.
    """
    normalized = normalize_input(request.value)
    if not normalized:
        return normalized

    seed = compute_seed(request.salt, request.hash_path, normalized)
    try:
        provider = get_provider(request.provider)
    except KeyError as exc:
        raise MaskingError(
            f"Generating fake for {request.column_path}",
            cause=f"Unknown provider {request.provider!r}.",
            remediation="Register the provider or fix mask-rules.yaml.",
        ) from exc

    base = provider.generate(seed, normalized, params=request.params)
    if request.is_unique:
        return apply_uniqueness(base, seed, provider=request.provider)
    return base
