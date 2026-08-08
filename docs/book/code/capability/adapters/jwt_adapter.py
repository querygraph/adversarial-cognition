"""JWT / OAuth-scope adapter — the bearer-token floor.

A signed JWT is the shared baseline of the field: an issuer (an OAuth
authorization server) signs a token for an authorized subject, and any holder of
the public key can verify it offline. PyJWT natively enforces exactly three of
this benchmark's properties, and this adapter claims only those:

- ``mint-capability`` — the issuer signs only for an authorized subject (its
  policy), a tampered token fails signature verification, and a denied subject
  gets no token;
- ``lease-expiry`` — the ``exp`` claim is enforced at verification;
- ``resource-instance-binding`` — the ``aud`` claim binds the token to one
  audience/resource, and PyJWT rejects a mismatch.

Everything else — attenuation, revocation-by-construction, reveal/declassify
gating, deny-by-default tool-calls, confused-deputy resistance, audit, wire
integrity — a bearer token simply does not provide, and the adapter declares
those unsupported rather than faking them.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone

import jwt  # PyJWT

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from common import run  # noqa: E402

SECRET = "capability-adversarial/jwt-issuer-key"
ALG = "HS256"
# The issuer's policy: which subjects it will sign a token for, on which resource.
ISSUER_POLICY = {("agent:operator", "customer/2"), ("agent:analyst", "customer/2")}

CAPABILITIES = ["mint-capability", "lease-expiry", "resource-instance-binding"]


def _issue(subject: str, resource: str, ttl_seconds: int = 300) -> str | None:
    # The authorization server refuses to sign for an unauthorized subject.
    if (subject, resource) not in ISSUER_POLICY:
        return None
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": subject, "aud": resource, "iat": now, "exp": now + timedelta(seconds=ttl_seconds)},
        SECRET, algorithm=ALG)


def run_case(case_id: str) -> bool:
    if case_id == "mint-authorized":
        token = _issue("agent:operator", "customer/2")
        claims = jwt.decode(token, SECRET, algorithms=[ALG], audience="customer/2")
        return claims["sub"] == "agent:operator"

    if case_id == "mint-denied-by-policy":
        # The issuer's policy has no entry for a write-only unauthorized subject.
        return _issue("agent:intruder", "customer/2") is None

    if case_id == "forged-capability-rejected":
        token = _issue("agent:operator", "customer/2")
        # Tamper the payload while keeping the old signature.
        header, _, sig = token.split(".")
        import base64
        forged_payload = base64.urlsafe_b64encode(b'{"sub":"agent:root","aud":"customer/2"}').rstrip(b"=").decode()
        forged = f"{header}.{forged_payload}.{sig}"
        try:
            jwt.decode(forged, SECRET, algorithms=[ALG], audience="customer/2")
            return False
        except jwt.InvalidTokenError:
            return True

    if case_id == "lease-expiry-enforced":
        now = datetime.now(timezone.utc)
        token = jwt.encode(
            {"sub": "agent:operator", "aud": "customer/2", "iat": now - timedelta(seconds=10),
             "exp": now - timedelta(seconds=1)}, SECRET, algorithm=ALG)
        try:
            jwt.decode(token, SECRET, algorithms=[ALG], audience="customer/2")
            return False
        except jwt.ExpiredSignatureError:
            return True

    if case_id == "resource-instance-bound":
        token = _issue("agent:operator", "customer/2")
        claims = jwt.decode(token, SECRET, algorithms=[ALG], audience="customer/2")
        return claims["aud"] == "customer/2"

    if case_id == "cross-resource-rejected":
        token = _issue("agent:operator", "customer/2")
        try:
            jwt.decode(token, SECRET, algorithms=[ALG], audience="customer/1")
            return False
        except jwt.InvalidAudienceError:
            return True

    return False


if __name__ == "__main__":
    run("pyjwt", CAPABILITIES, run_case)
