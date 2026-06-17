"""Tests for row-filter SQL composition in source batch fetching."""

from __future__ import annotations

from privaci.stream.fetch import compose_where


def test_compose_where_empty() -> None:
    assert compose_where(None, None) == ""


def test_compose_where_single_filter() -> None:
    assert compose_where("id = 1") == " WHERE (id = 1)"


def test_compose_where_pk_and_filter() -> None:
    clause = compose_where("org_id = 1", '"id" > $1')
    assert clause == ' WHERE (org_id = 1) AND ("id" > $1)'
