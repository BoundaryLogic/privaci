"""Elevated-object disposition checks for view/function replication."""

from __future__ import annotations

from privaci.catalog.models import CatalogResult, FunctionInfo, ViewInfo
from privaci.config.models import Config
from privaci.errors import PreflightError


def elevated_objects_in_scope(
    catalog: CatalogResult,
    config: Config,
) -> list[tuple[str, str]]:
    """Return ``(identifier, kind)`` for elevated objects that need dispositions.

    Only objects that would otherwise be replicated (flags enabled) are included.
    Elevated views/functions whose table dependencies are all ``strategy: exclude``
    are omitted — they are skipped via dependency exclusion instead.
    """
    excluded = {
        table_id
        for table_id, table_cfg in config.tables.items()
        if table_cfg.strategy == "exclude"
    }
    found: list[tuple[str, str]] = []
    if config.replicate_functions:
        for function in catalog.functions:
            if not function.is_elevated:
                continue
            deps = set(function.depends_on_tables)
            if deps and deps.issubset(excluded):
                continue
            found.append((function.identifier, "function"))
    if config.replicate_views:
        for view in catalog.views:
            if view.kind != "view" or not view.is_elevated:
                continue
            deps = set(view.depends_on)
            if deps and deps.issubset(excluded):
                continue
            found.append((view.identifier, "view"))
    return sorted(found, key=lambda item: item[0])


def validate_elevated_dispositions(
    catalog: CatalogResult,
    config: Config,
) -> None:
    """Fail when elevated objects lack an explicit ``replicate`` or ``skip``.

    Raises:
        PreflightError: When any in-scope elevated object is unresolved.
    """
    if config.schema_mode != "replicate":
        return
    missing = [
        identifier
        for identifier, _kind in elevated_objects_in_scope(catalog, config)
        if identifier not in config.elevated_objects
    ]
    if not missing:
        return
    listed = ", ".join(missing)
    raise PreflightError(
        "Checking elevated object dispositions",
        cause=(
            "Elevated objects require an explicit elevated_objects disposition "
            f"before replication: {listed}."
        ),
        remediation=(
            "Add each object to elevated_objects with replicate or skip "
            "(see docs/configuration.md#elevated-objects)."
        ),
    )


def validate_function_excluded_deps(
    catalog: CatalogResult,
    config: Config,
) -> None:
    """Fail when a replicated function depends on an excluded table."""
    if config.schema_mode != "replicate" or not config.replicate_functions:
        return
    excluded = {
        table_id
        for table_id, table_cfg in config.tables.items()
        if table_cfg.strategy == "exclude"
    }
    if not excluded:
        return
    for function in catalog.functions:
        if _should_skip_function(function, config):
            continue
        offenders = sorted(set(function.depends_on_tables) & excluded)
        if not offenders:
            continue
        raise PreflightError(
            "Checking function dependencies",
            cause=(
                f"Function {function.identifier} references excluded table(s): "
                + ", ".join(offenders)
            ),
            remediation=(
                "Remove strategy: exclude from the dependency, skip the function "
                "via elevated_objects or replicate_functions: false, or adjust "
                "the function body."
            ),
        )


def _should_skip_function(function: FunctionInfo, config: Config) -> bool:
    if function.is_elevated:
        return config.elevated_objects.get(function.identifier) != "replicate"
    return False


def disposition_for_view(view: ViewInfo, config: Config) -> str:
    """Return ``replicate``, ``skip``, or ``deferred`` for one plain view."""
    if view.kind != "view":
        return "skip"
    if not config.replicate_views:
        return "skip"
    if view.is_elevated:
        return config.elevated_objects.get(view.identifier, "deferred")
    return "replicate"


def disposition_for_function(function: FunctionInfo, config: Config) -> str:
    """Return ``replicate``, ``skip``, or ``deferred`` for one function."""
    if not config.replicate_functions:
        return "skip"
    if function.is_elevated:
        return config.elevated_objects.get(function.identifier, "deferred")
    return "replicate"
