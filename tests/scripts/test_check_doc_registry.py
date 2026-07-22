"""Tests for scripts/check_doc_registry.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from tests.fixtures.doc_registry_min import write_min_registry

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import doc_registry as _mod  # noqa: E402  # scripts/ on sys.path for package import


def _anchors_from_text(text: str) -> set[str]:
    anchors = set(_mod.EXPLICIT_ANCHOR_PATTERN.findall(text))
    for match in _mod.HEADING_PATTERN.finditer(text):
        anchors.add(_mod.slugify_heading(match.group(1)))
    return anchors


def test_collect_changed_files_uses_explicit_base_sha(mocker) -> None:
    # Arrange
    tracked = mocker.Mock(
        returncode=0, stdout="src/privaci/mask/engine.py\n", stderr=""
    )
    untracked = mocker.Mock(returncode=0, stdout="src/privaci/mask/new.py\n", stderr="")
    run = mocker.patch(
        "doc_registry.git_diff.subprocess.run",
        side_effect=[tracked, untracked],
    )

    # Act
    paths, errors = _mod.collect_changed_files(
        staged=False,
        skip_coupling=False,
        base_sha="abc123",
    )

    # Assert
    assert errors == []
    assert paths == frozenset({"src/privaci/mask/engine.py", "src/privaci/mask/new.py"})
    assert run.call_args_list[0].args[0] == [
        "git",
        "diff",
        "--name-only",
        "--diff-filter=ACMR",
        "abc123",
    ]
    assert run.call_args_list[1].args[0] == [
        "git",
        "ls-files",
        "--others",
        "--exclude-standard",
    ]


def test_collect_changed_files_rejects_staged_with_base_sha() -> None:
    # Act
    paths, errors = _mod.collect_changed_files(
        staged=True,
        skip_coupling=False,
        base_sha="abc123",
    )

    # Assert
    assert paths is None
    assert any("mutually exclusive" in err for err in errors)


def test_run_checks_passes_on_current_repository() -> None:
    # Act
    errors = _mod.run_checks(skip_coupling=True)

    # Assert
    assert errors == []


def test_check_coupling_fails_without_docs_touch() -> None:
    # Arrange
    registry = _mod.load_registry(_REPO_ROOT / "docs" / "registry.yaml")
    changed = frozenset({"src/privaci/mask/engine.py"})

    # Act
    errors = _mod.check_coupling(registry, changed)

    # Assert
    assert any("entry 'mask'" in err for err in errors)


def test_check_coupling_passes_with_docs_touch() -> None:
    # Arrange
    registry = _mod.load_registry(_REPO_ROOT / "docs" / "registry.yaml")
    changed = frozenset(
        {"src/privaci/mask/engine.py", "docs/configuration.md", "CHANGELOG.md"}
    )

    # Act
    errors = _mod.check_coupling(registry, changed)

    # Assert
    assert errors == []


def test_check_coupling_requires_changelog_when_marked_required(tmp_path: Path) -> None:
    # Arrange
    write_min_registry(tmp_path)
    registry = _mod.load_registry(tmp_path / "docs" / "registry.yaml")
    changed = frozenset({"src/privaci/cli/app.py", "docs/cli-reference.md"})

    # Act
    errors = _mod.check_coupling(registry, changed)

    # Assert
    assert any("CHANGELOG.md" in err for err in errors)


def test_check_package_coverage_fails_for_unregistered_package(tmp_path: Path) -> None:
    # Arrange
    write_min_registry(tmp_path, extra_package="runtime")

    # Act
    registry = _mod.load_registry(tmp_path / "docs" / "registry.yaml")
    errors = _mod.check_package_coverage(registry, tmp_path / "src" / "privaci")

    # Assert
    assert any("runtime" in err for err in errors)


def test_spikes_package_is_meta_excluded(tmp_path: Path) -> None:
    # Arrange
    write_min_registry(tmp_path)

    # Act
    registry = _mod.load_registry(tmp_path / "docs" / "registry.yaml")
    errors = _mod.check_package_coverage(registry, tmp_path / "src" / "privaci")

    # Assert
    assert errors == []


def test_waiver_suppresses_coupling(tmp_path: Path) -> None:
    # Arrange
    write_min_registry(tmp_path)
    registry_path = tmp_path / "docs" / "registry.yaml"
    text = registry_path.read_text(encoding="utf-8")
    text = text.replace(
        "  - id: mask\n    code:",
        '  - id: mask\n    waiver: "issue #99"\n    code:',
        1,
    )
    registry_path.write_text(text, encoding="utf-8")
    registry = _mod.load_registry(registry_path)
    mask_entry = next(entry for entry in registry.entries if entry.id == "mask")
    assert mask_entry.waiver == "issue #99"
    changed = frozenset({"src/privaci/mask/engine.py"})

    # Act
    errors = _mod.check_coupling(registry, changed)

    # Assert
    assert errors == []


def test_check_exit_code_anchors_fails_when_anchor_missing(tmp_path: Path) -> None:
    # Arrange
    write_min_registry(tmp_path)
    (tmp_path / "docs" / "error-codes.md").write_text(
        "# No anchors\n", encoding="utf-8"
    )

    # Act
    errors = _mod.check_exit_code_anchors(
        tmp_path / "src" / "privaci" / "errors.py",
        tmp_path / "docs" / "error-codes.md",
    )

    # Assert
    assert any("exit-code-1-generic-error" in err for err in errors)


def test_validate_structure_requires_spikes_exclude(tmp_path: Path) -> None:
    # Arrange
    write_min_registry(tmp_path, exclude_spikes=False)
    registry = _mod.load_registry(tmp_path / "docs" / "registry.yaml")

    # Act
    errors = _mod.validate_structure(registry, tmp_path)

    # Assert
    assert any("spikes" in err for err in errors)


def test_check_env_keys_fails_for_missing_key(tmp_path: Path) -> None:
    # Arrange
    write_min_registry(tmp_path)
    (tmp_path / ".env.example").write_text("MYSTERY_KEY=value\n", encoding="utf-8")
    registry = _mod.load_registry(tmp_path / "docs" / "registry.yaml")

    # Act
    errors = _mod.check_env_keys(registry, tmp_path)

    # Assert
    assert any("MYSTERY_KEY" in err for err in errors)


def test_path_matches_glob_supports_recursive_patterns() -> None:
    # Act & Assert
    assert _mod.path_matches_glob(
        "docs/generated/errors/exit-code-1-generic-error.md",
        "docs/generated/errors/**",
    )
    assert _mod.path_matches_glob("src/privaci/mask/engine.py", "src/privaci/mask/**")


def test_unsupported_mid_path_glob_is_rejected() -> None:
    # Arrange / Act / Assert
    reason = _mod.unsupported_glob_reason("src/**/engine.py")
    assert reason is not None
    assert (
        _mod.path_matches_glob("src/privaci/mask/engine.py", "src/**/engine.py")
        is False
    )


def test_validate_structure_rejects_mid_path_glob(tmp_path: Path) -> None:
    # Arrange
    write_min_registry(tmp_path)
    registry = _mod.load_registry(tmp_path / "docs" / "registry.yaml")
    bad_entry = _mod.RegistryEntry(
        id="leaky",
        code=("src/**/leaky.py",),
        docs=("docs/configuration.md",),
        changelog="optional",
        waiver=None,
    )
    registry = _mod.Registry(
        exclude_packages=registry.exclude_packages,
        entries=(*registry.entries, bad_entry),
    )

    # Act
    errors = _mod.validate_structure(registry, tmp_path)

    # Assert
    assert any("unsupported glob" in err for err in errors)


def test_check_exit_code_anchors_fails_when_exit_section_missing(
    tmp_path: Path,
) -> None:
    # Arrange
    write_min_registry(tmp_path)
    (tmp_path / "docs" / "error-codes.md").write_text(
        "# Exit codes\n\n## exit-code-1-generic-error\n\nok\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "privaci" / "errors.py").write_text(
        """
class PrivaCIError(Exception):
    exit_code = 1
    default_doc_anchor = "exit-code-1-generic-error"

class ConfigError(PrivaCIError):
    exit_code = 3
    default_doc_anchor = "exit-code-3-config-validation-failure"
""".lstrip(),
        encoding="utf-8",
    )

    # Act
    errors = _mod.check_exit_code_anchors(
        tmp_path / "src" / "privaci" / "errors.py",
        tmp_path / "docs" / "error-codes.md",
    )

    # Assert
    assert any("exit-code-3" in err for err in errors)


@pytest.mark.parametrize(
    ("heading", "anchor"),
    [
        ("Exit code 6: Drift detected (commercial)", "exit-code-6-drift-detected"),
        (
            "Exit code 5: License / entitlement failure",
            "exit-code-5-license-entitlement-failure",
        ),
    ],
)
def test_anchor_documented_accepts_heading_prefix(heading: str, anchor: str) -> None:
    # Arrange
    doc_anchors = _anchors_from_text(f"## {heading}\n")

    # Act
    ok = _mod.anchor_documented(anchor, doc_anchors)

    # Assert
    assert ok is True


def test_anchor_documented_rejects_numeric_prefix_collision() -> None:
    # Arrange / Act / Assert
    assert _mod.anchor_documented("exit-code-1", {"exit-code-10-something"}) is False


def test_collect_bindings_reads_ann_assign(tmp_path: Path) -> None:
    # Arrange
    errors_path = tmp_path / "errors.py"
    errors_path.write_text(
        """
class PrivaCIError(Exception):
    exit_code: int = 1
    default_doc_anchor: str = "exit-code-1-generic-error"
""".lstrip(),
        encoding="utf-8",
    )

    # Act
    bindings = _mod.collect_privaci_error_bindings(errors_path)

    # Assert
    assert bindings == [
        _mod.ErrorDocBinding(
            class_name="PrivaCIError",
            exit_code=1,
            default_doc_anchor="exit-code-1-generic-error",
        )
    ]
