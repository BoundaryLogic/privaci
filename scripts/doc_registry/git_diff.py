"""Git diff helpers for registry coupling checks."""

from __future__ import annotations

import subprocess
from pathlib import Path

from doc_registry.models import REPO_ROOT


def resolve_merge_base(repo_root: Path = REPO_ROOT) -> str | None:
    """Return merge-base SHA with origin/main or main, or None when unavailable."""
    for ref in ("origin/main", "main"):
        result = subprocess.run(
            ["git", "merge-base", "HEAD", ref],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        sha = result.stdout.strip()
        if result.returncode == 0 and sha:
            return sha
    return None


def _lines_to_paths(stdout: str) -> frozenset[str]:
    return frozenset(line.strip() for line in stdout.splitlines() if line.strip())


def _git_name_only(
    args: list[str],
    *,
    repo_root: Path,
    failure_prefix: str,
) -> tuple[frozenset[str] | None, list[str]]:
    result = subprocess.run(
        args,
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        return None, [f"{failure_prefix}: {detail}"]
    return _lines_to_paths(result.stdout), []


def _collect_unstaged_paths(
    *,
    base_sha: str | None,
    repo_root: Path,
) -> tuple[frozenset[str] | None, list[str]]:
    diff_base = (base_sha or "").strip() or resolve_merge_base(repo_root)
    if not diff_base:
        return None, [
            "cannot resolve merge-base with origin/main or main — "
            "run: git fetch origin main && git merge-base HEAD origin/main "
            "(or pass --base-sha on GitHub PRs)"
        ]
    tracked, errors = _git_name_only(
        ["git", "diff", "--name-only", "--diff-filter=ACMR", diff_base],
        repo_root=repo_root,
        failure_prefix="git diff failed",
    )
    if errors:
        return None, errors
    untracked, errors = _git_name_only(
        ["git", "ls-files", "--others", "--exclude-standard"],
        repo_root=repo_root,
        failure_prefix="git ls-files --others failed",
    )
    if errors:
        return None, errors
    if tracked is None or untracked is None:
        return None, ["git listing returned no paths without an error detail"]
    return tracked | untracked, []


def collect_changed_files(
    *,
    staged: bool,
    skip_coupling: bool,
    base_sha: str | None = None,
    repo_root: Path = REPO_ROOT,
) -> tuple[frozenset[str] | None, list[str]]:
    """Return changed repo-relative paths; None set means coupling cannot run.

    Diff bases (design D11): staged (pre-commit); ``base_sha`` (GitHub PR);
    otherwise merge-base with ``origin/main`` / ``main`` (ci-local). Non-staged
    modes also include untracked non-ignored files.
    """
    if skip_coupling:
        return frozenset(), []
    if staged and base_sha:
        return None, ["--staged and --base-sha are mutually exclusive"]
    if staged:
        return _git_name_only(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
            repo_root=repo_root,
            failure_prefix="git diff failed",
        )
    return _collect_unstaged_paths(base_sha=base_sha, repo_root=repo_root)
