"""LakeCat adapter: the live governed catalog under CATALOG-PROVENANCE-v1.

LakeCat is a spec-conformant Iceberg REST catalog, so commit and compare-and-swap
run through the same real, catalog-enforced path as every other catalog. On top
of that, LakeCat honours an ``Idempotency-Key`` on commits — a retried commit
replays its stored result instead of double-applying — which this adapter proves
live over the REST API.

LakeCat's deeper provable-transaction guarantees — durable audit, an outbox
staged atomically with the commit, offline-verifiable and chained receipts,
governed-scan authorization receipts bound to policy digests, tombstone
receipts, and hash-only evidence — are defined by the reference model (which is
a model of LakeCat's governed boundary) and gated in the LakeCat repository's
own release proof. Wiring those endpoints into this comparative harness is the
next unit of work; until then this adapter claims only what it verifies here.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from iceberg_rest import IcebergRestSystem
from protocol import run


class LakeCatSystem(IcebergRestSystem):
    name = "lakecat"
    capabilities = frozenset({"commit", "compare-and-swap", "idempotent-replay"})

    def __init__(self) -> None:
        base = os.environ.get("LAKECAT_URI", "http://lakecat:8181/catalog")
        super().__init__(
            name="lakecat", version=os.environ.get("LAKECAT_VERSION", "0.3.0"),
            uri=base, warehouse=os.environ.get("LAKECAT_WAREHOUSE", "s3://warehouse/lakecat"))
        self._rest = base.rstrip("/")

    def _table_path(self) -> str:
        ns, name = self._table.split(".", 1)
        return f"{self._rest}/v1/namespaces/{ns}/tables/{name}"

    def _load_json(self) -> dict:
        with urllib.request.urlopen(self._table_path(), timeout=30) as resp:
            return json.load(resp)

    def commit(self, table: str, expected: str, update: str,
               idempotency_key: str = "") -> dict:
        if not idempotency_key:
            # No key: exercise the standard snapshot commit + compare-and-swap
            # path shared with every Iceberg REST catalog.
            return super().commit(table, expected, update, idempotency_key)

        # Keyed commit: a set-properties updateTable carrying the idempotency
        # key. LakeCat advances the metadata pointer; a retry with the same key
        # replays the stored response, so the metadata-location does not move
        # a second time.
        loaded = self._load_json()
        uuid_ = loaded["metadata"]["table-uuid"]
        body = json.dumps({
            "requirements": [{"type": "assert-table-uuid", "uuid": uuid_}],
            "updates": [{"action": "set-properties", "updates": {"bench-seq": update}}],
        }).encode()
        req = urllib.request.Request(self._table_path(), data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Idempotency-Key", idempotency_key)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.load(resp)
        except Exception as error:  # noqa: BLE001
            raise error
        # The receipt is the committed metadata-location; identical on replay.
        return {"ok": True, "receipt": {"metadata_location": result.get("metadata-location"),
                                        "receipt_hash": result.get("metadata-location"),
                                        "prev_receipt": ""}}


if __name__ == "__main__":
    run(LakeCatSystem())
