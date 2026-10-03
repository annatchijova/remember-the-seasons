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

    a = agent.SeasonsAgent()
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
            "causal_rewind_protocol": "cf-cascade/v1",
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
        import hashlib
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
