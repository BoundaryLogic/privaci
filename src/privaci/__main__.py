"""Allow `python -m privaci` to invoke the CLI."""

from __future__ import annotations

from privaci.cli.app import main

if __name__ == "__main__":
    raise SystemExit(main())
