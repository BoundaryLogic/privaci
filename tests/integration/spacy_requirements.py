"""SpaCy NER stack requirements for integration tests and capability prep."""

from __future__ import annotations

SPACY_MODEL_NAME = "en_core_web_sm"

SPACY_NER_REMEDIATION = (
    "Install the NLP extra and download the English model:\n"
    "  pip install -e '.[nlp]'\n"
    f"  python -m spacy download {SPACY_MODEL_NAME}"
)


def spacy_ner_blocker() -> str | None:
    """Return a value-free reason when L2 NER is unavailable, else ``None``."""
    try:
        import spacy  # noqa: F401
    except ImportError:
        return "SpaCy is not installed (required for ner_mask / demo-corp L2 columns)."
    try:
        from privaci.mask.ner import _load_model
    except ImportError:
        return "PrivaCI NER module could not be imported."
    if _load_model() is None:
        return f"SpaCy model {SPACY_MODEL_NAME!r} is not installed."
    return None


def require_spacy_ner() -> None:
    """Fail fast when the L2 NER stack is not ready."""
    reason = spacy_ner_blocker()
    if reason is not None:
        msg = f"{reason}\n{SPACY_NER_REMEDIATION}"
        raise RuntimeError(msg)


def spacy_ner_available() -> bool:
    """Return whether ``require_spacy_ner()`` would succeed."""
    return spacy_ner_blocker() is None
