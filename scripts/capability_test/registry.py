"""Registry of testable public and commercial capabilities."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

RepoKind = Literal["public", "commercial"]
MetricsKind = Literal["unit", "postgres_run", "subsetting", "masking_quality"]
MetricsScope = Literal[
    "none",
    "infra",
    "demo-corp",
    "autodetect",
    "json-mask",
    "subsetting",
    "nlp",
]
PostValidateKind = Literal[
    "postgres_reachable",
    "target_has_users",
    "target_subset_smaller",
]


@dataclass(frozen=True, slots=True)
class Capability:
    """One selectable capability exercised via pytest and optional DB checks."""

    id: str
    label: str
    description: str
    repo: RepoKind
    test_paths: tuple[str, ...]
    requires_postgres: bool = False
    requires_commercial_env: bool = False
    requires_nlp: bool = False
    post_validate: PostValidateKind | None = None
    metrics_kind: MetricsKind = "unit"
    metrics_scope: MetricsScope = "none"
    tags: frozenset[str] = field(default_factory=frozenset)


CAPABILITIES: dict[str, Capability] = {
    # --- Public engine (unit) ---
    "public-detect-drift": Capability(
        id="public-detect-drift",
        label="Detect drift CLI",
        description="``privaci detect-drift`` wiring and exit code 6 (mocked).",
        repo="public",
        test_paths=("tests/cli/test_detect_drift.py",),
        tags=frozenset({"unit", "cli", "public"}),
    ),
    "public-init-plan": Capability(
        id="public-init-plan",
        label="Init and plan CLI",
        description=(
            "``privaci init`` scaffolds mask-rules.yaml; ``privaci plan`` "
            "previews masking source-only."
        ),
        repo="public",
        test_paths=(
            "tests/cli/test_init_plan.py",
            "tests/config/test_scaffold.py",
        ),
        tags=frozenset({"unit", "cli", "public", "config"}),
    ),
    "public-row-filter": Capability(
        id="public-row-filter",
        label="Streaming row filters",
        description="Subset ``WHERE`` injection in ``stream/fetch``.",
        repo="public",
        test_paths=("tests/stream/test_fetch_row_filter.py",),
        tags=frozenset({"unit", "streaming", "public"}),
    ),
    "public-run-enhancer": Capability(
        id="public-run-enhancer",
        label="Run enhancer contract",
        description="Community ``RunEnhancer`` fallback and plugin loading.",
        repo="public",
        test_paths=("tests/contracts/test_fallbacks.py",),
        tags=frozenset({"unit", "contracts", "public"}),
    ),
    "public-object-output": Capability(
        id="public-object-output",
        label="Object output URIs",
        description=(
            "``ObjectWriter`` plugin, URI parsing, and ``write_object`` "
            "for report/dry-run artifact paths."
        ),
        repo="public",
        test_paths=(
            "tests/storage/test_object_parser.py",
            "tests/storage/test_writer.py",
        ),
        tags=frozenset({"unit", "storage", "public", "artifacts"}),
    ),
    "public-keyed-pseudonymisation": Capability(
        id="public-keyed-pseudonymisation",
        label="Keyed pseudonymisation",
        description=(
            "``hmac_hash`` and ``pseudonym`` actions with ``PSEUDONYM_KEY`` "
            "determinism and salt separation."
        ),
        repo="public",
        test_paths=("tests/mask/test_keyed.py",),
        tags=frozenset({"unit", "masking", "public", "keyed"}),
    ),
    # --- Public engine (integration / Postgres) ---
    "public-spacy-ner": Capability(
        id="public-spacy-ner",
        label="SpaCy NER stack",
        description=(
            "Requires spacy + en_core_web_sm; smoke-tests L2 ner_mask before "
            "demo-corp runs."
        ),
        repo="public",
        test_paths=("tests/integration/test_spacy_ner_stack.py",),
        requires_postgres=False,
        requires_nlp=True,
        metrics_kind="unit",
        metrics_scope="nlp",
        tags=frozenset({"integration", "nlp", "public", "masking"}),
    ),
    "public-run": Capability(
        id="public-run",
        label="Demo Corp masking run",
        description=(
            "Full demo-corp pipeline with leak probes, action-shape checks, "
            "and value-free verify."
        ),
        repo="public",
        test_paths=("tests/integration/test_demo_corp_e2e.py",),
        requires_postgres=True,
        requires_nlp=True,
        post_validate="target_has_users",
        metrics_kind="masking_quality",
        metrics_scope="demo-corp",
        tags=frozenset({"integration", "e2e", "public", "masking"}),
    ),
    "public-autodetect": Capability(
        id="public-autodetect",
        label="Auto-detect on Postgres",
        description="Zero-config scanner assigns fake/email and pipeline masks it.",
        repo="public",
        test_paths=("tests/integration/test_autodetect_postgres.py",),
        requires_postgres=True,
        metrics_kind="masking_quality",
        metrics_scope="autodetect",
        tags=frozenset({"integration", "autodetect", "public", "masking"}),
    ),
    "public-determinism": Capability(
        id="public-determinism",
        label="Deterministic masking",
        description="Same salt yields identical masked values across runs.",
        repo="public",
        test_paths=("tests/integration/test_determinism_e2e.py",),
        requires_postgres=True,
        requires_nlp=True,
        metrics_kind="masking_quality",
        metrics_scope="demo-corp",
        tags=frozenset({"integration", "public", "masking"}),
    ),
    "public-resume": Capability(
        id="public-resume",
        label="Resume from checkpoint",
        description="Interrupted run resumes without duplicating rows.",
        repo="public",
        test_paths=("tests/integration/test_resume_gate.py",),
        requires_postgres=True,
        metrics_kind="unit",
        metrics_scope="infra",
        tags=frozenset({"integration", "public", "infra"}),
    ),
    "public-streaming": Capability(
        id="public-streaming",
        label="Streaming strategies",
        description="Binary COPY passthrough vs masked batch paths.",
        repo="public",
        test_paths=("tests/integration/test_streaming_strategies.py",),
        requires_postgres=True,
        metrics_kind="unit",
        metrics_scope="infra",
        tags=frozenset({"integration", "streaming", "public", "infra"}),
    ),
    "public-schema-modes": Capability(
        id="public-schema-modes",
        label="Schema replication modes (unit)",
        description=(
            "Unit coverage for schema_mode replicate vs assume_existing: "
            "validation, passthrough_copy, elevated dispositions, and "
            "view/function ordering helpers."
        ),
        repo="public",
        test_paths=(
            "tests/preflight/test_assume_existing.py",
            "tests/preflight/test_assume_existing_validate.py",
            "tests/preflight/test_passthrough_copy.py",
            "tests/preflight/test_target_collision.py",
            "tests/pipeline/test_schema_modes_lifecycle.py",
            "tests/catalog/test_routines_order.py",
            "tests/schema/test_elevated.py",
            "tests/schema/test_objects.py",
        ),
        tags=frozenset({"unit", "public", "schema"}),
    ),
    "public-schema-modes-replicate-integration": Capability(
        id="public-schema-modes-replicate-integration",
        label="Replicate mode object DDL",
        description=(
            "schema_mode: replicate creates invoker views/functions, applies "
            "elevated_objects skip, and audits Tier-3 skipped objects."
        ),
        repo="public",
        test_paths=("tests/integration/test_views_identity.py",),
        requires_postgres=True,
        requires_nlp=True,
        metrics_kind="unit",
        metrics_scope="demo-corp",
        tags=frozenset({"integration", "public", "schema", "replicate"}),
    ),
    "public-schema-modes-assume-existing-integration": Capability(
        id="public-schema-modes-assume-existing-integration",
        label="Assume-existing schema mode",
        description=(
            "schema_mode: assume_existing loads into a prebuilt target, emits "
            "schema.validated / schema.validation_failed, and does not "
            "replicate source views/functions."
        ),
        repo="public",
        test_paths=("tests/integration/test_assume_existing.py",),
        requires_postgres=True,
        requires_nlp=True,
        metrics_kind="unit",
        metrics_scope="demo-corp",
        tags=frozenset({"integration", "public", "schema", "assume_existing"}),
    ),
    "public-schema-modes-matrix": Capability(
        id="public-schema-modes-matrix",
        label="Schema modes likelihood matrix (public)",
        description=(
            "Ranked P1–P2 public cells: elevated dispositions, view/function "
            "flags, assume-fail-empty, passthrough_copy, partitions/streaming "
            "× assume_existing, and keyed hmac on a real load."
        ),
        repo="public",
        test_paths=("tests/integration/test_schema_modes_matrix.py",),
        requires_postgres=True,
        requires_nlp=True,
        metrics_kind="unit",
        metrics_scope="demo-corp",
        tags=frozenset({"integration", "public", "schema", "matrix"}),
    ),
    "public-harden-nuclear-findings": Capability(
        id="public-harden-nuclear-findings",
        label="Nuclear harden findings (CHECK, orphan FK, force-restart)",
        description=(
            "CHECK constraint round-trip, exclude-parent + null_orphan_fks, "
            "require_binary conflict, and --force-restart under fail policy."
        ),
        repo="public",
        test_paths=("tests/integration/test_harden_nuclear_findings.py",),
        requires_postgres=True,
        requires_nlp=False,
        metrics_kind="unit",
        metrics_scope="none",
        tags=frozenset({"integration", "public", "schema", "harden"}),
    ),
    "public-partitions": Capability(
        id="public-partitions",
        label="Partitioned tables",
        description="Partition parent/child streaming and row counts.",
        repo="public",
        test_paths=("tests/integration/test_partition_streaming.py",),
        requires_postgres=True,
        requires_nlp=True,
        metrics_kind="masking_quality",
        metrics_scope="demo-corp",
        tags=frozenset({"integration", "public", "masking"}),
    ),
    "public-docs-sync": Capability(
        id="public-docs-sync",
        label="Docs build sync",
        description=(
            "MkDocs reference generation and publishable operator-doc sync "
            "including quick-launch CloudFormation asset."
        ),
        repo="public",
        test_paths=(
            "tests/docs/test_generate_docs.py",
            "tests/scripts/test_sync_commercial_docs.py",
        ),
        tags=frozenset({"unit", "docs", "public"}),
    ),
    # --- Commercial (unit) ---
    "commercial-subset-closure": Capability(
        id="commercial-subset-closure",
        label="FK subset closure (unit)",
        description="SQL row filters from root predicates and FK edges.",
        repo="commercial",
        test_paths=("tests/test_subset_closure.py",),
        tags=frozenset({"unit", "subsetting", "commercial"}),
    ),
    "commercial-jsonb-transform": Capability(
        id="commercial-jsonb-transform",
        label="JSONB path transforms (unit)",
        description="Parse → path rule → re-serialize for json/jsonb cells.",
        repo="commercial",
        test_paths=("tests/test_json_mask_transform.py",),
        tags=frozenset({"unit", "jsonb", "commercial"}),
    ),
    "commercial-extensions-config": Capability(
        id="commercial-extensions-config",
        label="Commercial extensions YAML",
        description="Load and validate ``commercial-extensions.yaml`` schema.",
        repo="commercial",
        test_paths=("tests/test_commercial_extensions.py",),
        tags=frozenset({"unit", "config", "commercial"}),
    ),
    "commercial-preview-policy": Capability(
        id="commercial-preview-policy",
        label="Preview policy diff (unit)",
        description="Structured policy diff JSON for CI artifacts.",
        repo="commercial",
        test_paths=("tests/test_preview_policy_diff.py",),
        tags=frozenset({"unit", "preview", "commercial"}),
    ),
    "commercial-preview-sarif": Capability(
        id="commercial-preview-sarif",
        label="Preview SARIF (unit)",
        description="SARIF 2.1.0 output from autodetect findings.",
        repo="commercial",
        test_paths=("tests/test_preview_sarif.py",),
        tags=frozenset({"unit", "preview", "commercial"}),
    ),
    "commercial-drift-unit": Capability(
        id="commercial-drift-unit",
        label="Catalog drift (unit)",
        description="Drift detector compares schema snapshots.",
        repo="commercial",
        test_paths=("tests/test_drift.py", "tests/test_drift_fixtures.py"),
        tags=frozenset({"unit", "drift", "commercial"}),
    ),
    "commercial-reports-unit": Capability(
        id="commercial-reports-unit",
        label="Signed reports (unit)",
        description="Report canonicalization, signing, and verify helpers.",
        repo="commercial",
        test_paths=(
            "tests/test_reports.py",
            "tests/test_report_verify.py",
        ),
        tags=frozenset({"unit", "reports", "commercial"}),
    ),
    "commercial-license": Capability(
        id="commercial-license",
        label="License & entitlement (unit)",
        description=(
            "License Manager checkout, offline JWT validation, dev license "
            "bypass, tier normalization."
        ),
        repo="commercial",
        test_paths=(
            "tests/test_license_jwt.py",
            "tests/test_license_manager.py",
        ),
        tags=frozenset({"unit", "license", "commercial"}),
    ),
    "commercial-object-writer": Capability(
        id="commercial-object-writer",
        label="Commercial object writer (unit)",
        description=(
            "``CommercialObjectWriter`` S3 uploads, local paths, and "
            "entry-point registration."
        ),
        repo="commercial",
        test_paths=("tests/test_object_writer.py",),
        tags=frozenset({"unit", "storage", "commercial", "artifacts"}),
    ),
    # --- Commercial (integration / Postgres) ---
    "commercial-roundtrip": Capability(
        id="commercial-roundtrip",
        label="Commercial Postgres roundtrip",
        description="Licensed run → signed report → drift baseline.",
        repo="commercial",
        test_paths=("tests/integration/test_commercial_postgres_roundtrip.py",),
        requires_postgres=True,
        requires_commercial_env=True,
        requires_nlp=True,
        post_validate="target_has_users",
        metrics_kind="masking_quality",
        metrics_scope="demo-corp",
        tags=frozenset({"integration", "e2e", "commercial", "masking"}),
    ),
    "commercial-preview": Capability(
        id="commercial-preview",
        label="Preview CLI (integration)",
        description="``privaci preview`` policy diff + sample rows on Postgres.",
        repo="commercial",
        test_paths=("tests/integration/test_preview_postgres.py",),
        requires_postgres=True,
        requires_commercial_env=True,
        metrics_kind="unit",
        metrics_scope="infra",
        tags=frozenset({"integration", "preview", "commercial", "infra"}),
    ),
    "commercial-jsonb-postgres": Capability(
        id="commercial-jsonb-postgres",
        label="JSONB path masking (integration)",
        description=(
            "Commercial json_mask paths fake/hash/remove/null on Postgres JSONB."
        ),
        repo="commercial",
        test_paths=("tests/integration/test_json_mask_postgres.py",),
        requires_postgres=True,
        requires_commercial_env=True,
        metrics_kind="masking_quality",
        metrics_scope="json-mask",
        tags=frozenset({"integration", "jsonb", "commercial", "masking"}),
    ),
    "commercial-subsetting": Capability(
        id="commercial-subsetting",
        label="Subsetting run (integration)",
        description=(
            "FK-aware subset on acyclic subsetting-demo fixture; "
            "pytest asserts pipeline matches closure with visible row reduction."
        ),
        repo="commercial",
        test_paths=("tests/integration/test_subset_json_mask.py",),
        requires_postgres=True,
        requires_commercial_env=True,
        metrics_kind="subsetting",
        metrics_scope="subsetting",
        tags=frozenset({"integration", "subsetting", "commercial"}),
    ),
    "commercial-schema-modes-matrix": Capability(
        id="commercial-schema-modes-matrix",
        label="Schema modes likelihood matrix (commercial)",
        description=(
            "Ranked commercial cells: JSONB/subset/subset+JSONB and licensed "
            "roundtrip under schema_mode assume_existing + truncate."
        ),
        repo="commercial",
        test_paths=("tests/integration/test_schema_modes_matrix.py",),
        requires_postgres=True,
        requires_commercial_env=True,
        requires_nlp=True,
        metrics_kind="unit",
        metrics_scope="demo-corp",
        tags=frozenset({"integration", "commercial", "schema", "matrix"}),
    ),
}

CAPABILITY_GROUPS: dict[str, frozenset[str]] = {
    "public-unit": frozenset(
        cid
        for cid, cap in CAPABILITIES.items()
        if cap.repo == "public" and not cap.requires_postgres
    ),
    "public-integration": frozenset(
        cid
        for cid, cap in CAPABILITIES.items()
        if cap.repo == "public" and cap.requires_postgres
    ),
    "commercial-unit": frozenset(
        cid
        for cid, cap in CAPABILITIES.items()
        if cap.repo == "commercial" and not cap.requires_postgres
    ),
    "commercial-integration": frozenset(
        cid
        for cid, cap in CAPABILITIES.items()
        if cap.repo == "commercial" and cap.requires_postgres
    ),
    "all-public": frozenset(
        cid for cid, cap in CAPABILITIES.items() if cap.repo == "public"
    ),
    "all-commercial": frozenset(
        cid for cid, cap in CAPABILITIES.items() if cap.repo == "commercial"
    ),
    "all": frozenset(CAPABILITIES.keys()),
}


@dataclass(frozen=True, slots=True)
class CapabilitySuite:
    """Ordered phases of capability groups for the suite runner."""

    id: str
    description: str
    phases: tuple[tuple[str, ...], ...]
    requires_heavy: bool


CAPABILITY_SUITES: dict[str, CapabilitySuite] = {
    "quick": CapabilitySuite(
        id="quick",
        description="All unit capabilities (public + commercial); no Postgres.",
        phases=(("public-unit", "commercial-unit"),),
        requires_heavy=False,
    ),
    "public": CapabilitySuite(
        id="public",
        description="Public unit tests, then public Postgres integration.",
        phases=(("public-unit",), ("public-integration",)),
        requires_heavy=True,
    ),
    "commercial": CapabilitySuite(
        id="commercial",
        description="Commercial unit tests, then commercial Postgres integration.",
        phases=(("commercial-unit",), ("commercial-integration",)),
        requires_heavy=True,
    ),
    "standard": CapabilitySuite(
        id="standard",
        description=(
            "Unit tests for both repos, then public integration, "
            "then commercial integration (one Postgres session)."
        ),
        phases=(
            ("public-unit", "commercial-unit"),
            ("public-integration",),
            ("commercial-integration",),
        ),
        requires_heavy=True,
    ),
    "full": CapabilitySuite(
        id="full",
        description="Alias for standard — intended for CI or pre-release validation.",
        phases=(
            ("public-unit", "commercial-unit"),
            ("public-integration",),
            ("commercial-integration",),
        ),
        requires_heavy=True,
    ),
    "schema-modes-matrix": CapabilitySuite(
        id="schema-modes-matrix",
        description=(
            "Schema-mode unit helpers, then public matrix cells, then "
            "commercial matrix cells (sequential; heavy)."
        ),
        phases=(
            ("public-schema-modes",),
            ("public-schema-modes-matrix",),
            ("commercial-schema-modes-matrix",),
        ),
        requires_heavy=True,
    ),
}


def resolve_capability_ids(raw: list[str]) -> list[str]:
    """Expand group aliases and return de-duplicated capability ids in stable order."""
    seen: set[str] = set()
    ordered: list[str] = []
    tokens: list[str] = []
    for item in raw:
        tokens.extend(part.strip() for part in item.split(",") if part.strip())
    for key in tokens:
        if key in CAPABILITY_GROUPS:
            ids = CAPABILITY_GROUPS[key]
        elif key in CAPABILITIES:
            ids = frozenset({key})
        else:
            msg = f"Unknown capability or group: {key!r}"
            raise ValueError(msg)
        for cid in sorted(ids):
            if cid not in seen:
                seen.add(cid)
                ordered.append(cid)
    return ordered
