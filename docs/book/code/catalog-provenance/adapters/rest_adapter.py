"""Entrypoint: drive the provenance benchmark against a stock Iceberg REST catalog.

    python3 rest_adapter.py <nessie|gravitino|polaris>

Endpoints and auth match the proven catalog-bench harness. Governance
capabilities are unclaimed for all of these — a stock Iceberg REST catalog
exposes no audit, outbox, replay, governed-scan, receipt-chain, or idempotency
surface — so the driver reports those cases unsupported rather than failed.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from iceberg_rest import IcebergRestSystem
from protocol import run

# Internal Docker-network hostnames on the shared lakehouse network.
CATALOGS = {
    "nessie": dict(
        version="0.107.5",
        uri=os.environ.get("NESSIE_URI", "http://nessie:19120/iceberg/main"),
        warehouse=os.environ.get("NESSIE_WAREHOUSE", "s3://warehouse/nessie"),
        location_prefix=os.environ.get("NESSIE_WAREHOUSE", "s3://warehouse/nessie"),
    ),
    "gravitino": dict(
        version="oss",
        uri=os.environ.get("GRAVITINO_URI", "http://gravitino:9001/iceberg"),
        # Gravitino's standalone REST serves its own preconfigured warehouse.
        warehouse=os.environ.get("GRAVITINO_WAREHOUSE", ""),
    ),
    "polaris": dict(
        version="1.5.0",
        uri=os.environ.get("POLARIS_URI", "http://polaris:8181/api/catalog"),
        warehouse=os.environ.get("POLARIS_WAREHOUSE", os.environ.get("POLARIS_PREFIX", "bench")),
        # Polaris authenticates: a bearer token from its OAuth bootstrap.
        extra_props={"token": os.environ["POLARIS_TOKEN"]} if os.environ.get("POLARIS_TOKEN") else {},
    ),
}


def main() -> None:
    name = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("CATALOG_PROVENANCE_CATALOG", "")
    if name not in CATALOGS:
        sys.exit(f"usage: rest_adapter.py <{'|'.join(CATALOGS)}>")
    cfg = CATALOGS[name]
    run(IcebergRestSystem(
        name=name, version=cfg["version"], uri=cfg["uri"],
        warehouse=cfg["warehouse"], extra_props=cfg.get("extra_props"),
        location_prefix=cfg.get("location_prefix", "")))


if __name__ == "__main__":
    main()
