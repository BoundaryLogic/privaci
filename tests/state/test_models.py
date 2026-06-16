"""Unit tests for state enums and records."""

from __future__ import annotations

from privaci.state.models import (
    AuditLevel,
    CheckpointStatus,
    EventType,
    RunIdentity,
    RunStatus,
)


def test_run_status_values_match_ddl_check() -> None:
    # Assert
    assert {s.value for s in RunStatus} == {
        "in_progress",
        "succeeded",
        "failed",
        "interrupted",
    }


def test_checkpoint_status_values_match_ddl_check() -> None:
    # Assert
    assert {s.value for s in CheckpointStatus} == {
        "pending",
        "in_progress",
        "done",
        "failed",
    }


def test_audit_level_values_match_ddl_check() -> None:
    # Assert
    assert {level.value for level in AuditLevel} == {"info", "warning", "error"}


def test_event_type_includes_known_events() -> None:
    # Assert
    assert EventType.COLUMN_MASKED.value == "column.masked"
    assert EventType.CYCLE_BREAK.value == "cycle_break"


def test_run_identity_repr_redacts_full_hashes() -> None:
    # Arrange
    identity = RunIdentity(
        config_hash="c" * 64,
        salt_fingerprint="s" * 16,
        source_db_hash="d" * 64,
    )

    # Act
    text = repr(identity)

    # Assert
    assert "c" * 64 not in text
    assert "…" in text
