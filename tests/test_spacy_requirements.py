"""Unit tests for SpaCy NER requirement helpers."""

from __future__ import annotations

import pytest

from tests.integration import spacy_requirements as mod


def test_spacy_ner_blocker_reports_missing_package(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mod, "SPACY_MODEL_NAME", "en_core_web_sm")
    monkeypatch.setitem(__import__("sys").modules, "spacy", None)

    reason = mod.spacy_ner_blocker()

    assert reason is not None
    assert "SpaCy is not installed" in reason


def test_require_spacy_ner_raises_with_remediation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mod, "spacy_ner_blocker", lambda: "model missing")

    with pytest.raises(RuntimeError, match="model missing"):
        mod.require_spacy_ner()
