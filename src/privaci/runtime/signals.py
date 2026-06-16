"""POSIX signal handling for graceful run interruption.

Registers SIGINT/SIGTERM handlers that set a process-wide flag checked between
streaming batches. The flag is reset when a run starts and cleared when it ends.
"""

from __future__ import annotations

import logging
import signal
import threading
from collections.abc import Callable
from types import FrameType

logger = logging.getLogger(__name__)

_interrupt = threading.Event()
_Handler = Callable[[int, FrameType | None], object]
_previous_handlers: dict[int, _Handler | signal.Handlers | int | None] = {}


def request_interrupt() -> None:
    """Mark the current run as interrupted (idempotent)."""
    _interrupt.set()


def interrupt_requested() -> bool:
    """Return whether an interrupt signal has been received."""
    return _interrupt.is_set()


def clear_interrupt() -> None:
    """Clear the interrupt flag before starting a new run."""
    _interrupt.clear()


def install_handlers() -> None:
    """Install SIGINT/SIGTERM handlers for the current process."""
    for signum in (signal.SIGINT, signal.SIGTERM):
        previous = signal.getsignal(signum)
        _previous_handlers[signum] = previous
        signal.signal(signum, _handle_signal)


def restore_handlers() -> None:
    """Restore handlers installed by :func:`install_handlers`."""
    for signum, previous in _previous_handlers.items():
        signal.signal(signum, previous)
    _previous_handlers.clear()


def _handle_signal(signum: int, _frame: object | None) -> None:
    name = "SIGINT" if signum == signal.SIGINT else "SIGTERM"
    logger.warning("Received %s; finishing current batch then stopping", name)
    request_interrupt()
