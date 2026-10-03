"""LLM access: Nebius Token Factory when configured, deterministic stub
otherwise. The stub keeps the demo and every receipt reproducible with
no network and no key.

Per CLAUDE.md §5.1, the model NEVER touches the decision path in a way
that would change sealed values: recall ranking, receipts, and custody
events are all produced and sealed by the deterministic engine before
the LLM is asked to narrate them. The answer text is hashed as a
decision artifact — the field commits to the hash, not the prose.
"""

from __future__ import annotations

import json
import os
import re
import urllib.request

DEFAULT_MODEL = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"


def chat(messages: list[dict], model: str | None = None,
         temperature: float = 0.2) -> str:
    """OpenAI-compatible chat completion via Nebius Token Factory."""
    base = os.environ.get("NEBIUS_BASE_URL",
                          "https://api.tokenfactory.nebius.com/v1")
    key = os.environ.get("NEBIUS_API_KEY")
    model = model or os.environ.get("SEASONS_MODEL", DEFAULT_MODEL)
    if not key:
        return _stub(messages)
    body = {"model": model, "messages": messages,
            "temperature": temperature}
    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())["choices"][0]["message"]["content"]


def _stub(messages: list[dict]) -> str:
    """Offline answer: names which sealed memories it was handed.
    Deterministic — same recall, same answer — so receipts stay
    reproducible in CI and demos without a key."""
    ctx = ""
    for m in reversed(messages):
        if m["role"] == "user" and "MEMORIES:" in m["content"]:
            ctx = m["content"].split("MEMORIES:", 1)[1]
            break
    items = [ln.strip(" -") for ln in ctx.splitlines() if ln.strip()]
    if not items or items == ["(none)"]:
        return "I have no verified memories on record for that."
    return ("From sealed memory, I know: " + " | ".join(items[:5]))


_USED_RE = re.compile(r"^USED\s*:\s*(.*)$", re.IGNORECASE | re.MULTILINE)


def answer_with_used(question: str,
                     hits: list[tuple[str, str]],
                     served_ids: list[str],
                     model: str | None = None) -> tuple[str, list[str]]:
    """Ask the model to answer AND declare which memories it used.

    Returns (answer_text, used_ids). used_ids is clamped to served_ids —
    the model can only declare use of what recall actually served, and
    a hallucinated id is silently dropped rather than recorded. In stub
    mode, used = served (the stub literally consumed them all)."""
    if not os.environ.get("NEBIUS_API_KEY"):
        return _stub_answer(question, hits), list(served_ids) if hits else []

    listing = "\n".join(f"{mid}: {content}" for mid, content in hits) \
        if hits else "(none)"
    raw = chat([
        {"role": "system",
         "content": "Answer only from the provided memories. If none "
                    "apply, say you have no record. After the answer, on "
                    "a new line, write 'USED: ' followed by the memory "
                    "ids you actually relied on (or 'USED: none')."},
        {"role": "user",
         "content": f"QUESTION: {question}\nMEMORIES:\n{listing}"}],
        model=model)

    used = []
    m = _USED_RE.search(raw)
    answer = raw
    if m:
        answer = raw[:m.start()].rstrip()
        used = [t.strip() for t in m.group(1).split(",")
                if t.strip() in set(served_ids)]
    else:
        used = list(served_ids)   # model didn't declare; all served
    return answer, used


def _stub_answer(question: str, hits: list[tuple[str, str]]) -> str:
    if not hits:
        return "I have no verified memories on record for that."
    return ("From sealed memory, I know: " +
            " | ".join(c for _, c in hits[:5]))
