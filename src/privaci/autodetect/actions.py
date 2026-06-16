"""Map pattern rules to config column actions, respecting column types."""

from __future__ import annotations

from privaci.autodetect.patterns import PatternRule
from privaci.catalog.models import ColumnInfo
from privaci.config.actions import (
    ColumnAction,
    FakeAction,
    HashAction,
    NerMaskAction,
    StaticAction,
)

_TEXTLIKE = frozenset(
    {"text", "character varying", "character", "varchar", "char", "citext", "name"}
)

# Column base types each fake provider can produce a valid value for. Providers
# absent from this map are treated as text-only.
_PROVIDER_TYPES: dict[str, frozenset[str]] = {
    "dob": frozenset({"date"}) | _TEXTLIKE,
    "ip_address": frozenset({"inet", "cidr"}) | _TEXTLIKE,
    "uuid": frozenset({"uuid"}) | _TEXTLIKE,
}


def _base_type(data_type: str) -> str:
    head, _, _ = data_type.strip().lower().partition("(")
    return head.strip()


def action_for_column(rule: PatternRule, column: ColumnInfo) -> ColumnAction | None:
    """Build a type-compatible action for ``column``, or ``None`` to skip.

    Returns ``None`` when the matched rule's action cannot produce a value
    valid for the column's type (e.g. ``hash`` on a ``uuid`` column), so the
    scanner can leave the column as passthrough rather than emit a broken mask.
    """
    base = _base_type(column.data_type)
    if rule.action == "fake":
        return _fake_action(rule, base)
    if rule.action == "hash":
        return _hash_action(base)
    if rule.action == "static":
        if base not in _TEXTLIKE:
            return None
        value = rule.static_value or "privaci-test-pw"
        return StaticAction(action="static", value=value)
    if base not in _TEXTLIKE:
        return None
    return NerMaskAction(action="ner_mask")


def _fake_action(rule: PatternRule, base: str) -> ColumnAction | None:
    if rule.provider is None:
        msg = f"fake rule {rule.rule_id} missing provider"
        raise ValueError(msg)
    allowed = _PROVIDER_TYPES.get(rule.provider, _TEXTLIKE)
    if base not in allowed:
        return None
    return FakeAction(action="fake", provider=rule.provider)


def _hash_action(base: str) -> ColumnAction | None:
    if base == "uuid":
        return FakeAction(action="fake", provider="uuid")
    if base in _TEXTLIKE:
        return HashAction(action="hash")
    return None
