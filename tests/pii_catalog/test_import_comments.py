"""Unit tests for PII catalog models and comment import heuristics."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from privaci.pii_catalog import (
    PiiCatalog,
    catalog_from_comment_rows,
    render_catalog_yaml,
    sensitivity_from_comment,
)


@pytest.mark.parametrize(
    ("comment", "expected"),
    [
        ("PII: login email", "pii_direct"),
        ("pii_direct: ssn", "pii_direct"),
        ("indirect: soft id", "pii_indirect"),
        ("internal: ops only", "internal"),
        ("public: display name", "public"),
        ("something else", "pii_indirect"),
    ],
)
def test_sensitivity_heuristics(comment: str, expected: str) -> None:
    # Arrange / Act / Assert
    assert sensitivity_from_comment(comment) == expected


def test_catalog_from_comments_groups_tables() -> None:
    # Arrange
    rows = [
        ("public", "users", "email", "PII: login"),
        ("public", "users", "id", "internal: pk"),
        ("public", "orders", "note", "misc"),
    ]

    # Act
    catalog = catalog_from_comment_rows(rows)

    # Assert
    assert catalog.version == "1.0"
    assert [entry.table for entry in catalog.catalog] == [
        "public.orders",
        "public.users",
    ]
    users = catalog.catalog[1]
    assert users.columns[0].sensitivity == "pii_direct"
    assert users.columns[0].source == "pg_comment"
    yaml_text = render_catalog_yaml(catalog)
    assert "secret-value" not in yaml_text
    assert "PII: login" in yaml_text


def test_empty_comments_yield_empty_catalog() -> None:
    # Arrange / Act
    catalog = catalog_from_comment_rows([])

    # Assert
    assert catalog.catalog == []
    assert "catalog: []" in render_catalog_yaml(catalog)


def test_unknown_sensitivity_rejected() -> None:
    # Arrange / Act / Assert
    with pytest.raises(ValidationError):
        PiiCatalog.model_validate(
            {
                "version": "1.0",
                "catalog": [
                    {
                        "table": "public.users",
                        "columns": [
                            {"name": "email", "sensitivity": "confidential"},
                        ],
                    }
                ],
            }
        )
