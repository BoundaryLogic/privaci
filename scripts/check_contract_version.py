#!/usr/bin/env python3
"""Release guard: validate CONTRACT_VERSION against the engine package version.

The commercial layer pins ``privaci.contracts.CONTRACT_VERSION`` (ABI major).
Pre-1.0 engine releases (``0.x``) may ship contract major ``1``; from engine
``1.0.0`` onward the package and contract majors must match.

Run: ``python scripts/check_contract_version.py``
"""

from __future__ import annotations

import sys
from importlib.metadata import PackageNotFoundError, version

from privaci.contracts import CONTRACT_VERSION


def _major(component: str) -> int:
    head = component.strip().split(".", 1)[0]
    try:
        return int(head)
    except ValueError as exc:
        msg = f"Unparseable version component {component!r}"
        raise ValueError(msg) from exc


def validate_contract_version(*, package_version: str, contract_version: str) -> None:
    """Raise ``ValueError`` when the version pairing is inconsistent."""
    pkg_major = _major(package_version)
    contract_major = _major(contract_version)
    if pkg_major == 0 and contract_major == 1:
        return
    if pkg_major == contract_major:
        return
    msg = (
        f"CONTRACT_VERSION {contract_version!r} (major {contract_major}) is "
        f"incompatible with engine package version {package_version!r} "
        f"(major {pkg_major})."
    )
    raise ValueError(msg)


def main() -> int:
    """Return 0 when versions are consistent."""
    try:
        package_version = version("privaci")
    except PackageNotFoundError:
        package_version = "0.0.0"
    try:
        validate_contract_version(
            package_version=package_version,
            contract_version=CONTRACT_VERSION,
        )
    except ValueError as exc:
        sys.stderr.write(f"ERROR: {exc}\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
