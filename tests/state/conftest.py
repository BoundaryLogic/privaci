"""Fixtures for state unit tests (mocked asyncpg connections)."""

from __future__ import annotations

from types import TracebackType
from unittest.mock import AsyncMock, MagicMock

import pytest


class _FakeTransaction:
    """Async context manager standing in for ``asyncpg`` transactions."""

    async def __aenter__(self) -> None:
        return None

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        return False


@pytest.fixture
def fake_conn() -> AsyncMock:
    """Return an AsyncMock connection with a working transaction CM."""
    conn = AsyncMock()
    conn.transaction = MagicMock(return_value=_FakeTransaction())
    conn.execute = AsyncMock(return_value="UPDATE 1")
    return conn
