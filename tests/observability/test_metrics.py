"""Tests for the optional Prometheus metrics endpoint."""

from __future__ import annotations

import builtins
from collections.abc import Callable

import pytest
from pytest_mock import MockerFixture

from privaci.errors import ConfigError
from privaci.observability.metrics import start_metrics_server


def test_start_metrics_server_raises_when_client_missing(
    mocker: MockerFixture,
) -> None:
    # Arrange: simulate prometheus_client not being importable.
    real_import: Callable[..., object] = builtins.__import__

    def _fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "prometheus_client":
            raise ImportError("no module named prometheus_client")
        return real_import(name, *args, **kwargs)

    mocker.patch.object(builtins, "__import__", side_effect=_fake_import)

    # Act / Assert
    with pytest.raises(ConfigError, match="prometheus-client"):
        start_metrics_server(9100)
