#!/usr/bin/env python3
"""Deterministic generator for the mneme-cf-bundle/v1 conformance
corpus. The world is a function of operations.json — there is no
clock and no randomness in this path: timestamps come from a fixed
base counter, embeddings from the deterministic local tokenizer, and
the signing key is a fixed TEST-ONLY seed.

  python3 generate.py            regenerate golden/ + positive/
  python3 generate.py --check    regenerate to a temp dir and require
                                 byte-identical artifacts — the
                                 committed corpus never gets touched
                                 by verification.

NEVER regenerate to make a failing check pass. If the artifacts
drifted, the protocol drifted: bump the semantic version, regenerate
deliberately, and show the diff.
"""

import base64
import hashlib
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", ".."))

# Force the deterministic path BEFORE any project import reads env.
for var in ("NEBIUS_API_KEY", "RTS_KASSANDRA_SALT",
            "RTS_ENFORCE_KASSANDRA_SALT"):
    os.environ.pop(var, None)
os.environ["SEASONS_EMBED_MODEL"] = "conformance-stub"

OPS = json.load(open(os.path.join(HERE, "operations.json")))
GOLDEN = os.path.join(HERE, "golden")
POSITIVE = os.path.join(HERE, "positive")


def _clock(seq_counter):
    base = datetime.fromisoformat(OPS["time_base"])
    step = OPS["time_step_us"]

    def now_ts():
        t = base + timedelta(microseconds=step * next(seq_counter))
        return t.strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")
    return now_ts


def build(out_dir):
    """Replay operations.json against a frozen clock and write every
    artifact a verifier consumes."""
    counter = iter(range(1000000))
    ts = _clock(counter)

    from mneme import authority, custody
    custody.now_ts = ts                       # the clock is ours now
    gid = iter(range(1000000))
    authority._new_grant_id = lambda: \
        f"grant-{next(gid):012d}"             # so are grant ids
    from seasons import agent, trajectory
    from mneme.canonical import canonical_json

    a = agent.SeasonsAgent(
        key_seed=OPS["agent_seed_test_only"])
    intervention = {}
    for op in OPS["operations"]:
        kind = op["op"]
        if kind == "remember":
            a.remember(op["text"])
        elif kind == "taint":
            custody.append_event(
                a.cur, memory_id=op["memory_id"],
                event_type="TAINT_FLAGGED", actor_id="seasons-agent",
                reason=op["reason"], created_at=ts(), payload={})
            a.cur.execute(
                "UPDATE memories SET custody_status='TAINT_FLAGGED'"
                " WHERE memory_id=?", (op["memory_id"],))
            a.conn.commit()
        elif kind == "rehabilitate":
            custody.append_event(
                a.cur, memory_id=op["memory_id"],
                event_type="REHABILITATED", actor_id="seasons-agent",
                reason=op["reason"], created_at=ts(), payload={})
            a.cur.execute(
                "UPDATE memories SET custody_status='CLEAN'"
                " WHERE memory_id=?", (op["memory_id"],))
            a.conn.commit()
        elif kind == "ask":
            a.ask(op["question"])
        elif kind == "export_signed_bundle":
            seq = next(e["seq"] for e in trajectory.load_chain(
                a.cur, op["memory_id"])
                if e["event_type"] == op["excise_event_type"])
            intervention = {"memory_id": op["memory_id"], "seq": seq}

    from nacl.signing import SigningKey
    seed = OPS["signing_seed_test_only"]
    vk = SigningKey(bytes.fromhex(seed)).verify_key.encode().hex()

    env = trajectory.export_cf_bundle_signed(
        a.cur, memory_id=intervention["memory_id"],
        excise_seq=intervention["seq"],
        sign_seed_hex=seed, keyid=OPS["keyid"])
    report = json.loads(base64.b64decode(env["payload"]))["report"]

    os.makedirs(os.path.join(out_dir, "golden"), exist_ok=True)
    os.makedirs(os.path.join(out_dir, "positive"), exist_ok=True)

    json.dump(env, open(os.path.join(
        out_dir, "golden", "canonical.dsse.json"), "w"), indent=1)
    json.dump({OPS["keyid"]: vk}, open(os.path.join(
        out_dir, "golden", "trusted-keys.json"), "w"), indent=1)
    json.dump({
        "verdict": "VERIFIED_AUTHENTICATED",
        "signer": OPS["keyid"],
        "divergent_receipts": len(report["divergent_receipts"]),
        "ungrounded_decisions": len(report["ungrounded_decisions"]),
        "invalidated_events": len(report["invalidated"]),
        "counterfactual_state":
            report["counterfactual_states"][intervention["memory_id"]],
        "report_sha256": report["report_sha256"],
    }, open(os.path.join(out_dir, "golden", "expected.json"), "w"),
        indent=1)

    manifest = {
        "protocol_manifest": "mneme-cf-manifest/1",
        "comment": "exact semantic versions this corpus is sealed "
                   "under — a verifier answers only for versions it "
                   "implemented and tested",
        "semantics": {
            "bundle_protocol": "mneme-cf-bundle/v1",
            "causal_rewind_protocol": "cf-cascade/v2",
            "causal_ontology": "2.0.0",
            "canonicalization_protocol": "mneme-cjson/1.0.0",
            "payload_type":
                "application/vnd.mneme.cf-bundle+json;version=1",
            "signature_profile": "dsse-ed25519-rfc8032/v1",
        },
        "artifacts": {},
    }

    # Positive compatibility vectors — alternate-but-legal encodings
    # of the SAME authenticated payload.
    url_env = dict(env)
    url_env["payload"] = base64.urlsafe_b64encode(
        base64.b64decode(env["payload"])).decode()
    url_env["signatures"] = [{
        "keyid": s["keyid"],
        "sig": base64.urlsafe_b64encode(
            base64.b64decode(s["sig"])).decode()}
        for s in env["signatures"]]
    json.dump(url_env, open(os.path.join(
        out_dir, "positive", "base64url.dsse.json"), "w"), indent=1)

    nok = dict(env)
    nok["signatures"] = [{"sig": s["sig"]}
                         for s in env["signatures"]]
    json.dump(nok, open(os.path.join(
        out_dir, "positive", "empty-keyid.dsse.json"), "w"), indent=1)

    ext = dict(env)
    ext["extensions"] = {"note": "unknown envelope fields are"
                         " ignored per DSSE"}
    json.dump(ext, open(os.path.join(
        out_dir, "positive", "extra-field.dsse.json"), "w"), indent=1)

    import copy as _c
    ms = _c.deepcopy(env)
    ms["signatures"] = [{
        "keyid": "mallory",
        "sig": base64.b64encode(b"0" * 64).decode()}] \
        + env["signatures"]
    json.dump(ms, open(os.path.join(
        out_dir, "positive", "multi-sig.dsse.json"), "w"), indent=1)

    # legacy-v1 positive: the same world with every v2 antecedent
    # field stripped (causes[] AND caused_by_decision_id) — evidence
    # in the pre-ontology shape. Under the unified rule it must
    # produce the SAME verdict: adjacency covers exactly the events
    # the write path would have declared.
    bundle_now = json.loads(base64.b64decode(env["payload"]))
    legacy = _c.deepcopy(bundle_now)
    for ch in legacy["evidence"]["chains"].values():
        for e in ch:
            p = json.loads(e["payload_json"])
            p.pop("causes", None)
            p.pop("caused_by_decision_id", None)
            e["payload_json"] = canonical_json(p)
    # A TRUE v1 bundle also carries a v1 report: the killed set under
    # the adjacency rule excludes events whose only antecedent is an
    # event-cause (STATE_CHANGED promotions). Replay's arithmetic
    # guard makes the counterfactual states identical either way —
    # the promotion fires, the threshold check fails, NEUTRAL — so
    # only invalidated/propagation lists drop entries.
    dead_types = {et for _, _, et in legacy["report"]["invalidated"]}
    rep = legacy["report"]
    rep["invalidated"] = [i for i in rep["invalidated"]
                          if i[2] != "STATE_CHANGED"]
    for edge in rep["propagation"]:
        edge["invalidated"] = [
            i for i in edge["invalidated"]
            if legacy["evidence"]["chains"][i[0]][i[1]]
               ["event_type"] != "STATE_CHANGED"]
    rep["report_sha256"] = hashlib.sha256(
        canonical_json({k: v for k, v in rep.items()
                        if k != "report_sha256"}).encode()).hexdigest()
    # and it declares what it is: a v1 bundle knows no causal ontology
    legacy["semantics"]["causal_rewind_protocol"] = "cf-cascade/v1"
    legacy["semantics"].pop("causal_ontology", None)
    # recompute every entry_hash after the payload rewrite — a valid
    # v1 chain, not a forgery
    from mneme import chain as _chain
    from mneme import custody as _cust
    for mid, ch in legacy["evidence"]["chains"].items():
        prev = _cust.genesis_hash(mid)
        for e in ch:
            e["prev_hash"] = prev
            e["entry_hash"], _ = _chain.compute_hash(
                _cust.SPEC, prev_hash=prev, subject_id=mid,
                seq=e["seq"], event_type=e["event_type"],
                actor_id=e["actor_id"], reason=e["reason"],
                created_at=e["created_at"],
                payload=json.loads(e["payload_json"]))
            prev = e["entry_hash"]
    # a true v1 bundle predates the attribution layer — no per-actor
    # keys, no per-event signatures (and the copied sigs would cover
    # the pre-rewrite hashes anyway)
    legacy["evidence"].pop("actor_keys", None)
    legacy["evidence"].pop("event_sigs", None)
    legacy.pop("bundle_sha256", None)
    legacy["bundle_sha256"] = hashlib.sha256(
        canonical_json(legacy).encode()).hexdigest()
    lb = json.dumps(legacy, indent=1).encode()
    pt = env["payloadType"].encode()
    pae = (b"DSSEv1 " + str(len(pt)).encode() + b" " + pt + b" " +
           str(len(lb)).encode() + b" " + lb)
    leg_env = _c.deepcopy(env)
    leg_env["payload"] = base64.b64encode(lb).decode()
    leg_env["signatures"] = [{
        "keyid": OPS["keyid"],
        "sig": base64.b64encode(
            SigningKey(bytes.fromhex(seed)).sign(pae).signature
        ).decode()}]
    json.dump(leg_env, open(os.path.join(
        out_dir, "positive", "legacy-v1.dsse.json"), "w"), indent=1)

    # Negative corpus — sealed mutants with their expected failure.
    # Each names the check that must kill it, not merely "rejected".
    import copy as _copy
    import hashlib as _hl
    bundle = json.loads(base64.b64decode(env["payload"]))
    mut_dir = os.path.join(out_dir, "mutants")
    os.makedirs(mut_dir, exist_ok=True)

    def reseal(bb):
        bb["bundle_sha256"] = _hl.sha256(
            canonical_json(bb).encode()).hexdigest()
        return bb

    def mutant(name, fn, expect):
        bb = _copy.deepcopy(bundle)
        fn(bb)
        json.dump(reseal(bb), open(
            os.path.join(mut_dir, name + ".json"), "w"), indent=1)
        json.dump({"expect": "REJECTED", "check": expect},
                  open(os.path.join(mut_dir, name + ".expected.json"),
                       "w"), indent=1)

    mutant("wrong-seq",
           lambda bb: bb["intervention"].__setitem__("seq", 99),
           "CF3")
    mutant("tampered-event",
           lambda bb: bb["evidence"]["chains"]["mem-0000"][1]
           .__setitem__("reason", "forged reason"),
           "CF1")
    mutant("dropped-edge",
           lambda bb: bb["report"]["propagation"].pop(0),
           "CF3")
    mutant("orphan-invalidation",
           lambda bb: bb["report"]["invalidated"].append(
               ["mem-0000", 0, "REINFORCED"]),
           "CF3")
    mutant("phantom-ungrounding",
           lambda bb: bb["report"]["ungrounded_decisions"].append(
               {"decision_id": "dec-x", "used": ["mem-0000"],
                "fallen": ["mem-0000"]}),
           "CF3")
    mutant("chain-deletion",
           lambda bb: bb["evidence"]["chains"]["mem-0000"].pop(1),
           "CF1")
    mutant("unknown-protocol",
           lambda bb: bb["semantics"].__setitem__(
               "causal_rewind_protocol", "cf-cascade/v99"),
           "CF0.5")
    def _transitivity_break(bb):
        # sever the event-cause: a promotion no longer names the
        # REINFORCED that produced it — the recomputed cascade keeps
        # it alive where the report claims it dead
        for ch in bb["evidence"]["chains"].values():
            for e in ch:
                p = json.loads(e["payload_json"])
                if (e["event_type"] == "STATE_CHANGED"
                        and p.get("causes")):
                    p["causes"] = []
                    e["payload_json"] = canonical_json(p)
                    return
    mutant("transitivity-break", _transitivity_break, "CF3")

    def _causes_stripped(bb):
        # remove BOTH spellings of the decision-cause from a killed
        # REINFORCED — recomputation keeps it alive, report claims
        # it dead
        dead_r = {m: s for m, s, et in
                  bb["report"]["invalidated"] if et == "REINFORCED"}
        for mid, s in dead_r.items():
            e = bb["evidence"]["chains"][mid][s]
            p = json.loads(e["payload_json"])
            p.pop("causes", None)
            p.pop("caused_by_decision_id", None)
            e["payload_json"] = canonical_json(p)
            return
    mutant("causes-stripped", _causes_stripped, "CF1")

    def _phantom_cause(bb):
        # a well-formed, correctly-hashed chain whose declared cause
        # resolves to NOTHING — the malicious producer's trick: sign a
        # lie properly. The event-cause points at a seq that does not
        # exist; every hash is recomputed so CF1 passes and only
        # referential integrity (CF1.7) can reject it.
        for mid, ch in bb["evidence"]["chains"].items():
            for e in ch:
                p = json.loads(e["payload_json"])
                if e["event_type"] == "STATE_CHANGED" \
                        and p.get("causes"):
                    p["causes"] = [{"kind": "event",
                                    "memory_id": mid, "seq": 4000000}]
                    e["payload_json"] = canonical_json(p)
                    break
            else:
                continue
            break
        # recompute the whole chain's hashes — the forgery must be
        # structurally impeccable, failing only at reference check
        from mneme import chain as _ch
        from mneme import custody as _cu
        prev = _cu.genesis_hash(mid)
        for e in bb["evidence"]["chains"][mid]:
            e["prev_hash"] = prev
            e["entry_hash"], _ = _ch.compute_hash(
                _cu.SPEC, prev_hash=prev, subject_id=mid,
                seq=e["seq"], event_type=e["event_type"],
                actor_id=e["actor_id"], reason=e["reason"],
                created_at=e["created_at"],
                payload=json.loads(e["payload_json"]))
            prev = e["entry_hash"]
    mutant("phantom-cause", _phantom_cause, "CF1.7")

    def _wrong_actor_sig(bb):
        # a real Ed25519 signature over the right entry_hash — but
        # under a key that belongs to NOBODY here. The chain is
        # untouched; attribution is the only lie.
        from nacl.signing import SigningKey
        rogue = SigningKey(bytes.fromhex("cc" * 32))
        ev = bb["evidence"]
        first = ev["event_sigs"][0]
        e = next(e for e in ev["chains"][first["memory_id"]]
                 if e["seq"] == first["seq"])
        first["sig"] = rogue.sign(
            e["entry_hash"].encode("ascii")).signature.hex()
    mutant("wrong-actor-sig", _wrong_actor_sig, "CF1.8")

    mutant("coherent-false",
           lambda bb: (bb["report"].__setitem__(
                           "divergent_receipts", []),
                       bb["report"].__setitem__(
                           "ungrounded_decisions", []),
                       bb["report"].__setitem__("invalidated", []),
                       bb["report"].__setitem__("propagation", []),
                       bb["report"].__setitem__(
                           "counterfactual_states", {}),
                       bb["report"].__setitem__(
                           "report_sha256", _hl.sha256(
                               canonical_json(
                                   {k: v for k, v in
                                    bb["report"].items()
                                    if k != "report_sha256"})
                               .encode()).hexdigest())),
           "CF3")
    open(os.path.join(mut_dir, "dup-keys.json"), "w").write(
        '{"protocol": "a", "protocol": "b"}')
    json.dump({"expect": "REJECTED", "check": "parse"},
              open(os.path.join(mut_dir, "dup-keys.expected.json"),
                   "w"), indent=1)
    npt = _copy.deepcopy(env)
    del npt["payloadType"]
    json.dump(npt, open(os.path.join(
        mut_dir, "missing-payloadtype.json"), "w"), indent=1)
    json.dump({"expect": "REJECTED", "check": "parse/schema"},
              open(os.path.join(
                  mut_dir, "missing-payloadtype.expected.json"),
                  "w"), indent=1)

    rels = ["golden/canonical.dsse.json", "golden/expected.json",
            "golden/trusted-keys.json",
            "positive/base64url.dsse.json",
            "positive/empty-keyid.dsse.json",
            "positive/extra-field.dsse.json"]
    mut_dir2 = os.path.join(out_dir, "mutants")
    for f in sorted(os.listdir(mut_dir2)):
        rels.append(f"mutants/{f}")
    for rel in rels:
        data = open(os.path.join(out_dir, rel), "rb").read()
        manifest["artifacts"][rel] = hashlib.sha256(data).hexdigest()
    json.dump(manifest, open(os.path.join(
        out_dir, "protocol-manifest.json"), "w"), indent=1)

    return len(report["divergent_receipts"]), \
        len(report["ungrounded_decisions"]), len(report["invalidated"])


def main():
    if "--check" in sys.argv:
        tmp = tempfile.mkdtemp(prefix="cf-corpus-")
        build(tmp)
        drift = []
        for root, _, files in os.walk(tmp):
            for f in files:
                a_ = os.path.join(root, f)
                b_ = os.path.join(HERE, os.path.relpath(a_, tmp))
                if not os.path.exists(b_):
                    drift.append(f"missing: {os.path.relpath(a_, tmp)}")
                elif open(a_, "rb").read() != open(b_, "rb").read():
                    drift.append(f"drifted: {os.path.relpath(a_, tmp)}")
        extra = []
        for root, _, files in os.walk(HERE):
            for f in files:
                rel = os.path.relpath(os.path.join(root, f), HERE)
                if (rel.startswith(("golden/", "positive/"))
                        or rel == "protocol-manifest.json"):
                    if not os.path.exists(os.path.join(tmp, rel)):
                        extra.append(rel)
        for e in extra:
            drift.append(f"untracked: {e}")
        if drift:
            print("DRIFT — the corpus no longer regenerates:")
            for d in drift:
                print(" ", d)
            sys.exit(1)
        print("no drift — the corpus regenerates byte-for-byte.")
        return

    d, u, i = build(HERE)
    print(f"golden: {d} divergent, {u} ungrounded, {i} invalidated")
    print(f"artifacts in {HERE}")


if __name__ == "__main__":
    main()
