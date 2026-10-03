"""Remember the Seasons — CLI.

    python3 -m seasons <cmd> [args]        (from product/)

    remember "text"             store a memory
    ask "question"              recall + answer (receipt printed)
    import <vault-dir>          Obsidian .md -> memories + links
    update <mem> "text"         supersession (new memory, lineage)
    forget <mem> | revive <mem> audited FORGOTTEN / back to NEUTRAL
    link <a> <b>                explicit RESONANT edge
    chain <mem>                 the memory's biography
    provenance <trace> [depth]  summary|direct|impact|counterfactual
    whatif <mem> <seq> "q"      excise transition, replay recall
    search "text"               recall without answering (browse)
    memories                    list the field
    bundle > out.json           sealed evidence for offline audit
    serve [port]                the demo UI

Everything mutating writes a custody event; every command works on the
same sqlite field (RTS_DB_PATH or ./seasons.db).
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from seasons import agent
from mneme import field
from seasons import embed


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    cmd, args = argv[1], argv[2:]
    a = agent.SeasonsAgent(
        db_path=os.environ.get("RTS_DB_PATH", "seasons.db"))

    def need(n: int) -> None:
        if len(args) < n:
            print(f"{cmd} needs {n} arg(s)", file=sys.stderr)
            sys.exit(2)

    if cmd == "remember":
        need(1)
        print(a.remember(args[0]))
    elif cmd == "ask":
        need(1)
        r = a.ask(args[0])
        print(r["answer"])
        print(f"  receipt {r['receipt'][:24]}… served {r['served']} "
              f"used {r['used']} decision {r['decision']}")
    elif cmd == "import":
        need(1)
        r = a.import_vault(args[0])
        print(f"imported {r['imported']} notes, {r['links']} links")
        for n, m in r["name_to_id"].items():
            print(f"  {n} -> {m}")
    elif cmd == "update":
        need(2)
        print(a.update(args[0], args[1]))
    elif cmd in ("forget", "revive"):
        need(1)
        getattr(a, cmd)(args[0])
        print(f"{args[0]} -> {'FORGOTTEN' if cmd == 'forget' else 'NEUTRAL'}")
    elif cmd == "link":
        need(2)
        a.link(args[0], args[1])
        print(f"{args[0]} -> {args[1]} RESONANT")
    elif cmd == "backlinks":
        need(1)
        for b in a.backlinks(args[0]):
            print(f"  {b['from']} -{b['link_type']}-> {args[0]} "
                  f"({'auto' if b['auto'] else 'manual'})")
    elif cmd == "outlinks":
        need(1)
        for o in a.outlinks(args[0]):
            print(f"  {args[0]} -{o['link_type']}-> {o['to']}")
    elif cmd == "chain":
        need(1)
        for e in a.chain(args[0]):
            print(f"  {e[0]:>3} {e[1]:<22} {e[2]:<14} {e[4][:60]}")
    elif cmd == "whatif":
        need(3)
        r = a.what_if_transition(args[2], args[0],
                                 excise_seq=int(args[1]))
        print(f"actual : {r['actual']['served']}")
        print(f"cf     : {r['counterfactual']['served']}")
        print(f"delta  : {r['delta']}")
        print(f"report {r['report_sha256'][:24]}… (hypothetical)")
    elif cmd == "search":
        need(1)
        hits, receipt = field.recall(
            a.cur,
            query_embedding=field.quantize_embedding(embed.embed(args[0])))
        for h in hits:
            print(f"  {h.memory_id}  [{h.field_state}]  {h.content[:60]}")
        print(f"  receipt {receipt.receipt_sha256[:24]}… (not persisted — browse)")
    elif cmd == "provenance":
        need(1)
        print(json.dumps(
            a.request_provenance(args[0],
                                 depth=args[1] if len(args) > 1
                                 else "summary"), indent=2))
    elif cmd == "memories":
        a.cur.execute(
            "SELECT memory_id, field_state, custody_status, content"
            " FROM memories ORDER BY memory_id")
        for mid, fs, cs, c in a.cur.fetchall():
            print(f"  {mid}  [{fs}/{cs}]  {c[:70]}")
    elif cmd == "bundle":
        print(a.export_bundle())
    elif cmd == "serve":
        import subprocess
        subprocess.call([sys.executable, "server.py",
                         args[0] if args else "8420"])
    else:
        print(f"unknown command {cmd!r} — try help", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
