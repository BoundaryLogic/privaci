"""Tests for the centralized CLI error boundary."""

from __future__ import annotations

import click
import pytest

from privaci.cli._errors import run_cli
from privaci.errors import (
    ConfigError,
    LicenseError,
    PreflightError,
    PrivaCIError,
    RunInterruptedError,
)


def _raise(exc: BaseException) -> object:
    raise exc


def test_success_returns_zero() -> None:
    # Act
    code = run_cli(lambda: None)

    # Assert
    assert code == 0


def test_passthrough_integer_result() -> None:
    # Act — Click non-standalone returns the Exit code as an int
    code = run_cli(lambda: 1)

    # Assert
    assert code == 1


@pytest.mark.parametrize(
    ("error", "expected_code"),
    [
        (ConfigError("bad config"), 3),
        (PreflightError("target not empty"), 2),
        (LicenseError("bad license"), 5),
        (RunInterruptedError("stopped", cause="SIGINT"), 130),
        (PrivaCIError("boom"), 1),
    ],
)
def test_privaci_error_maps_to_exit_code(
    error: PrivaCIError,
    expected_code: int,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Act
    code = run_cli(lambda: _raise(error))
    captured = capsys.readouterr()

    # Assert
    assert code == expected_code
    assert str(error) in captured.err


def test_structured_error_renders_remediation(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Arrange
    error = ConfigError(
        "Loading mask-rules.yaml",
        cause="Unknown action 'shuffle'",
        remediation="Use a supported action.",
    )

    # Act
    code = run_cli(lambda: _raise(error))
    captured = capsys.readouterr()

    # Assert
    assert code == 3
    assert "Context:" in captured.err
    assert "Cause:" in captured.err
    assert "Remediation:" in captured.err
    assert "docs/error-codes.md#exit-code-3" in captured.err


def test_keyboard_interrupt_maps_to_130(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Act
    code = run_cli(lambda: _raise(KeyboardInterrupt()))
    captured = capsys.readouterr()

    # Assert
    assert code == 130
    assert "exit-code-130" in captured.err


def test_usage_error_maps_to_one(capsys: pytest.CaptureFixture[str]) -> None:
    # Act
    code = run_cli(lambda: _raise(click.exceptions.UsageError("no such command")))

    # Assert
    assert code == 1


def test_unexpected_exception_maps_to_generic_one(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Act
    code = run_cli(lambda: _raise(RuntimeError("kaboom")))
    captured = capsys.readouterr()

    # Assert
    assert code == 1
    assert "exit-code-1-generic-error" in captured.err
    assert "kaboom" not in captured.err
