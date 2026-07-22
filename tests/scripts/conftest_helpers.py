"""Shared helpers for scripts/ checker unit tests."""

from __future__ import annotations

import importlib.util
import sys
import textwrap
import types
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"


def ensure_scripts_path() -> Path:
    """Put ``scripts/`` on ``sys.path`` for gate-lib imports."""
    if str(_SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS_DIR))
    return _SCRIPTS_DIR


def load_scripts_module(name: str, filename: str) -> types.ModuleType:
    """Load a ``scripts/*.py`` module by path for unit tests."""
    ensure_scripts_path()
    path = _SCRIPTS_DIR / filename
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load scripts module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_py(root: Path, rel: str, body: str) -> Path:
    """Write a dedented Python file under ``root/rel``."""
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path
