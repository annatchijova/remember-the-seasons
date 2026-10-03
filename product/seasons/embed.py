"""Embeddings: deterministic local fallback, Nebius when configured.

The field ranks with exact rational arithmetic; embeddings are the one
sanctioned float crossing (a measurement, quantized once at ingestion).
A deterministic local embedder keeps the whole demo runnable with zero
network — same text, same vector, on every machine.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import urllib.request

DIM = 64

_TOKEN = re.compile(r"[a-z0-9]+")


def embed_local(text: str, dim: int = DIM) -> list[float]:
    """Deterministic token-hash embedding. Not semantic-grade — the point
    is stability and reproducibility, not retrieval quality. The Nebius
    path below is the real one."""
    v = [0.0] * dim
    for tok in _TOKEN.findall(text.lower()):
        h = hashlib.sha256(f"tok:{tok}".encode()).digest()
        bucket = int.from_bytes(h[:4], "big") % dim
        sign = 1.0 if h[4] & 1 else -1.0
        v[bucket] += sign
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def embed_nebius(text: str, model: str | None = None) -> list[float]:
    """Nebius Token Factory embeddings (OpenAI-compatible)."""
    base = os.environ.get("NEBIUS_BASE_URL",
                          "https://api.tokenfactory.nebius.com/v1")
    key = os.environ["NEBIUS_API_KEY"]
    model = model or os.environ.get("SEASONS_EMBED_MODEL", "Qwen/Qwen3-Embedding-8B")
    body = {"model": model, "input": text}
    req = urllib.request.Request(
        f"{base}/embeddings",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())["data"][0]["embedding"]


def embed(text: str) -> list[float]:
    """Nebius if a key is present, deterministic local otherwise."""
    if os.environ.get("NEBIUS_API_KEY"):
        return embed_nebius(text)
    return embed_local(text)


def model_name() -> str:
    return "nebius" if os.environ.get("NEBIUS_API_KEY") else "seasons-local"


def embed_with_provenance(text: str):
    """Quantized embedding + declared provenance: who embedded, which
    model, hashes of model input and stored vector. B3 re-checks it —
    without this, embedding drift is undetectable by construction."""
    from mneme import field
    qemb = field.quantize_embedding(embed(text))
    prov = field.declare_embedding(
        provider="nebius" if os.environ.get("NEBIUS_API_KEY")
        else "local-deterministic",
        model=os.environ.get("SEASONS_EMBED_MODEL",
                             "Qwen/Qwen3-Embedding-8B")
        if os.environ.get("NEBIUS_API_KEY") else "seasons-local-hash",
        revision=os.environ.get("NEBIUS_MODEL_REVISION", "unknown"),
        embedding=qemb, model_input=text, preprocessing="none")
    return qemb, prov
