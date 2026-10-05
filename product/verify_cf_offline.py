#!/usr/bin/env python3
"""Independent verifier for counterfactual bundles (mneme-cf-bundle/v1).

IMPLEMENTATION-INDEPENDENT by design: this file imports NOTHING from
the producing codebase — no seasons, no trajectory.py, no mneme. The
custody envelope, the replay state machine, the canonical JSON form
and ranking_protocol/1.0.0 are TRANSCRIBED here from the spec. If
producer and verifier shared the recall code, a bug in it would pass
both sides; two transcriptions of one protocol is what "independent"
means. Alignment between the two is proven by conformance tests
(test_cf_bundle_pure.py golden-vector agreement), not assumed.

Trust boundary (declared, not hidden): integrity and semantic
correctness are verified relative to the commitments in the bundle.
Full-history recommit is NOT yet closed — that needs an external
trust anchor (Ed25519/DSSE), which is the next gate.

Checks:
  CF0    bundle digest re-computes over canonical bytes.
  CF0.5  fail closed on semantics this verifier does not implement.
  CF1    every custody entry_hash recomputed from its canonical
         envelope — a forged event with borrowed hashes dies here.
  CF1.5  query embeddings must match the receipt's historical
         commitment (receipt.query_sha256), not merely be
         self-consistent.
  CF2    actual-world consistency: each decision-cited receipt's
         served set recomputes from the untampered evidence at t_d.
  CF3    the cascade: divergent receipts, ungrounded decisions,
         invalidated events, propagation edges, cf states, digest.

Usage: python3 verify_cf_offline.py bundle.json
Exit 0 = ACCEPT (recomputation agrees). Exit 1 = REJECT.
"""

import hashlib
import json
import os
import sys
from decimal import Decimal
from fractions import Fraction
from math import isqrt


# ----------------------------------------------------------------------
# Transcription 1 — mneme canonical JSON (custody canonicalization v1)
# ----------------------------------------------------------------------

_SCALE = 10


def _canon(obj, path="$"):
    if obj is None or isinstance(obj, (str, int)) \
            and not isinstance(obj, bool):
        return obj
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, float):
        raise TypeError(f"{path}: float forbidden.")
    if isinstance(obj, Decimal):
        if obj.as_tuple().exponent != -_SCALE:
            raise ValueError(f"{path}: Decimal off canonical scale.")
        return format(obj, "f")
    if isinstance(obj, dict):
        return {k: _canon(v, f"{path}.{k}") for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_canon(v, f"{path}[{i}]") for i, v in enumerate(obj)]
    raise TypeError(f"{path}: {type(obj).__name__} not serializable.")


def canonical_json(payload: dict) -> str:
    if not isinstance(payload, dict):
        raise TypeError("top-level must be a dict.")
    return json.dumps(_canon(payload), sort_keys=True,
                      separators=(",", ":"), ensure_ascii=False)


def strict_loads(s):
    """JSON with duplicate keys is ambiguous — two parsers read two
    different objects from one byte string, so a hostile payload could
    verify under one reading and lie under another. RFC 8785's rule:
    names MUST be unique. Reject, never pick."""
    def no_dupes(pairs):
        out = {}
        for k, v in pairs:
            if k in out:
                raise ValueError(f"duplicate JSON key: {k!r}")
            out[k] = v
        return out
    return json.loads(s, object_pairs_hook=no_dupes)


# ----------------------------------------------------------------------
# Transcription 2 — custody envelope hashing (custody_protocol 1.1.0)
# ----------------------------------------------------------------------

def _genesis(memory_id: str) -> str:
    return hashlib.sha256(
        b"MNEME_CUSTODY_GENESIS:" + memory_id.encode()).hexdigest()


def _entry_hash(memory_id: str, e: dict, prev: str) -> str:
    env = {"memory_id": memory_id, "seq": e["seq"],
           "event_type": e["event_type"], "actor_id": e["actor_id"],
           "reason": e["reason"], "created_at": e["created_at"],
           "payload": strict_loads(e["payload_json"])}
    return hashlib.sha256(
        prev.encode("ascii")
        + canonical_json(env).encode("utf-8")).hexdigest()


def _embedding_json(vec) -> str:
    return canonical_json({"v": [Decimal(x) for x in vec]})


def _embedding_sha256(vec) -> str:
    return hashlib.sha256(
        _embedding_json(vec).encode("utf-8")).hexdigest()


# ----------------------------------------------------------------------
# Transcription 3 — replay state machine (replay_protocol 1.1.0,
# excised-world variant per cf-cascade/v1: recompute, never trust)
# ----------------------------------------------------------------------

_ALPHA = Fraction(1, 4)
_PROMOTION = Fraction(3, 4)


def replay(chain, dead, as_of=None):
    status, fstate = "CLEAN", "NEUTRAL"
    conf = Fraction(1, 2)
    for ev in chain:
        if ev["seq"] in dead:
            continue
        if as_of is not None and ev["created_at"] >= as_of:
            continue
        et = ev["event_type"]
        if et == "QUARANTINED":
            status = "QUARANTINED"
        elif et == "SUPERSEDED_BY":
            status = "SUPERSEDED"
        elif et == "TAINT_FLAGGED":
            if status == "CLEAN":
                status = "TAINT_FLAGGED"
        elif et == "REHABILITATED":
            status = "CLEAN"
        elif et == "REINFORCED":
            conf = conf + _ALPHA * (1 - conf)
        elif et == "STATE_CHANGED":
            p = strict_loads(ev["payload_json"])
            to = p.get("to")
            if p.get("from") == "NEUTRAL" and to == "REINFORCED":
                if conf >= _PROMOTION:
                    fstate = "REINFORCED"
            elif to is not None:
                fstate = to
    return status, fstate, conf


# ----------------------------------------------------------------------
# Transcription 4 — ranking_protocol 1.0.0 (the recall itself)
# ----------------------------------------------------------------------

_STATE_BOOST = {"REINFORCED": Fraction(3, 2),
                "NEUTRAL": Fraction(1, 1),
                "FORGOTTEN": Fraction(0, 1)}
_DECAY = Fraction(43, 50)
_RESONANT_STEP = Fraction(1, 2)
_MAX_HOPS = 10


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def independent_recall(memories, links, query_vec, top_k, hops):
    """ranking_protocol/1.0.0 transcribed: gate CLEAN → FORGOTTEN out →
    argmax seed (sign-aware squared compare, memory_id tiebreak) →
    BFS over links between CLEAN endpoints (INHIBITORY silences,
    RESONANT extends + +1/2 per in-edge) → score t²/nv with decay and
    state boost, REINFORCED rescue, (-rank, memory_id) sort, top_k."""
    servable = {m["memory_id"] for m in memories
                if m["custody_status"] == "CLEAN"}
    cands = []
    for m in memories:
        if m["memory_id"] not in servable:
            continue
        if m["field_state"] == "FORGOTTEN":
            continue
        vec = [Fraction(Decimal(x)) for x in m["embedding"]]
        nv = _dot(vec, vec)
        if nv == 0:
            continue
        cands.append((m["memory_id"], vec, nv,
                      _dot(query_vec, vec), m["field_state"]))
    if not cands:
        return []

    def sim_key(c):
        _, _, nv, d, _ = c
        return (0, Fraction(0)) if d <= 0 else (1, d * d / nv)

    best, best_key = None, None
    for c in cands:
        k = sim_key(c)
        if best is None or k > best_key or (k == best_key
                                            and c[0] < best[0]):
            best, best_key = c, k
    seed = best[0]

    link_map = {}
    for l in links:
        if l["from_id"] in servable and l["to_id"] in servable:
            link_map.setdefault(l["from_id"], []).append(
                (l["to_id"], l["link_type"]))

    hop_of, inhibited, boost = {}, set(), {}
    frontier = {seed}
    for depth in range(min(hops, _MAX_HOPS) + 1):
        nxt = set()
        for mid in sorted(frontier):
            if mid in inhibited or mid in hop_of:
                continue
            hop_of[mid] = depth
            for tgt, lt in link_map.get(mid, []):
                if lt == "INHIBITORY":
                    inhibited.add(tgt)
                elif lt == "RESONANT":
                    nxt.add(tgt)
                    boost[tgt] = boost.get(tgt, Fraction(0)) \
                        + _RESONANT_STEP
                else:
                    nxt.add(tgt)
        frontier = nxt - set(hop_of) - inhibited

    scored = []
    for mid, vec, nv, d, state in cands:
        if mid in inhibited and mid != seed \
                and state != "REINFORCED":
            continue          # rescued iff REINFORCED
        hop = hop_of.get(mid, -1)
        decay = _DECAY ** hop if hop >= 0 else Fraction(1)
        m = _STATE_BOOST[state] * decay + boost.get(mid, Fraction(0))
        t = d * m
        rank = Fraction(0) if t <= 0 else t * t / nv
        scored.append((rank, mid))
    scored.sort(key=lambda s: (-s[0], s[1]))
    return [mid for _, mid in scored[:top_k]]


# ----------------------------------------------------------------------
# Verification
# ----------------------------------------------------------------------

# Every semantic version this transcription implements, per protocol.
# cf-cascade/v2 = v1 + declared-causes closure; v1 evidence verifies
# identically under the rule, so both are listed. A bundle declaring
# anything not here fails closed — semantics never silently drift.
KNOWN_SEMANTICS = {
    "bundle_protocol": {"mneme-cf-bundle/v1"},
    "causal_rewind_protocol": {"cf-cascade/v1", "cf-cascade/v2"},
    "custody_protocol": {"1.1.0"},
    "replay_protocol": {"1.1.0"},
    "ranking_protocol": {"1.0.0"},
    "taint_protocol": {"2.0.0"},
    "authority_protocol": {"1.3.0"},
    "receipt_protocol": {"2.0.0"},
    "claim_protocol": {"1.1.0"},
    "causal_ontology": {"2.0.0"},
}


def _ed25519_verify(payload: bytes, sig: bytes, vkey: bytes) -> bool:
    """RFC 8032 Ed25519 verification, pure-python transcription —
    this file's independence claim covers crypto too. Reference
    domain: ed25519 curve over GF(2^255-19), SHA-512 challenge."""
    import hashlib as _h
    p = 2 ** 255 - 19
    q = 2 ** 252 + 27742317777372353535851937790883648493
    d = -121665 * pow(121666, p - 2, p) % p
    I = pow(2, (p - 1) // 4, p)

    def xrecover(y):
        xx = (y * y - 1) * pow(d * y * y + 1, p - 2, p)
        x = pow(xx, (p + 3) // 8, p)
        if (x * x - xx) % p != 0:
            x = x * I % p
        if x % 2 != 0:
            x = p - x
        return x

    By = 4 * pow(5, p - 2, p) % p
    B = (xrecover(By), By)

    def edwards(P, Q):
        x1, y1, x2, y2 = P[0], P[1], Q[0], Q[1]
        denom = pow(1 + d * x1 * x2 * y1 * y2, p - 2, p)
        x3 = (x1 * y2 + x2 * y1) * denom % p
        denom = pow(1 - d * x1 * x2 * y1 * y2, p - 2, p)
        y3 = (y1 * y2 + x1 * x2) * denom % p
        return (x3, y3)

    def scalarmult(P, e):
        Q = (0, 1)
        while e:
            if e & 1:
                Q = edwards(Q, P)
            P = edwards(P, P)
            e >>= 1
        return Q

    def decodepoint(s):
        y = int.from_bytes(s, "little") & (2 ** 255 - 1)
        x = xrecover(y)
        if x & 1 != (s[31] >> 7):
            x = p - x
        if not (-x * x + y * y - 1 - d * x * x * y * y) % p == 0:
            raise ValueError("point not on curve")
        return (x, y)

    def decodeint(s):
        return int.from_bytes(s, "little")

    if len(sig) != 64 or len(vkey) != 32:
        return False
    R_enc, S_enc = sig[:32], sig[32:]
    try:
        R = decodepoint(R_enc)
        A = decodepoint(vkey)
    except (ValueError, IndexError):
        return False
    S = decodeint(S_enc)
    if S >= q:
        return False
    h = decodeint(_h.sha512(R_enc + vkey + payload).digest()) % q
    return scalarmult(B, S) == edwards(R, scalarmult(A, h))


def _b64decode_any(s):
    """DSSE permits standard AND URL-safe base64 — a verifier that only
    accepts the encoding its own producer emits has not implemented
    the envelope."""
    import base64
    try:                                   # standard first
        return base64.b64decode(s, validate=True)
    except Exception:
        pass
    try:                                   # then URL-safe alphabet
        return base64.b64decode(
            s.translate(str.maketrans("-_", "+/")), validate=True)
    except Exception:
        pass
    raise ValueError("not base64")


def _check_signature(env, trusted_keys) -> tuple[bool, str]:
    try:
        payload = _b64decode_any(env["payload"])
        if env["payloadType"] != \
                "application/vnd.mneme.cf-bundle+json;version=1":
            return False, ""
    except Exception:
        return False, ""
    t = env["payloadType"].encode()
    pae = (b"DSSEv1 " + str(len(t)).encode() + b" " + t + b" "
           + str(len(payload)).encode() + b" " + payload)
    for s in env.get("signatures", []):
        try:
            sig = _b64decode_any(s["sig"])
        except Exception:
            continue
        for label, vkey_hex in trusted_keys.items():
            try:
                if _ed25519_verify(pae, sig,
                                   bytes.fromhex(vkey_hex)):
                    return True, label
            except Exception:
                continue
    return False, ""


def main(path, keys_path=None, fmt="text"):
    raw = strict_loads(open(path).read())
    checks = []
    verdict = {"checks": {}, "recomputed": {}}

    def check(name, cond, detail=""):
        tag = name.split()[0]
        verdict["checks"][tag] = "PASS" if cond else "FAIL"
        if fmt != "json":
            print(f"  {'PASS' if cond else 'FAIL'}  {name}  {detail}")
        checks.append(cond)

    if fmt != "json":
        print("=" * 64)
        print("counterfactual bundle verification — mneme-cf-bundle/v1")
        print("(implementation-independent: no seasons, no mneme"
              " imports)")
        print("=" * 64)

    authenticated, signer = False, ""
    if "payloadType" in raw and "signatures" in raw:
        import base64
        trusted = {}
        kp = keys_path or os.environ.get("RTS_TRUSTED_KEYS_FILE")
        if kp and os.path.exists(kp):
            trusted = json.load(open(kp))
        elif os.environ.get("RTS_TRUSTED_KEYS"):
            trusted = json.loads(os.environ["RTS_TRUSTED_KEYS"])
        authenticated, signer = _check_signature(raw, trusted)
        b = strict_loads(_b64decode_any(raw["payload"]))
        if trusted:
            check("CF-1 DSSE envelope authentic under trusted keys",
                  authenticated, f"signer={signer!r}" if signer
                  else "no trusted signature found")
        elif fmt != "json":
            print("  NOTE: signed bundle, no trusted keys configured"
                  " — ORIGIN_UNTRUSTED verdict: integrity and"
                  " semantics are checked; provenance is not.")
    else:
        if fmt != "json":
            print("  NOTE: unsigned bundle — ORIGIN_UNTRUSTED verdict.")
        b = raw

    seal = b.pop("bundle_sha256", None)
    check("CF0 bundle digest",
          seal == hashlib.sha256(
              canonical_json(b).encode("utf-8")).hexdigest())

    sem = b.get("semantics", {})
    unknown = {k: v for k, v in sem.items()
               if v not in KNOWN_SEMANTICS.get(k, set())}
    check("CF0.5 declared semantics are implemented here",
          not unknown, f"unknown: {unknown}" if unknown else "all known")

    ev = b["evidence"]
    chains = ev["chains"]
    mid_i = b["intervention"]["memory_id"]
    seq_i = b["intervention"]["seq"]

    linked = True
    for mid, ch in chains.items():
        prev = _genesis(mid)
        sch = sorted(ch, key=lambda x: x["seq"])
        if [e["seq"] for e in sch] != list(range(len(sch))):
            linked = False   # seqs must be dense 0..N-1: no silent
                             # insertion, deletion, or renumbering
        for e in sch:
            if e["prev_hash"] != prev:
                linked = False
            if e["entry_hash"] != _entry_hash(mid, e, prev):
                linked = False
            try:
                if (canonical_json(strict_loads(e["payload_json"]))
                        != e["payload_json"]):
                    linked = False   # stored bytes must BE the
                                     # canonical bytes that were hashed
            except (ValueError, TypeError):
                linked = False
            prev = e["entry_hash"]
    check("CF1 entry_hash recomputed + linked", linked)

    inputs_ok = all(
        d["query_embedding_sha256"] == _embedding_sha256(
            d["query_embedding"])
        and ev["receipts"].get(d["receipt_sha256"], {})
        .get("query_sha256") == d["query_embedding_sha256"]
        for d in ev["decisions"])
    check("CF1.5 embeddings committed at recall time", inputs_ok)

    # CF1.7 — every sealed reference must resolve to an existing
    # object in the evidence universe of its reference type. A
    # dangling cause is an integrity failure, not an inert
    # dependency: "this cause does not exist" is not "this cause has
    # no effect". A cause pointing at an event that was later excised
    # is NOT dangling — excision is counterfactual semantics; the
    # event exists in the committed history.
    seqs = {mid: {e["seq"] for e in ch}
            for mid, ch in chains.items()}
    decs = {d["decision_id"] for d in ev["decisions"]}
    recs = set(ev["receipts"].keys())
    mids = {m["memory_id"] for m in ev["memories"]}
    dangling = []
    for mid, ch in chains.items():
        for e in ch:
            try:
                p = strict_loads(e["payload_json"])
            except (ValueError, TypeError):
                continue
            for c in p.get("causes") or []:
                k = c.get("kind")
                if k == "event":
                    tmid, tseq = c.get("memory_id"), c.get("seq")
                    if tmid not in seqs \
                            or tseq not in seqs.get(tmid, set()):
                        dangling.append(
                            f"{mid}#{e['seq']} -> event({tmid},{tseq})")
                elif k == "decision" and c.get("id") not in decs:
                    dangling.append(
                        f"{mid}#{e['seq']} -> decision({c.get('id')})")
                elif k == "receipt" and c.get("id") not in recs:
                    dangling.append(
                        f"{mid}#{e['seq']} -> receipt({c.get('id')})")
            cb = p.get("caused_by_decision_id")
            if cb is not None and cb not in decs:
                dangling.append(
                    f"{mid}#{e['seq']} caused_by_decision({cb})")
    for link in ev["cell_links"]:
        for end in ("from_id", "to_id"):
            if link.get(end) not in mids:
                dangling.append(f"cell_links.{end}={link.get(end)}")
    for s in ev.get("event_sigs") or []:
        if s["seq"] not in seqs.get(s["memory_id"], set()):
            dangling.append(
                f"event_sig ({s['memory_id']},{s['seq']}) signs "
                f"nothing — an attestation with no event")
    check("CF1.7 every sealed reference resolves", not dangling,
          f"{len(dangling)} dangling: {dangling[:4]}")

    # CF1.8 — per-actor attribution. If actor_keys declares a key for
    # an actor, every event BY that actor must carry an event_sig that
    # verifies over the entry_hash under one of that actor's keys.
    # Events by keyless actors are unsigned and legal — attribution is
    # declared capability, not global mandate. The bundle's DSSE
    # envelope signs the whole; these sigs sign WHO WROTE WHAT inside.
    _key_actor = {}
    for k in ev.get("actor_keys") or []:
        _key_actor.setdefault(k["actor_id"], {})[
            k["keyid"]] = k["verify_key_hex"]
    _sigs = {}
    for s in ev.get("event_sigs") or []:
        _sigs[(s["memory_id"], s["seq"])] = s
    bad_sig = []
    for mid, ch in chains.items():
        for e in ch:
            akeys = _key_actor.get(e["actor_id"])
            if not akeys:
                continue
            s = _sigs.get((mid, e["seq"]))
            vk = akeys.get(s["keyid"]) if s else None
            if vk is None or not _ed25519_verify(
                    e["entry_hash"].encode("ascii"),
                    bytes.fromhex(s["sig"]), bytes.fromhex(vk)):
                bad_sig.append((mid, e["seq"]))
    check("CF1.8 every keyed actor's events carry valid signatures",
          not bad_sig, f"{len(bad_sig)} bad: {bad_sig[:4]}")

    # The world as data: memory dicts whose states the verifier sets.
    memories = []
    for m in ev["memories"]:
        memories.append({
            "memory_id": m["memory_id"],
            "embedding": m["embedding_json"]["v"]
            if isinstance(m["embedding_json"], dict)
            else strict_loads(m["embedding_json"])["v"],
            "custody_status": m["custody_status"],
            "field_state": m["field_state"]})
    links = ev["cell_links"]
    t_i = next(e["created_at"] for e in chains[mid_i]
               if e["seq"] == seq_i)

    def served_at(qvec, dead, as_of):
        """Recall in the world: each chain replayed truncated at
        as_of minus dead events; states written onto copies, never
        the evidence."""
        world = []
        for m in memories:
            ch = chains.get(m["memory_id"], [])
            st, fs, _ = replay(ch, dead.get(m["memory_id"], set()),
                               as_of)
            world.append({**m, "custody_status": st,
                          "field_state": fs})
        return independent_recall(
            world, links,
            [Fraction(Decimal(x)) for x in qvec],
            top_k=rec_top_k, hops=rec_hops)

    rec_top_k = next(iter(ev["receipts"].values()))["top_k"]
    rec_hops = next(iter(ev["receipts"].values()))["hops"]

    consistent = True
    for d in ev["decisions"]:
        if d["created_at"] <= t_i:
            continue
        rec = ev["receipts"].get(d["receipt_sha256"])
        if rec is None or \
                served_at(d["query_embedding"], {},
                          d["created_at"]) != rec["served"]:
            consistent = False
    check("CF2 actual-world receipts self-consistent", consistent)

    def own_consequences(did):
        """A decision's consequences — declared causes naming it
        (causal-ontology/v2), plus the legacy DU + adjacent REINFORCED
        pair for pre-v2 events with no causes."""
        out = {}
        for mid, ch in chains.items():
            sch = sorted(ch, key=lambda x: x["seq"])
            for j, e in enumerate(sch):
                et = e["event_type"]
                p = strict_loads(e["payload_json"])
                caused = any(
                    c.get("kind") == "decision" and c.get("id") == did
                    for c in p.get("causes", []))
                if caused or (et == "DECISION_USED_MEMORY"
                              and p.get("decision_id") == did):
                    out.setdefault(mid, set()).add(e["seq"])
                    if (j + 1 < len(sch)
                            and not p.get("causes")
                            and sch[j + 1]["event_type"] == "REINFORCED"
                            and strict_loads(
                                sch[j + 1]["payload_json"]).get(
                                    "caused_by_decision_id") is None
                            and not strict_loads(
                                sch[j + 1]["payload_json"]).get(
                                    "causes")):
                        out[mid].add(sch[j + 1]["seq"])
                elif (et == "REINFORCED"
                        and p.get("caused_by_decision_id") == did):
                    out.setdefault(mid, set()).add(e["seq"])
        return out

    def closure(dead_nodes, dead_decisions):
        """Fixpoint over declared causes: an event dies if any cause
        names a dead event or dead decision — the dependency graph,
        not event types."""
        changed = True
        while changed:
            changed = False
            for mid, ch in chains.items():
                for e in ch:
                    if e["seq"] in dead_nodes.get(mid, set()):
                        continue
                    p = strict_loads(e["payload_json"])
                    if (p.get("caused_by_decision_id")
                            in dead_decisions
                            and p.get("caused_by_decision_id")
                            is not None):
                        dead_nodes.setdefault(mid, set()).add(
                            e["seq"])
                        changed = True
                        continue
                    for c in p.get("causes", []):
                        if (c.get("kind") == "decision"
                                and c.get("id") in dead_decisions):
                            dead_nodes.setdefault(mid, set()).add(
                                e["seq"])
                            changed = True
                            break
                        if (c.get("kind") == "event"
                                and c.get("seq") in dead_nodes.get(
                                    c.get("memory_id"), set())):
                            dead_nodes.setdefault(mid, set()).add(
                                e["seq"])
                            changed = True
                            break

    dead_decisions = set()
    dead = {mid_i: {seq_i}}
    divergent, ungrounded, invalidated, propagation = [], [], [], []
    for d in sorted(ev["decisions"],
                    key=lambda x: (x["created_at"], x["decision_id"])):
        if d["created_at"] <= t_i:
            continue
        dead_eval = {mid: set(ds) for mid, ds in dead.items()}
        for mid, ds in own_consequences(d["decision_id"]).items():
            dead_eval.setdefault(mid, set()).update(ds)
        cf_served = set(served_at(d["query_embedding"], dead_eval,
                                  d["created_at"]))
        fallen = sorted(m for m in d["used"] if m not in cf_served)
        if not fallen:
            continue
        divergent.append(d["receipt_sha256"])
        dead_decisions.add(d["decision_id"])
        before = {m: set(s) for m, s in dead.items()}
        # legacy fallback for pre-v2 events with no causes[]
        for mid in sorted(d["used"]):
            sch = sorted(chains.get(mid, []), key=lambda x: x["seq"])
            for j, e in enumerate(sch):
                p = strict_loads(e["payload_json"])
                if (e["event_type"] == "DECISION_USED_MEMORY"
                        and p.get("decision_id") == d["decision_id"]):
                    dead.setdefault(mid, set()).add(e["seq"])
                    if (j + 1 < len(sch)
                            and not p.get("causes")
                            and sch[j + 1]["event_type"] == "REINFORCED"
                            and strict_loads(
                                sch[j + 1]["payload_json"]).get(
                                    "caused_by_decision_id") is None
                            and not strict_loads(
                                sch[j + 1]["payload_json"]).get(
                                    "causes")):
                        dead[mid].add(sch[j + 1]["seq"])
        closure(dead, dead_decisions)
        kill = sorted(
            (m, s) for m, ds in dead.items() for s in ds
            if s not in before.get(m, set()))
        kill = [(m, s, next(e["event_type"] for e in chains[m]
                            if e["seq"] == s)) for m, s in kill]
        ungrounded.append({"decision_id": d["decision_id"],
                           "used": d["used"], "fallen": fallen})
        invalidated.extend(kill)
        propagation.append({"decision_id": d["decision_id"],
                            "invalidated": [[m, s]
                                            for m, s, _ in kill]})

    rep = b["report"]
    check("CF3 divergent receipts recomputed",
          rep["divergent_receipts"] == divergent,
          f"claimed {len(rep['divergent_receipts'])},"
          f" recomputed {len(divergent)}")
    check("CF3 ungrounded decisions recomputed",
          rep["ungrounded_decisions"] == ungrounded)
    check("CF3 invalidated set recomputed",
          [list(x) for x in rep["invalidated"]]
          == [list(x) for x in invalidated],
          f"claimed {len(rep['invalidated'])},"
          f" recomputed {len(invalidated)}")
    check("CF3 propagation edges recomputed",
          rep["propagation"] == propagation)

    cf_states = {}
    for mid, ds in dead.items():
        st, fs, cf = replay(chains[mid], ds)
        cf_states[mid] = {"custody_status": st, "field_state": fs,
                          "confidence": str(cf)}
    check("CF3 counterfactual states recomputed",
          rep["counterfactual_states"] ==
          {m: cf_states[m] for m in sorted(cf_states)})
    check("CF3 report digest seals the recomputed result",
          rep["report_sha256"] == hashlib.sha256(
              canonical_json({k: v for k, v in rep.items()
                              if k != "report_sha256"})
              .encode("utf-8")).hexdigest())

    verdict["intervention"] = {"memory_id": mid_i, "seq": seq_i}
    verdict["recomputed"] = {
        "divergent_receipts": len(divergent),
        "ungrounded_decisions": len(ungrounded),
        "invalidated_events": len(invalidated)}
    verdict["payload_type"] = raw.get("payloadType")
    verdict["protocols"] = sem
    if all(checks):
        verdict["verdict"] = ("VERIFIED_AUTHENTICATED"
                              if authenticated
                              else "VERIFIED_ORIGIN_UNTRUSTED")
        if authenticated:
            verdict["verified_by"] = [signer]
    else:
        verdict["verdict"] = "REJECTED"

    if fmt == "json":
        print(json.dumps(verdict, indent=1, sort_keys=True))
    else:
        print()
        if all(checks):
            if authenticated:
                print(f"VERIFIED_AUTHENTICATED — signed by {signer!r};"
                      " the cascade recomputes from sealed evidence.")
            else:
                print("VERIFIED_INTEGRITY_AND_SEMANTICS —"
                      " ORIGIN_UNTRUSTED: the cascade recomputes, but"
                      " no trusted signature anchors this history. A"
                      " well-formed forgery could reach this line.")
        else:
            print("REJECTED — the report does not follow from the"
                  " evidence.")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(
        description="Independent mneme-cf-bundle/v1 verifier")
    ap.add_argument("bundle")
    ap.add_argument("trusted_keys", nargs="?")
    ap.add_argument("--format", choices=["text", "json"],
                    default="text")
    a = ap.parse_args()
    sys.exit(main(a.bundle, a.trusted_keys, a.format))
