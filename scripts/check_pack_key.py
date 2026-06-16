#!/usr/bin/env python3
"""Release/CI guard: the engine must ship no embedded config-pack trust anchor.

A hardcoded public key in ``src/privaci/packs/keys.py`` would let anyone holding
the matching private key forge packs the engine trusts. The production key is
injected at runtime via ``PRIVACI_PACK_PUBLIC_KEY`` instead, so this check fails
the build if any 32-byte (64 hex char) key literal — in particular the test
fixture key — leaks into the shipped source.

Run: ``python scripts/check_pack_key.py``
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_KEYS_FILE = _REPO_ROOT / "src" / "privaci" / "packs" / "keys.py"
_HEX_KEY_PATTERN = re.compile(r"['\"][0-9a-fA-F]{64}['\"]")


def main() -> int:
    """Return 0 when no embedded key is present, 1 otherwise."""
    source = _KEYS_FILE.read_text(encoding="utf-8")
    matches = _HEX_KEY_PATTERN.findall(source)
    if matches:
        sys.stderr.write(
            "ERROR: a hardcoded 32-byte key literal was found in "
            f"{_KEYS_FILE}. The engine must ship no embedded pack trust anchor; "
            "provision it via PRIVACI_PACK_PUBLIC_KEY instead.\n"
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
