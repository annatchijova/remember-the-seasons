#!/usr/bin/env python3
"""Remember the Seasons — demo server (stdlib-only, no deps).

    python3 server.py [port]          # default :8420
    NEBIUS_API_KEY=... python3 server.py   # live LLM + embeddings

One page. The point of the demo is that every answer carries
verifiable evidence and every transition can be replayed
counterfactually — the UI shows exactly that, nothing else.
"""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from seasons import agent

A = agent.SeasonsAgent()


def seed():
    A.cur.execute("SELECT COUNT(*) FROM memories")
    if A.cur.fetchone()[0] == 0:
        for c in [
            "The deploy gate requires staging to pass.",
            "Rollbacks run via `ops rollback <release>`.",
            "Maria prefers short standups before 10am.",
            "Incident 114: hotfix skipped staging and took prod down.",
        ]:
            A.remember(c)


PAGE = r"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Remember the Seasons</title>
<style>
:root{--g:#76b900;--bg:#0b0f0a;--p:#121810;--dim:#8fa383;--tx:#e7f0e3;--warn:#e8b33d}
*{box-sizing:border-box;margin:0}
body{background:var(--bg);color:var(--tx);font:14px/1.5 ui-monospace,monospace;padding:24px;max-width:1100px;margin:auto}
h1{color:var(--g);font-size:22px;letter-spacing:2px}
.sub{color:var(--dim);margin-bottom:20px}
.panel{background:var(--p);border:1px solid #22301c;border-radius:8px;padding:16px;margin-bottom:14px}
h2{color:var(--g);font-size:13px;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:10px}
input,select,button{background:#0a0e08;border:1px solid #2c4220;color:var(--tx);padding:9px 12px;border-radius:6px;font:inherit}
button{background:var(--g);color:#0b0f0a;font-weight:700;cursor:pointer;border:none}
button.ghost{background:transparent;color:var(--g);border:1px solid var(--g)}
.row{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
.mem{border-left:3px solid var(--g);padding:6px 10px;margin:6px 0;background:#0d130b}
.mem .id{color:var(--g)}
.badge{display:inline-block;font-size:11px;padding:1px 8px;border-radius:9px;margin-left:8px;border:1px solid}
.b-REINFORCED{color:var(--g);border-color:var(--g)}
.b-NEUTRAL{color:var(--dim);border-color:var(--dim)}
.b-FORGOTTEN{color:#c66;border-color:#c66}
.ev{padding:3px 0 3px 14px;border-left:2px solid #22301c;color:var(--dim);font-size:12px}
.ev b{color:var(--tx)}
.ev .seq{color:var(--g);display:inline-block;width:22px}
.hash{color:#5a7050;font-size:11px;word-break:break-all}
.split{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.delta{color:var(--warn)}
.hyp{color:var(--warn);border:1px solid var(--warn);padding:2px 8px;border-radius:9px;font-size:11px}
pre{white-space:pre-wrap;font-size:12px;color:var(--dim)}
.ans{background:#0d130b;border-radius:6px;padding:10px;margin:8px 0}
.ctl{opacity:.85;font-size:12px}
a{color:var(--g)}
</style></head><body>
<h1>REMEMBER THE SEASONS</h1>
<div class="sub">persistent agent memory — same query, different history, verifiable why.
<span id="backend">…</span></div>

<div class="panel"><h2>Ask the field</h2>
<div class="row">
<input id="q" size="46" placeholder="What do I need before deploying?" value="What do I need before deploying?">
<button onclick="ask()">ask</button>
<button class="ghost" onclick="learn()">remember something new</button>
<button class="ghost" onclick="season()">replay a past season</button>
</div>
<div id="answer"></div></div>

<div class="split">
<div class="panel"><h2>Memories — operational state</h2><div id="mems"></div></div>
<div class="panel"><h2>Provenance — click a memory</h2><div id="prov">select a memory to open its chain.</div></div>
</div>

<div class="panel"><h2>Trajectory counterfactual — what if it hadn't happened?</h2>
<div class="row"><select id="ev" disabled><option>select a memory above to inspect excisable events</option></select>
<button id="cfbtn" onclick="cf()" disabled>excise &amp; replay</button>
<span class="ctl">runs the SAME production recall in a SAVEPOINT, then rolls back.</span></div>
<div id="cf"></div></div>

<script>
const $=id=>document.getElementById(id);
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

async function ask(){
  const r=await fetch('/api/ask?q='+encodeURIComponent($('q').value));
  const d=await r.json();
  $('answer').innerHTML=`<div class="ans"><b>answer:</b> ${esc(d.answer)}</div>
    <div class="hash">receipt ${d.receipt} · decision ${d.decision||'—'} · served ${JSON.stringify(d.served)} · used ${JSON.stringify(d.used)}</div>`;
  refresh();
}
const NEW_MEMORIES=[
 'Policy change: staging gate is now mandatory for ALL deploys, including hotfixes.',
 'On-call rotations changed: deploys freeze Friday after 15:00.',
 'Incident 114 follow-up: the rollback playbook now requires a second pair of eyes.',
 'Maria asked that her deploy requests always cite the staging run id.'];
let mi=0;
async function learn(){
  if(mi>=NEW_MEMORIES.length) return;
  await fetch('/api/remember?content='+encodeURIComponent(NEW_MEMORIES[mi++]));
  refresh();
}
async function season(){
  const r=await fetch('/api/season?q='+encodeURIComponent($('q').value));
  const d=await r.json();
  $('answer').innerHTML=`<div class="ans"><b>replayed season:</b> served ${JSON.stringify(d.served)}</div>
    <div class="hash">receipt ${d.receipt} — computed from chains truncated at as_of, not a stored snapshot</div>`;
}
async function refresh(){
  const ms=await (await fetch('/api/memories')).json();
  $('mems').innerHTML=ms.map(m=>`<div class="mem" onclick="prov('${m.memory_id}')">
    <span class="id">${m.memory_id}</span>${esc(m.content)}
    <span class="badge b-${m.field_state}">${m.field_state}</span></div>`).join('');
}
async function prov(mid){
  const p=await (await fetch(`/api/provenance?id=${mid}&depth=counterfactual`)).json();
  const evs=p.chains[mid].map(e=>`<div class="ev"><span class="seq">${e.seq}</span>
    <b>${e.event_type}</b> by ${e.actor_id}</div>`).join('');
  $('prov').innerHTML=`<div class="id" style="color:var(--g)">${mid}</div>${evs}
    <div class="hash">impact: receipts ${p.impact[mid].direct_receipts.length}, decisions ${p.impact[mid].direct_decisions.length}</div>`;
  const opts=p.excisable[mid].map(e=>`<option value="${mid}:${e.seq}">excise ${mid} seq ${e.seq} (${e.event_type})</option>`).join('');
  $('ev').innerHTML=opts||'<option>no excisable transitions on this chain</option>';
  $('ev').disabled=!opts; $('cfbtn').disabled=!opts;
}
async function cf(){
  const [mid,seq]=$('ev').value.split(':');
  const r=await fetch(`/api/whatif?q=${encodeURIComponent($('q').value)}&mid=${mid}&seq=${seq}`);
  const d=await r.json();
  $('cf').innerHTML=`<div class="split">
    <div><b>actual</b><div class="ans">${JSON.stringify(d.actual.served)}</div></div>
    <div><b>counterfactual</b> <span class="hyp">hypothetical</span>
      <div class="ans">${JSON.stringify(d.counterfactual.served)}</div></div></div>
    <div class="delta">Δ removed=${JSON.stringify(d.delta.removed)} entered=${JSON.stringify(d.delta.entered)} rank_changed=${JSON.stringify(d.delta.rank_changed)}</div>
    <div class="hash">report ${d.report_sha256} · hypothetical=${d.hypothetical} · excised ${d.excised.event_type} at seq ${d.excised.seq} → cf state ${JSON.stringify(d.counterfactual_state)}</div>`;
}
fetch('/api/info').then(r=>r.json()).then(d=>$('backend').textContent=d.backend);
refresh();
</script></body></html>"""


class H(BaseHTTPRequestHandler):
    def _j(self, obj, code=200):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        try:
            if u.path == "/":
                b = PAGE.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)
            elif u.path == "/api/info":
                import os
                if os.environ.get("NEBIUS_API_KEY"):
                    self._j({"backend": "running on Nebius Token Factory · "
                             + os.environ.get(
                                 "NEBIUS_MODEL",
                                 "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B")
                             + " + Qwen3-Embedding-8B"})
                else:
                    self._j({"backend": "offline deterministic stub — "
                             "no NEBIUS_API_KEY"})
            elif u.path == "/api/ask":
                self._j(A.ask(q["q"][0]))
            elif u.path == "/api/remember":
                self._j({"memory_id": A.remember(q["content"][0])})
            elif u.path == "/api/season":
                rows = A.cur.execute(
                    "SELECT MIN(created_at) FROM custody_chain").fetchone()
                d = A.season(q["q"][0], as_of=rows[0])
                self._j({"served": [h[0] for h in d["hits"]],
                         "hits": d["hits"], "receipt": d["receipt"]})
            elif u.path == "/api/memories":
                A.cur.execute(
                    "SELECT memory_id, content, custody_status,"
                    " field_state, confidence FROM memories"
                    " ORDER BY memory_id")
                self._j([{"memory_id": r[0], "content": r[1],
                          "custody_status": r[2], "field_state": r[3],
                          "confidence": r[4]}
                         for r in A.cur.fetchall()])
            elif u.path == "/api/provenance":
                self._j(A.request_provenance(
                    q["id"][0], depth=q.get("depth", ["summary"])[0]))
            elif u.path == "/api/whatif":
                self._j(A.what_if_transition(
                    q["q"][0], q["mid"][0], excise_seq=int(q["seq"][0])))
            else:
                self._j({"error": "unknown"}, 404)
        except Exception as e:  # demo server: surface, don't hide
            self._j({"error": str(e)}, 500)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    seed()
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8420
    print(f"Remember the Seasons → http://localhost:{port}")
    HTTPServer(("0.0.0.0", port), H).serve_forever()
