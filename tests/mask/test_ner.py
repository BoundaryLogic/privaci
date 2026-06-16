"""Tests for optional SpaCy NER masking."""

from __future__ import annotations

import sys
import types
from dataclasses import dataclass

import pytest

import privaci.mask.ner as ner_module
from privaci.errors import MaskingError
from tests.fixtures.constants import TEST_SALT


@dataclass
class _FakeEnt:
    """Stand-in for a SpaCy entity span."""

    label_: str
    text: str
    start_char: int
    end_char: int


class _FakeDoc:
    """Stand-in for a SpaCy document exposing ``ents``."""

    def __init__(self, ents: list[_FakeEnt]) -> None:
        self._ents = ents

    @property
    def ents(self) -> list[_FakeEnt]:
        return self._ents


def test_ner_passthrough_when_model_unavailable() -> None:
    # Arrange
    text = "Alice met Bob in Paris."

    # Act
    result = ner_module.mask_entities_in_text(
        text,
        salt=TEST_SALT,
        column_path="public.notes.body",
    )

    # Assert — without SpaCy installed, text is unchanged.
    assert result == text


def test_ner_empty_string_unchanged() -> None:
    # Act / Assert
    assert (
        ner_module.mask_entities_in_text(
            "", salt=TEST_SALT, column_path="public.notes.body"
        )
        == ""
    )


@pytest.fixture
def _reset_model() -> object:
    """Restore the module-level model cache after a test mutates it."""
    original = ner_module._MODEL
    yield
    ner_module._MODEL = original


def test_ner_replaces_known_entities_and_keeps_unknown(
    _reset_model: object,
) -> None:
    # Arrange — text: "Alice visited Acme on Tuesday."
    text = "Alice visited Acme on Tuesday."
    ents = [
        _FakeEnt("PERSON", "Alice", 0, 5),
        _FakeEnt("ORG", "Acme", 14, 18),
        _FakeEnt("DATE", "Tuesday", 22, 29),  # unmapped label is left intact
    ]
    ner_module._MODEL = lambda _text: _FakeDoc(ents)

    # Act
    result = ner_module.mask_entities_in_text(
        text, salt=TEST_SALT, column_path="public.notes.body"
    )

    # Assert — known entities are replaced; the original names do not survive.
    assert "Alice" not in result
    assert "Acme" not in result
    assert "Tuesday" in result  # DATE is not in the provider map
    assert result.endswith("on Tuesday.")


def test_ner_is_deterministic(_reset_model: object) -> None:
    # Arrange
    ents = [_FakeEnt("PERSON", "Alice", 0, 5)]
    ner_module._MODEL = lambda _text: _FakeDoc(ents)

    # Act
    first = ner_module.mask_entities_in_text(
        "Alice.", salt=TEST_SALT, column_path="p.t.c"
    )
    second = ner_module.mask_entities_in_text(
        "Alice.", salt=TEST_SALT, column_path="p.t.c"
    )

    # Assert
    assert first == second


def test_ner_wraps_model_failure(_reset_model: object) -> None:
    # Arrange — a model that raises mid-parse.
    def _boom(_text: str) -> object:
        raise RuntimeError("model exploded")

    ner_module._MODEL = _boom

    # Act / Assert
    with pytest.raises(MaskingError, match="NER on public.notes.body"):
        ner_module.mask_entities_in_text(
            "Alice.", salt=TEST_SALT, column_path="public.notes.body"
        )


def test_load_model_returns_cached_instance(_reset_model: object) -> None:
    # Arrange
    sentinel = lambda _text: _FakeDoc([])  # noqa: E731
    ner_module._MODEL = sentinel

    # Act
    loaded = ner_module._load_model()

    # Assert
    assert loaded is sentinel


def test_load_model_returns_none_without_spacy(
    monkeypatch: pytest.MonkeyPatch, _reset_model: object
) -> None:
    # Arrange — make `import spacy` fail regardless of install state.
    ner_module._MODEL = None
    monkeypatch.setitem(sys.modules, "spacy", None)

    # Act / Assert
    assert ner_module._load_model() is None


def test_load_model_loads_and_caches(
    monkeypatch: pytest.MonkeyPatch, _reset_model: object
) -> None:
    # Arrange — inject a fake spacy whose load() returns a pipeline.
    pipeline = lambda _text: _FakeDoc([])  # noqa: E731
    fake_spacy = types.ModuleType("spacy")
    fake_spacy.load = lambda _name: pipeline  # type: ignore[attr-defined]
    ner_module._MODEL = None
    monkeypatch.setitem(sys.modules, "spacy", fake_spacy)

    # Act
    loaded = ner_module._load_model()

    # Assert
    assert loaded is pipeline


def test_load_model_returns_none_when_model_missing(
    monkeypatch: pytest.MonkeyPatch, _reset_model: object
) -> None:
    # Arrange — spacy imports, but the model is not downloaded (OSError).
    def _raise_oserror(_name: str) -> object:
        raise OSError("model en_core_web_sm not found")

    fake_spacy = types.ModuleType("spacy")
    fake_spacy.load = _raise_oserror  # type: ignore[attr-defined]
    ner_module._MODEL = None
    monkeypatch.setitem(sys.modules, "spacy", fake_spacy)

    # Act / Assert
    assert ner_module._load_model() is None
