# Changelog

## Unreleased

- Add the source-owned *Adversarial Cognition* book: a manuscript that
  introduces the QueryGraph stack from first principles, frames TypeDID
  identity, the TypeSec capability-gated vault, unforgeable lineage, and
  auditable receipts, makes the enterprise case for governed cognition, and
  presents the benchmark, the six-system results, and the reproducible Docker
  stack — with a generated seal cover and the FirstPair build contract.
- Package the benchmark as a reproducible Docker stack: a Dockerfile baking
  each adapter's pinned dependency set, a compose stack wiring Fluree and
  Letta as services with an optional bundled Ollama, an entrypoint that runs
  every system and writes the report, and a uniform capture script.
- Record the six-system comparative results (Marciana 18/18, Akka + Fluree
  16/16, Letta 7/9, Graphiti 6/8, Mem0 6/9, Cognee 5/8) with per-case
  findings, and add the shared OSS adapter scenario driver.
- Add a panoramic headboard illustration depicting Plato and Diogenes’ rug dispute
  at an Academy symposium.
- Extract MARCIANA-ADVERSARIAL-v1 from querygraph/marciana (`cbf3592`) into
  a standalone repository: the deterministic reference backend, the
  eighteen-case pinned corpus, hard-gate and category-metric evaluation,
  the comparative adapter protocol, the offline public-corpus inventory,
  the runner, and the full test suite.
- Make the external adapter timeout configurable through
  `MARCIANA_ADVERSARIAL_TIMEOUT_SECONDS` for slow local-model adapters.
