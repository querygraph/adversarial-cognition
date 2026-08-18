# Part VIII — The agent: authority on two planes

## The layer where every boundary is crossed at once

The three benchmarks behind us each guarded a single seam. Marciana guarded a
memory; the catalog guarded a table's history; the capability ladder guarded
authority itself. This part is about the layer that touches all of them in one
breath — the **agent**, the orchestration framework that takes a model's
suggestion and turns it into a tool call, a database scan, an email, a write.
An agent is the one program in the stack that crosses a tenant boundary, a
catalog boundary, a purpose boundary, and a channel boundary in the course of a
single ordinary task, and it does so on the word of a model that an attacker may
be quietly steering. If the earlier parts asked whether each door could be
forced, this one asks the harder question: when a single visitor walks through
all the doors in one visit, what keeps each door honest?

The frameworks that do this orchestrating — Pydantic AI, LangChain, CrewAI, and
their peers — are not security products, and it would be unfair to grade them as
if they were. What they *do* offer, each in its own vocabulary, is a place to
stand between the model's suggestion and the tool's execution: a pre-tool hook,
an approval gate, a piece of middleware. The benchmark of this part,
**AGENTGYM-v1**, does not test whether those hooks exist. It tests what a
decision made *at* such a hook can actually bind — and it discovers that the
answer depends entirely on which of two planes the danger lives in.

## Two planes, and the door that sees one

Here is the distinction the whole part turns on, and it is worth slowing down
for, because it is the pivot on which every result below swings.

When a model proposes a tool call, the integration holds, right then, a set of
facts about the request: the subject making it, the tool named, the resource
string, the stated purpose, the delegated user, the arguments. Call these the
**request-plane** facts — everything legible at the moment of dispatch. A
poisoned catalog name that points at a neighbor's table, a query widened to
`SELECT *`, a purpose quietly relabeled from research to marketing, one user's
OAuth grant spent under another user's name — each of these is an adversarial
value sitting in plain sight in the request itself.

But a second kind of fact does not exist yet when the request is inspected. It
comes into being only *at or after execution*: the sensitivity label on the
data that a scan is about to return; the hash of the call a human actually
approved, as against the one now being run; the receipt chain a replay must
match; which tenant a parallel branch's result truly came from; whether a
capability has already been spent once. Call these the **execution-plane**
facts. They are not in the request because they cannot be — they are properties
of the world the request is about to change, not of the request.

Most real agent breaches, it turns out, do not live on the request plane at all.
They are valid request-plane values whose harm surfaces only on the execution
plane: an authorized Gmail send whose body was stuffed, by a prompt injection in
a database cell, with raw household rows; an approved Drive write whose arguments
were edited in the instant between approval and execution. The request looks
correct at dispatch because, on the plane a decision point can see, it *is*
correct. The AgentGym world — the same QG Energy Cooperative that runs through
this book, an analyst studying a utility dataset under an approved purpose, with
WorkOS granting the project and Arcade authorizing the SaaS tools — is arranged
so that each of its fourteen scenarios plants its attack in whichever plane the
real attack lives in, and then asks four enforcement modes which plane they can
bind.

## AGENTGYM-v1: four modes, one corpus

The corpus is fourteen scenarios, each a benign task paired with a matched
attack, and the same task is driven through every mode with a *scripted* model —
a predetermined sequence of tool calls — so that what is measured is the
enforcement substrate and not the weather of a live model. Four modes climb the
same ladder of ambition we have now seen twice:

**Native** is the deliberately weak floor: authenticate once, check one broad
entitlement, trust the validated arguments. It is a common integration pattern,
not a claim about the strongest middleware a careful engineer could write, and
it exists to mark the ground level.

**Open Policy Agent** and **Cerbos** are the two policy engines from the last
part, met again — but this time not as coverage rows in an authority ladder, as
*live competitors* enforcing the agent boundary. Each runs as a real container,
evaluating an honest translation of the world's policy: OPA from Rego rules,
Cerbos from a typed principal/resource/action model with conditions. They are
configured to their strengths, with the strongest faithful rendering of the
constraints, precisely so that where they stop is not a matter of a weak setup.

**TypeSec** is the reference, the composition the earlier parts climbed toward —
the compiled Rust gate and ODRL engine, wrapped around the provider decisions,
and, crucially, *mediating execution* rather than only judging the request.

Each mode's verdict is enforced at each framework's own documented pre-tool hook,
and the oracle — as everywhere in this book — watches side effects, not
apologies. A mode earns nothing by *reporting* a denial; it earns safety only if
the forbidden effect never happened. WorkOS and Arcade appear as wire-faithful
emulators of their current contracts, with the fault injection — timeouts,
malformed responses, stale allows, replayed completions — that a real
integration must survive.

## Reading the line

The result is the cleanest cross-section in the book, because the line falls
exactly where the two planes divide.

The native floor, predictably, lets every attack through: a broad entitlement is
a skeleton key. And then the finding that makes the part worth writing. The two
real policy engines — OPA reasoning from rules, Cerbos from typed conditions,
two mechanisms with nothing in common internally — land on *identical* safety:
they block every one of the nine attacks whose adversarial value is a
request-plane fact, and they fail every one of the five whose deciding fact
lives on the execution plane. The sensitive content in an authorized channel;
the arguments edited after approval; the spliced receipt; the policy construct a
hand-translation never parsed; the parallel join that mixed tenants and spent a
capability twice — five attacks, and both engines are blind to all five, in the
same place, for the same reason. They are decision points, and a decision point
is never shown the second plane.

This is not the engines failing at what they do; it is the benchmark's fairness
machinery drawing an honest line. OPA and Cerbos are excellent, and they are
configured to their strengths, and they still cannot bind what they cannot see.
The safety gate — any forbidden side effect caps the grade — holds them at the
same grade as the weak floor, not because they are weak, but because in security
a door that holds nine times out of fourteen is a door that opens. TypeSec
clears the gate not by being a cleverer decision engine but by being a different
kind of thing: a substrate that sits *in* the execution path, so the content
label, the approval hash, the receipt chain, and the branch's provenance are
facts it holds rather than facts it never receives.

The moral earns its aphorism, and it is the one the whole stack has been
building toward: **a policy engine decides the request; only a substrate that
mediates the execution can bind what the request cannot say.** The agent is the
layer where that difference stops being academic — because the agent is the one
caller that will, on some ordinary Tuesday, carry a value that is individually
valid and collectively catastrophic through every door in this book at once, on
the suggestion of a model that someone else is steering. Two of the industry's
best engines will stop it nine times in fourteen. The last five are why the rest
of this book exists.

---
