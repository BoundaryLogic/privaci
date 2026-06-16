#!/usr/bin/env python3
"""Run Week-1 architecture spikes and print a JSON-friendly summary."""

from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import asdict

from privaci.spikes._env import dsn_from_env
from privaci.spikes.copy_binary import run_copy_binary_spike
from privaci.spikes.cyclic_fk import run_cyclic_fk_spike
from privaci.spikes.spacy_throughput import run_spacy_throughput_spike


async def _run_db_spikes() -> dict[str, object]:
    source = dsn_from_env("SOURCE_DB_URL")
    target = dsn_from_env("TARGET_DB_URL")
    if not source or not target:
        return {
            "copy_binary": {
                "skipped": True,
                "reason": "SOURCE_DB_URL/TARGET_DB_URL unset",
            },
            "cyclic_fk": {"skipped": True, "reason": "SOURCE_DB_URL unset"},
        }
    copy_result = await run_copy_binary_spike(source, target)
    cyclic_result = await run_cyclic_fk_spike(source)
    return {
        "copy_binary": {**asdict(copy_result), "passed": copy_result.passed},
        "cyclic_fk": {**asdict(cyclic_result), "passed": cyclic_result.passed},
    }


def main() -> int:
    """Execute all spikes; exit 1 if any executed spike fails."""
    summary: dict[str, object] = {}
    try:
        spacy_result = run_spacy_throughput_spike()
        summary["spacy"] = {**asdict(spacy_result), "passed": spacy_result.passed}
    except RuntimeError as exc:
        summary["spacy"] = {"skipped": True, "reason": str(exc)}

    summary.update(asyncio.run(_run_db_spikes()))
    print(json.dumps(summary, indent=2))

    failed = [
        name
        for name, payload in summary.items()
        if isinstance(payload, dict)
        and not payload.get("skipped")
        and payload.get("passed") is False
    ]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
