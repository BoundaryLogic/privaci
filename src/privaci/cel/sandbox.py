"""Compile and evaluate sandboxed CEL ``when:`` expressions."""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass
from typing import Any, cast

import celpy
from celpy import celtypes
from celpy.evaluation import CELEvalError

from privaci.cel.ast_policy import assert_expression_policy
from privaci.cel.pg_types import wrap_cel_value
from privaci.errors import ConfigError, MaskingError

logger = logging.getLogger(__name__)

MAX_EXPRESSION_LENGTH = 512
# Cooperative post-eval budget — celpy cannot hard-preempt a stuck evaluate.
EVAL_MAX_ELAPSED_SECONDS = 0.005
# Back-compat alias for callers/tests that still import the old name.
EVAL_DEADLINE_SECONDS = EVAL_MAX_ELAPSED_SECONDS

_REMEDIATION = (
    "Fix the when: expression or column types; see "
    "docs/configuration.md#conditional-masking-when."
)


@dataclass(frozen=True, slots=True)
class CompiledWhen:
    """A compiled CEL program bound to catalog column annotations.

    Attributes:
        source: Original expression text.
        expression_hash: SHA-256 hex of ``source`` (audit payloads).
        column_path: ``tables.<t>.columns.<c>.when`` for errors.
        annotations: Column name → celpy type used at compile time.
        program: celpy runner ready for per-row evaluation.
    """

    source: str
    expression_hash: str
    column_path: str
    annotations: dict[str, type]
    program: Any

    def __repr__(self) -> str:
        return (
            f"CompiledWhen(path={self.column_path!r}, "
            f"hash={self.expression_hash[:12]}…)"
        )


def expression_hash(source: str) -> str:
    """Return a stable hex digest of the CEL source (no row values)."""
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def compile_when(
    source: str,
    *,
    column_path: str,
    annotations: dict[str, type] | None = None,
) -> CompiledWhen:
    """Compile a CEL expression with optional catalog type annotations.

    Args:
        source: CEL source from ``when:``.
        column_path: YAML path for error attribution.
        annotations: Column→celpy type map; empty for syntax-only compile.

    Raises:
        ConfigError: On empty/oversized/invalid/disallowed CEL (exit 3).
    """
    text = _require_expression_text(source, column_path=column_path)
    env = celpy.Environment(annotations=cast(Any, annotations or {}))
    try:
        ast = env.compile(text)
        program = env.program(ast)
    except ConfigError:
        raise
    except Exception as exc:
        raise ConfigError(
            f"Compiling {column_path}",
            cause=f"Invalid CEL: {exc}",
            remediation=_REMEDIATION,
        ) from None
    assert_expression_policy(ast, column_path=column_path)
    return CompiledWhen(
        source=text,
        expression_hash=expression_hash(text),
        column_path=column_path,
        annotations=dict(annotations or {}),
        program=program,
    )


def evaluate_when(
    compiled: CompiledWhen,
    row: dict[str, Any],
) -> bool:
    """Evaluate a compiled ``when`` against one row.

    Raises:
        MaskingError: On elapsed budget, CEL runtime error, or non-bool result.
    """
    activation = {
        name: wrap_cel_value(row.get(name), annotation)
        for name, annotation in compiled.annotations.items()
    }
    started = time.perf_counter()
    result = _run_program(compiled, activation)
    _assert_eval_budget(compiled, started)
    if not isinstance(result, celtypes.BoolType) and not isinstance(result, bool):
        raise MaskingError(
            f"Evaluating {compiled.column_path}",
            cause="when: must evaluate to a boolean.",
            remediation="Rewrite the expression to return true or false.",
        )
    return bool(result)


def _require_expression_text(source: str, *, column_path: str) -> str:
    text = source.strip()
    if not text:
        raise ConfigError(
            f"Validating {column_path}",
            cause="when: must be a non-empty CEL expression.",
            remediation="Provide a boolean CEL expression or remove when:.",
        )
    if len(text) > MAX_EXPRESSION_LENGTH:
        raise ConfigError(
            f"Validating {column_path}",
            cause=(
                f"when: exceeds {MAX_EXPRESSION_LENGTH} characters "
                f"({len(text)} given)."
            ),
            remediation=(
                "Shorten the expression; see "
                "docs/configuration.md#conditional-masking-when."
            ),
        )
    return text


def _run_program(compiled: CompiledWhen, activation: dict[str, Any]) -> Any:
    """Evaluate without chaining celpy exceptions (may embed row values)."""
    try:
        return compiled.program.evaluate(activation)
    except CELEvalError:
        logger.debug("CEL eval error at %s", compiled.column_path)
        raise MaskingError(
            f"Evaluating {compiled.column_path}",
            cause="CEL evaluation failed for a row (details omitted).",
            remediation=_REMEDIATION,
        ) from None
    except Exception as exc:
        logger.debug(
            "CEL eval error at %s: %s", compiled.column_path, type(exc).__name__
        )
        raise MaskingError(
            f"Evaluating {compiled.column_path}",
            cause="CEL evaluation failed for a row (details omitted).",
            remediation=_REMEDIATION,
        ) from None


def _assert_eval_budget(compiled: CompiledWhen, started: float) -> None:
    elapsed = time.perf_counter() - started
    if elapsed <= EVAL_MAX_ELAPSED_SECONDS:
        return
    raise MaskingError(
        f"Evaluating {compiled.column_path}",
        cause=(
            f"CEL evaluation exceeded {EVAL_MAX_ELAPSED_SECONDS * 1000:.0f} ms "
            "elapsed budget."
        ),
        remediation="Simplify the when: expression and retry.",
    )
