# Part III — Marciana, a governed cognition engine

## Cognition proposes; the vault commits

Marciana sits one layer above the foundations and one layer below the
applications, and its entire design can be compressed into a single equation:

$$
S_{t+1} = \operatorname{commit}\big(S_t,\; \operatorname{authorize}(\operatorname{propose}(E_t))\big)
$$

Durable state $S_{t+1}$ is the previous state $S_t$ plus an *authorized*
proposal derived from the evidence $E_t$ available at the time. The proposal is
not itself a commit. Authorization sits between them, and it is owned by TypeSec,
not by the thing that proposed. That single interposition — cognition proposes,
the vault commits — is what prevents a language model from becoming an implicit
database administrator, and it is the property the entire benchmark is built to
stress.

The orchestration behind the equation is a deliberate, ordered state machine.
When an agent asks Marciana to improve a memory, the worker authenticates and
binds the intent, persists or recovers a durable job under a renewable lease,
obtains TypeSec preauthorization and a governed LakeCat scan, ingests the mapped
rows through TypeSec, runs a fixed Sail computation, revalidates the catalog
grant, obtains a manifest-only reauthorization from TypeSec, stages the exact
proposal digest, and only then performs a single atomic guarded commit — or a
typed *no-change* outcome if the proposal turns out to mutate nothing. A commit
issues a TypeDID-bound receipt. No proposal-derived result becomes observable
before both post-computation authorization gates have passed.

If that sounds like a lot of machinery for "update a fact," it is — and that is
the point. The machinery is the difference between a memory you can deploy in a
regulated enterprise and one you cannot.

## The four verbs

Marciana exposes exactly four verbs, and their unusual property is that every one
of them enters the same capability-gated vault and the same guarded mutation
seam:

1. **Remember** creates an authored or derived item with its source lineage.
2. **Recall** selects authorized items for a purpose and a time boundary — and
   returns only what the caller is entitled to, ranked, never revealing
   protected content the caller may not see.
3. **Improve** creates a replacement while retaining the superseded history, so
   that correction never destroys the record of what was previously believed.
4. **Forget** performs a scoped, receipt-producing lifecycle transition —
   removing an item and everything derived from it, and proving that it did.

Vector search, graph traversal, semantic extraction, and agent tools are ways to
*propose* or *rank*. They are not alternate verbs, and they do not get their own
private path to a mutation. There is one door, and it is guarded.

## Why the enterprise needs governed cognition

It is worth being blunt about why this matters, because "governed" can sound like
a tax on capability rather than an enabler of it.

An enterprise deploying agents over its data has a problem that consumer AI does
not: it must be able to *stand behind* what the system did. When a memory
influences a decision — a price quoted, a customer flagged, a document
retrieved — someone will eventually ask how, and "the model thought so" is not an
answer that survives an audit, a dispute, or a regulator. The enterprise needs to
be able to say: this fact entered here, from this authorized source, under this
identity; it was visible to these principals for these purposes; it was corrected
on this date, superseding this prior value; and here is the receipt for every one
of those transitions.

A cognition engine that cannot produce those answers is not merely less
convenient — it is *unbounded liability wearing the costume of a feature*. The
model can be as creative as you like in what it proposes, precisely *because* the
commit boundary is conservative. Governance is what lets the enterprise turn
cognition up rather than down, because the blast radius of a bad proposal is
bounded: a forged source cannot commit, a stale proposal cannot overwrite a
newer fact, a replayed request cannot double a mutation, and a deleted record
cannot come back. Governance does not restrain the useful cases. It restrains the
catastrophic ones, and by doing so it makes the useful cases deployable.

This is the argument the benchmark exists to make concrete. It is one thing to
claim a boundary is unforgeable. It is another to attack it eighteen ways and
publish where it held.

## Time, supersession, and the discipline of forgetting

Two capabilities deserve special mention because they are where governed memory
most visibly diverges from a vector store.

**Time has two axes.** An observation can be *valid* over a market interval and
become *known* to the system at a later moment. Recall must be able to answer
both "what was true on date X?" and "what did the system know as of date Y?" — and
the two answers can differ. Marciana's context bundle carries an as-of qualifier,
and its plan, citations, explanations, and rendered output all bind to that same
cutoff, so a historical reconstruction cannot silently be contaminated by
later-known facts. A vector store that returns "the most similar memory" has no
way to make this distinction; it will happily hand you a current price when you
asked what was true a year ago.

**Forgetting is a discipline, not a delete.** When a governed system forgets, it
does not simply remove a row. It performs a lifecycle transition, cascades to the
memories derived from the forgotten one, and produces a receipt. And — this is the
subtle part the benchmark checks explicitly — forgetting must be *surgical*: it
removes the forgotten fact and its derivations while leaving untouched the
unrelated memories that legitimately match a later query. A forget that nukes
recall entirely would pass a naive test while being wrong; a forget that leaves a
derived summary behind would pass a naive test while being dangerous. Governed
forgetting threads that needle, and it proves that it did.

---

