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
