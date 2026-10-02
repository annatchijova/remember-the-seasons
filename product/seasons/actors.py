"""Actor bootstrap: the authority ledger's genesis actors."""

from __future__ import annotations

from mneme import authority

ROOT = "seasons-root"
AGENT = "seasons-agent"
OPERATOR = "seasons-operator"


def bootstrap(cur) -> None:
    """One-time authority genesis. Idempotent by design of the ledger:
    bootstrap_root refuses to run twice."""
    authority.bootstrap_root(
        cur, actor_id=ROOT, display_name="Seasons Root", kind="HUMAN",
        reason="field genesis: operator provisioned out of band")
    authority.register_actor(
        cur, actor_id=AGENT, display_name="Seasons Agent", kind="AGENT",
        issuer_id=ROOT, reason="the product's memory-owning agent")
    authority.grant(
        cur, subject_id=AGENT,
        capabilities=["STORE", "REINFORCE", "DECIDE"],
        issuer_id=ROOT, reason="remember, adapt, and answer")
    authority.register_actor(
        cur, actor_id=OPERATOR, display_name="Seasons Operator", kind="HUMAN",
        issuer_id=ROOT, reason="forensic/counterfactual review")
    authority.grant(
        cur, subject_id=OPERATOR,
        capabilities=["COUNTERFACTUAL", "QUARANTINE_MEMORY",
                      "QUARANTINE_ACTOR", "REHABILITATE", "REINFORCE"],
        issuer_id=ROOT, reason="incident review and what-if analysis")
