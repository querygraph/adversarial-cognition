# Conclusion — One boundary, composed

This book has been three descents. From an agent's memory to the catalog beneath
a data lake to the raw question of authority itself, each part began with a
humble object — a throwaway sentence, a file in a bucket, a login — and built
from it, in its own vocabulary, to a benchmark that went looking for the seam
where a promise tears. Read that way, the three are neighbors: adjacent chapters
about adjacent systems that happen to rhyme.

They do more than rhyme. Ascend now, look back down the way we came, and the same
few figures are standing in every part, wearing the local costume. They are not
echoes. They are the same characters, because underneath the three domains there
is one boundary, built once and composed everywhere — and the composition, not
any single benchmark, is the real argument of the book.

## The recurring cast

**One adversary.** The attacker in Part IV, planting instruction-shaped memories
and replaying nonces across a restart, is the attacker in Part VI, racing the
metadata pointer and editing a receipt, is the attacker in Part VII, forging a
capability and aiming it at the wrong resource. Grant this single character
control of content, of the request path, and of the clock, and every part of the
stack must answer the same three questions: can it be forged, can it be replayed,
can a stale thing overwrite a newer one? A benchmark is just that character, made
deterministic and let loose.

**One artifact of trust: the receipt.** Every layer's promise resolves to the
same object — a record sealed by its own digest, verifiable by a stranger with no
help from the server that made it, and *deterministic*, so that two identical
runs produce two identical receipts or the audit trail means nothing. The
cognition commit issues one; the catalog transaction issues one; the capability
decision leaves one. In each, the same subtle discipline: a receipt is a function
of what actually happened, never a form the caller fills in afterward. The
receipts prove; they do not grant.

**One atom: the digest.** Beneath every receipt is a domain-separated hash — a
fingerprint that binds a purpose into its bytes so that evidence computed for one
thing can never be mistaken for evidence of another. It is the same primitive in
TypeDID's length-framed envelope transcript, in the catalog's chained
transaction receipts, and in Marciana's unforgeable lineage. Learn it once in the
glossary and you have read the machinery of all three.

**One door.** In each domain, authority has exactly one home and exactly one
guarded entrance. Marciana's four verbs — remember, recall, improve, forget — all
enter the same capability-gated vault; there is no private path to a mutation.
The capability system has one minting function and no public constructor, so the
mere existence of a capability is proof the policy already approved it. The
catalog has one commit path, and a change that cannot be made atomically is not
made at all. Everywhere, the same refusal of the convenience API that quietly
does an end-run around the gate.

**One refrain: proof is not authority.** This is the deepest of the parallels,
and the one the stack is organized around. A verified TypeDID identifies who is
asking and grants nothing — authorization is a separate, later decision. A valid
governed-scan proof identifies an authorized snapshot and does *not*, by itself,
prove that some text a caller staples to it came from there. A bearer token's
whole disease is that holding it *is* being authorized. And when the Python
Iceberg client sent `Authorization: Bearer None` — an authority never
established, presented with total confidence — a governed catalog rejected it,
for the same reason a capability cannot be struct-literaled into existence and a
"verified" message cannot be fabricated from caller-supplied fields. Possession
of a proof is never silently promoted to possession of authority. The two are
kept apart on purpose, in that order, always.

**One direction: things only narrow.** Authority attenuates — a delegated
capability may drop grants and shorten its lease but never widen or extend.
Memory forgets surgically — removing exactly the forgotten fact and its
derivations, never more, never less. The catalog's compare-and-swap lets the
newer state win and rejects the stale writer rather than letting it silently
overwrite. In every part, the conservative move is the safe move, and the system
is built so that nothing widens quietly.

**One constitution.** And the benchmarks that test all this share a single
scoring law, stated the same way three times. Safety failures are counted in
named hard gates that must be zero and are *never* averaged into a quality score —
because a system that recalls brilliantly and occasionally leaks is not a
slightly worse system, but a different and disqualifying kind of thing. Each
system is scored only on what its adapter *declares* it enforces; an unclaimed
capability is reported unsupported, never faked in either direction; a gate can
be tripped only by a claim. The corpus is pinned by its own digest so no
expectation can be quietly adjusted after the fact. This is why TypeSec appears
in its own benchmark holding seventeen of eighteen rather than a triumphant
eighteen — the fairness machinery leaves a visible, truthful mark even on the
author's system, which is exactly what should make the seventeen believable.

## Why the parallels are not a coincidence

Six recurring figures across three unrelated domains would be a curiosity. They
are not a coincidence, and the reason is the whole point: these are not three
boundaries that happen to resemble one another. They are one boundary, built in
the foundations and *composed* into each domain.

The stack is layered so that authority has a single authoritative implementation.
TypeDID and TypeSec own identity and capability; Grust owns the atomic commit;
Sail owns computation and is never handed a mutation; LakeCat owns catalog proof;
Marciana composes them into governed cognition — and the load-bearing rule is
that the foundations never depend on the layers above them. Because authority has
one home, "who can change this?" has one answer, and that answer can be audited.
The parts of this book are not siblings; they are floors of one building. Marciana
*is* TypeSec's memory crate, so the cognition benchmark stands squarely on the
capability benchmark's subject. LakeCat's governed-scan proof is consumed by
Marciana's trusted adapter, bound to a one-use digest of the exact draft, so the
catalog's guarantee flows upward into the memory's. Prove the boundary in one
domain and you have not merely encouraged confidence in the others — you have
strengthened a shared foundation they all rest on.

The composability runs one level higher still, into the method itself. The three
benchmarks share not only a constitution but a mechanism: one JSON adapter
protocol, one notion of a declared capability, one corpus-digest discipline, one
ledger of hard gates. A fourth layer of the stack — a new domain, a new
adversary — would not need a new theory of testing. It would slot into the same
frame, declare its capabilities, submit to the same gates, and take its honest
marks. A composable stack deserves a composable proof, and it has one.

## The price, and what it buys

At every floor, the same trade recurs, and it is worth naming plainly because
"governed" can sound like a tax on capability rather than the thing that makes
capability safe to deploy. Governance is a per-operation toll — a couple of
milliseconds of durable bookkeeping per catalog commit, a state machine of
authorizations per cognition job, a minting ceremony per capability. What the
toll buys is a *bounded blast radius*. A forged source cannot commit; a stale
proposal cannot overwrite a newer fact; a replayed request cannot double a
mutation; a revoked capability cannot act; a deleted record cannot return. The
governance does not restrain the useful cases. It forecloses the catastrophic
ones, and by foreclosing them it lets you turn the useful ones *up* — let the
model propose freely, let the agents act broadly — precisely because the commit
boundary underneath is conservative.

That is the argument, composed and complete. A promise worth trusting is not made
loudly; it is made in the grammar of the system, so that breaking it is not
against the rules but against the language. Build that grammar once, in types and
identities and receipts. Compose it into memory, into transactions, into
authority. Then attack each composition on purpose — eighteen and seventeen and
eighteen ways — and publish, gate by gate, exactly what held. Cognition may be as
ambitious as you like. In the enterprise, the evidence must be conservative. A
model may propose anything; only a capability-bound commit may write; and every
write leaves a receipt that a stranger, months later, can verify without trusting
the model, the operator, or the vendor who sold it. That is not a constraint on
what these systems can do. It is the precondition — buildable, composable, and
provable — for trusting them with anything that matters.

---
