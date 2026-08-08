# Akka + Fluree adapter

Runs MARCIANA-ADVERSARIAL-v1 against [Fluree](https://flur.ee) as the
semantic-ledger/query authority. This adapter represents the comparative
"Akka port with Fluree as the semantic-ledger/query role" described in
Marciana's documentation: **the actor/service layer is represented by the
adapter process itself** — it enforces the service input bound and
orchestrates requests — while every authorization filter, temporal filter,
ranking aggregation, guarded mutation, nonce claim, and idempotency guard is
executed by the Fluree ledger. No JVM Akka deployment is involved, and the
README says so on purpose.

## Setup

```sh
docker compose up -d fluree     # from the repository root; serves :58090
cat request.json | ./run.sh     # stdlib-only Python, no packages
```

`MARCIANA_FLUREE_URL` overrides the endpoint (default
`http://localhost:58090/v1/fluree`). Each benchmark case runs in a fresh
ledger (`bench/<uuid>`), created through `POST /v1/fluree/create`; mutations
go through `POST /v1/fluree/update` (JSON-LD inserts and
`application/sparql-update` with a `Fluree-Ledger` header), queries through
`POST /v1/fluree/query` (`application/sparql-query` with `FROM <ledger>`).

## Capability rationale — what the ledger enforces

| Capability | Fluree feature backing the claim |
|---|---|
| retrieval | Per-token `VALUES`/`CONTAINS` match with `COUNT` ranking and `ORDER BY`, computed in the SPARQL engine |
| temporal | `validFrom`/`validUntil` xsd:date `FILTER`s evaluated in the query |
| abstention | Filter-based retrieval returns the empty set for non-matching queries; no nearest-neighbor fallback exists |
| isolation | Principal visibility (`owner`/`private` filters) evaluated in the query engine |
| provenance | Guarded update: the improve transaction's `WHERE` requires the current `sourceDigest`; a mismatch makes the transaction a ledger-side no-op |
| replay-protection | Nonce claim and memory write in one transaction guarded by `FILTER NOT EXISTS` on the nonce entity |
| idempotency | The improve transaction is also guarded by `FILTER NOT EXISTS` on the job entity; a retry is a no-op whose recorded outcome is read back |
| forget + derived-tracking | Tombstones written by ledger-matched updates, including a `derivedFrom` join the ledger resolves |
| persistence | Ledgers are server-side; restart is a fresh stateless session |

Not claimed: **clearance** and **purpose** — this Fluree server build exposes
no policy-engine surface through its minimal HTTP API, so analyst visibility
is an adapter-authored query filter, which qualifies as isolation, not as
ledger-enforced clearance. The corresponding cases are declared unsupported.

Honest notes: query tokenization (lowercase `[a-z0-9]+`, deduplicated,
capped at 16 tokens) and the 4,096-character service input bound live in the
adapter — that is the actor-layer role this system assigns to its service
tier, and the oversized-query rejection is service-layer behavior. An empty
query short-circuits to the empty result without a ledger round-trip.
