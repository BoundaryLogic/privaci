"""Likelihood-ranked schema_mode combination matrix for capability tests.

Cells are explicit operator-relevant combinations — not a full cartesian product.
See docs/test-fixtures.md#schema-modes-matrix.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

RepoKind = Literal["public", "commercial"]
MatrixRank = Literal["P0", "P1", "P2", "P3"]


@dataclass(frozen=True, slots=True)
class MatrixCell:
    """One ranked schema-mode / capability combination."""

    id: str
    rank: MatrixRank
    repo: RepoKind
    label: str
    axes: dict[str, str]
    capability_ids: tuple[str, ...]
    triage_note: str


MATRIX_CELLS: tuple[MatrixCell, ...] = (
    MatrixCell(
        id="replicate-default",
        rank="P0",
        repo="public",
        label="Greenfield replicate defaults",
        axes={"schema_mode": "replicate", "on_existing_data": "fail"},
        capability_ids=(
            "public-run",
            "public-schema-modes-replicate-integration",
        ),
        triage_note="Default Demo Corp path",
    ),
    MatrixCell(
        id="assume-truncate-auto",
        rank="P0",
        repo="public",
        label="DBA staging assume_existing + truncate",
        axes={
            "schema_mode": "assume_existing",
            "on_existing_data": "truncate",
            "passthrough_copy": "auto",
        },
        capability_ids=("public-schema-modes-assume-existing-integration",),
        triage_note="Primary staging happy path",
    ),
    MatrixCell(
        id="jsonb-x-replicate",
        rank="P0",
        repo="commercial",
        label="JSONB path masking under replicate",
        axes={"schema_mode": "replicate"},
        capability_ids=("commercial-jsonb-postgres",),
        triage_note="Baseline commercial JSONB load",
    ),
    MatrixCell(
        id="subset-jsonb-x-replicate",
        rank="P0",
        repo="commercial",
        label="Subset + JSONB under replicate",
        axes={"schema_mode": "replicate"},
        capability_ids=("commercial-subsetting",),
        triage_note="Combined commercial fixture path",
    ),
    MatrixCell(
        id="assume-fail-empty",
        rank="P1",
        repo="public",
        label="assume_existing + fail with empty prebuilt tables",
        axes={
            "schema_mode": "assume_existing",
            "on_existing_data": "fail",
        },
        capability_ids=("public-schema-modes-matrix",),
        triage_note="Documented empty+fail allow path",
    ),
    MatrixCell(
        id="elevated-unresolved-fail",
        rank="P1",
        repo="public",
        label="Unresolved elevated objects fail preflight",
        axes={"schema_mode": "replicate", "elevated": "unresolved"},
        capability_ids=("public-schema-modes-matrix",),
        triage_note="Deny-by-default elevated gate",
    ),
    MatrixCell(
        id="elevated-replicate-one",
        rank="P1",
        repo="public",
        label="Explicit elevated replicate disposition",
        axes={"schema_mode": "replicate", "elevated": "replicate"},
        capability_ids=("public-schema-modes-matrix",),
        triage_note="Allow elevated view onto target",
    ),
    MatrixCell(
        id="replicate-views-functions-off",
        rank="P1",
        repo="public",
        label="Rollback flags disable view/function DDL",
        axes={
            "schema_mode": "replicate",
            "replicate_views": "false",
            "replicate_functions": "false",
        },
        capability_ids=("public-schema-modes-matrix",),
        triage_note="Documented near-current behaviour rollback",
    ),
    MatrixCell(
        id="jsonb-x-assume",
        rank="P1",
        repo="commercial",
        label="JSONB masking under assume_existing",
        axes={
            "schema_mode": "assume_existing",
            "on_existing_data": "truncate",
        },
        capability_ids=("commercial-schema-modes-matrix",),
        triage_note="Staging + JSONB — high likelihood",
    ),
    MatrixCell(
        id="subset-x-assume",
        rank="P1",
        repo="commercial",
        label="Subsetting under assume_existing",
        axes={
            "schema_mode": "assume_existing",
            "on_existing_data": "truncate",
        },
        capability_ids=("commercial-schema-modes-matrix",),
        triage_note="Staging + subset — high likelihood",
    ),
    MatrixCell(
        id="subset-jsonb-x-assume",
        rank="P2",
        repo="commercial",
        label="Subset + JSONB under assume_existing",
        axes={
            "schema_mode": "assume_existing",
            "on_existing_data": "truncate",
        },
        capability_ids=("commercial-schema-modes-matrix",),
        triage_note="Common paid staging combo",
    ),
    MatrixCell(
        id="roundtrip-x-assume",
        rank="P2",
        repo="commercial",
        label="Licensed run → report → drift under assume",
        axes={
            "schema_mode": "assume_existing",
            "on_existing_data": "truncate",
        },
        capability_ids=("commercial-schema-modes-matrix",),
        triage_note="Compliance wrap after staging load",
    ),
    MatrixCell(
        id="keyed-x-replicate",
        rank="P2",
        repo="public",
        label="hmac_hash / pseudonym on a real load",
        axes={"schema_mode": "replicate"},
        capability_ids=("public-schema-modes-matrix",),
        triage_note="Keyed actions during mask pass",
    ),
    MatrixCell(
        id="passthrough-batch",
        rank="P2",
        repo="public",
        label="passthrough_copy: batch succeeds",
        axes={"schema_mode": "replicate", "passthrough_copy": "batch"},
        capability_ids=("public-schema-modes-matrix",),
        triage_note="Force named COPY path",
    ),
    MatrixCell(
        id="passthrough-require-binary-fail",
        rank="P2",
        repo="public",
        label="require_binary refuses ineligible target",
        axes={
            "schema_mode": "assume_existing",
            "passthrough_copy": "require_binary",
        },
        capability_ids=("public-schema-modes-matrix",),
        triage_note="Strict binary gate failure",
    ),
    MatrixCell(
        id="partitions-x-assume",
        rank="P2",
        repo="public",
        label="Partitioned tables under assume_existing",
        axes={
            "schema_mode": "assume_existing",
            "on_existing_data": "truncate",
        },
        capability_ids=("public-schema-modes-matrix",),
        triage_note="Partitioned staging reload",
    ),
    MatrixCell(
        id="streaming-x-assume",
        rank="P2",
        repo="public",
        label="Streaming/passthrough under assume_existing",
        axes={
            "schema_mode": "assume_existing",
            "on_existing_data": "truncate",
        },
        capability_ids=("public-schema-modes-matrix",),
        triage_note="Prebuilt target + load path",
    ),
    MatrixCell(
        id="resume-x-replicate-objects-on",
        rank="P3",
        repo="public",
        label="Resume with view/function replication enabled",
        axes={"schema_mode": "replicate", "replicate_views": "true"},
        capability_ids=("public-resume",),
        triage_note="Deferred — elevated dispositions in resume YAML",
    ),
    MatrixCell(
        id="determinism-x-assume",
        rank="P3",
        repo="public",
        label="Determinism under assume_existing",
        axes={"schema_mode": "assume_existing"},
        capability_ids=("public-determinism",),
        triage_note="Stretch",
    ),
    MatrixCell(
        id="autodetect-x-assume",
        rank="P3",
        repo="public",
        label="Autodetect under assume_existing",
        axes={"schema_mode": "assume_existing"},
        capability_ids=("public-autodetect",),
        triage_note="Stretch",
    ),
)


def cells_for_rank(*ranks: MatrixRank) -> tuple[MatrixCell, ...]:
    """Return matrix cells matching one or more ranks."""
    wanted = frozenset(ranks)
    return tuple(cell for cell in MATRIX_CELLS if cell.rank in wanted)


def cell_by_id(cell_id: str) -> MatrixCell:
    """Return one matrix cell by id.

    Raises:
        KeyError: When ``cell_id`` is unknown.
    """
    for cell in MATRIX_CELLS:
        if cell.id == cell_id:
            return cell
    raise KeyError(cell_id)
