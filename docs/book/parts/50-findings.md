# Part V — What the benchmark reveals

## A word on numbers, and where they live

This part describes what the benchmark *finds* — the kinds of failure it drags
into the light, illustrated by the real systems it has been run against. What it
does not do is print a scoreboard. The exact coverage and correctness of each
system on each run — which shift as models change, as adapters mature, as new
systems join — live in a companion **results report**, regenerated every time the
suite runs and stamped with the corpus digest that proves which corpus produced
them. The book keeps to what does not change with the scores: the shape of the
attack, and the character of what it reveals. Read the two together — the book
for the *why*, the report for the *what, today*.

## A field of memory systems

The reference run pits **Marciana**, the governed engine, against a field of
widely used open-source memory systems, each driven through its own adapter
against local models — inference and embeddings from a local Ollama,
infrastructure brought up locally, no cloud keys anywhere. The roster is worth
meeting not as competitors but as *specimens*, because each embodies a different
answer to the question "what is a memory?":

- **Marciana** — the governed reference, exercising the full boundary: the four
  verbs, capability-gated reveal, digest-bound proposals, durable replay
  protection, deterministic receipts.
- **Akka + Fluree** — a semantic-ledger design, in which a Fluree ledger is the
  query and policy authority and an actor tier is the adapter. A ledger is
  exactly the kind of substrate that can enforce the properties the benchmark
  cares about.
- **Letta** — the current self-hosted App Server and Agent SDK, driving
  persistent MemFS through an agent loop against a local model.
- **Mem0** — an open-source retrieve-and-update memory over a local vector store.
- **Graphiti** — a knowledge-graph memory over an embedded Kuzu backend.
- **Cognee** — a Python knowledge-graph pipeline that builds and searches a
  graph.
- **cognee-rs** — the native Rust rewrite of Cognee, run through its own CLI,
  deliberately kept separate from the Python entry so the two are never
  conflated.

The list grows; systems come and go; a vendor may send an adapter tomorrow. That
is precisely why the roster is treated here as a set of *examples* and the live
tally is kept elsewhere. What follows holds regardless of the day's numbers.

## How to read a run

Three habits make a results report legible, and they are the same three whatever
the roster.

First, **coverage and correctness are two axes, not one.** A system is scored
only on the cases whose capability it *declares* it enforces; a case it does not
claim is marked unsupported — never a pass, never a failure. So "correct on
everything it claimed" and "claimed almost nothing" are both true of the same
row, and a small, honest system is not flattered by its silence nor punished for
it. Scores taken over different coverage are not directly comparable, and the
report says so on its face.

Second, **the gate ledger is separate from the quality score, and dominates it.**
The named hard gates — unauthorized disclosure, cross-scope leakage, stale or
replayed mutation, residual recall after forget, non-deterministic receipts, and
the rest — must be zero, and no amount of recall accuracy buys back a single one.
A run is read gates-first.

Third, **unsupported is an honest answer, not a hidden failure.** When an
adapter declines a case, it is saying "this system does not claim this boundary,"
and the benchmark records that as information rather than converting it into a
loss. The most useful thing a comparison can produce is not a ranking but a *map*
of exactly which parts of the boundary each system holds.

## The character of the findings

With those habits in hand, here is what the attack actually surfaces — each an
example of a whole class, drawn from a real system, and each invisible to any
recall score.

**A ledger enforces the boundary almost for free.** The strongest comparative
result in the field has consistently been the semantic-ledger design, and
instructively so. A ledger serializes transactions, filters by time and
authorization as ordinary query clauses, guards a conditional write that fails if
its condition no longer holds, and tombstones on delete — which is to say it
already speaks the grammar the benchmark tests. Give it those capabilities and it
passes them; where its particular build ships no policy engine, its adapter
*declines* clearance and purpose rather than faking them. That is the benchmark
working as intended: a real boundary is credited, an absent one is declared.

**The intra-tenant clearance leak is the enterprise finding.** A popular
vector-store memory scopes by a single axis — a user id. Model an analyst and an
operator as what they actually are — one tenant, differing only in *clearance* —
and such a system cannot withhold the operator's private memory from the analyst,
because it has no notion of clearance *within* a tenant. The private record
leaks. This is the exact failure the disclosure gates exist to catch, and it is
invisible to every recall benchmark on earth, because the record is recalled
*perfectly* — to the wrong person. An organization could run such a system for a
year, pass every recall benchmark, demo beautifully, and never see it, until the
day someone does and it becomes an incident report.

**Ranking can be unstable under a reordered query.** A knowledge-graph memory may
return one ranked result for a query and a different one when the query's tokens
are reordered — an order-invariance failure. Nothing leaked; nothing was lost;
but an audit that depends on the same question producing the same answer has
quietly lost its footing.

**Input that isn't bounded is a latent liability.** Several systems accept an
oversized query, or error on an empty one instead of abstaining, or let a
Unicode look-alike through. None of these is dramatic in a demo. All of them are
load-bearing the moment an adversary, rather than a user, is typing.

**A response contract is part of the boundary.** Exercised through its agent
loop, one system returns no bounded identifiers across most retrieval and
robustness cases and only clears the empty-query abstention — a configuration and
response-shape finding, not a leak or an authorization claim, and its adapter
says so by declining the cases it cannot honestly support rather than
manufacturing a boundary it lacks.

**A young engine wears its youth honestly.** The native Rust rewrite of a
graph-memory pipeline claims only what it natively provides — retrieval and
persistence — and explicitly declares that its dataset name is *not* an
authorization boundary, so tenant and clearance cases stay unsupported rather
than pretending. On the strength of what it does claim, an early build may not
yet hold determinism across a restart or bound its inputs; the benchmark records
that plainly, and — because it scores only the four cases the engine actually
claims — the picture is a fair one of a system still under construction, not a
caricature of one.

Every one of these is a single, nameable property. That is the deliverable: not
a verdict, but a map.

## What the findings mean for an enterprise deployment

Step back from the specimens and the pattern is stark, and it is the pattern
rather than any row that matters. Every general-purpose open-source memory system
recalls facts well. Not one of them ships the *full* governed boundary — and the
specific things they lack are precisely the things that do not surface until an
adversary, a regulator, or an incident goes looking: clearance within a tenant,
bounded input, stable ranking, durable replay protection, deterministic receipts.

This is the enterprise case for governed cognition, made not by assertion but by
the negative space in a results table. The value of Marciana is not that it
recalls better — several of these systems recall comparably. The value is that it
is the only participant that holds *every* part of the boundary at once, and can
prove it did, because the boundary is not a feature bolted onto a memory. It is
the composition of TypeDID identity, TypeSec capabilities, LakeCat proofs,
Grust's atomic commits, and deterministic receipts described in Part II — the
thing the whole stack was built to make unforgeable. An enterprise does not need
the best recall. It needs a memory it can stand behind when someone asks how.

## Reproducing it: the Docker stack

None of this is worth anything on the authors' word. The benchmark ships as a
source repository with a one-command Docker stack, so anyone can rerun every
system against the same corpus on their own hardware and generate their own copy
of the results report.

```sh
ollama pull gpt-oss:20b nomic-embed-text
docker compose build
docker compose run --rm benchmark      # all systems → out/RESULTS.md
```

The compose stack brings up the infrastructure services, resolves each adapter's
pinned dependencies inside the benchmark image, runs every configured system
against the corpus, and writes the machine-readable report and a human-readable
`RESULTS.md` — the companion report this part has deferred to throughout. Every
report contains bounded identifiers, digests, counts, and timings, **never memory
plaintext**: report assembly rejects any string long enough to be plaintext, and
a test asserts that no seeded phrase appears in a rendered report. The corpus
digest is stamped into every run, so two people who run the benchmark are
demonstrably running the same benchmark — and the book you are holding never goes
stale, because the numbers were never in it.

---
