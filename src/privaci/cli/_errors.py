"""Centralized CLI error boundary.

Translates :class:`PrivaCIError` (and interrupts) into the
Context + Cause + Remediation output and the stable exit codes documented in
``docs/error-codes.md``. Keeping this in one place means individual commands
raise domain errors and never deal with exit codes or signal handling.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

import click
import typer

from privaci.errors import ERROR_DOCS_PATH, PrivaCIError

logger = logging.getLogger(__name__)

INTERRUPTED_EXIT_CODE = 130
USAGE_EXIT_CODE = 1


def emit_error(error: PrivaCIError) -> None:
    """Print a PrivaCIError to stderr in Context + Cause + Remediation form."""
    typer.echo(str(error), err=True)


def _emit_interrupt() -> None:
    message = (
        "Context: Running PrivaCI\n"
        "Cause: Interrupted by signal (SIGINT/SIGTERM).\n"
        "Remediation: Resume the run with `privaci resume`.\n"
        f"See: {ERROR_DOCS_PATH}#exit-code-130-interrupted-by-signal"
    )
    typer.echo(message, err=True)


def run_cli(entrypoint: Callable[[], object]) -> int:
    """Invoke a CLI entrypoint and map outcomes to stable exit codes."""
    try:
        result = entrypoint()
    except PrivaCIError as exc:
        return _handle_privaci_error(exc)
    except click.exceptions.UsageError as exc:
        return _handle_usage_error(exc)
    except click.exceptions.ClickException as exc:
        return _handle_click_exception(exc)
    except click.exceptions.Abort:
        return _handle_abort()
    except KeyboardInterrupt:
        return _handle_keyboard_interrupt()
    except Exception:
        return _handle_unexpected_error()
    return result if isinstance(result, int) else 0


def _handle_privaci_error(exc: PrivaCIError) -> int:
    emit_error(exc)
    return exc.exit_code


def _handle_usage_error(exc: click.exceptions.UsageError) -> int:
    exc.show()
    return USAGE_EXIT_CODE


def _handle_click_exception(exc: click.exceptions.ClickException) -> int:
    exc.show()
    return int(exc.exit_code)


def _handle_abort() -> int:
    typer.echo("Aborted.", err=True)
    return INTERRUPTED_EXIT_CODE


def _handle_keyboard_interrupt() -> int:
    _emit_interrupt()
    return INTERRUPTED_EXIT_CODE


def _handle_unexpected_error() -> int:
    logger.exception("Unexpected CLI failure")
    typer.echo(
        "Context: Running PrivaCI\n"
        "Cause: An unexpected internal error occurred.\n"
        "Remediation: Re-run with `--log-level debug` and file an issue.\n"
        f"See: {ERROR_DOCS_PATH}#exit-code-1-generic-error",
        err=True,
    )
    return 1
