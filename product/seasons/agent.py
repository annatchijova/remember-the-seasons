"""SeasonsAgent — the product loop.

    remember(text)      -> field.store            (custody event: STORED)
    ask(question)       -> recall -> llm -> decision -> reinforce
                           (receipt + DECISION_USED_MEMORY + REINFORCED
                            / STATE_CHANGED events, all in one txn)
    season(question, t) -> recall(as_of=t)        (historical view:
                           what would this query have returned then?)
    what_if(question, world) -> compare_worlds    (sealed counterfactual)

Reinforcing served memories is the deliberate, audited act that closes
the adaptive loop the research measured: recall -> use -> reinforcement
-> future state. Skipping it would make the field a static index.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from mneme import causality, counterfactual, custody, field

from . import actors, db, embed, llm, signing

POLICY_VERSION = "seasons/0.1"


class SeasonsAgent:
    def __init__(self, db_path: str = ":memory:",
                 actor_id: str = actors.AGENT,
                 key_seed: str | None = None):
        self.actor = actor_id
        self.keyid = None
        self.conn: sqlite3.Connection = db.open_db(db_path)
        self.cur = self.conn.cursor()
        self.cur.execute("SELECT COUNT(*) FROM actors")
        if self.cur.fetchone()[0] == 0:
            actors.bootstrap(self.cur)
            self.conn.commit()
        if key_seed is not None:
            # per-actor Ed25519: this agent's writes are attributable —
            # the key registers in the field, the signer signs each of
            # THIS actor's events inside their own transaction
            vk = signing.verify_key_hex(key_seed)
            self.keyid = vk[:16]
            self.cur.execute(
                "INSERT OR IGNORE INTO actor_keys "
                "(actor_id, keyid, verify_key_hex, created_at) "
                "VALUES (?, ?, ?, ?)",
                (actor_id, self.keyid, vk, custody.now_ts()))
            self.conn.commit()

            # NOTE: the signer closes over THIS cursor — rebinding
            # self.cur after init leaves signatures writing to the
            # stale cursor. Agents keep one conn for their lifetime.
            def _sign(entry, _cur=self.cur, _seed=key_seed):
                _cur.execute(
                    "INSERT INTO event_sigs (memory_id, seq, keyid,"
                    " sig) VALUES (?, ?, ?, ?)",
                    (entry.memory_id, entry.seq, self.keyid,
                     signing.sign_entry_hash(entry.entry_hash, _seed)))
            custody.entry_signers[actor_id] = (self.conn, _sign)

    def _next_memory_id(self) -> str:
        # the counter is a property of the FIELD, not of this process —
        # two agents sharing the field must not hand each other state
        self.cur.execute("SELECT COUNT(*) FROM memories")
        return f"mem-{self.cur.fetchone()[0]:04d}"

    def _next_decision_id(self) -> str:
        self.cur.execute("SELECT COUNT(*) FROM seasons_decisions")
        return f"dec-{self.cur.fetchone()[0]:04d}"

    # ---------- write path ----------

    def remember(self, content: str, *, topic: str | None = None,
                 claim: str | None = None) -> str:
        # Concurrent writers may compute the same next id before either
        # commits: UNIQUE rejects the loser, who must retry — the field
        # assigns, the writer accepts. Bounded retries; a persistent
        # collision is a real failure, not a retry storm.
        qemb, prov = embed.embed_with_provenance(content)
        for _ in range(4):
            mid = self._next_memory_id()
            try:
                field.store(
                    self.cur, memory_id=mid, actor_id=self.actor,
                    reason="agent observed/experienced this",
                    content=content, embedding=qemb,
                    embedding_model=embed.model_name(),
                    embedding_provenance=prov,
                    topic=topic, claim=claim)
                self.conn.commit()
                return mid
            except sqlite3.IntegrityError:
                self.conn.rollback()
        raise RuntimeError("memory_id allocation kept colliding — the "
                           "field's assignment is contested")

    def import_vault(self, path: str) -> dict[str, Any]:
        """Obsidian-style vault: .md -> memories, [[links]] -> RESONANT
        edges that actually change recall. Returns name->id map."""
        from . import vault
        out = vault.import_vault(self.cur, path)
        self.conn.commit()
        return out

    def link(self, from_id: str, to_id: str,
             link_type: str = "RESONANT") -> None:
        """Explicit edge: RESONANT amplifies, INHIBITORY silences."""
        from . import vault
        vault.link(self.cur, from_id, to_id, link_type)
        self.conn.commit()

    def backlinks(self, memory_id: str) -> list:
        """What links TO this note — inbound edges = resonant boost."""
        from . import vault
        return vault.backlinks(self.cur, memory_id)

    def outlinks(self, memory_id: str) -> list:
        from . import vault
        return vault.outlinks(self.cur, memory_id)

    def forget(self, memory_id: str, *, reason: str | None = None) -> None:
        """Deliberate forgetting: audited STATE_CHANGED to FORGOTTEN —
        invisible to recall, evidence preserved, revivable."""
        from . import vault
        vault.forget(self.cur, memory_id,
                     reason=reason or "deliberately forgotten")
        self.conn.commit()

    def revive(self, memory_id: str, *, reason: str | None = None) -> None:
        """Reverse of forget: audited STATE_CHANGED back to NEUTRAL."""
        from . import vault
        vault.revive(self.cur, memory_id,
                     reason=reason or "brought back to the field")
        self.conn.commit()

    def update(self, old_memory_id: str, new_content: str,
               *, reason: str | None = None) -> str:
        """An 'edit' is a supersession: new memory names its
        predecessor; the old one stays as evidence (M4)."""
        from . import vault
        mid = vault.update(self.cur, old_memory_id, new_content,
                           reason=reason)
        self.conn.commit()
        return mid

    # ---------- the loop ----------

    def ask(self, question: str, *, top_k: int = 5) -> dict[str, Any]:
        """Recall -> answer -> sealed decision -> reinforce used memory.

        Returns the answer text plus the forensic artifacts so a caller
        can show WHY this answer, not just what it was.
        """
        hits, receipt = field.recall(
            self.cur,
            query_embedding=field.quantize_embedding(embed.embed(question)),
            top_k=top_k, actor_id=self.actor)
        field.persist_receipt(self.cur, receipt)

        served = [h.memory_id for h in hits]
        # served != used != reinforced. The LLM declares which memories
        # it relied on — that declaration is its CLAIM, recorded as such
        # (even a steered one: the lie stays on the chain as evidence).
        # Reinforcement, the payoff a memory-poisoning attack wants,
        # follows only the DETERMINISTICALLY CORROBORATED subset.
        answer, declared, violation = llm.answer_with_used(
            question, [(h.memory_id, h.content) for h in hits],
            served_ids=served,
            session_material=receipt.receipt_sha256)
        reinforced = llm.corroborated(
            answer, [(h.memory_id, h.content) for h in hits], declared)

        dec_id = None
        if declared:
            for _ in range(4):
                dec_id = self._next_decision_id()
                try:
                    causality.record_decision(
                        self.cur, receipt=receipt,
                        used_memory_ids=declared,
                        decision_sha256=causality.decision_hash(answer),
                        policy_version=POLICY_VERSION,
                        actor_id=self.actor,
                        reason=f"answered: {question[:80]}",
                        decision_id=dec_id)
                    self.cur.execute(
                        "INSERT INTO seasons_decisions (decision_id,"
                        " question, created_at) VALUES (?, ?, ?)",
                        (dec_id, question, custody.now_ts()))
                    break
                except sqlite3.IntegrityError:
                    self.conn.rollback()
            else:
                raise RuntimeError("decision_id allocation kept "
                                   "colliding")


            for mid in reinforced:
                field.reinforce(
                    self.cur, memory_id=mid, actor_id=self.actor,
                    reason="used in a decision this turn",
                    caused_by_decision_id=dec_id)
        self.conn.commit()

        return {"answer": answer,
                "receipt": receipt.receipt_sha256,
                "served": served,
                "used": declared,
                "reinforced": reinforced,
                "integrity_violation": violation,
                "decision": dec_id,
                "withheld": {"custody": receipt.excluded_custody,
                             "forgotten": receipt.excluded_forgotten,
                             "inhibited": receipt.excluded_inhibited}}

    # ---------- seasons: the product's name primitive ----------

    def season(self, question: str, as_of: str, *, top_k: int = 5):
        """The same query, in an earlier season of the field.

        as_of is a canonical UTC microsecond timestamp. The answer is
        what the agent legitimately had at that instant — reconstructed
        by replaying custody chains truncated at t, not by trusting a
        snapshot column. Nothing is written; a season is a view.
        """
        hits, receipt = field.recall(
            self.cur,
            query_embedding=field.quantize_embedding(embed.embed(question)),
            top_k=top_k, as_of=as_of, actor_id=actors.OPERATOR)
        return {"hits": [(h.memory_id, h.content, str(h.score))
                         for h in hits],
                "receipt": receipt.receipt_sha256,
                "state_at": field.logical_state_at(self.cur, as_of)}

    def what_if(self, question: str, world: dict[str, str] | None,
                *, top_k: int = 5):
        """Sealed counterfactual: the same query against a hypothetical
        custody world. The receipt carries the override inside its
        digest — a what-if receipt can never pass for a real one."""
        return counterfactual.compare_worlds(
            self.cur,
            query_embedding=field.quantize_embedding(embed.embed(question)),
            world_a=None, world_b=world, top_k=top_k,
            actor_id=actors.OPERATOR)

    def what_if_transition(self, question: str, memory_id: str,
                           excise_seq: int, *, top_k: int = 5):
        """Trajectory counterfactual: same query in the world where
        custody event (memory_id, excise_seq) never happened — the gap
        the research identified. Sealed report, marked hypothetical."""
        from . import trajectory
        return trajectory.what_if_transition(
            self.cur,
            query_embedding=field.quantize_embedding(embed.embed(question)),
            memory_id=memory_id, excise_seq=excise_seq, top_k=top_k,
            actor_id=actors.OPERATOR)

    def do_transition(self, memory_id: str, excise_seq: int,
                      top_k: int = 5,
                      actor_id: str | None = None) -> dict:
        """`do(T_i = ∅)` — the cascade: which downstream receipts
        diverge, which decisions unground, which events on OTHER
        chains die. See docs/CAUSAL_REWIND.md."""
        return trajectory.do_transition(
            self.cur, memory_id=memory_id, excise_seq=excise_seq,
            top_k=top_k, actor_id=actor_id)

    def export_cf_bundle(self, memory_id: str, excise_seq: int,
                         top_k: int = 5) -> dict:
        """Self-contained counterfactual evidence bundle — a third
        party can recompute the cascade and reach the same result
        without trusting this implementation (verify_cf_offline.py)."""
        from . import trajectory
        return trajectory.export_cf_bundle(
            self.cur, memory_id=memory_id, excise_seq=excise_seq,
            top_k=top_k)

    def decision_what_if(self, decision_id: str, memory_id: str,
                         excise_seq: int, *, top_k: int = 5):
        """Would this decision's evidence base survive without that
        transition? Replays the question that fed the decision in the
        excised world; the report names which used memories fall out."""
        from . import trajectory
        return trajectory.decision_what_if(
            self.cur, decision_id=decision_id, memory_id=memory_id,
            excise_seq=excise_seq, top_k=top_k,
            actor_id=actors.OPERATOR)

    def request_provenance(self, trace_id: str, *, depth: str = "summary"):
        """The facade: receipt / decision / memory -> bounded evidence
        projection. depth: summary | direct | impact | counterfactual."""
        from . import provenance
        return provenance.request_provenance(
            self.cur, trace_id=trace_id, depth=depth)

    # ---------- forensics ----------

    def chain(self, memory_id: str):
        """Full custody chain of one memory — its whole history."""
        self.cur.execute(
            "SELECT seq, event_type, actor_id, reason, created_at "
            "FROM custody_chain WHERE memory_id=? ORDER BY seq", (memory_id,))
        return self.cur.fetchall()

    def impact(self, memory_id: str):
        """Blast radius: which recalls served it, which decisions used it."""
        return causality.impact(self.cur, memory_id)

    def export_bundle(self) -> str:
        """Sealed evidence bundle — verifiable offline by a party that
        distrusts this process entirely (verify_offline.py)."""
        from mneme import bundle
        return bundle.export_bundle(self.cur)


def _nebius() -> bool:
    import os
    return bool(os.environ.get("NEBIUS_API_KEY"))
