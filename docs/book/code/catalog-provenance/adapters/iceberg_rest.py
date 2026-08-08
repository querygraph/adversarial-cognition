"""A CatalogSystem over any standard Iceberg REST catalog, via pyiceberg.

This backs the capabilities every real Iceberg REST catalog genuinely provides
and this harness can prove the *catalog* enforces:

- ``commit`` — create a table and append a real snapshot through the catalog;
- ``compare-and-swap`` — a stale writer's commit is rejected by the catalog's
  own optimistic concurrency. We hold an un-refreshed table handle from before
  a concurrent commit and let the catalog reject the stale assertion; the
  adapter never re-implements the check.

Every governance capability (audit, outbox, replay, governed scan, receipt
chain, tombstone, hash-only evidence, idempotency) is left unclaimed — a stock
Iceberg REST catalog exposes no such surface, so those cases are reported
unsupported rather than failed.
"""

from __future__ import annotations

import copy
import os
import uuid

import pyarrow as pa
from pyiceberg.catalog.rest import RestCatalog
from pyiceberg.exceptions import CommitFailedException
from pyiceberg.schema import Schema
from pyiceberg.types import NestedField, StringType

from protocol import CatalogSystem

_SCHEMA = Schema(NestedField(1, "seq", StringType(), required=False))
_ROW = pa.table({"seq": ["x"]})


class IcebergRestSystem(CatalogSystem):
    """Commit and compare-and-swap over a real Iceberg REST catalog."""

    capabilities = frozenset({"commit", "compare-and-swap"})

    def __init__(self, name: str, version: str, uri: str,
                 warehouse: str, extra_props: dict | None = None,
                 location_prefix: str = "") -> None:
        self.name = name
        self.version = version
        self._uri = uri
        # `warehouse` is the pyiceberg catalog-selection prop (an S3 path for
        # Nessie, a catalog name for Polaris, empty for Gravitino).
        self._warehouse = warehouse
        # `location_prefix` is where to place created tables when the catalog
        # does not place them itself; empty means let the catalog choose.
        self._location_prefix = location_prefix
        self._props = extra_props or {}
        self._namespace = "provenance"

    def _catalog(self) -> RestCatalog:
        props = {
            "uri": self._uri,
            "s3.endpoint": os.environ.get("AWS_ENDPOINT", "http://minio:9000"),
            "s3.access-key-id": os.environ.get("AWS_ACCESS_KEY_ID", "admin"),
            "s3.secret-access-key": os.environ.get("AWS_SECRET_ACCESS_KEY", "password"),
            "s3.region": os.environ.get("AWS_REGION", "us-east-1"),
            "s3.path-style-access": "true",
            **self._props,
        }
        # Some catalogs (Gravitino's standalone REST) serve a preconfigured
        # warehouse and reject a client-supplied S3-path warehouse; those pass
        # an empty warehouse and let the catalog place the table.
        if self._warehouse:
            props["warehouse"] = self._warehouse
        # Without an OAuth credential, pyiceberg 0.11 still installs its legacy
        # OAuth2 manager, which sends a literal `Authorization: Bearer None`.
        # Gravitino's authenticator validates that bogus bearer and returns 401;
        # Nessie ignores it. Select the no-auth manager so no bearer is sent.
        # Polaris (which supplies a real `token`) keeps the OAuth manager.
        if "token" not in self._props:
            props["auth"] = {"type": "noop"}
        cat = RestCatalog(self.name, **props)
        # pyiceberg requests vended S3 credentials by default, which Polaris and
        # Gravitino cannot provide against MinIO. We pass explicit static S3
        # credentials, so drop the delegation request and let pyiceberg write
        # directly — the same static-credential model Nessie already uses.
        try:
            cat._session.headers.pop("X-Iceberg-Access-Delegation", None)
        except Exception:
            pass
        return cat

    def reset(self) -> None:
        self._cat = self._catalog()
        try:
            self._cat.create_namespace(self._namespace)
        except Exception:
            pass
        self._table = f"{self._namespace}.t_{uuid.uuid4().hex[:10]}"
        # a fresh witness handle per witnessed pointer value
        self._witness: dict[str, object] = {}

    def create(self, table: str) -> None:
        if self._location_prefix:
            location = f"{self._location_prefix.rstrip('/')}/{table.replace('.', '/')}"
            self._cat.create_table(self._table, schema=_SCHEMA, location=location)
        else:
            # Let the catalog place the table in its own default location.
            self._cat.create_table(self._table, schema=_SCHEMA)

    def _load(self):
        return self._cat.load_table(self._table)

    def pointer(self, table: str) -> str:
        snap = self._load().current_snapshot()
        return str(snap.snapshot_id) if snap else "none"

    def commit(self, table: str, expected: str, update: str,
               idempotency_key: str = "") -> dict:
        # Witness the table state at first sight of `expected`, un-refreshed, so
        # a second commit against the same expected asserts a now-stale snapshot
        # and the catalog rejects it.
        if expected not in self._witness:
            self._witness[expected] = self._load()
        handle = copy.copy(self._witness[expected])
        try:
            handle.append(_ROW)
            return {"ok": True, "receipt": None}
        except CommitFailedException:
            return {"ok": False, "receipt": None}
        except Exception as error:
            # a real error (network, auth) — surface as a failed probe
            raise error
