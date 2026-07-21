"""Fail-closed SpaCy prerequisite probes for ner_mask."""

from __future__ import annotations

import sys
import types

import pytest

import privaci.mask.ner as ner_module
from privaci.errors import MaskingError
from tests.fixtures.constants import TEST_SALT


@pytest.fixture
def _reset_model() -> object:
    """Clear SpaCy probe/load caches around each test."""
    ner_module._reset_model_cache_for_tests()
    yield
    ner_module._reset_model_cache_for_tests()


def test_ner_raises_when_model_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    _reset_model: object,
) -> None:
    # Arrange
    text = "Alice met Bob in Paris."
    monkeypatch.setattr(ner_module, "_load_model", lambda: None)

    # Act / Assert
    with pytest.raises(MaskingError, match="NER on public.notes.body"):
        ner_module.mask_entities_in_text(
            text,
            salt=TEST_SALT,
            column_path="public.notes.body",
        )


def test_spacy_available_false_when_probe_fails(
    monkeypatch: pytest.MonkeyPatch,
    _reset_model: object,
) -> None:
    # Arrange
    monkeypatch.setattr(ner_module, "_probe_spacy_package", lambda: False)

    # Act / Assert
    assert ner_module.spacy_available() is False
    assert ner_module.spacy_available() is False  # cached


def test_spacy_available_true_when_package_present(
    monkeypatch: pytest.MonkeyPatch,
    _reset_model: object,
) -> None:
    # Arrange — cheap probe only; does not load the model.
    monkeypatch.setattr(ner_module, "_probe_spacy_package", lambda: True)

    # Act / Assert
    assert ner_module.spacy_available() is True
    assert ner_module._MODEL is None


def test_spacy_available_false_when_load_failed(
    monkeypatch: pytest.MonkeyPatch,
    _reset_model: object,
) -> None:
    # Arrange
    def _raise_oserror(_name: str) -> object:
        raise OSError("model missing")

    fake_spacy = types.ModuleType("spacy")
    fake_spacy.load = _raise_oserror  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "spacy", fake_spacy)

    # Act
    assert ner_module._load_model() is None

    # Assert — probe inherits negative cache
    assert ner_module.spacy_available() is False
