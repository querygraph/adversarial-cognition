# Changelog

## Unreleased

- Add a separate native `cognee-rs` benchmark adapter and entry. It invokes
  the official Rust CLI in an isolated store and claims only retrieval and
  persistence; Python Cognee remains a distinct adapter.

## Unreleased

- Replace the Letta integration with Agent SDK 0.6.2 and the self-hosted App
  Server. Retain a bounded `llama3.1:latest` capture from
  real agent turns over persistent MemFS: 1/6 claimed cases, 12 unsupported;
  no adapter-mediated isolation or authorization result is claimed.
- Add the source-owned *Adversarial Cognition* book: a manuscript that
  introduces the QueryGraph stack from first principles, frames TypeDID
  identity, the TypeSec capability-gated vault, unforgeable lineage, and
  auditable receipts, makes the enterprise case for governed cognition, and
  presents the benchmark, the auditable comparative results, and the reproducible Docker
  stack — with a generated seal cover and the FirstPair build contract.
- Package the benchmark as a reproducible Docker stack: a Dockerfile baking
  each adapter's pinned dependency set, a compose stack wiring Fluree and
  Letta as services with an optional bundled Ollama, an entrypoint that runs
  every system and writes the report, and a uniform capture script.
- Record bounded raw adapter outputs for Akka + Fluree, Letta, Graphiti, Mem0,
  and Cognee with per-case findings, and add the shared OSS scenario driver.
- Add a panoramic headboard illustration depicting Plato and Diogenes’ rug dispute
  at an Academy symposium.
- Extract MARCIANA-ADVERSARIAL-v1 from querygraph/marciana (`cbf3592`) into
  a standalone repository: the deterministic reference backend, the
  eighteen-case pinned corpus, hard-gate and category-metric evaluation,
  the comparative adapter protocol, the offline public-corpus inventory,
  the runner, and the full test suite.
- Make the external adapter timeout configurable through
  `MARCIANA_ADVERSARIAL_TIMEOUT_SECONDS` for slow local-model adapters.
