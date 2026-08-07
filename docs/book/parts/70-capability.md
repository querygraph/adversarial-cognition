# Part VII — The capability: authority as an object

## The question every system answers badly

This part, like the last, is self-contained: it assumes you have logged into
something, and builds everything else from there. Its subject is the oldest
question in computing security — *may this caller do this thing?* — and a
benchmark that asks it adversarially of a whole field of systems at once, from
the humble signed token to QueryGraph's own TypeSec.

Begin by splitting the question in two, because the split is where half the
world's confusion lives. **Authentication** asks *who are you?* — and is
answered with passwords, keys, and the TypeDID signatures of the Introduction.
**Authorization** asks *given who you are, what may you do?* — and it is the
harder question, because its answer must survive delegation, time, retries, and
malice. This part is about authorization, and about a serene, radical answer to
it: that authority should be an *object* — a thing you hold, inspect, narrow,
and revoke — rather than a *fact about you* scattered through other people's
databases.

## Four families, one ladder

Every authorization system in production today belongs to one of a few families,
and it pays to meet them in ascending order of ambition — because the benchmark
at the end of this part is, in essence, this ladder made executable.

**The bearer token.** The workhorse of the modern web — OAuth, JWT — is a signed
note: *the holder of this may read calendars, valid until Friday.* The signature
(a cryptographic seal only the issuer can produce) makes the note tamper-proof:
change "calendars" to "bank accounts" and the seal breaks visibly. This is real
protection, and its limits are just as real. The note authorizes the *holder* —
whoever that is; stolen is as good as issued. It cannot be narrowed: to give a
subordinate a smaller version you must go back to the issuer. And it dies only by
expiring; there is no built-in way to kill it *now*.

**The policy engine.** The enterprise's answer — OPA with its rule language,
Amazon's Cedar — centralizes the rules: every request is sent to a decision
point, which consults policy and answers allow or deny. Its cousin,
**relationship-based access control** (ReBAC — Google's Zanzibar design, embodied
in SpiceDB and OpenFGA), derives the decision from a graph of relationships:
*Alice may edit the doc because Alice is an editor of the folder that contains
it.* These systems are genuinely expressive and genuinely default-deny. But
notice what they hand the caller: *nothing*. The decision evaporates the moment
it is made. There is no artifact to carry, delegate, or verify later — only the
standing obligation to ask the server again, and to trust it.

**The capability token.** The research lineage — Macaroons out of Google, Biscuit
from the systems community, UCAN from the decentralized web — makes authority
*portable and shrinkable*. A macaroon is a bearer note that anyone can narrow by
appending a **caveat** ("…only table 7", "…only before 5 pm"), each folded into a
cryptographic chain so caveats can be added but never removed. Authority that can
only shrink as it is passed along is called **attenuation**, and it is the single
most important word in this part. Biscuit adds public-key verification and
logic-language caveats; UCAN roots the chain in decentralized identifiers like
TypeDID's. These are true capabilities — but they are still *just* tokens:
nothing gates their minting, and revocation is an afterthought bolted on outside.

**The capability system.** The top of the ladder is where TypeSec lives, and the
Introduction already showed its heart: authority as an unforgeable *typed* value,
`Capability<P, R>`, mintable only through a policy decision, narrowable only
downward, bound to one resource, expiring on a lease, revocable mid-flight, and
required — by the compiler — for every protected act. Where the token families
make authority portable, and the policy families make it governed, a capability
system makes it *both*, and adds the one thing none of the others attempt:
**information-flow labels**, secrecy levels riding on the data itself, so that
reading above your clearance is not denied so much as rendered inexpressible.

One classic villain stalks this whole ladder, and deserves his formal
introduction: the **confused deputy**. A deputy is any program that acts on
behalf of others while holding standing powers of its own — and an attacker who
cannot do a thing directly can often *ask the deputy* to do it, borrowing the
deputy's authority for a purpose it was never granted. The billing service that
can delete files, tricked into deleting *your rival's* files, is confused in
exactly this way. Ambient authority — power that is simply *in the air* around a
program rather than attached to a specific request — is what makes the confusion
possible. The capability answer is austere and total: a deputy holds no ambient
power at all; every request must arrive *carrying* the capability that justifies
it, and an unaccompanied request — however politely phrased — finds no authority
lying around to borrow.

## CAPABILITY-ADVERSARIAL-v1: the ladder, attacked

The benchmark grants the adversary the request path, the clock, and a wallet of
captured or hand-crafted tokens, and sets it loose on eighteen cases across
eleven claimed capabilities. Each case is one clean attack with one correct
outcome. Forge a capability, or tamper one to widen its grants — the seal must
fail. Delegate with *broader* permissions or a *longer* lease than the parent —
attenuation must refuse to go up. Aim a capability for `customer/2` at
`customer/1` — instance binding must hold. Replay a capability after revocation
(by id, or by a mid-lease revoke-everything epoch) or past its lease — it must be
dead. Call a tool with no capability at all — deny-by-default must find nothing
to borrow. Use a search authority to drive a delete — the deputy must refuse the
confusion. Read above clearance — the label must redact, not reveal. Smuggle an
unexpected field into the request itself — the wire must reject it before policy
ever runs.

Ten hard gates with the by-now-familiar constitution — `forged_capability_accepted`,
`permission_widened`, `lease_extended`, `revoked_capability_honored`,
`confused_deputy_exploited`, `ambient_tool_call_executed`, `label_leaked`, and
their siblings — each an authorization failure that fails the release outright,
each trippable only by a capability a system *claimed*. And the same
capability-declared honesty: every system runs live, through its own adapter,
over its **real** library — no simulations, no reimplemented checks — and a
system is scored only on what it declares. The roster is the ladder itself: JWT
as the bearer floor; Macaroons, Biscuit, and UCAN as the token band; Cedar, OPA,
SpiceDB, and OpenFGA as the decision band; TypeSec as the capability system; and
a dependency-free reference modeling the idealized full boundary. The exact
coverage each system posts on a given run lives, as ever, in the companion
results report; what the book keeps is the shape, because the shape is the
argument.

## Reading the bands

No gate trips anywhere in the field — every system holds every property it
claims, which is itself a compliment to a mature ecosystem. What separates them
is *coverage*: how much of the boundary each can even claim. And the coverage
clusters into bands so cleanly that the table reads like a geological
cross-section.

The four decision engines — Cedar and OPA reasoning from policy rules, OpenFGA
and SpiceDB from relationship graphs, two mechanisms with nothing in common
internally — land on *identical* coverage: instance binding, deny-by-default,
deputy resistance, and nothing more. That is what a decision, however
sophisticated, can enforce — and all that it can, because a decision engine
mints nothing. There is no object to attenuate, revoke, lease, or verify
offline; there is only the server's answer, evaporating as it is spoken. The
token band climbs higher exactly as far as its cryptography carries: a caveat
chain buys real attenuation; public-key blocks and revocation identifiers buy
the band's best result; a younger library claims less, conservatively. But every
token system falls off the same cliff: nothing gates the *mint* — anyone holding
a root key may issue anything — and nothing in any of them has ever heard of a
clearance label.

TypeSec sits at the top of the cross-section, one case short of the idealized
reference — holding the policy-gated mint *and* the monotone attenuation *and*
the instance binding, the epoch and id revocation, the leases, the label-gated
reveal and declassify, the deny-by-default tool plane, the audited decisions —
because it is not a better token or a smarter decision engine but the
*composition* the ladder was climbing toward: the decision engine's governance
wrapped around the token's portability, expressed in types that make the whole
arrangement unforgeable at compile time. The single case it declines,
wire-integrity — rejecting a request whose serialized form smuggles unknown
fields — it declines *honestly*, because the capability core has no request wire
to harden: minting takes typed arguments, not parsed bytes. No real system in the
field claims that column either; only the reference's idealized boundary holds
it. The abstention is the benchmark's fairness machinery leaving a visible,
truthful mark on its own author's system — which is precisely what should make
the rest of the row believable.

The moral of the cross-section deserves its aphorism: **policy engines decide,
capability tokens travel, bearer scopes gate — and only a capability system
makes the authority itself unforgeable, attenuation-monotone, instance-bound,
revocable, and label-aware, all at once.** That intersection is not a luxury.
It is the minimum an autonomous agent needs before you can hand it power and
sleep: every one of this part's eighteen attacks is something a prompt-injected
model, or a compromised tool, will eventually *try*.

---
