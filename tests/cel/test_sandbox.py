"""Unit tests for the CEL ``when:`` sandbox."""

from __future__ import annotations

import traceback

import pytest
from celpy import celtypes
from celpy.evaluation import CELEvalError

from privaci.cel.binding import annotations_for_when
from privaci.cel.pg_types import cel_annotation_for_pg_type, wrap_cel_value
from privaci.cel.sandbox import (
    EVAL_MAX_ELAPSED_SECONDS,
    compile_when,
    evaluate_when,
    expression_hash,
)
from privaci.errors import ConfigError, MaskingError

_SENTINEL_EMAIL = "john.doe@acme.example"


def test_compile_and_evaluate_true_false() -> None:
    # Arrange
    annotations = {
        "status": celtypes.StringType,
        "archived": celtypes.BoolType,
    }
    compiled = compile_when(
        "status == 'closed' && !archived",
        column_path="tables.t.columns.c.when",
        annotations=annotations,
    )

    # Act / Assert
    assert evaluate_when(compiled, {"status": "closed", "archived": False})
    assert not evaluate_when(compiled, {"status": "open", "archived": False})


def test_expression_hash_stable() -> None:
    # Arrange / Act / Assert
    assert expression_hash("a == 1") == expression_hash("a == 1")
    assert expression_hash("a == 1") != expression_hash("a == 2")


def test_oversized_expression_rejected() -> None:
    # Arrange
    huge = "true && " * 200 + "true"

    # Act / Assert
    with pytest.raises(ConfigError, match="exceeds"):
        compile_when(huge, column_path="tables.t.columns.c.when")


def test_invalid_cel_rejected() -> None:
    # Arrange / Act / Assert
    with pytest.raises(ConfigError, match="Invalid CEL"):
        compile_when("status ==", column_path="tables.t.columns.c.when")


def test_non_bool_result_fails() -> None:
    # Arrange
    compiled = compile_when(
        "status",
        column_path="tables.t.columns.c.when",
        annotations={"status": celtypes.StringType},
    )

    # Act / Assert
    with pytest.raises(MaskingError, match="boolean"):
        evaluate_when(compiled, {"status": "closed"})


def test_unsupported_pg_type() -> None:
    # Arrange / Act / Assert
    with pytest.raises(ConfigError, match="not supported"):
        cel_annotation_for_pg_type("jsonb", column_path="t.c")


def test_wrap_null_and_timestamp() -> None:
    # Arrange / Act / Assert
    assert wrap_cel_value(None, celtypes.StringType) is None
    wrapped = wrap_cel_value("x", celtypes.StringType)
    assert isinstance(wrapped, celtypes.StringType)


def test_matches_builtin_rejected() -> None:
    # Arrange / Act / Assert
    with pytest.raises(ConfigError, match="disallowed"):
        compile_when(
            "status.matches('a.*')",
            column_path="tables.t.columns.c.when",
            annotations={"status": celtypes.StringType},
        )


def test_map_builtin_rejected() -> None:
    # Arrange / Act / Assert
    with pytest.raises(ConfigError, match="disallowed"):
        compile_when(
            "[1, 2].map(x, x + 1)",
            column_path="tables.t.columns.c.when",
        )


def test_contains_method_allowed() -> None:
    # Arrange
    compiled = compile_when(
        "status.contains('ose')",
        column_path="tables.t.columns.c.when",
        annotations={"status": celtypes.StringType},
    )

    # Act / Assert
    assert evaluate_when(compiled, {"status": "closed"})


def test_eval_budget_exceeded(mocker: pytest.Mock) -> None:
    # Arrange
    compiled = compile_when(
        "true",
        column_path="tables.t.columns.c.when",
    )
    mocker.patch(
        "privaci.cel.sandbox.time.perf_counter",
        side_effect=[0.0, EVAL_MAX_ELAPSED_SECONDS + 0.001],
    )

    # Act / Assert
    with pytest.raises(MaskingError, match="exceeded"):
        evaluate_when(compiled, {})


def test_celeval_error_does_not_chain_row_pii(mocker: pytest.Mock) -> None:
    # Arrange
    compiled = compile_when(
        "status == 'x'",
        column_path="tables.t.columns.c.when",
        annotations={"status": celtypes.StringType},
    )
    mocker.patch.object(
        compiled.program,
        "evaluate",
        side_effect=CELEvalError(f"StringType({_SENTINEL_EMAIL!r}) overload failed"),
    )

    # Act
    with pytest.raises(MaskingError) as raised:
        evaluate_when(compiled, {"status": _SENTINEL_EMAIL})

    # Assert
    err = raised.value
    assert err.__cause__ is None
    assert _SENTINEL_EMAIL not in "".join(traceback.format_exception(err))


def test_annotations_ignore_string_literal_column_name() -> None:
    # Arrange — jsonb column name appears only inside a string literal
    column_types = {
        "status": "text",
        "payload": "jsonb",
    }

    # Act
    annotations = annotations_for_when(
        "status == 'has payload inside'",
        column_path="tables.t.columns.c.when",
        column_types=column_types,
    )

    # Assert
    assert set(annotations) == {"status"}


def test_annotations_reject_unknown_column() -> None:
    # Arrange / Act / Assert
    with pytest.raises(ConfigError, match="unknown column"):
        annotations_for_when(
            "missing == 1",
            column_path="tables.t.columns.c.when",
            column_types={"status": "text"},
        )


def test_annotations_reject_unsupported_referenced_type() -> None:
    # Arrange / Act / Assert
    with pytest.raises(ConfigError, match="unsupported"):
        annotations_for_when(
            "payload != null",
            column_path="tables.t.columns.c.when",
            column_types={"payload": "jsonb", "notes": "text"},
        )
