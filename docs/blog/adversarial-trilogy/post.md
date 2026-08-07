# The Adversarial Cognition Trilogy: one boundary, attacked at three layers

![Philosophers of data in dispute — attacking a claim is the oldest move in the book, and the frontispiece of a trilogy about attacking the claims a system makes.](headboard.png)

What began as a single benchmark for an AI's memory is now three, and the
reason is worth stating plainly, because we did not set out to build a suite.
We set out to attack one boundary — the governed boundary that decides *who may
reveal or change this, and whether you can prove what happened* — and every time
we looked one layer down the stack, the same boundary was waiting, wearing
different clothes. The memory that anchors an agent. The catalog that anchors a
data lake. The authority that anchors both. Three domains; one question; and, it
turns out, one adversary who is equally at home in all of them.

So the collection is now a trilogy — **MARCIANA-ADVERSARIAL** for cognition,
**CATALOG-PROVENANCE** and its companion **catalog-bench** for the catalog, and
**CAPABILITY-ADVERSARIAL** for authority — with a book expanded to hold all
three, a home at [adversari.al](https://adversari.al), and a second version of
the original already taking shape from the sharpest objection we have received.
This post is the tour.

## One idea, stated once

Every part of this rests on a single, slightly heretical idea: that the safest
way to keep a rule is not to *check* it while the program runs — a check can be
forgotten, skipped, or duplicated until the copies disagree — but to write the
rule into the program's *grammar*, so that a program which breaks it does not
fail at run time but fails to *compile*. In the QueryGraph stack this is
**TypeSec**: authority is not a flag but an unforgeable typed value, a
`Capability<P, R>` with no public constructor, mintable only through a policy
decision — so the mere existence of one *is* proof the policy approved it.
Identity is **TypeDID**: a request is *signed*, not accompanied by a copyable
password, and — the invariant the whole stack is organized around — **verified
identity is not authority.** Proving who you are grants nothing until a policy
turns that identity into a narrow, expiring, typed capability.

From that one idea the benchmarks inherit their spine. Every system is scored
**only on the capabilities it declares** — never faked, never punished for an
honest "unsupported." Safety failures land in **named hard gates that must be
zero** and are never averaged into a quality score. And the corpus is pinned by
content digest, so changing an expectation is a visible, reviewable act, not a
quiet edit. Three benchmarks, one constitution.

## Cognition: the origin — and a version two already forming

MARCIANA-ADVERSARIAL began as Marciana's release gate: a deterministic,
adversarial benchmark for governed AI memory that asks not "did it remember the
right thing?" but "does the boundary hold when the memory and the request path
are actively trying to break it?" Eighteen cases, nine gates, a field of widely
used open-source memory systems each driven through its own adapter against
local models. What it finds are failures no recall score can see: a private
record that leaks to a lower-clearance user *in the same tenant*; a ranking that
changes when you reorder the words of a query; input that isn't bounded until an
adversary, rather than a user, is typing. The live numbers live on
[adversari.al/cognition](https://adversari.al/cognition) and in the benchmark's
companion report — the book keeps to the *character* of the findings, which does
not change with the day's scores.

The interesting news is v2, and it comes from being contested. A careful
reviewer pointed out that placing a system driven through a full **agent loop**
(model reasoning, tool calls, a response parser) in one table with adapters that
call a storage API **directly** mixes abstraction layers — and even documented,
one table invites an ordinal read of unlike measurements. That is correct.
**MARCIANA-ADVERSARIAL-v2** answers it with three changes: two explicit
**tracks** (a *memory-store* track and an *agent-memory* track) compared only
within a track; a **controlled agent-memory harness** where every backend runs
under the same model, loop, prompts, tool contract, and context budget so only
the memory varies; and **authorization exercised through distinct authenticated
identities**, never adapter-selected partitions — the same failure mode a
previous review had caught, where an adapter that routes each principal to its
own store *manufactures* an isolation the system does not enforce. The first
piece has already shipped: every adapter now declares an **`interface`**
(`direct-api` or `agent-loop`), and the Letta adapter can run both ways, so the
cost of the agent loop becomes the *delta between two rows of the same product*
rather than an argument.

Underneath the version bump is a principle the expanded book now argues in a
chapter of its own — *A claim is a boundary.* You cannot escape a test of your
claims by renaming the category. A system that "reasons about time rather than
remembering" has not stepped out of the ring; it has named the punch it is most
inviting, because temporal reasoning is exactly one of the boundaries the corpus
attacks. Whether cognition is wrapped in an agent or exposed as a library, the
claims are the same, and each can be attacked in its own domain and measured.
The label on the box is marketing; the claim is the contract; and the contract
is what gets tested.

## Catalog: provable transactions, and what they cost

Descend from the agent's memory to the catalog beneath a data lake and the same
questions are waiting. **CATALOG-PROVENANCE** asks not which Iceberg catalog
commits *fastest* — a fair question with its own answer — but the one you cannot
see until something goes wrong: when a catalog accepts a transaction, **can you
prove what happened, offline, months later, without trusting the server that
says so?** The benchmark builds that question from first principles — a table is
files in a bucket; a version of it is a snapshot; a catalog is the single pointer
to the current one; a commit moves the pointer — and then attacks the commit
with a stale writer, a duplicate retry, a tampered receipt, a scan replayed under
the wrong policy.

The shape of the result *is* the finding. Three real, competent, widely deployed
stock catalogs each hold exactly two capabilities — `commit` and
`compare-and-swap` — cleanly and honestly, and decline all eleven governance
capabilities, because a stock catalog has no such surface to claim. No idempotent
replay, no durable audit, no atomic outbox, no receipt an auditor could verify
offline. **Every Iceberg catalog gives you compare-and-swap; only a governed
catalog gives you a transaction you can prove.** LakeCat's governed boundary
holds them all.

And because provenance is a cost paid on every commit, it deserves an honest
price, which is what the companion **catalog-bench** measures: the same catalogs,
one shared MinIO, identical commits, latency then throughput under contention.
The durable finding is a ranking with a moral — a lean version store leads on raw
sequential latency, LakeCat sits a couple of milliseconds behind it (the price of
seven durable writes inside every commit), and under contention, where governance
is supposed to hurt most, LakeCat is *fastest*. **LakeCat is paying for features,
not losing on speed.** The two benchmarks are one argument stated twice: the
performance suite measures the cost of the governed commit; the provenance suite
measures what the cost buys. Stated as a price, the difference between a logbook
and a ledger is milliseconds.

## Capability: authority as an object

Descend once more, to authority itself. **CAPABILITY-ADVERSARIAL** asks whether
the authority a system grants is one an attacker — or the model itself — cannot
forge, widen on delegation, replay past revocation, or aim at the wrong resource.
It runs ten authorization systems, live, each over its *real* library, and the
roster is a ladder: a bearer-token floor (JWT/OAuth); a capability-token band
(Macaroons, Biscuit, UCAN) that makes authority portable and shrinkable; a
decision band (Cedar, OPA, and the relationship engines SpiceDB and OpenFGA) that
makes it governed but evaporating; and TypeSec at the top.

The bands cluster so cleanly the table reads like a geological cross-section, and
the moral has an aphorism: **policy engines decide, capability tokens travel, and
bearer scopes gate — and only a capability system makes the authority itself
unforgeable, attenuation-monotone, instance-bound, revocable, and label-aware,
all at once.** TypeSec is that intersection, one honest case short of an idealized
reference — and the case it declines, `wire-integrity`, it declines truthfully,
because no real system in the field claims it either. That visible, truthful mark
on the author's own system is exactly what should make the rest of the row
believable.

## Why the three are one

Read the trilogy together and the same few figures stand in every part, wearing
the local costume. One **adversary** — forge, replay, stale-overwrite — equally at
home in a memory, a pointer swap, and a delegation chain. One **receipt** — sealed
by its own digest, verifiable by a stranger, deterministic so identical runs
agree. One **atom** — the domain-separated digest beneath every receipt. One
**guarded door** — authority with a single home and no convenience API around it.
One refrain, the deepest — **proof is not authority** — from a verified identity
that grants nothing, to a scan proof that does not vouch for stapled text, to the
phantom `Authorization: Bearer None` a governed catalog rightly rejected. And one
**direction**: authority only ever narrows.

These are not three boundaries that happen to resemble one another. They are one
boundary, built once in the foundations and *composed* into each domain — Marciana
is literally TypeSec's memory crate; LakeCat's governed-scan proof flows upward
into Marciana's commits — so proving the boundary in one place strengthens a
foundation the others rest on. A composable stack deserves a composable proof, and
now it has one.

## The book, expanded; the site, alive

If the benchmarks are the evidence, the book is the argument in full. **[*Adversarial
Cognition*](https://firstpair.org/read/adversarial-cognition/)** has grown from a
single-benchmark release note into the trilogy's companion: a sweeping,
from-first-principles Introduction on type-level security and TypeDID; a part
each for cognition, catalog, and capability, every one self-contained; the *A
claim is a boundary* chapter; and a glossary and index that hold the whole
vocabulary. It is written to be **durable** — it describes the systems and the
*why*, never the shifting numbers, which live in a companion results report — so
it does not go stale between runs. Read it in the [FirstPair
reader](https://firstpair.org/read/adversarial-cognition/), or take the
[PDF](https://adversari.al/book/adversarial-cognition.pdf) and
[EPUB](https://adversari.al/book/adversarial-cognition.epub) from adversari.al.

And the collection has a living face. **[adversari.al](https://adversari.al)** now
carries all three benchmarks — [cognition](https://adversari.al/cognition),
[catalog](https://adversari.al/catalog), [capability](https://adversari.al/capability)
— and opens with a picture of the whole thesis in motion: data percolating upward
through the governed boundaries into an append-only ledger, while what is forged,
stale, or replayed flares red at the membrane and is turned away, never recorded.

## Get involved, and run it yourself

This is a young collection, and we would far rather it be contested than ignored —
v2 exists because someone contested it well. The most useful contribution is a
**vendor-authored adapter** for a system not yet in the comparison; the contract
is small, and your adapter declares exactly what your system enforces — we will
never fake a capability on your behalf, and we would genuinely like to publish
your numbers next to ours. Sharper fairness objections are welcome as issues; the
v2 tracking issue is open now.

```sh
git clone https://github.com/querygraph/adversarial-cognition
cd adversarial-cognition
python3 -m unittest discover -s tests -p 'test_*.py' -q   # the reference is the CI gate
docker compose run --rm benchmark                          # the full comparison → out/RESULTS.md
```

Cognition may be as ambitious as you like. In the enterprise, the evidence must
be conservative: a model may propose anything; only a capability-bound commit may
write; and every write leaves a receipt a stranger can verify. That is not a
constraint on what these systems can do. It is the precondition — buildable,
composable, and provable — for trusting them with anything that matters.
