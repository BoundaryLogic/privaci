"""NLP stack checks for capability test prep."""

from __future__ import annotations

from tests.integration.spacy_requirements import (
    SPACY_MODEL_NAME,
    SPACY_NER_REMEDIATION,
    spacy_ner_blocker,
)


def check_spacy_ner() -> tuple[bool, str]:
    """Return ``(ready, detail)`` for capability prep logging."""
    reason = spacy_ner_blocker()
    if reason is None:
        return True, f"SpaCy NER ready ({SPACY_MODEL_NAME})."
    return False, f"{reason}\n{SPACY_NER_REMEDIATION}"


def require_spacy_ner_for_capabilities(*, capability_ids: tuple[str, ...]) -> None:
    """Raise when any selected capability requires L2 NER but SpaCy is missing."""
    if not capability_ids:
        return
    ready, detail = check_spacy_ner()
    if ready:
        return
    caps = ", ".join(capability_ids)
    msg = (
        f"Capability prep refused: L2 NER required for {caps} but stack is "
        f"incomplete.\n{detail}"
    )
    raise RuntimeError(msg)
