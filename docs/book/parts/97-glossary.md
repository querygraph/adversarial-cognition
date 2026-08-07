# Glossary

Every term of art in this book, in one place. Terms are grouped by the layer
they belong to; within each group, they are ordered so that each definition can
lean only on the ones before it.

## The stack

**QueryGraph** — a stack for governed, auditable answers over enterprise data.
Its applications (Navigator, QGLake, semantic models) consume Marciana through a
thin integration and never reach past it into the foundations.

**Marciana** — the governed cognition and memory engine; the composition layer
that owns the four verbs, cognition jobs, the memory ledger, receipts, and
recovery. The subject of Parts I–V.

**TypeSec** — the authority layer. Owns capabilities, policy, protected content,
labels, retention, quarantine, proposal validation, and the identity system. Its
capability-gated vault is the only authority that may reveal or mutate protected
memory. The subject of Part VII.

**TypeDID** — the identity system within TypeSec. A cryptographic decentralized
identifier bound to each request; without one, a request has no scope. The basis
of unforgeable identity and of commit-bound receipts.

**Grust** — the persistence layer. Generic graph and query types, transactions,
guarded commits, and durable backends. Owns the physical, atomic commit that a
mutation maps into.

**Sail** — the compute layer. Generic Arrow and Spark-Connect execution. Runs
the computation that produces proposals; never receives an authoritative
mutation handle.

**LakeCat** — the governed catalog. Iceberg catalog state, provable
transactions, and governed-scan proofs. The subject of Part VI.

## Identity and cryptography

**Digest (hash)** — a short, fixed-length fingerprint computed from data (this
book's systems use SHA-256), with two properties: identical input always yields
the identical fingerprint, and no one can construct a different input with the
same fingerprint. The atom of verifiable evidence.

**Domain separation** — mixing a purpose label into a digest so that a
fingerprint computed for one purpose can never be mistaken for one computed for
another. A small discipline that closes an entire class of splicing attacks.

**Decentralized identifier (DID)** — an identity backed by cryptographic keys
rather than a shared secret, so a request *proves* who issued it instead of
presenting a password anyone could have copied.

**Signature** — a cryptographic seal over exact bytes that only the holder of a
private key can produce and anyone with the public key can check. TypeDID signs
with Ed25519 and encrypts via X25519 key agreement feeding a ChaCha20-Poly1305
cipher.

**Envelope** — TypeDID's sealed message: signed by the sender, encrypted to the
recipient, with the signature covering a canonical, length-framed transcript of
the whole so that tampering, splicing, replaying, back-dating, and key-confusion
each produce a flat cryptographic rejection.

**Bearer token** — a signed note authorizing *whoever holds it* (OAuth and JWT
are the ubiquitous forms). Tamper-proof but theft-transparent: stolen is as good
as issued. The floor of Part VII's ladder.

**Replay** — presenting a captured, once-valid message or credential a second
time. Defeated by nonces, replay stores, expiry windows, and idempotency —
durably, so a restart does not amnesty the attacker.

## Ledgers, catalogs, and transactions

**Table** — rows and columns. In a data lake, not an object inside a database
but a set of files plus the metadata that says which files.

**Data lake** — an architecture in which tables live as ordinary files in cheap
object storage, readable by any query engine, rather than inside one database.

**Object storage** — a service (Amazon S3; its open-source stand-in MinIO) that
stores files in buckets and serves them back. Infinitely dumb, infinitely
scalable.

**Parquet** — the compact, columnar file format in which lake tables usually
keep their rows.

**Apache Iceberg** — the open table format that makes files into tables: each
version of a table is an immutable *snapshot* described by a *metadata file*
listing exactly the data files that belong to it.

**Catalog** — the service that holds, per table, the single pointer to the
current metadata file. The keeper of "which files *is* the table right now."
LakeCat, Nessie, Polaris, and Gravitino all speak the Iceberg REST protocol.

**Commit** — the moment a table changes: validate the update, write the new
metadata file, advance the pointer. The unit of everything Part VI measures.

**Lost update** — the original sin of concurrency: two writers race, and one's
committed work is silently replaced by the other's, with no error and no trace.

**Compare-and-swap (CAS)** — the defense: a commit that says "advance the
pointer *if it still points where I last saw it*." The stale racer is rejected
instead of destroying work. Also called optimistic concurrency.

**Ledger** — a record with obligations: durable entries, never erased (a
correction is a new entry), each following from the last, verifiable later by a
stranger. What a catalog becomes when its transactions are provable.

**Idempotency key** — a unique key attached to an operation so that a retry
returns the stored result of the first execution instead of applying the change
twice. Same key, same answer, exactly one effect.

**Transactional outbox** — the announcement of a change written *inside the
same atomic transaction* as the change itself, so downstream evidence can never
be lost to a crash between committing and telling anyone.

**Receipt** — a record of one operation whose fields are sealed by their own
digest, so any alteration is self-evident without the server's help. In
QueryGraph, versioned, TypeDID-bound, and deterministic: identical runs produce
identical receipts.

**Receipt chain** — each receipt carries the digest of its predecessor, linking
history into a sequence that cannot be silently reordered, trimmed, or spliced.

**Offline verification** — checking evidence with no help from — and no trust
in — the server that produced it. What elevates a receipt from assertion to
evidence.

**Tombstone** — the receipt covering a deletion, so that even removal leaves
evidence that it happened, when, and under whose authority.

**Provable transaction** — the executable definition of Part VI: a commit with
CAS, idempotent replay, audit and outbox staged atomically, and a chained,
offline-verifiable receipt, all evidence hash-only.

**Governed-scan proof** — LakeCat's cryptographic evidence that a read came from
a specific authorized snapshot under a specific policy. A proof of the scan, not
of arbitrary text a caller staples to it.

**Lineage** — the recorded path from source, through authorization and
computation, to committed result — every node carrying an identity and a digest.

## Authority

**Authentication** — *who are you?* Answered by TypeDID.

**Authorization** — *given who you are, what may you do?* The subject of Part
VII.

**Capability** — authority as an object: a non-cloneable, single-purpose token
that must be *held* to act and is consumed by the exact operation it authorizes.
In TypeSec, a typed value `Capability<P, R>` with no public constructor,
mintable only through a policy decision.

**Policy engine** — a centralized decision point (OPA with the Rego language;
Amazon's Cedar) that answers allow-or-deny per request. Expressive and
default-deny — but the decision evaporates; nothing travels.

**Relationship-based access control (ReBAC)** — deriving decisions from a graph
of relationships ("editor of the folder containing the doc"), after Google's
Zanzibar design; embodied in SpiceDB and OpenFGA.

**Capability token** — portable, shrinkable authority: Macaroons (caveat chains
under HMAC), Biscuit (public-key blocks with logic-language caveats), UCAN
(DID-rooted delegation chains).

**Caveat** — a restriction appended to a capability token, cryptographically
folded in so it can be added but never removed.

**Attenuation** — the property that delegated authority can only *narrow* —
fewer grants, a shorter lease — never widen. The single most important word in
Part VII.

**Lease** — an expiry on authority: a capability is minted to die, and a use
past its lease is inert.

**Revocation** — killing authority before its lease ends: by individual id, or
by *epoch* — a mid-lease revoke-everything that invalidates all outstanding
capabilities minted before it.

**Ambient authority** — power that is simply "in the air" around a program
rather than attached to a specific request. The precondition for the confused
deputy; abolished by deny-by-default capability discipline.

**Confused deputy** — a program with standing powers tricked into exercising
them on an attacker's behalf. The classic argument for capabilities: a deputy
that holds no ambient power cannot be confused into lending it.

**Information-flow label** — a secrecy level (public, internal, sensitive)
riding on the data itself, so that reads above the reader's clearance are
redacted and lowering a label requires an explicit *declassify* grant.

**Clearance** — the maximum label a principal may read. Distinct from tenancy:
two users of one organization can differ in clearance, which is exactly the
distinction the recorded cognition run found some systems missing.

## Type-level security

**Type** — the compile-time classification of a value that determines what a
program may do with it. The load-bearing idea of the Introduction: rules encoded
in types are checked before the program ever runs.

**Phantom type** — a type parameter that carries no run-time data yet makes two
otherwise-identical types distinct to the compiler — how `Capability<CanRead, R>`
and `Capability<CanWrite, R>` become as different as a number and a sentence, at
zero cost.

**Sealed trait** — a family of types that outside code cannot extend. TypeSec's
permissions are sealed: the vocabulary of authority is closed, and closed
vocabularies can be reasoned about completely.

**SecureValue** — TypeSec's opaque envelope for protected data: carries an
information-flow label, allows transformation without extraction, keeps the
stricter label when values combine, and yields cleartext only to a matching
capability.

**Typestate** — encoding a protocol's states as distinct types, so that
operations invalid in a state simply do not exist on it. An unauthenticated
agent has no authenticated methods to call — not denied; absent.

**Unforgeable** — the recurring adjective, meaning something precise: possession
is constructible only through the guarded path. A `Capability` cannot be
struct-literaled into existence; a verified message cannot be fabricated from
caller-supplied fields; a receipt is a function of what happened, not a form to
fill in.

## The benchmarks

**MARCIANA-ADVERSARIAL-v1** — the cognition benchmark: eighteen cases, nine
hard gates, six systems (Parts IV–V, Appendices A–B).

**CATALOG-PROVENANCE-v1** — the provable-transaction benchmark: seventeen
cases, eleven capabilities, seven hard gates, four catalogs (Part VI, Appendix
C). Its companion, **catalog-bench**, measures the commit's speed — the cost of
what provenance buys.

**CAPABILITY-ADVERSARIAL-v1** — the authority benchmark: eighteen cases, eleven
capabilities, ten hard gates, ten systems in three bands (Part VII, Appendix D).

**Hard gate** — a named safety property that must be zero for a benchmark to
pass; never averaged into a quality score. The constitutional device shared by
all three benchmarks.

**Capability-declared scoring** — the fairness rule shared by all three: each
system's adapter declares what the system enforces; unclaimed capabilities are
reported *unsupported*, never scored, and never faked; a gate can only be
tripped by a claim.

**Adapter** — the thin program that drives one system through a benchmark's
cases using the system's own real interface, declaring its capabilities and
returning outcomes — never re-implementing a check the system lacks.

**Corpus digest** — the SHA-256 fingerprint of a benchmark's entire expectation
set, stamped into every report, so that no expectation can be quietly adjusted
after the fact and two runs are demonstrably of the same benchmark.

---
