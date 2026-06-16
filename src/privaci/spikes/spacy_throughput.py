"""SpaCy throughput spike for Level-2 masking feasibility."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

logger = logging.getLogger(__name__)

TARGET_ROWS_PER_SEC = 1_000
_DEFAULT_NOTE_PATH = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "fixtures"
    / "spikes"
    / "freeform_notes.txt"
)


@dataclass(frozen=True, slots=True)
class SpacySpikeResult:
    """Throughput metrics for SpaCy NER on representative notes."""

    row_count: int
    elapsed_seconds: float
    rows_per_second: float
    batch_size: int
    model_name: str

    @property
    def passed(self) -> bool:
        """True when throughput meets the Week-1 target (≥1k rows/sec)."""
        return self.rows_per_second >= TARGET_ROWS_PER_SEC


def run_spacy_throughput_spike(
    *,
    row_count: int = 2_000,
    batch_size: int = 64,
    note_path: Path | None = None,
) -> SpacySpikeResult:
    """Measure ``en_core_web_sm`` throughput on freeform clinical-style text.

    Args:
        row_count: Number of documents to process (replicated from fixtures).
        batch_size: ``nlp.pipe`` batch size.
        note_path: Optional path to representative notes; defaults to fixture file.

    Returns:
        Timing metrics for ``docs/spikes/2.2-spacy-throughput.md``.

    Raises:
        RuntimeError: If the SpaCy model is not installed locally.
    """
    texts = _load_texts(note_path or _DEFAULT_NOTE_PATH, row_count)
    nlp = _load_model()
    started = perf_counter()
    _run_pipe(nlp, texts, batch_size)
    elapsed = perf_counter() - started
    rows_per_second = row_count / elapsed if elapsed > 0 else 0.0
    result = SpacySpikeResult(
        row_count=row_count,
        elapsed_seconds=elapsed,
        rows_per_second=rows_per_second,
        batch_size=batch_size,
        model_name="en_core_web_sm",
    )
    logger.info("SpaCy spike finished", extra={"rows_per_second": rows_per_second})
    return result


def _load_texts(path: Path, row_count: int) -> list[str]:
    if not path.is_file():
        msg = f"Fixture notes not found: {path}"
        raise FileNotFoundError(msg)
    paragraphs = [
        line.strip() for line in path.read_text(encoding="utf-8").split("\n\n")
    ]
    paragraphs = [p for p in paragraphs if p]
    if not paragraphs:
        msg = f"No paragraphs in fixture file: {path}"
        raise ValueError(msg)
    return [paragraphs[i % len(paragraphs)] for i in range(row_count)]


def _load_model() -> object:
    try:
        import spacy
    except ImportError as exc:
        msg = "SpaCy is not installed; pip install -e '.[nlp]'"
        raise RuntimeError(msg) from exc
    try:
        return spacy.load("en_core_web_sm")
    except OSError as exc:
        msg = (
            "Model en_core_web_sm missing; run: python -m spacy download en_core_web_sm"
        )
        raise RuntimeError(msg) from exc


def _run_pipe(nlp: object, texts: list[str], batch_size: int) -> None:
    # Spike assumes a loaded spaCy Language; typed as object to avoid hard dep.
    list(nlp.pipe(texts, batch_size=batch_size))  # type: ignore[attr-defined]
