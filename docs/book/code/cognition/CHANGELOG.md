# Changelog

## Unreleased

- Add a companion panoramic headboard inspired by the adversari.al About animation,
  depicting governed requests crossing membranes into a chained receipt ledger.

- Begin MARCIANA-ADVERSARIAL-v2 (issue #3): design doc plus the `track`
  model (`adversarial_cognition/tracks.py`) separating a memory-store track
  from an agent-memory track, compared only within a track. Additive scaffold;
  v1 scoring and rendering are unchanged.

- Declare and report each adapter's `interface` (`direct-api` | `agent-loop`),
  so how a system's memory was reached is legible in the results, not implied.
  The adapter enforces no gate in either case; this is metadata only.

- Add an optional second Letta entry (`letta-direct`) driving its memory store
  directly rather than through the agent loop, so the cost of the loop is the
  delta between the two rows. The Python mode switch, honest capability/interface
  declarations, and registry entry are in place; the `direct-memory` bridge path
  fails loudly until wired against the live App Server passage API (see
  `adapters/letta/BUILD_NOTES.md`) rather than silently mislabeling an agent run.

- Align comparative results wording with the 24 KB oversized-query fixture and
  make coverage-scoped accuracy explicit rather than presenting an ordinal
  ranking.

- Refresh the comparative report from the preserved adapter captures, include
  the merged Cognee 1.4.1 result, and order the systems by coverage-scoped
  diagnostic accuracy (with unsupported systems last).

- Remove the unconfigured Zep placeholder from the active adapter inventory,
  documentation, tests, and comparative output.

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
