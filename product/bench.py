#!/usr/bin/env python3
"""Latency benchmarks — the numbers the audit asked for.

Times the operations that must be cheap enough to stay in the hot
path, over a field of N memories with realistic chains:

    recall          — the read every decision takes
    provenance/sum  — bounded expansion
    provenance/ctr  — counterfactual depth (projection only)
    what_if_transition — SAVEPOINT + recompute + production recall
    export_bundle   — the heavy one, off the hot path by design

Usage: python3 bench.py [n_memories] [n_asks]   (default 200 / 40)
Offline (deterministic embedder) — Nebius latency is network-bound
and says nothing about the engine.
"""

import statistics
import sys
import time

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from seasons import agent, embed as _embed
from mneme import field

N = int(sys.argv[1]) if len(sys.argv) > 1 else 200
ASKS = int(sys.argv[2]) if len(sys.argv) > 2 else 40


def pct(ts, p):
    ts = sorted(ts)
    return ts[min(len(ts) - 1, int(len(ts) * p / 100))]


def main():
    a = agent.SeasonsAgent()
    for i in range(N):
        a.remember(f"note {i}: the {i}th thing about deploys and "
                   f"staging and rollbacks and gates")
    for _ in range(ASKS):
        a.ask("deploy gate staging?")
    a.conn.commit()

    def t(fn, n=50):
        ts = []
        for _ in range(n):
            t0 = time.perf_counter()
            fn()
            ts.append((time.perf_counter() - t0) * 1000)
        return pct(ts, 50), pct(ts, 95)

    qemb = field.quantize_embedding(_embed.embed("deploy gate staging?"))
    results = {}

    results["recall"] = t(lambda: field.recall(
        a.cur, query_embedding=qemb))
    results["provenance/summary"] = t(
        lambda: a.request_provenance("mem-0000", depth="summary"))
    results["provenance/counterfactual"] = t(
        lambda: a.request_provenance("mem-0000",
                                     depth="counterfactual"))
    # pick a memory that actually has a REINFORCED event to excise
    target = next(
        m for m in (f"mem-{i:04d}" for i in range(N))
        if any(e[1] == "REINFORCED" for e in a.chain(m)))
    seq = next(e[0] for e in a.chain(target) if e[1] == "REINFORCED")
    results["what_if_transition"] = t(
        lambda: a.what_if_transition("deploy gate staging?",
                                     target, excise_seq=seq))
    results["export_bundle"] = t(a.export_bundle, n=5)

    print(f"field: {N} memories, {ASKS} asks (offline embedder)")
    print(f"{'operation':<30} {'p50':>9} {'p95':>9}")
    for name, (p50, p95) in results.items():
        print(f"{name:<30} {p50:>8.1f}ms {p95:>8.1f}ms")


if __name__ == "__main__":
    main()
