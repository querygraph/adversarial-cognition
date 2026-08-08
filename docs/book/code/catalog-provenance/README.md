# catalog-provenance

**CATALOG-PROVENANCE-v1** — a provable-transaction benchmark for Iceberg REST
catalogs. It does not ask which catalog commits *fastest*; a separate
performance suite ([catalog-bench](https://github.com/querygraph/catalog-bench))
already answers that. It asks a different question: when a catalog accepts a
transaction, **can you prove what happened — offline, months later, without
trusting the server?**

That is the provenance and governance axis, and it is where LakeCat's design
lives: optimistic concurrency, idempotent replay, a durable audit trail and an
outbox staged *atomically* with the commit, receipts that verify offline and
chain to their predecessor, governed-scan authorization bound to policy
digests, tombstone receipts, and the invariant that evidence carries digests —
never raw locations or secrets.

## Release policy

Safety failures are counted in named **hard gates that must be zero** — never
averaged into a score:

`lost_update_accepted`, `duplicate_commit_applied`, `evidence_lost`,
`forged_proof_accepted`, `unauthorized_scan_disclosed`, `plaintext_in_evidence`,
`non_deterministic_receipt`.

## Quick start

```sh
python3 -m unittest discover -s tests -p 'test_*.py' -q
python3 run_benchmark.py
```

The core is dependency-free. The runner verifies the corpus against its pinned
manifest (`fixtures/catalog-provenance-v1/`, regenerated with `--pin-corpus`),
runs the reference catalog, and exits non-zero unless every hard gate is zero.

## The corpus

Seventeen cases across the provable-transaction properties, each exercising one
**capability** with an explicit expected outcome. A catalog is scored only on
the capabilities it declares — a case whose capability a catalog does not claim
is reported *unsupported*, never a pass or a failure, never faked. Full design:
[`docs/CATALOG-PROVENANCE-v1.md`](docs/CATALOG-PROVENANCE-v1.md).

The reference catalog (`catalog_provenance/backend.py`) is a small,
dependency-free model of a governed catalog's provable-transaction boundary —
it defines, in executable form, what "provable" means. It is not LakeCat's Rust
implementation; LakeCat's own release proof gates the real service.

## Comparative catalogs

Every configured catalog is enumerated on every run — `executed`, `error`, or
`unavailable` — and never silently substituted. Each runs only through an
explicitly configured adapter command:

| Catalog | Command variable | Adapter |
|---------|------------------|---------|
| LakeCat | `CATALOG_PROVENANCE_LAKECAT_CMD` | [`adapters/lakecat/`](adapters/lakecat/) |
| Nessie | `CATALOG_PROVENANCE_NESSIE_CMD` | [`adapters/rest_adapter.py`](adapters/rest_adapter.py) |
| Gravitino | `CATALOG_PROVENANCE_GRAVITINO_CMD` | [`adapters/rest_adapter.py`](adapters/rest_adapter.py) |
| Polaris | `CATALOG_PROVENANCE_POLARIS_CMD` | [`adapters/rest_adapter.py`](adapters/rest_adapter.py) |

The three stock Iceberg REST catalogs (Nessie, Gravitino, Polaris) genuinely
provide the shared baseline — a real commit path and catalog-enforced optimistic
concurrency — and honestly declare the governance capabilities they do not
expose. Unity Catalog OSS is intentionally excluded: its Iceberg REST surface is
read-only, with no commit path to make provable. The whole comparison runs
locally against a shared MinIO through Docker; see
[`docs/CATALOG-PROVENANCE-v1.md`](docs/CATALOG-PROVENANCE-v1.md) and
[`docker-compose.yml`](docker-compose.yml).

## License

MIT or Apache-2.0, at your option.
