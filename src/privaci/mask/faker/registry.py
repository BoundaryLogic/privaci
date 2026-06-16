"""Provider registry and extension API."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from privaci.errors import ConfigError
from privaci.mask.faker.base import FakeProvider
from privaci.mask.faker.providers import builtin_providers

if TYPE_CHECKING:
    from privaci.config.models import Config

logger = logging.getLogger(__name__)

_REGISTRY: dict[str, FakeProvider] = {}


def _bootstrap() -> None:
    """Load built-in providers when the registry is first accessed."""
    if _REGISTRY:
        return
    for provider in builtin_providers():
        _REGISTRY[provider.name] = provider


def register_provider(provider: FakeProvider) -> None:
    """Register a custom or replacement provider by ``provider.name``.

    Args:
        provider: A :class:`FakeProvider` implementation. Must be deterministic.

    Raises:
        ValueError: When ``provider.name`` is empty.
    """
    if not provider.name:
        msg = "provider.name must be non-empty"
        raise ValueError(msg)
    _bootstrap()
    _REGISTRY[provider.name] = provider
    logger.debug("Registered fake provider", extra={"provider": provider.name})


def get_provider(name: str) -> FakeProvider:
    """Return a registered provider by name.

    Raises:
        KeyError: When the name is not registered.
    """
    _bootstrap()
    return _REGISTRY[name]


def known_providers() -> frozenset[str]:
    """Return the set of registered provider names."""
    _bootstrap()
    return frozenset(_REGISTRY)


def validate_fake_providers(config: Config) -> None:
    """Reject config that references unknown ``fake`` providers (exit 3).

    Args:
        config: A validated :class:`~privaci.config.models.Config`.

    Raises:
        ConfigError: When any ``fake`` action names an unregistered provider.
    """
    known = known_providers()
    missing: list[str] = []
    for table_id, table in config.tables.items():
        for column, action in table.columns.items():
            if action.action != "fake":
                continue
            if action.provider not in known:
                missing.append(f"{table_id}.{column} -> {action.provider}")
    if not missing:
        return
    raise ConfigError(
        "Validating fake provider names",
        cause="Unknown provider(s): " + "; ".join(sorted(missing)),
        remediation=("Use a built-in provider; see docs/configuration.md#actions."),
    )
