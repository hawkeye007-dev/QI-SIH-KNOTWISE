"""Shared, solver-neutral setup used by controlled benchmark scripts."""

from __future__ import annotations

import random
from typing import Any

from knotwise.optimization.genome import Genome, random_genome
from knotwise.optimization.objective import ObjectiveCache
from knotwise.optimization.solver import _local_search_refine


def shared_informed_seed(
    fleet: dict[str, Any], regulations: dict[str, Any], prices: dict[str, Any], *, seed: int
) -> Genome:
    """Create one feasible anchor and apply one solver-neutral polish sweep.

    Both comparison arms receive the returned plan.  This deliberately turns
    off QIEA's mean-field initializer in the caller, isolating search behavior
    after an identical informed start rather than re-testing the initializer.
    """
    rng = random.Random(seed)
    genome = random_genome(fleet, rng)
    anchored, _ = _local_search_refine(
        genome, fleet, regulations, prices, rng, max_sweeps=1, cache=ObjectiveCache()
    )
    return anchored
