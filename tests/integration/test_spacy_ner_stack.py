"""Integration tests for the SpaCy NER stack used by demo-corp L2 masking."""

from __future__ import annotations

import pytest

from privaci.mask.ner import mask_entities_in_text
from tests.fixtures.constants import TEST_SALT
from tests.integration.spacy_requirements import require_spacy_ner

pytestmark = [pytest.mark.integration]


def test_spacy_model_is_installed() -> None:
    """L2 NER must be available — passthrough when SpaCy is missing is not allowed."""
    require_spacy_ner()


def test_ner_mask_replaces_detected_entities() -> None:
    """Smoke test that en_core_web_sm loads and mutates PERSON/ORG spans."""
    require_spacy_ner()

    original = "Patient John Smith works at Acme Health Systems."
    masked = mask_entities_in_text(
        original,
        salt=TEST_SALT,
        column_path="public.ticket_messages.body",
    )

    assert masked != original
    assert "John Smith" not in masked
    assert "Acme Health Systems" not in masked
