#!/usr/bin/env python3
"""H14: causal-influence restoration after temporary memory absence.

Independent, bounded deterministic experimental harness (stdlib only).
Not a Raven or MNEME implementation; a falsifiable testbed for H14.

Runs six matched arms, an intrinsic-state x historical-link factorial,
relearning, two reference worlds, and a surgical contribution ablation.
No external services, LLM, secrets, clocks, random generators, or git writes.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from dataclasses import dataclass, field
from fractions import Fraction as F
from typing import Dict, Tuple

NODES = ("A", "B", "C", "D")
QUERIES = (
    {"A": F(8, 10), "B": F(6, 10), "C": F(4, 10), "D": F(2, 10)},
    {"A": F(5, 10), "B": F(7, 10), "C": F(6, 10), "D": F(3, 10)},
    {"A": F(7, 10), "B": F(3, 10), "C": F(6, 10), "D": F(5, 10)},
    {"A": F(4, 10), "B": F(6, 10), "C": F(3, 10), "D": F(8, 10)},
)
# Two action alternatives: a choice changes only when the argmax crosses
# a decision boundary. State-only ranking changes do not count as influence.
ACTION = {"A": "X", "B": "Y", "C": "Y", "D": "X"}


@dataclass
class World:
    strength: Dict[str, F] = field(default_factory=lambda: {k: F(1) for k in NODES})
    # Directed associations: incident links are shared state, not owned by A.
    links: Dict[Tuple[str, str], F] = field(default_factory=dict)
    available: set[str] = field(default_factory=lambda: set(NODES))
    prior_choice: str | None = None

    def clone(self) -> "World":
        return copy.deepcopy(self)


def base_world() -> World:
    w = World()
    w.strength.update({"A": F(3, 2), "B": F(1), "C": F(5, 4), "D": F(1)})
    w.links.update({("A", "B"): F(1, 3), ("B", "A"): F(1, 4),
                    ("A", "D"): F(1, 4), ("C", "A"): F(1, 3),
                    ("B", "C"): F(1, 5)})
    return w


def contribution(w: World, query: Dict[str, F], neutralize: str | None = None) -> Dict[str, F]:
    """Single-step nonrecursive propagation; no rewiring or deletions.

    Neutralizing A blocks A's own score AND incoming/outgoing propagation
    mediated by A, while preserving nodes, links, and all other strengths.
    This is a *controlled intervention*, not deletion/re-embedding.
    """
    visible = w.available - ({neutralize} if neutralize else set())
    result = {node: F(0) for node in NODES}
    for node in visible:
        result[node] += query[node] * w.strength[node]
    for (src, dst), weight in sorted(w.links.items()):
        if src in visible and dst in visible:
            result[dst] += query[src] * w.strength[src] * weight
    return result


def decision(w: World, query: Dict[str, F], neutralize: str | None = None) -> str:
    scores = contribution(w, query, neutralize)
    totals = {"X": F(0), "Y": F(0)}
    for node in NODES:
        totals[ACTION[node]] += scores[node]
    return "X" if totals["X"] >= totals["Y"] else "Y"  # pinned tie policy


def influence_vector(w: World) -> tuple[int, ...]:
    if "A" not in w.available:
        return tuple(0 for _ in QUERIES)
    return tuple(int(decision(w, q) != decision(w, q, neutralize="A")) for q in QUERIES)


def signature(w: World) -> tuple[tuple[str, str], ...]:
    return tuple((decision(w, q), decision(w, q, neutralize="A")) for q in QUERIES)


def learn(w: World, query: Dict[str, F], reinforce: bool = True) -> None:
    """An explicit toy plasticity rule; not inherited Raven dynamics.

    Retrieval selects highest-scoring *memory*, then reinforces it. The
    resulting choice is not assumed to be a clinical/cognitive outcome.
    """
    scores = contribution(w, query)
    eligible = sorted(w.available)
    if not eligible:
        return
    winner = min(eligible, key=lambda n: (-scores[n], n))
    if reinforce:
        w.strength[winner] = min(F(2), w.strength[winner] + F(1, 8))
        if w.prior_choice and w.prior_choice != winner:
            edge = (w.prior_choice, winner)
            w.links[edge] = min(F(1, 2), w.links.get(edge, F(0)) + F(1, 16))
    w.prior_choice = winner


def suppress(w: World) -> None:
    w.available.discard("A")
    # Crucial: we do NOT delete A, its state, or incident link records.


def shared_link_aging(w: World) -> None:
    """An explicit background process affecting shared relationships.

    It does NOT update A's intrinsic state or activate A. This creates a
    meaningful contrast between 'current' and historical incident edges.
    """
    for edge in tuple(w.links):
        if "A" in edge:
            w.links[edge] *= F(7, 8)


def relearn_exposure(w: World) -> None:
    """Fresh bounded exposure, not copying any pre-absence coefficients."""
    assert "A" in w.available
    w.strength["A"] = min(F(2), w.strength["A"] + F(1, 8))
    # Association formed with the most recently retrieved alternative.
    peer = w.prior_choice
    if peer is not None and peer != "A":
        w.links[("A", peer)] = min(F(1, 2), w.links.get(("A", peer), F(0)) + F(1, 16))


def reinstate(w: World, historic: World, own_state: bool, edges: bool) -> None:
    """Factorial 2x2; rest of world untouched unless incident edges explicitly treated."""
    w.available.add("A")
    w.strength["A"] = historic.strength["A"] if own_state else F(1)
    if edges or not own_state:
        # Reset incident edges for reexposure or deliberate historical
        # restoration. Strict-local restoration retains aged CURRENT edges.
        for e in tuple(w.links):
            if "A" in e:
                del w.links[e]
        if edges:
            for e, weight in historic.links.items():
                if "A" in e:
                    w.links[e] = weight


def run(absence_steps: int = 8, followup_steps: int = 12) -> dict:
    historic = base_world()
    # Warm-up before the absence: all arms share history until this fork.
    for i in range(6):
        learn(historic, QUERIES[i % len(QUERIES)])
    before = historic.clone()
    no_absence = before.clone()
    absent = before.clone()
    suppress(absent)
    for i in range(absence_steps):
        q = QUERIES[(i + 1) % len(QUERIES)]
        learn(no_absence, q)
        learn(absent, q)
        shared_link_aging(absent)
    # A's frozen incident links are saved separately as custody evidence.
    # During absence, no A endpoints are activated or trained.
    baseline = absent.clone()
    arms = {"no_absence": no_absence,
            "reexposure": baseline.clone(),
            "strict": baseline.clone(),
            "links_only": baseline.clone(),
            "state_and_links": baseline.clone(),
            "relearning": baseline.clone()}
    reinstate(arms["reexposure"], before, False, False)
    reinstate(arms["strict"], before, True, False)
    reinstate(arms["links_only"], before, False, True)
    reinstate(arms["state_and_links"], before, True, True)
    reinstate(arms["relearning"], before, False, False)
    # New experiences relearn rather than copying any historical state.
    initial = {name: influence_vector(w) for name, w in arms.items()}
    states_after_absence = {k: v.strength.copy() for k, v in arms.items()}
    for i in range(followup_steps):
        q = QUERIES[(i + absence_steps + 1) % len(QUERIES)]
        for name, w in arms.items():
            learn(w, q)
            if name == "relearning" and i in (0, 3, 6, 9):
                relearn_exposure(w)
    final = {name: influence_vector(w) for name, w in arms.items()}
    reference = final["no_absence"]
    dists = {name: sum(x != y for x, y in zip(v, reference))
             for name, v in final.items()}
    # Core invariants; check throughout, not only in tests.
    assert all(w.available == set(NODES) for w in arms.values())
    assert states_after_absence["strict"]["B"] == states_after_absence["reexposure"]["B"]
    assert states_after_absence["links_only"]["B"] == states_after_absence["state_and_links"]["B"]
    payload = {
        "status": "EXECUTED_TOY_ASSAY_NOT_RAVEN", "absence_steps": absence_steps,
        "followup_steps": followup_steps, "queries": len(QUERIES),
        "pre_absence_influence": list(influence_vector(before)),
        "initial": {k: list(v) for k, v in initial.items()},
        "final": {k: list(v) for k, v in final.items()},
        "hamming_to_no_absence": dists,
        "mechanism": "1-step directed propagation + per-memory reinforcement + co-recall edges + shared edge aging",
        "relearning_dose": sum(i in (0, 3, 6, 9) for i in range(followup_steps)),
        "limits": "Small synthetic scenario; no efficacy, clinical analogy, statistical generalization or Raven/MNEME equivalence claimed."
    }
    data = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    payload["sha256"] = hashlib.sha256(data.encode()).hexdigest()
    return payload


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--absence", type=int, default=8)
    ap.add_argument("--followup", type=int, default=12)
    args = ap.parse_args()
    if args.absence < 1 or args.followup < 0:
        ap.error("--absence >= 1 and --followup >= 0 required")
    print(json.dumps(run(args.absence, args.followup), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
