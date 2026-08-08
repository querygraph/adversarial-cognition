# Part VI — The catalog: a ledger for tables

## What a table is, when it lives in a lake

This part is self-contained. It assumes you know roughly what a file is and what
a database does, and nothing else; every term it uses, it introduces. By the end
you will know precisely what it means for a data platform's transactions to be
*provable*, why almost none are, and what it costs to make them so.

Start with the humblest object in modern data infrastructure: a **table** — rows
and columns, like a spreadsheet. In a classical database, the table lives inside
the database engine, which guards it jealously; nothing touches the bytes but the
engine itself. The modern **data lake** inverts this arrangement. The rows are
written into ordinary files — typically a compact columnar format called
**Parquet** — and the files are parked in cheap **object storage**: Amazon's S3,
or its open-source stand-in MinIO, which behaves like an infinite bucket you can
put files into and get files out of. The table is no longer *inside* anything. It
is a swarm of files in a bucket, and anyone's query engine — Spark, Trino,
DataFusion, a laptop — can read them.

This inversion is liberating, and it immediately raises a question: if a table is
just files, *which* files? Yesterday the table was files A and B. This morning a
job added C and rewrote B into B′. A query that reads {A, B, C} sees a table that
never existed. Something must say, authoritatively, "as of now, the table *is*
exactly these files." The open-source answer is a format called **Apache
Iceberg**, and its device is charmingly bureaucratic: alongside the data files
sits a small **metadata file** that lists them. Each version of the table — each
**snapshot** — is one metadata file, naming exactly the data files that belong to
that version. Change the table and you do not touch the old snapshot; you write a
*new* metadata file describing the new state. The table's whole history is a
chain of these immutable snapshots.

Which only sharpens the question by one step: which *metadata file* is current?
And that question — five words, deceptively small — is answered by the subject of
this part.

## The catalog, and the moment called commit

A **catalog** is the service that holds, for every table, a single pointer: *the
current metadata file is this one.* That is nearly all it does, and it is enough
to make it the most important service in the lake. Query engines ask the catalog
where the table is; writers ask the catalog to advance the pointer. The catalogs
in this part — **LakeCat** (QueryGraph's own), **Nessie**, **Apache Polaris**,
and **Apache Gravitino** — all speak a common protocol, the Iceberg REST API, so
one client can talk to any of them, which is precisely what makes an honest
comparison possible.

The pointer's movement has a name that carries two thousand years of accounting
gravity: the **commit**. A commit is the moment a table changes — validate the
proposed update, write the new metadata file, swing the pointer. Everything
downstream of a data platform — every report, every model, every decision — hangs
off some chain of commits. And two writers can want to move the same pointer at
the same time, which is where the trouble starts.

Suppose writers X and Y both read the pointer, both see snapshot 41, and both
prepare snapshot 42 — X's version and Y's version. X commits first. If the
catalog now accepts Y's commit too, Y's 42 silently replaces X's, and X's work
has vanished without an error, a warning, or a trace. This is the **lost
update**, the original sin of concurrent systems. The defense, as old as it is
elegant, is **compare-and-swap**: each writer's commit says not "set the pointer
to 42" but "set the pointer to 42 *if it still points at 41*." X's succeeds; Y's
condition is now false, and the catalog *rejects* it. Y retries against the real
current state, and no work is ever silently destroyed. Compare-and-swap — CAS,
optimistic concurrency, the conditional commit; the names vary, the idea does
not — is the bedrock guarantee of the Iceberg protocol, and, as we will see, it
is the *only* strong guarantee every catalog shares.

## What a ledger knows that a logbook does not

Now raise the stakes from correctness to *accountability*. A pointer that moves
correctly tells you what the table is. It does not tell you what happened.

The word **ledger** is doing precise work here. A logbook records events as
someone described them; pages can be lost, rewritten, or forged, and the logbook
has no opinion. A ledger, in the accountant's sense, is a record with obligations:
every entry is durable, entries are never erased (a correction is a *new* entry),
each entry follows from the one before, and the whole is arranged so that a
stranger — an auditor — can verify it later without trusting the person who kept
it. The question this part asks of a data catalog is exactly the auditor's
question: *when you accepted a transaction, what happened — and can you prove it,
offline, months later, without trusting the server that says so?*

To even pose that question precisely, we need four small tools, each explained
from scratch:

**The digest.** A digest (or hash) is a short fingerprint computed from data —
the benchmark uses SHA-256 — with two properties that make it a truth-machine:
the same input always yields the same fingerprint, and no one can construct a
*different* input with the *same* fingerprint. Store the digest of a thing and
you can later prove a copy is genuine — or that a claimed copy is not — without
storing, or revealing, the thing itself.

**The idempotency key.** Networks fail in an awkward way: a client that sends a
commit and hears nothing back cannot know whether the commit happened. It must
retry — and a naive retry applies the change *twice*. The cure is to attach a
unique key to the operation. The first arrival executes and stores its result
under the key; any retry with the same key returns the *stored* result, changing
nothing. Same key, same answer, exactly one effect — this is **idempotency**, and
retries become safe.

**The receipt.** A receipt here is not a courtesy printout but a cryptographic
object: a record of one transaction whose fields are sealed by their own digest.
Alter one character of a sealed receipt and its digest no longer matches — the
forgery is self-evident to anyone, with no server's help. That property is called
**offline verification**, and it is what elevates a receipt from *assertion* to
*evidence*. Receipts can also **chain**: each carries the digest of its
predecessor, so the whole history links into a sequence that cannot be silently
reordered, trimmed, or spliced.

**The outbox.** Downstream systems — lineage graphs, search indexes, audit
stores — need to hear about each commit. Announce the news *after* committing and
a crash in between loses the announcement forever: the change happened and no one
was told. The **transactional outbox** closes the gap by writing the announcement
*inside the same atomic transaction* as the commit — one indivisible operation
that either wholly happens or wholly does not. Evidence and change succeed
together or fail together; there is no in-between to crash in.

Assemble the four and you have the executable definition this part's benchmark
encodes: a **provable transaction** is a commit that rejects stale writers (CAS),
deduplicates retries (idempotency), stages its audit trail and outbox atomically
with the change, and issues a chained, offline-verifiable receipt — with every
piece of evidence carrying digests rather than raw locations or secrets, so the
audit trail cannot itself become the leak.

## CATALOG-PROVENANCE-v1: attacking the transaction

The benchmark, CATALOG-PROVENANCE-v1, turns that definition into seventeen
executable cases across eleven **capabilities** — named properties a catalog may
claim to enforce, from `commit` and `compare-and-swap` up through
`idempotent-replay`, `durable-audit`, `atomic-outbox`, `replayable-proof`,
`receipt-chain`, `governed-scan-proof`, `tombstone-proof` (a deletion covered by
a receipt, so even *removal* leaves evidence), `hash-only-evidence`, and
`lineage-evidence`. The adversary is the same character who stalked the cognition
benchmark, now loose in a data lake: a stale writer racing the pointer; a network
retry bearing a duplicate commit; a tamperer editing a receipt; a reader
replaying a scan against a different policy than the one it was authorized under;
a commit smuggling a secret-looking location toward the audit log.

The scoring rules are the collection's now-familiar honesty machinery, and they
matter more here than anywhere, because the comparison spans catalogs of wildly
different ambition. Each catalog runs through its own adapter and **declares**
which capabilities it enforces; a case whose capability a catalog does not claim
is reported *unsupported* — never a pass, never a failure, never quietly faked by
the adapter re-implementing a check the catalog lacks. Compare-and-swap is proved
by the *catalog's own* rejection: the harness keeps a deliberately stale handle
from before a concurrent commit and lets the catalog refuse it. Safety failures
land in seven **hard gates that must be zero** — among them
`lost_update_accepted`, `duplicate_commit_applied`, `evidence_lost`,
`forged_proof_accepted`, and `plaintext_in_evidence` — and a gate can only be
tripped by a capability a catalog *claimed* and got wrong. An honest "no" is
never punished; a false "yes" is never survivable.

The recorded run has every catalog writing to one MinIO through Docker, so the
object store cancels out of the comparison, and the shape it produces — not the
digits, which live in the companion results report — *is* the finding. Three
real, competent, widely deployed stock catalogs sit in that table, and every one
of them holds exactly the same two capabilities: `commit` and `compare-and-swap`,
cleanly and honestly. And every one declines all eleven governance capabilities,
because a stock catalog has no such surface to claim. No idempotent replay. No
durable audit. No atomic outbox. No receipt an auditor could verify offline, no
chain, no tombstone evidence, no hash-only discipline. **Every Iceberg catalog
gives you compare-and-swap; only a governed catalog gives you a transaction you
can prove.** The reference — a deterministic model of LakeCat's governed commit
boundary, standing in until the live service adapter lands — holds all eleven
governance capabilities with every gate at zero, which is what defines the far
edge of the table: not what exists everywhere today, but what *provable* means.

One incident from the recorded run deserves its footnote in the main text,
because it is the book's thesis in miniature. Gravitino initially refused every
connection with an authentication error while its siblings ran clean, and the
obvious suspects — storage credentials — were innocent. The real cause: the
Python Iceberg client, given no credential at all, still sent the literal header
`Authorization: Bearer None` — a phantom credential, an authority never
established but confidently presented. Nessie and Polaris ignored it; Gravitino
*validated* it and rejected the bogus token. The fix was to send no bearer at
all — and the moral is the same invariant this stack enforces at every layer: an
authority you did not actually establish must never be presented as if you had.

The fix is three lines, and it reads like a footnote to the whole book:

```python
# Without an OAuth credential, pyiceberg 0.11 still installs its legacy
# OAuth2 manager, which sends a literal `Authorization: Bearer None`.
# Gravitino's authenticator validates that bogus bearer and returns 401;
# Nessie ignores it. Select the no-auth manager so no bearer is sent.
# Polaris (which supplies a real `token`) keeps the OAuth manager.
if "token" not in self._props:
    props["auth"] = {"type": "noop"}
```

Absence of authority had been getting encoded as the *string* `"None"` and then
presented as a credential; the correct behavior is to present nothing at all.
Gravitino, alone among the three, was strict enough to catch it — which is
exactly the disposition you want in the thing that guards a boundary. *Full
source in the vault:
[catalog-provenance/adapters/iceberg_rest.py](../Evidence/catalog-provenance/adapters/iceberg_rest.py).*

## The other axis: what the proof costs

Provenance is the axis you cannot see until something goes wrong. The axis you
*can* see is speed, and it deserves its own honest number rather than a wave of
the hand — because every governance property in the table above is a durable
write paid *per commit*, and a fair account must say what the toll is.

That account is **catalog-bench**, the companion performance suite: the same four
catalogs, the same shared MinIO, one driver issuing identical minimal commits —
first a run in sequence to measure latency, then a crowd of concurrent writers
hammering one table to measure throughput under contention. The exact figures
belong in the results report, where they can be rerun and revised; the durable
finding is a ranking with a moral. A lean version store with no governance
machinery leads on sequential latency, as it should. LakeCat sits just behind it,
its gap a matter of a couple of milliseconds per commit — the price of writing a
compare-and-swap check, a pointer log, an audit event, a transactional outbox,
and an idempotency record, roughly seven durable writes, *inside* every single
commit. And under contention, where governance bookkeeping ought to hurt most,
LakeCat is *fastest*. The one-line summary the suite keeps earning: LakeCat is
paying for features, not losing on speed.

The two benchmarks are one argument stated twice. The performance suite measures
the cost of the governed commit; the provenance suite measures what the cost
buys. A couple of milliseconds per commit purchases the ability, months later,
facing an auditor or an incident or a regulator, to answer *what happened* with a
receipt instead of a shrug. Stated as a price, the conclusion of this part is
almost embarrassingly cheap: the difference between a logbook and a ledger is
milliseconds.

---
