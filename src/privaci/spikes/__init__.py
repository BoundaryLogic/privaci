"""Week-1 architecture spikes (COPY-binary, SpaCy, cyclic FK)."""

from __future__ import annotations

from privaci.spikes.copy_binary import CopyBinarySpikeResult, run_copy_binary_spike
from privaci.spikes.cyclic_fk import CyclicFkSpikeResult, run_cyclic_fk_spike
from privaci.spikes.spacy_throughput import (
    SpacySpikeResult,
    run_spacy_throughput_spike,
)

__all__ = [
    "CopyBinarySpikeResult",
    "CyclicFkSpikeResult",
    "SpacySpikeResult",
    "run_copy_binary_spike",
    "run_cyclic_fk_spike",
    "run_spacy_throughput_spike",
]
