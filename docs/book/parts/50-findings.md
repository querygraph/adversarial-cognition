# Part V — What the benchmark found

## Six systems under attack

The reference run pits Marciana against five widely used open-source memory
systems, each driven through its own adapter against local models — LLM inference
and embeddings served by a local Ollama, infrastructure (a Fluree ledger, an
embedded graph store) brought up locally, no cloud keys anywhere. The systems:

- **Marciana** — the governed reference, exercising the full boundary.
- **Akka + Fluree** — a semantic-ledger design in which Fluree is the
  query/policy authority and the actor tier is the adapter process.
- **Letta App Server** — the current Agent SDK drives persistent MemFS through
  the agent loop, using local `llama3.1:latest` for the recorded run.
- **Mem0** — an open-source retrieval-and-update memory over a local vector store.
- **Graphiti** — a knowledge-graph memory over an embedded Kuzu backend.
- **Cognee** — a knowledge-graph pipeline that builds and searches a graph.

The results, recorded on a single local host, scored only on supported cases:

| System | Supported | Correct | The finding |
|---|:---:|:---:|---|
| **Marciana** | 18 | 18 | Every hard gate zero. |
| **Akka + Fluree** | 16 | 16 | All claimed cases pass. |
| **Letta App Server** | 6 | 1 | Empty-query abstention passed; temporal output was out of contract. |
| **Graphiti** | 8 | 6 | Ranking and input-bound failures. |
| **Mem0** | 9 | 6 | Same-tenant clearance leak. |
| **Cognee** | 8 | 5 | Empty/input-bound failures. |

The reference and the ledger runs are deterministic. The LLM-backed systems
depend on the local model and hardware, so their numbers will vary by host; that
variability is stated plainly and is itself a reason the benchmark ships as a
reproducible stack rather than a leaderboard.

## Reading the results

The numbers are less interesting than what the adversarial cases *surfaced*,
because every failure here is a specific, legible property — not a vague
"weakness."

**Akka + Fluree** is the strongest comparative result, and instructively so.
Fluree is a ledger, and a ledger is exactly the kind of substrate that can
enforce the properties the benchmark cares about: authorization and temporal
filters run as query clauses, ranking as an aggregation, nonce claims and
digest-guarded improvements as conditional transactions that fail if the
condition does not hold, and forgetting as a cascading tombstone. It passes all
sixteen capabilities it claims — including every safety gate that applies to
them — and it *declines* clearance and purpose, honestly, because that Fluree
build ships no policy engine and the adapter refuses to fake one. This is the
benchmark working as intended: a system that enforces a real boundary is
credited for it, and one that lacks a boundary says so rather than pretending.

**Letta** is exercised through its current self-hosted App Server and Agent SDK.
The agent loop handles each remember, recall, and forget operation against
persistent MemFS. On the retained `llama3.1:latest` run, it returns no bounded
IDs in current retrieval, restart, order, and oversized-query cases. Its
temporal output is not a corpus ID; only empty-query abstention passes, for
1/6. These are configuration-specific response and input-validation findings,
not a memory-leak or authorization claim. The adapter does not claim
isolation merely because it selects a principal's agent, leaving twelve cases
unsupported rather than manufacturing a security boundary.

**Mem0** produces the most consequential enterprise finding in the set. Its only
scoping axis is `user_id`: principals in the same organization share a store.
Model an analyst and an operator as the same tenant — which is what they are,
differing only in *clearance* — and Mem0 cannot withhold the operator's private
memory from the analyst, because it has no notion of clearance *within* a tenant.
The private record leaks. This is exactly the failure the `unauthorized_disclosure`
family of gates exists to catch, and it is invisible to any recall benchmark,
because Mem0 recalls the record perfectly — to the wrong person.

**Graphiti** fails order-invariance — reordering the tokens of a query changes
the ranked result — and, like the others, accepts oversized input. **Cognee** is
the only open-source system in the set whose clearance mechanism (dataset tiers)
genuinely withholds private data from the under-cleared caller, a real and
creditable boundary; yet it errors on an empty query instead of abstaining and
bounds no input. Each of these is a single, nameable property, and that is the
deliverable: not a score, but a map of exactly which parts of the boundary each
system holds.

## What the findings mean for an enterprise deployment

Step back from the individual systems and the pattern is stark. Every
general-purpose open-source memory system in the set recalls facts well. Not one
of them ships the *full* governed boundary — and the specific things they lack
are precisely the things that do not show up until an adversary, or a regulator,
or an incident, goes looking.

The intra-tenant clearance leak in Mem0 is the clearest example. An organization
could run Mem0 for a year, pass every recall benchmark, demo beautifully, and
never notice that a lower-clearance user could read a higher-clearance user's
private data — until the day someone does, and it becomes an incident report. The
missing input bounds in the tested Letta configuration, Graphiti, and Cognee are the same shape of
problem: latent until adversarial, and then suddenly load-bearing.

This is the enterprise case for governed cognition, made not by assertion but by
the negative space in the results table. The value of Marciana is not that it
recalls better — several of these systems recall comparably. The value is that it
is the only participant that *holds every part of the boundary at once*, and can
prove it did, because the boundary is not a feature bolted onto a memory. It is
the composition of TypeDID identity, TypeSec capabilities, LakeCat proofs, Grust's
atomic commits, and deterministic receipts described in Part II — the thing the
whole stack was built to make unforgeable.

An enterprise does not need the best recall. It needs a memory it can stand
behind when someone asks how. That is what "governed" buys, and the benchmark is
the receipt.

## Reproducing it: the Docker stack

None of the above is worth anything if you have to take the authors' word for it.
The benchmark ships as a source repository with a one-command Docker stack, so
that anyone can rerun every system against the same corpus on their own hardware.

```sh
ollama pull gpt-oss:20b nomic-embed-text
docker compose build
docker compose run --rm benchmark      # all systems → out/RESULTS.md
```

The compose stack brings up the Fluree and Letta services, resolves each
adapter's pinned dependencies inside the benchmark image, runs every configured
system against the corpus, and writes the machine-readable report and a
human-readable `RESULTS.md`. Every report contains bounded identifiers, digests,
counts, and timings — **never memory plaintext.** This is enforced structurally,
not by convention: report assembly rejects any string long enough to be
plaintext, and a test asserts that no seeded memory phrase appears in a rendered
report. The corpus digest is stamped into every run, so two people who run the
benchmark are demonstrably running the same benchmark.

The core — the reference backend, the corpus, the gates, the report scripts — is
dependency-free Python and runs with no network and no keys. The Docker stack is
the full comparison; the core is the release gate that runs in continuous
integration on every change. Both are in the repository, and both are the
deliverable.

---

