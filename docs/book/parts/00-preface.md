% Adversarial Cognition
% Alexy Khrabrov
% First Pair Press, 2026

![Plato disputing with Diogenes over the rug at an Academy symposium — the original adversarial gesture, and the frontispiece of a book about attacking a boundary on purpose.](cover/adversarial-cognition-headboard.png)

# Preface — When memory becomes a liability

There is a moment, early in every enterprise's encounter with agentic AI, when
memory stops being a feature and becomes a liability. It happens the first time
someone in the room asks a question that has nothing to do with model quality.
Not "how good is the recall?" but: *who was allowed to see that? how do we know
it's true? can we delete it and prove it's gone? and if a regulator asks what
the system knew on a particular day, can we answer without guessing?*

Those are not machine-learning questions. They are database questions, security
questions, and audit questions, and they arrive whether or not anyone planned
for them. An agent that remembers is not a model with a longer prompt. It is a
system that makes claims about the world, keeps those claims over time, decides
who may act on them, and changes them — ideally without losing the reasons they
changed. Ship that system without a governed boundary and you have not built a
memory; you have built an unaudited, self-modifying database with a language
model for an administrator.

This book began as the story of that boundary in one domain — **Marciana**, the
governed cognition engine of the **QueryGraph** stack, and the benchmark,
**MARCIANA-ADVERSARIAL-v1**, that attacks it on purpose. It has since grown the
way the stack itself grew: by discovering that the same boundary, and the same
adversary, reappear at every layer. The catalog that anchors a data lake faces
the same questions as the memory that anchors an agent — *who may change this,
and can you prove what happened?* — and so does the authorization layer beneath
them both, and so, finally, does the agent itself, the orchestrator that crosses
all of these boundaries in a single run. So this book now holds four benchmarks,
one for each layer, each attacked the same way and scored by the same unforgiving
rules.

If you have never heard of QueryGraph, you are the reader this book is written
for, and nothing here presumes prior acquaintance with any of it. The
Introduction lays the shared foundation — security written into the *types* of a
program, identity you cannot fabricate, lineage you cannot forge. Parts I
through V tell the cognition story in full: the enterprise memory problem, the
stack from first principles, Marciana, the benchmark, and what it found when
turned loose on Marciana and a field of widely used open-source memory systems. Part
VI descends to the catalog — beginning with what a table in a data lake even
*is* — and asks which catalogs can prove their transactions, and what such proof
costs. Part VII descends further still, to authority itself, and runs ten
authorization systems — from the humble signed token to policy engines,
relationship graphs, capability tokens, and TypeSec — through the same
adversarial mill. Part VIII rises back to the surface, to the agent that crosses
every one of these boundaries at once, and asks the question the whole stack was
built to answer: when a framework hands a model a tool, what keeps its authority
impossible to confuse — and how far can two of the industry's real policy
engines carry that burden before the ground gives way beneath them? Each part is
self-contained and explains every term it uses; a glossary and an index at the
back hold the whole vocabulary in one place.

The thesis is simple and, I hope, by the end, unavoidable: in the enterprise,
cognition may be as ambitious as you like, but the evidence must remain
conservative. A model may propose anything. Only a capability-bound commit may
write. And every write must leave a receipt that a stranger, months later, can
verify without trusting the model, the operator, or the vendor who sold it.

---

