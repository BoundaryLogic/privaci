"""Tests for run interrupt signal coordination."""

from __future__ import annotations

from privaci.runtime.signals import (
    clear_interrupt,
    interrupt_requested,
    request_interrupt,
)


def test_interrupt_flag_lifecycle() -> None:
    # Arrange
    clear_interrupt()

    # Assert
    assert not interrupt_requested()

    # Act
    request_interrupt()

    # Assert
    assert interrupt_requested()

    # Act
    clear_interrupt()

    # Assert
    assert not interrupt_requested()
