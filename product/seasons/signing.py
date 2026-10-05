"""DSSE envelope + Ed25519 signing for cf bundles.

A hash chain proves bytes did not change RELATIVE to the commitments
inside the object — it cannot distinguish the committed history from
an equally-coherent fully-rewritten one, because the attacker can
recompute every hash. The thing the attacker cannot recompute is a
signature under a key they don't hold. That is the trust anchor:
authenticity is anchored OUTSIDE the rewritable object.

Format: DSSE (Dead Simple Signing Envelope)
  PAE     = "DSSEv1" SP len(type) SP type SP len(payload) SP payload
  payload = the canonical bundle bytes (mneme-canonical-json/v1)
  sig     = Ed25519(PAE)

The verdict is two-mode, honestly:
  VERIFIED_AUTHENTICATED  — signature checks against a trusted key
  VERIFIED_INTEGRITY_AND_SEMANTICS + ORIGIN_UNTRUSTED
                          — the cascade recomputes but nobody we
                            trust signed it; a well-formed forgery
                            passes everything except this line.

keyid is a HINT for key selection, never an authentication decision.
"""

from __future__ import annotations

import base64
import binascii
import os

try:
    from nacl.signing import SigningKey, VerifyKey
    _HAVE_NACL = True
except ImportError:
    _HAVE_NACL = False

PAYLOAD_TYPE = "application/vnd.mneme.cf-bundle+json;version=1"


def _pae(payload: bytes) -> bytes:
    t = PAYLOAD_TYPE.encode()
    return (b"DSSEv1 " + str(len(t)).encode() + b" " + t + b" "
            + str(len(payload)).encode() + b" " + payload)


def available() -> bool:
    return _HAVE_NACL


def sign_envelope(payload: bytes, seed_hex: str,
                  keyid: str = "") -> dict:
    """Wrap canonical bundle bytes in a signed DSSE envelope."""
    if not _HAVE_NACL:
        raise RuntimeError("pynacl not available — cannot sign.")
    sk = SigningKey(bytes.fromhex(seed_hex))
    sig = sk.sign(_pae(payload)).signature
    return {
        "payloadType": PAYLOAD_TYPE,
        "payload": base64.b64encode(payload).decode(),
        "signatures": [{"keyid": keyid,
                        "sig": base64.b64encode(sig).decode()}],
    }


def verify_envelope(env: dict,
                    trusted_keys: dict[str, str]) -> tuple[bool, str]:
    """Check every signature against the trusted key set.

    trusted_keys: {keyid_or_label: verify_key_hex}. keyid in the
    envelope only SELECTS candidate keys; a signature that verifies
    under ANY trusted key is accepted. Returns (authenticated, signer).
    """
    if not _HAVE_NACL:
        return False, ""
    try:
        payload = base64.b64decode(env["payload"])
        if env.get("payloadType") != PAYLOAD_TYPE:
            return False, ""
    except (KeyError, binascii.Error):
        return False, ""
    for s in env.get("signatures", []):
        try:
            sig = base64.b64decode(s["sig"])
        except (KeyError, binascii.Error):
            continue
        candidates = (trusted_keys.items()
                      if not s.get("keyid")
                      else [(k, v) for k, v in trusted_keys.items()
                            if k == s["keyid"]] or trusted_keys.items())
        for label, vkey_hex in candidates:
            try:
                VerifyKey(bytes.fromhex(vkey_hex)).verify(
                    _pae(payload), sig)
                return True, label
            except Exception:
                continue
    return False, ""


def load_trusted_keys(path: str | None = None) -> dict[str, str]:
    """Trusted key set: {label: verify_key_hex} from a JSON file or
    the RTS_TRUSTED_KEYS env var (JSON). An empty set means
    ORIGIN_UNTRUSTED — never silently trust a key the bundle names."""
    src = path or os.environ.get("RTS_TRUSTED_KEYS_FILE")
    if src and os.path.exists(src):
        import json
        return json.load(open(src))
    if os.environ.get("RTS_TRUSTED_KEYS"):
        import json
        return json.loads(os.environ["RTS_TRUSTED_KEYS"])
    return {}


def sign_entry_hash(entry_hash_hex: str, seed_hex: str) -> str:
    """Ed25519 over the custody entry_hash (the hex string's ASCII
    bytes — what the chain itself commits). Attribution, not
    tamper-evidence: the chain proves integrity, the sig proves who."""
    if not _HAVE_NACL:
        raise RuntimeError("pynacl not available — cannot sign.")
    sk = SigningKey(bytes.fromhex(seed_hex))
    return sk.sign(entry_hash_hex.encode("ascii")).signature.hex()


def verify_key_hex(seed_hex: str) -> str:
    if not _HAVE_NACL:
        raise RuntimeError("pynacl not available.")
    return SigningKey(bytes.fromhex(seed_hex)).verify_key.encode().hex()
