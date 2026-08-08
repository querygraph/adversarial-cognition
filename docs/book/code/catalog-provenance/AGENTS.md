# Repository Guidance

- The benchmark core (`catalog_provenance/`) is dependency-free Python; keep it
  that way. Catalog adapters under `adapters/` own their environments.
- Safety gates are zero-tolerance and never averaged into a score. Reports carry
  bounded IDs, digests, and counts — never plaintext locations or secrets.
- The corpus is versioned by content digest in
  `fixtures/catalog-provenance-v1/manifest.json`; any case change must repin via
  `run_benchmark.py --pin-corpus` in the same commit.
- Adapters never re-implement a check the catalog lacks: a capability is claimed
  only if the *catalog* enforces it; unclaimed capabilities are declared
  unsupported, never faked.
- This benchmark is the provenance/governance axis. The performance axis (commit
  latency and throughput vs Nessie/Gravitino/Polaris) lives separately in
  catalog-bench and must stay separate.
