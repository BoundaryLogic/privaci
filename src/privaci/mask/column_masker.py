"""Apply one configured column action to a single cell value."""

from __future__ import annotations

import hashlib
import re
from typing import Any, get_args

from privaci.config.actions import (
    AiRefineAction,
    ColumnAction,
    FakeAction,
    HashAction,
    HmacHashAction,
    NerMaskAction,
    NullAction,
    PassthroughAction,
    PseudonymAction,
    RegexMaskAction,
    StaticAction,
)
from privaci.errors import L3NotInstalledError, MaskingError
from privaci.mask.faker import FakeRequest, generate_fake
from privaci.mask.keyed import (
    compute_keyed_digest,
    encode_keyed_digest,
    generate_keyed_pseudonym,
    normalize_for_hmac,
)
from privaci.mask.ner import mask_entities_in_text
from privaci.mask.regex_safe import safe_regex_sub

# Derived from the ColumnAction union so the defensive error below can never
# drift from the supported set. ColumnAction is Annotated[Union[...], Field],
# so the union itself is the first arg.
_SUPPORTED_ACTION_NAMES = ", ".join(
    member.__name__ for member in get_args(get_args(ColumnAction)[0])
)


def unique_column_names(
    *,
    primary_key: tuple[str, ...],
    unique_groups: tuple[tuple[str, ...], ...],
    unique_index_columns: tuple[tuple[str, ...], ...],
) -> frozenset[str]:
    """Return the set of column names that participate in a uniqueness guarantee.

    The single source of truth for what counts as "unique" (primary key, unique
    constraints, unique indexes). Callers in hot paths precompute this once and
    test membership rather than re-scanning the tuples per row.
    """
    names: set[str] = set(primary_key)
    for group in unique_groups:
        names.update(group)
    for group in unique_index_columns:
        names.update(group)
    return frozenset(names)


def is_unique_column(
    column_name: str,
    *,
    primary_key: tuple[str, ...],
    unique_groups: tuple[tuple[str, ...], ...],
    unique_index_columns: tuple[tuple[str, ...], ...],
) -> bool:
    """Return whether uniqueness suffixing should apply to ``column_name``."""
    return column_name in unique_column_names(
        primary_key=primary_key,
        unique_groups=unique_groups,
        unique_index_columns=unique_index_columns,
    )


def mask_column_value(
    value: Any,
    action: ColumnAction,
    *,
    salt: str,
    column_path: str,
    is_unique: bool,
    pseudonym_key: str | None = None,
) -> Any:
    """Mask one cell according to its configured action.

    ``NULL`` and empty strings pass through unchanged for every action except
    ``null`` and ``static``.

    Raises:
        MaskingError: When the action cannot process the value type.
        L3NotInstalledError: When ``ai_refine`` is invoked without L3 installed.
    """
    if value is None:
        return None
    if isinstance(value, str) and value == "":
        return _mask_empty_string(action)
    return _dispatch_mask_action(
        value,
        action,
        salt=salt,
        column_path=column_path,
        is_unique=is_unique,
        pseudonym_key=pseudonym_key,
    )


def _mask_empty_string(action: ColumnAction) -> Any:
    if isinstance(action, NullAction):
        return None
    if isinstance(action, StaticAction):
        return action.value
    return ""


def _dispatch_mask_action(
    value: Any,
    action: ColumnAction,
    *,
    salt: str,
    column_path: str,
    is_unique: bool,
    pseudonym_key: str | None,
) -> Any:
    if isinstance(action, PassthroughAction):
        return value
    elif isinstance(action, NullAction):
        return None
    elif isinstance(action, StaticAction):
        return action.value
    elif isinstance(action, HashAction):
        return _hash_value(value, salt)
    elif isinstance(action, HmacHashAction):
        return _hmac_hash_value(value, action, column_path, pseudonym_key)
    elif isinstance(action, PseudonymAction):
        return _pseudonym_value(value, action, column_path, is_unique, pseudonym_key)
    elif isinstance(action, FakeAction):
        return _fake_value(value, action, salt, column_path, is_unique)
    elif isinstance(action, RegexMaskAction):
        return _regex_mask(value, action)
    elif isinstance(action, NerMaskAction):
        return _ner_mask(value, salt=salt, column_path=column_path)
    elif isinstance(action, AiRefineAction):
        raise L3NotInstalledError(
            "Masking a column with ai_refine",
            cause="Level 3 connectors require the commercial layer.",
            remediation="Install privaci-commercial or use a Level-1/2 action.",
        )
    # Exhaustive over ColumnAction, so mypy proves this terminal unreachable;
    # CodeQL's mixed-return rule still wants an explicit non-returning statement
    # rather than an implicit fall-through (it does not model ``assert_never``).
    msg = (  # type: ignore[unreachable]
        f"Unsupported column action type: {type(action).__name__}. "
        f"Supported types are: {_SUPPORTED_ACTION_NAMES}."
    )
    raise TypeError(msg)


def _hash_value(value: Any, salt: str) -> str:
    text = str(value)
    digest = hashlib.sha256()
    digest.update(salt.encode("utf-8"))
    digest.update(text.encode("utf-8"))
    return digest.hexdigest()


def _require_pseudonym_key(pseudonym_key: str | None) -> str:
    if pseudonym_key is None:
        raise MaskingError(
            "Applying keyed masking action",
            cause="pseudonym_key was not resolved for this run.",
            remediation=(
                "Set pseudonym_key or PSEUDONYM_KEY before using keyed actions."
            ),
        )
    return pseudonym_key


def _hmac_hash_value(
    value: Any,
    action: HmacHashAction,
    column_path: str,
    pseudonym_key: str | None,
) -> str:
    key = _require_pseudonym_key(pseudonym_key)
    normalized = normalize_for_hmac(value)
    digest = compute_keyed_digest(key, column_path, normalized)
    return encode_keyed_digest(digest, encoding=action.encoding)


def _pseudonym_value(
    value: Any,
    action: PseudonymAction,
    column_path: str,
    is_unique: bool,
    pseudonym_key: str | None,
) -> str:
    key = _require_pseudonym_key(pseudonym_key)
    request = FakeRequest(
        salt="",
        column_path=column_path,
        value=str(value),
        provider=action.provider,
        seed_alias=action.seed_alias,
        is_unique=is_unique,
        params=dict(action.params),
    )
    return generate_keyed_pseudonym(request, pseudonym_key=key)


def _fake_value(
    value: Any,
    action: FakeAction,
    salt: str,
    column_path: str,
    is_unique: bool,
) -> str:
    request = FakeRequest(
        salt=salt,
        column_path=column_path,
        value=str(value),
        provider=action.provider,
        seed_alias=action.seed_alias,
        is_unique=is_unique,
        params=dict(action.params),
    )
    return generate_fake(request)


def _ner_mask(value: Any, *, salt: str, column_path: str) -> str:
    """Mask named entities in a text value.

    Like :func:`_regex_mask`, NER operates only on text: running entity
    recognition over a stringified number or boolean is meaningless, so a
    non-text value is rejected rather than silently coerced with ``str()``.
    """
    if not isinstance(value, str):
        raise MaskingError(
            "Applying ner_mask",
            cause="ner_mask requires a text column value.",
            remediation="Use fake or hash for non-text types.",
        )
    return mask_entities_in_text(value, salt=salt, column_path=column_path)


def _regex_mask(value: Any, action: RegexMaskAction) -> str:
    if not isinstance(value, str):
        raise MaskingError(
            "Applying regex_mask",
            cause="regex_mask requires a text column value.",
            remediation="Use fake or hash for non-text types.",
        )
    flags = 0
    # action.flags is validated at config-parse time by
    # RegexMaskAction._flags_must_be_known (restricted to _ALLOWED_REGEX_FLAGS,
    # all of which are real re attributes), so getattr here cannot fail.
    for flag_name in action.flags:
        flags |= getattr(re, flag_name.upper())
    return safe_regex_sub(
        action.pattern,
        action.replace,
        value,
        flags=flags,
    )
