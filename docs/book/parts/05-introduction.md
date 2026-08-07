# Introduction — The shape of a promise you can keep

Every system that stores something on your behalf is making you a promise. *I
will remember this. I will show it only to the right people. I will let only the
right people change it. And if you ever ask me what I did, I will tell you the
truth.* We have grown so used to hearing that promise broken — the leaked
database, the silent overwrite, the audit log that turns out to be fiction — that
we have quietly lowered our expectations to *probably*, *mostly*, *as far as we
can tell*. This book is about a stack that refuses to lower them, and about three
benchmarks that go looking, on purpose, for the exact moment a promise gives way.

The stack is **QueryGraph**. The promises it keeps are made in an unusual place:
not in careful code that checks the rules at the right moments, but in the
*types* — the compile-time skeleton of the program itself, the part a computer
verifies before the software is ever allowed to run. That is the single idea from
which everything in this book unfolds, and it is worth pausing on, because it
inverts the way most of us have been taught to think about security.

## Two ways to keep a rule

There are, at bottom, only two ways to make a program obey a rule.

The first is to *check* the rule while the program runs. Before revealing the
salary, ask the access-control list whether this user may see salaries; if yes,
proceed. This is how nearly all software works, and its weakness is not that the
check is wrong but that the check is *optional*. It sits in one code path and not
another. It can be forgotten in the function written under deadline, skipped in
the endpoint nobody remembered, duplicated slightly differently in three places
until the three disagree. The rule exists, but its enforcement is scattered
across every place someone remembered to enforce it, and security lives or dies
by the completeness of that memory. A single forgotten check is a breach.

The second way is to make the rule part of the program's *grammar* — to arrange
things so that a program which breaks the rule is not a program that fails at
run time, but a program that *will not compile*, the way a sentence with the verb
missing is not a false statement but not a statement at all. There is no code
path to forget, because the forbidden operation was never expressible in the
first place. The check is not skipped; it has been dissolved into the structure,
paid once at compile time, and thereafter free and unskippable forever.

QueryGraph's security layer, **TypeSec**, takes the second way, and its slogan is
disarmingly literal: *policies are encoded in types; violations are compile
errors.* To see how a slogan becomes a mechanism, we need one beautiful little
object.

## The capability that cannot be forged

In TypeSec, the authority to do something protected — to read a sensitive value,
to write to a governed record — is not a flag, not a boolean, not a row in a
permissions table. It is a *capability*: a value of a type written
`Capability<P, R>`, where `P` names a permission and `R` names a resource. A
`Capability<CanRead, Salary>` is the standing, portable proof that its holder may
read a salary. And here is the sleight of hand that is not a sleight of hand at
all: the two little names `P` and `R` are *phantom* — they carry no bytes, cost
nothing at run time — yet they make `Capability<CanRead, Salary>` and
`Capability<CanWrite, Salary>` genuinely *different types*, as different to the
compiler as a number is from a sentence. A function that demands the power to
write cannot be handed the power merely to read. Not *should* not — *cannot*. The
mismatch is a compile error, discovered before the program runs, every time,
with no exceptions and no vigilance required.

Now close the trap. The `Capability` type has no public constructor. There is
exactly one way in the entire system to bring one into existence: a function that
first consults the policy engine and mints the capability *only* if the policy
says yes. You cannot write `Capability { ... }` yourself; the language forbids
it. So the mere *existence* of a `Capability<CanRead, Salary>` anywhere in a
running program is, by construction, a proof that the policy engine already
approved this exact reading. The capability does not represent permission. The
capability **is** the permission, in the same way a key is not a note asking
politely to open the door. You hold it, or you do not; and you can only have come
to hold it through the one guarded door that mints it.

From this single object the rest of the edifice grows with a kind of inevitability
that is a pleasure to watch:

- **Sealed permissions.** The permissions themselves — `CanRead`, `CanWrite`,
  `CanReadSensitive` — belong to a *sealed* family that no outside code can
  extend. You cannot invent a new permission to slip past the ones that exist.
  The vocabulary of authority is closed, and closed vocabularies can be reasoned
  about completely.
- **Secured values.** Protected data does not travel as bare bytes but wrapped in
  a `SecureValue`, an opaque envelope that carries a secrecy *label* and refuses
  to yield its contents except to the matching capability. You may pass it around,
  combine it, transform it — and combining a secret with a public thing yields a
  secret, because the envelope always keeps the stricter label — but you cannot
  *read* it without proving you are allowed to. Information-flow control, enforced
  by the type checker.
- **Typestates.** An agent that has not authenticated is, to the compiler, a
  *different type* from one that has, and the methods that matter simply do not
  exist on the unauthenticated form. There is no "check if logged in"; there is
  only a door that isn't there until you are.

Notice what has happened. Every one of these is a rule that, in an ordinary
system, would be a run-time check somebody could forget. Here they are load-bearing
walls of the type system, and forgetting them is not a vulnerability — it is a
program that does not build.

## Identity that is not authority

There is a second foundation, and the discipline with which QueryGraph keeps it
*separate* from the first is the whole game.

Before any of this authority can be exercised, the system must know who is asking.
Most software answers with a bearer token — a long secret string that means
"whoever holds this is allowed." The trouble with a bearer token is right there in
the name: it authorizes the *bearer*. Copy it, steal it, fish it out of a log, and
you are, as far as the system can tell, the person it was issued to. The secret
and the identity are the same thing, so leaking the secret leaks the identity.

**TypeDID** severs them. It gives each participant a *decentralized identifier*
backed not by a shared secret but by a cryptographic key pair, so that a request
is *signed* by its sender rather than merely accompanied by a password. Under the
hood — and the care here is exquisite — every message is sealed into an envelope
that is signed with one key (Ed25519, for authentication) and encrypted to the
recipient with another (X25519 key agreement feeding a ChaCha20-Poly1305 cipher,
for confidentiality). The signature covers a *canonical transcript* of the whole
envelope, built so that no two different messages can ever hash to the same
signed bytes: every field is length-framed, every purpose is domain-tagged, so
that tampering with a claim, reordering the fields, splicing a ciphertext from one
envelope onto the header of another, back-dating, replaying, or repointing the
"which key signed this" field at the wrong key each produce, not a subtle
misbehavior, but a flat cryptographic rejection. A stolen log file contains
nothing an attacker can replay as you, because what the log holds is
identifiers and digests — evidence that something happened — never the reusable
authority to make it happen again. **The receipts prove; they do not grant.**

And now the line that the entire stack is organized around, stated as an
invariant and enforced as one: **verified identity is not authority.** Proving who
you are does not, by itself, let you do anything at all. A verified TypeDID tells
the system the *subject* of a request — and then, and only then, that subject is
handed to the policy engine, which decides whether to mint a capability. Identity
answers *who*; capabilities answer *what may they do*; and the bridge between them
is a policy decision that leaves a receipt. Even the payload of a verified message
arrives sealed inside a `SecureValue`, unreadable until a capability opens it — so
that authenticating a message and being *allowed to read it* remain two distinct
events, in that order, always.

## One stack, one boundary, three attacks

Hold those two foundations together — authority you must *hold* as an unforgeable
typed object, identity you *prove* rather than *present* — and you have the shape
of every honest promise in the system. A caller proves who they are. A policy
turns that identity into a narrow, typed, expiring capability. The capability, and
nothing else, opens the protected operation. And the whole path leaves a receipt
that a stranger can check months later without trusting the model, the operator,
or the vendor who sold the thing.

QueryGraph builds that shape once and then *reuses* it across wildly different
domains, and that reuse is the reason this book has the structure it does. The
same boundary that governs an AI's memory also governs a data lake's transactions
and a fleet of agents' permissions — because at bottom all three are the same
question wearing different clothes: *who may reveal or change this, and can you
prove what happened?* Three domains, one boundary, and therefore three ways to go
looking for the seam where it tears:

- **Cognition** — can an AI's memory be made to leak, to double-commit, to
  resurrect a deleted fact, to forge its own provenance? This is Marciana, and the
  benchmark is MARCIANA-ADVERSARIAL-v1.
- **Catalog** — when a data lake accepts a transaction, can you *prove*, offline
  and months later, what it did? This is LakeCat, and the benchmark is
  CATALOG-PROVENANCE-v1, shadowed by a performance benchmark that measures what
  that proof *costs*.
- **Capability** — is the authority a system grants one that an attacker, or the
  model itself, cannot forge, widen, replay past revocation, or aim at the wrong
  resource? This is TypeSec's own boundary, and the benchmark is
  CAPABILITY-ADVERSARIAL-v1, run against the whole field of the world's
  authorization systems.

Each of the three parts that follow is written to stand on its own. If you have
never thought about a database ledger, the catalog part begins with what a ledger
*is*. If you have never minted a capability, the capability part begins with what
authorization *is*. You may read them in any order, or only the one you came for.
But read together they make a single argument, and it is the argument of the whole
book: that a promise worth trusting is not one made loudly, but one made *in the
grammar of the system* — so that breaking it is not against the rules, but against
the language — and then attacked, on purpose, eighteen and seventeen and eighteen
ways, until what remains standing is not a claim but a receipt.

Let us begin where the trouble first announced itself: with a memory that
remembered too well.

---
