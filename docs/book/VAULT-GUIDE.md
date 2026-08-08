## About this vault — the Adversarial Cognition Trilogy

This is the code-book edition of *Adversarial Cognition*. It joins the complete
manuscript to a verified snapshot of every benchmark the book describes, so you
can read an argument and open the code that backs it in the same window.

### How it is organized

- **`Reader/`** — the book, one file per part, in reading order: the Preface and
  Introduction, Parts I–V on governed cognition, Part VI on catalogs, Part VII on
  capabilities, then the conclusion, appendices, glossary, and index.
- **`Evidence/`** — the full source of all four benchmarks, one tree each:
  - `cognition/` — MARCIANA-ADVERSARIAL: the deterministic reference boundary
    (`adversarial_cognition/backend.py`), the shared adapter contract
    (`adapters/protocol.py`), and every competitor adapter under `adapters/`.
  - `catalog-provenance/` — CATALOG-PROVENANCE: the Iceberg-REST adapters
    (`adapters/iceberg_rest.py` and the per-catalog drivers) and the provable-
    transaction cases.
  - `catalog-bench/` — the companion performance suite (`crates/`), same four
    catalogs measured for latency and throughput.
  - `capability/` — CAPABILITY-ADVERSARIAL: the live adapters for ten
    authorization systems, including the TypeSec reference
    (`adapters/typesec/src/main.rs`).

### Reading code beside the argument

Where the manuscript prints an excerpt, the caption ends with a *"Full source in
the vault"* link straight to the file under `Evidence/`. Follow it to read the
excerpt in context, then use Obsidian search (by symbol, filename, or crate) to
explore the rest of the tree. Each excerpt is a window, not the whole
implementation — the surrounding module and its tests are one click away.

The exact source revision of every snapshot is recorded in
`Evidence/*/` (see each benchmark's own README) and in
`docs/book/code/PROVENANCE.md` in the source repository. Generated build output,
caches, downloaded tool binaries, and virtual environments are intentionally
excluded; edit a copy in a real checkout rather than the vault snapshot if you
want to run anything.
