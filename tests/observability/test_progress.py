"""Tests for the table.progress throttle."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from privaci.observability.progress import ProgressThrottle


@pytest.fixture
def clock() -> MagicMock:
    """A controllable monotonic clock starting at t=0."""
    fake = MagicMock()
    fake.return_value = 0.0
    return fake


def test_first_emit_is_throttled_until_interval(
    clock: MagicMock, mocker: MockerFixture
) -> None:
    # Arrange
    emit = mocker.patch("privaci.observability.progress.emit")
    throttle = ProgressThrottle(
        "public", "users", estimated_rows=100, interval_seconds=2.0, clock=clock
    )

    # Act
    clock.return_value = 1.0
    emitted = throttle.maybe_emit(50)

    # Assert
    assert emitted is False
    emit.assert_not_called()


def test_emit_after_interval_elapses(clock: MagicMock, mocker: MockerFixture) -> None:
    # Arrange
    emit = mocker.patch("privaci.observability.progress.emit")
    throttle = ProgressThrottle(
        "public", "users", estimated_rows=100, interval_seconds=2.0, clock=clock
    )

    # Act
    clock.return_value = 2.5
    emitted = throttle.maybe_emit(50)

    # Assert
    assert emitted is True
    emit.assert_called_once()
    _, kwargs = emit.call_args
    assert kwargs["rows_processed"] == 50
    assert kwargs["percent_complete"] == 50.0


def test_percent_complete_is_none_without_estimate(
    clock: MagicMock, mocker: MockerFixture
) -> None:
    # Arrange
    emit = mocker.patch("privaci.observability.progress.emit")
    throttle = ProgressThrottle(
        "public", "users", estimated_rows=None, interval_seconds=1.0, clock=clock
    )

    # Act
    clock.return_value = 2.0
    throttle.maybe_emit(10)

    # Assert
    _, kwargs = emit.call_args
    assert kwargs["percent_complete"] is None


def test_percent_complete_caps_at_100(clock: MagicMock, mocker: MockerFixture) -> None:
    # Arrange
    emit = mocker.patch("privaci.observability.progress.emit")
    throttle = ProgressThrottle(
        "public", "users", estimated_rows=10, interval_seconds=1.0, clock=clock
    )

    # Act
    clock.return_value = 2.0
    throttle.maybe_emit(50)

    # Assert
    _, kwargs = emit.call_args
    assert kwargs["percent_complete"] == 100.0
