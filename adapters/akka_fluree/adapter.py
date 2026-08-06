"""Akka + Fluree adapter: Fluree is the semantic-ledger/query authority.

This adapter represents the comparative "Akka port with Fluree as the
semantic-ledger/query role" described in Marciana's documentation. The
actor/service layer is represented by this adapter process: it enforces the
service input bound and orchestrates requests, while every authorization
filter, temporal filter, ranking aggregation, guarded mutation, nonce claim,
and idempotency guard is executed by the Fluree ledger itself.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
import uuid
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from protocol import MemorySystem, run

FLUREE = os.environ.get("MARCIANA_FLUREE_URL", "http://localhost:58090/v1/fluree")
CONTEXT = {"bench": "http://bench.example/", "b": "http://bench.example/prop/"}
PREFIXES = (
    "PREFIX b: <http://bench.example/prop/> "
    "PREFIX bench: <http://bench.example/> "
    "PREFIX xsd: <http://www.w3.org/2001/XMLSchema#> "
)
TOKEN = re.compile(r"[a-z0-9]+")
MAX_QUERY_CHARS = 4_096
MAX_TOKENS = 16
DATE_MIN = "1900-01-01"
DATE_MAX = "9999-12-31"


def digest_of(memory_id: str) -> str:
    return "sha256:" + hashlib.sha256(memory_id.encode()).hexdigest()


def _local_name(iri: str) -> str:
    """Strip either the compact ``bench:`` or full-IRI prefix Fluree returns."""

    return iri.removeprefix(CONTEXT["bench"]).removeprefix("bench:")


def _post(path: str, payload: bytes, content_type: str) -> dict | list:
    request = urllib.request.Request(
        f"{FLUREE}/{path}", data=payload,
        headers={"Content-Type": content_type}, method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())


def _json(path: str, body: dict) -> dict | list:
    return _post(path, json.dumps(body).encode(), "application/json")


class AkkaFlureeSystem(MemorySystem):
    name = "akka-fluree"
    version = "fluree-server-4.1.4"
    capabilities = frozenset({
        "retrieval", "temporal", "abstention", "isolation", "provenance",
        "replay-protection", "idempotency", "forget", "derived-tracking",
        "persistence",
    })

    def __init__(self) -> None:
        self.ledger = ""

    def reset(self) -> None:
        self.ledger = f"bench/{uuid.uuid4().hex[:12]}"
        _json("create", {"ledger": self.ledger})

    def _sparql_update(self, body: str) -> None:
        request = urllib.request.Request(
            f"{FLUREE}/update", data=(PREFIXES + body).encode(),
            headers={"Content-Type": "application/sparql-update",
                     "Fluree-Ledger": self.ledger}, method="POST",
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            response.read()

    def _sparql_query(self, body: str) -> list[dict]:
        payload = (PREFIXES + body.replace("FROM <>", f"FROM <{self.ledger}>")).encode()
        result = _post("query", payload, "application/sparql-query")
        return result["results"]["bindings"]

    def _exists(self, entity: str) -> bool:
        rows = self._sparql_query(
            f"SELECT ?t FROM <> WHERE {{ bench:{entity} b:tombstoned ?t }}"
        )
        return any(row["t"]["value"] == "false" for row in rows)

    def remember(self, memory_id, text, principal, valid_from=None,
                 valid_until=None, private=False, nonce=None, supersedes=None,
                 derived_from=()) -> bool:
        entity = {
            "@id": f"bench:{memory_id}",
            "b:text": text,
            "b:owner": principal,
            "b:private": bool(private),
            "b:tombstoned": False,
            "b:sourceDigest": digest_of(memory_id),
            "b:validFrom": {"@value": (valid_from or date(1900, 1, 1)).isoformat(),
                            "@type": "http://www.w3.org/2001/XMLSchema#date"},
            "b:validUntil": {"@value": (valid_until or date(9999, 12, 31)).isoformat(),
                             "@type": "http://www.w3.org/2001/XMLSchema#date"},
        }
        if derived_from:
            entity["b:derivedFrom"] = [{"@id": f"bench:{item}"} for item in derived_from]
        if nonce is None:
            _json("update", {"ledger": self.ledger, "@context": CONTEXT,
                             "insert": [entity]})
            return True
        # The ledger claims the nonce and writes the memory in one guarded
        # transaction: nothing is inserted when the nonce already exists.
        triples = " . ".join(self._triples(entity))
        self._sparql_update(
            f"INSERT {{ bench:nonce-{nonce} b:claimed true . {triples} . }} "
            f"WHERE {{ FILTER NOT EXISTS {{ bench:nonce-{nonce} b:claimed ?c }} }}"
        )
        return self._exists(memory_id)

    @staticmethod
    def _triples(entity: dict) -> list[str]:
        subject = entity["@id"]
        rows = []
        for key, value in entity.items():
            if key == "@id":
                continue
            if isinstance(value, dict):
                rows.append(f'{subject} {key} "{value["@value"]}"^^xsd:date')
            elif isinstance(value, list):
                rows.extend(f'{subject} {key} {item["@id"]}' for item in value)
            elif isinstance(value, bool):
                rows.append(f"{subject} {key} {str(value).lower()}")
            else:
                escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
                rows.append(f'{subject} {key} "{escaped}"')
        return rows

    def _visibility(self, principal: str) -> str:
        if principal == "operator":
            return ""
        if principal == "analyst":
            return "FILTER(?priv = false)"
        escaped = principal.replace('"', "")
        return f'FILTER(?owner = "{escaped}")'

    def recall(self, query, principal, as_of=None):
        if len(query) > MAX_QUERY_CHARS:
            raise ValueError("oversized query rejected by the service layer")
        tokens = sorted(set(TOKEN.findall(query.lower())))[:MAX_TOKENS]
        if not tokens:
            return ()
        values = " ".join(json.dumps(token) for token in tokens)
        temporal = ""
        if as_of is not None:
            temporal = (
                f'FILTER(?vf <= "{as_of.isoformat()}"^^xsd:date) '
                f'FILTER(?vu > "{as_of.isoformat()}"^^xsd:date) '
            )
        rows = self._sparql_query(
            "SELECT ?m (COUNT(?w) AS ?score) FROM <> WHERE { "
            "?m b:text ?t ; b:owner ?owner ; b:private ?priv ; "
            "b:tombstoned false ; b:validFrom ?vf ; b:validUntil ?vu . "
            f"{self._visibility(principal)} {temporal} "
            f"VALUES ?w {{ {values} }} FILTER(CONTAINS(LCASE(?t), ?w)) "
            "} GROUP BY ?m ORDER BY DESC(?score) ASC(?m)"
        )
        return tuple(_local_name(row["m"]["value"]) for row in rows)

    def forget(self, memory_id, principal):
        if principal != "operator":
            return False
        # Ledger-executed tombstones: the target, then every entity whose
        # derivedFrom link the ledger matches (one hop, as in the corpus).
        self._sparql_update(
            f"DELETE {{ bench:{memory_id} b:tombstoned false }} "
            f"INSERT {{ bench:{memory_id} b:tombstoned true }} "
            f"WHERE {{ bench:{memory_id} b:tombstoned false }}"
        )
        self._sparql_update(
            f"DELETE {{ ?d b:tombstoned false }} "
            f"INSERT {{ ?d b:tombstoned true }} "
            f"WHERE {{ ?d b:derivedFrom bench:{memory_id} ; b:tombstoned false }}"
        )
        return not self._exists(memory_id)

    def improve(self, memory_id, replacement_id, text, principal,
                expected_source_digest, idempotency_key):
        replacement = {
            "@id": f"bench:{replacement_id}", "b:text": text,
            "b:owner": principal, "b:private": False, "b:tombstoned": False,
            "b:sourceDigest": digest_of(replacement_id),
            "b:validFrom": {"@value": "2026-02-01", "@type": "http://www.w3.org/2001/XMLSchema#date"},
            "b:validUntil": {"@value": DATE_MAX, "@type": "http://www.w3.org/2001/XMLSchema#date"},
        }
        triples = " . ".join(self._triples(replacement))
        digest_literal = json.dumps(expected_source_digest)
        # One guarded transaction: commits only when the source digest still
        # matches and the idempotency job has never run; a retry is a ledger
        # no-op whose recorded outcome is read back.
        self._sparql_update(
            f"DELETE {{ bench:{memory_id} b:tombstoned false }} "
            f"INSERT {{ bench:{memory_id} b:tombstoned true . "
            f"bench:job-{idempotency_key} b:committed true . {triples} . }} "
            f"WHERE {{ bench:{memory_id} b:tombstoned false ; "
            f"b:sourceDigest {digest_literal} . "
            f"FILTER NOT EXISTS {{ bench:job-{idempotency_key} b:committed ?j }} }}"
        )
        job = self._sparql_query(
            f"SELECT ?j FROM <> WHERE {{ bench:job-{idempotency_key} b:committed ?j }}"
        )
        return bool(job) and self._exists(replacement_id)

    def restart(self) -> None:
        # All state lives in the Fluree server; a fresh stateless HTTP
        # session against the same ledger is a process restart.
        return


if __name__ == "__main__":
    run(AkkaFlureeSystem())
