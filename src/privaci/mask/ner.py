"""Level-2 SpaCy NER masking with deterministic entity replacement."""

from __future__ import annotations

import importlib.util
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

_SPACY_MODEL_NAME = "en_core_web_sm"


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
_LOAD_FAILED: bool = False
_PROBE_RESULT: bool | None = None


def spacy_available() -> bool:
    """Return whether SpaCy and ``en_core_web_sm`` appear installable.

    Cheap probe for config/preflight (import + package meta). Full model load
    is deferred to the first ``mask_entities_in_text`` call. Fail-closed: a
    positive probe that later fails to load still raises at runtime.
    """
    global _PROBE_RESULT
    if _PROBE_RESULT is not None:
        return _PROBE_RESULT
    if _LOAD_FAILED:
        result = False
    elif _MODEL is not None:
        result = True
    else:
        result = _probe_spacy_package()
    _PROBE_RESULT = result
    return result


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


def _probe_spacy_package() -> bool:
    """Return True when the SpaCy package and model meta are present."""
    if importlib.util.find_spec("spacy") is None:
        return False
    try:
        from spacy.util import is_package
    except ImportError:
        return False
    return bool(is_package(_SPACY_MODEL_NAME))


def _load_model() -> _SpacyLanguage | None:
    """Lazy-load ``en_core_web_sm`` when the optional NLP extra is installed."""
    global _MODEL, _LOAD_FAILED, _PROBE_RESULT
    if _LOAD_FAILED:
        return None
    if _MODEL is not None:
        return _MODEL
    try:
        import spacy

        _MODEL = cast(_SpacyLanguage, spacy.load(_SPACY_MODEL_NAME))
    except (ImportError, OSError):
        _LOAD_FAILED = True
        _PROBE_RESULT = False
        return None
    _PROBE_RESULT = True
    return _MODEL


def _reset_model_cache_for_tests() -> None:
    """Clear module caches (test-only)."""
    global _MODEL, _LOAD_FAILED, _PROBE_RESULT
    _MODEL = None
    _LOAD_FAILED = False
    _PROBE_RESULT = None
