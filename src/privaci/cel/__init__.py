"""CEL sandbox for optional column ``when:`` guards."""

from __future__ import annotations

from privaci.cel.binding import annotations_for_when
from privaci.cel.pg_types import (
    CelBindingError,
    cel_annotation_for_pg_type,
    wrap_cel_value,
)
from privaci.cel.sandbox import (
    EVAL_DEADLINE_SECONDS,
    EVAL_MAX_ELAPSED_SECONDS,
    MAX_EXPRESSION_LENGTH,
    CompiledWhen,
    compile_when,
    evaluate_when,
    expression_hash,
)

__all__ = [
    "EVAL_DEADLINE_SECONDS",
    "EVAL_MAX_ELAPSED_SECONDS",
    "MAX_EXPRESSION_LENGTH",
    "CelBindingError",
    "CompiledWhen",
    "annotations_for_when",
    "cel_annotation_for_pg_type",
    "compile_when",
    "evaluate_when",
    "expression_hash",
    "wrap_cel_value",
]
