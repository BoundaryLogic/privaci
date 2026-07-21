"""Level-2 SpaCy NER masking with deterministic entity replacement."""

from __future__ import annotations

from typing import Protocol, cast

from privaci.errors import MaskingError
from privaci.mask.faker import FakeRequest, generate_fake

_ENTITY_PROVIDER: dict[str, str] = {
    "PERSON": "full_name",
    "ORG": "company",
    "GPE": "city",
    "LOC": "city",
}

NER_MASK_REMEDIATION = (
    "Install the NLP extra (`pip install 'privaci[nlp]'`) and download "
    "en_core_web_sm, or change the column action away from ner_mask. "
    "See docs/configuration.md#actions."
)


class _SpacyEntity(Protocol):
    """Minimal SpaCy entity surface used by NER masking."""

    label_: str
    text: str
    start_char: int
    end_char: int


class _SpacyDoc(Protocol):
    """Minimal SpaCy document surface used by NER masking."""

    @property
    def ents(self) -> list[_SpacyEntity]:
        pass


class _SpacyLanguage(Protocol):
    """Callable SpaCy language pipeline."""

    def __call__(self, text: str) -> _SpacyDoc:
        pass


_MODEL: _SpacyLanguage | None = None


def spacy_available() -> bool:
    """Return whether SpaCy and ``en_core_web_sm`` can be loaded.

    Used by config/preflight gates so ``ner_mask`` never silently passthroughs.
    """
    return _load_model() is not None


def mask_entities_in_text(text: str, *, salt: str, column_path: str) -> str:
    """Replace named entities in ``text`` with deterministic fakes.

    Empty strings are returned unchanged. When SpaCy is unavailable, raises
    rather than returning source text (fail-closed for privacy).

    Raises:
        MaskingError: When SpaCy is unavailable, or when it fails to process
            the text.
    """
    if not text:
        return text
    nlp = _load_model()
    if nlp is None:
        raise MaskingError(
            f"Running NER on {column_path}",
            cause=("SpaCy or model en_core_web_sm is not available for ner_mask."),
            remediation=NER_MASK_REMEDIATION,
        )
    try:
        doc = nlp(text)
    except Exception as exc:
        raise MaskingError(
            f"Running NER on {column_path}",
            cause="The SpaCy model failed to process the text.",
            remediation="Verify en_core_web_sm is installed.",
        ) from exc
    return _replace_entities(text, doc, salt=salt, column_path=column_path)


def _replace_entities(
    text: str,
    doc: _SpacyDoc,
    *,
    salt: str,
    column_path: str,
) -> str:
    parts: list[str] = []
    cursor = 0
    for ent in doc.ents:
        if ent.label_ not in _ENTITY_PROVIDER:
            continue
        parts.append(text[cursor : ent.start_char])
        provider = _ENTITY_PROVIDER[ent.label_]
        fake = generate_fake(
            FakeRequest(
                salt=salt,
                column_path=f"{column_path}#ner:{ent.label_}",
                value=ent.text,
                provider=provider,
            )
        )
        parts.append(fake)
        cursor = ent.end_char
    parts.append(text[cursor:])
    return "".join(parts)


def _load_model() -> _SpacyLanguage | None:
    """Lazy-load ``en_core_web_sm`` when the optional NLP extra is installed."""
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    try:
        import spacy
    except ImportError:
        return None
    try:
        _MODEL = cast(_SpacyLanguage, spacy.load("en_core_web_sm"))
    except OSError:
        return None
    return _MODEL
