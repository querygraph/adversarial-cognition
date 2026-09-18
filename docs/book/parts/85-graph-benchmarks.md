# Part IX — The graph: what counts as the same work

The graph layer brings a different boundary into view. A benchmark can use the
same input and name the same algorithm while asking its implementations to
produce materially different results. The boundary that needs a test is then
neither authority nor persistence. It is the output contract.

The graph section of adversari.al separates these experiments. Its
[graph-query suite](https://adversari.al/graph/queries) retains the extensive
LSQB-derived and adversarial query evidence, historical cohorts, and timing
corrections. Its [strain ledger](https://adversari.al/graph/strain) records
longer-running workload experiments. The new
[algorithm benchmark](https://adversari.al/graph/algorithms) compares kernels
and explicitly defined outputs. These are siblings under the
[Graph index](https://adversari.al/graph), not components of a combined score.

## A distance is not a path

Dijkstra computes shortest paths, but an API may expose only the distance to
each destination. Another API may expose the complete sequence of nodes and
cumulative costs along each route. The first result has one distance per
reachable destination. The second can contain vastly more data.

Consider a directed chain of n nodes, with the source at its beginning. The
source's path contains one node; the next contains two; the last contains n.
Across all destinations, each path array therefore contains n(n + 1) / 2
entries. A chain with 65,536 nodes requires 2,147,516,416 node-ID entries and
the same number of cumulative-cost entries when every path is materialized
and consumed. This is a property of the requested output, not a defect in a
particular implementation.

The early comparison placed distance-only native results next to Neo4j's
full-path procedure, and a bounded large-chain probe timed out. That historical
record remains available as a separate cohort. The full-path experiment
changes the contract for every implementation: compute the distances, retain
predecessors, construct source-first node and cumulative-cost arrays, and
consume every requested entry. The source has a one-node path. Unreachable
nodes have no path. Equal-cost alternatives may choose different valid
shortest paths.

The full-path mode removes the transaction and process deadlines. Paths are
processed incrementally rather than retained together. Native implementations
visit one path at a time; Neo4j streams its official procedure output into
server-side Cypher aggregation. A large total output does not require a large
simultaneously resident output.

## Five implementations and their boundaries

Icebug is the original C++ Apache Arrow update of NetworKit. Icecat is the
first Rust rewrite, using immutable Arrow adjacency. Grustcat is the
Grust-compatible Rust implementation with an Arrow graph projection.
Grustcat Cypher adds the Grust parser and semantic analyzer followed by a
focused typed Arrow execution backend. The fifth variant runs official Neo4j
Community 2026.08.0 with Graph Data Science 2026.08.1, using the unmodified
single-source Dijkstra stream procedure.

The September 13, 2026 Docker completion run returned the following times in
seconds. Each large case has one measured sample and no warmup.

| Variant | 16,384 nodes | 65,536 nodes |
|---|---:|---:|
| Icebug | 1.102 | 22.233 |
| Icecat | 1.053 | 16.648 |
| Grustcat | 1.032 | 16.710 |
| Grustcat Cypher | 1.028 | 16.727 |
| Neo4j GDS | 11.889 | 194.113 |

These are completion and correctness measurements, not stable performance
rankings. They were taken in Linux ARM64 Docker containers on an Apple M1 Max
host. Each service had a two-CPU quota and a 4 GiB memory limit, while the
algorithm concurrency was one. Neo4j used a 2 GiB heap and 512 MiB page cache.
The published graph-query suite's timing incidents and resource envelopes
belong to that separate suite; none of its samples are pooled here.

The native timers include algorithm execution, path construction, and
aggregation; the Rust variants also construct an Arrow distance result.
Grustcat Cypher additionally parses, validates, and plans its query. Neo4j's
number is server query time, including Cypher aggregation, with client wall
time retained in the raw result. Input loading and graph projection are
outside these timers. Identical requested outputs do not imply identical
allocation strategies, internal work, or query machinery.

The
[raw five-way evidence](https://adversari.al/evidence/graph-algorithms/2026-09-13/docker-cypher-full-path.json)
records samples, query text, configuration, validation, and binary hashes.
The [environment receipt](https://adversari.al/evidence/graph-algorithms/2026-09-13/docker-cypher-full-path-environment.json)
records source hashes, compiler/package versions, and container limits.

```{=typst}
#pagebreak(weak: true)
```

## A query language without intermediate row explosions

The Grustcat Cypher variant uses a deliberately limited procedure subset. A
full-path query requests the node and cost arrays, expands their positions,
and aggregates the count and sums:

```cypher
CALL grustcat.fullPaths($source) YIELD nodeIds, costs
UNWIND range(0, size(nodeIds)-1) AS i
RETURN count(*) AS path_entries,
       sum(nodeIds[i]) AS node_sum,
       sum(costs[i]) AS cost_sum
```

The backend validates the entire parsed syntax tree. It then fuses the
expansion and aggregates over actual path arrays, avoiding billions of
intermediate row objects. It rejects unsupported query forms explicitly.
Its aggregate semantics are checked against the real Grust reference Cypher
executor on small injected path fixtures.

This focused backend is not the general Grust reference executor, and it does
not claim Neo4j GDS procedure compatibility. General algorithm dispatch needs
an extensible registry of names, typed arguments, output schemas, and provider
implementations. The execution context must carry the graph or projection,
cancellation, budgets, and concurrency. Streaming must continue through the
surrounding query pipeline: a streaming procedure cannot bound memory if the
next operator eagerly collects all its output. Projection, filtering, and
aggregation need incremental execution; sorting and grouping need explicit
resource behavior.

That distinction matters to a reader interpreting a fast Cypher result. It
identifies the physical execution path that produced the number instead of
attributing it to an undifferentiated language label.

## Validation before interpretation

All five variants passed thirty small cases: six graph families at 128 nodes,
across BFS, Dijkstra, weak and strong components, and PageRank. The families
are paths, hubs, clusters, layered graphs, uniform graphs, and R-MAT graphs.
The final runtime image also passed forty-five kernel and Arrow interchange
checks, alongside the Rust API tests.

Each algorithm has its own comparison rules. BFS checks reachability and level
order because the result shapes differ. Component partitions are
canonicalized. PageRank uses the same weighted uniform model but different
native and GDS convergence criteria; normalized scores are checked within
recorded tolerances. These differences remain visible instead of disappearing
into a combined score.

Small Neo4j paths are checked edge by edge. The large chain has unique shortest
paths, allowing independent checks of all distances, the entry count, the
node-ID sum, and the cumulative-cost sum. All five passed those checks. On an
arbitrary graph with tied routes, matching aggregates alone would not be a
collision-resistant proof of every interior node. Validation claims must stay
within the evidence that supports them.

## The reproducible unit

The [benchmark repository](https://github.com/querygraph/adversarial-graph-algorithms)
contains a checksum-verified snapshot of the measured sources. Readers need
Docker Compose v2 and Python 3.12+, not a collection of unpublished sibling
checkouts. The `--frozen` flag selects that snapshot; without it the runner
measures current upstream sources at their pinned commits, which is what the
rest of this chapter reports. Official Neo4j and GDS archives are downloaded separately and
checksum-verified. Base-image tags and transitive operating-system packages
are not immutable, so package and source receipts remain part of the record.

```sh
git clone https://github.com/querygraph/adversarial-graph-algorithms
cd adversarial-graph-algorithms
./docker/run.sh --frozen --output /tmp/frozen -- --full-path \
  --algorithms dijkstra --families path --sizes 16384 65536 \
  --warmups 0 --repeats 1 --label reproduced-full-path
```

A useful comparison starts by saying what must exist when execution finishes,
what must have been consumed, and what the clock includes. The graph experiment
makes that discipline unusually concrete: two arrays, billions of entries,
and a completed run whose claims can be checked independently.

## When the sources moved, the contract held and the numbers did not

The first run measured a frozen snapshot. Pointing the same protocol at current
upstream sources added six columns to the five, and one of them mattered more
than the rest: the general Cypher executor. The original Cypher column was a
typed Arrow adapter, a Cypher-shaped front end over a fast path, and the
repository always said so. Nothing had ever measured what an ordinary query
costs.

It cost about ninety times direct execution. The obvious explanation was the
query: one column expands a row per path entry, the other folds each path in
place, which at 65,536 nodes is 2.1 billion interpreter rows against 65,536.
Removing the expansion entirely saved about four per cent.

A profiler put roughly 83 per cent of the time in reading the clock. The bounded
read policy requires a finite deadline, that participant disclosed a twenty-four
hour ceiling, and the execution context checked the deadline on every charge
against the work budget — about 8.4 million times on a 4,096-node chain. Direct
execution sets no deadline, never reads the clock, and did the same work in 197
milliseconds.

Two facts turned that from a verdict about an engine into a verdict about a
policy. The measuring host's clocksource was paravirtual rather than a register
read, which inflates any per-unit check on that machine specifically. And the
compared engine samples its own termination check — every ten thousand nodes,
with the underlying flag refreshed every ten seconds — while this one checked
every unit. The systems were not computing at different speeds. They were asking
a question at different rates.

Underneath that sat the same shape of problem twice more. The cooperative budget
meter, which kernels enter once per unit of graph work, took a mutex on every
call: about 134 million acquisitions on one chain, 72.8 per cent of kernel time,
against 14.8 per cent for visiting the paths it was guarding. And a streaming
procedure call deep-copied every yielded value into each row, cloning a path list
once per path, while still charging work per entry after charging had become
cheap.

Fixing the three in turn — lock-free admission, sampled deadlines, borrowed lists
with work admitted per path — took the 65,536-node run from three and a half
hours to thirty-five minutes, and ordinary Cypher on that chain from 5,808,625
milliseconds to 594,419. Through all of it the four frozen historical binaries
were byte-identical and moved by at most 1.4 per cent. That unchanged column is
what licenses the claim that anything else moved because of the code.

Two changes made it worse before they made it better. A first attempt at sampling
slowed every path that sets no deadline, by 13 to 46 per cent, because the
sampling counter ticked whether or not a deadline existed; it reached the main
branch before the paired measurement that caught it. A later change removed a
regression it had introduced on the one workload that its other gains did not
reach. Both are in the record, because a benchmark that publishes only the
changes that worked has stopped measuring.

## The bug that was not in an algorithm

A durable-loading experiment failed every one of its thirty-six samples. Neither
the write-grouping setting under test nor the journal mode was responsible.
Results were being associated with nodes by position in the loaded snapshot
rather than by node identifier. Bulk loading inserts in input order, so position
and identifier agreed and the defect stayed invisible; four concurrent writers
scrambled insertion order, and every distance landed on the wrong node.

The returned values were an exact permutation of the reference: identical
multisets, wrong positions. Every aggregate a careless check might compare — the
count, the sum of identifiers, the sum of costs — was correct. The snapshot
verifier could not catch it either, and not by oversight: it compares sorted
records, because database scan order is legitimately arbitrary, which makes it
blind to a permutation by construction.

What caught it was the discipline of comparing every sample against an
independent reference, element by element, including on the runs nobody expected
to fail. A benchmark that validates only its headline case would have published
the wrong numbers for the configurations it did not check.

## The other graph experiment: completion under strain

The algorithms benchmark asks whether two systems did the same work. The strain
ledger asks a different question: which workloads a store completes correctly
inside a stated budget, before any comparison of speed is permitted at all.

A store can answer quickly and still fail the workload around the answer. It can
exhaust memory while loading, lose an acknowledged write under contention, or
accumulate a queue when requests arrive independently of its response time. So
the experiment qualifies first and compares second. Six groups of questions
decide qualification: whether the graph loads with its edge count preserved,
whether hub fan-out and deep walks return the oracle's own answers, whether
sixteen writers attaching two hundred edges each to one hub all apply durably or
receive a typed refusal, how long until the first correct answer and what happens
to response tails, whether unbounded requests are refused in time and guarded
commits replay exactly once, and whether typed graphs keep their declared
semantics under recursive deletes and contention.

Nine hard gates must stay at zero: wrong answers, lost writes, duplicate durable
mutations, isolation anomalies, policy bypasses, hangs without refusal,
out-of-memory or crash, unauthorized disclosure, and nondeterministic receipts.
No latency figure compensates for a gate that fired. That single rule is what
makes the rest of the ledger legible.

By September 2026 the ledger held 352 runs in 33 verified evidence bundles across
five machines, summarized as 1,121 current cells over fifteen backend routes and
fourteen graphs, with superseded cells retained alongside the runs that replaced
them. A cell is one graph, backend, scenario, edge slice and profile: a piece of
evidence, not a certificate for an engine.

Reach is deliberately strict — a whole untyped graph must load and all four core
families must pass. On those terms Neo4j over both its routes, Turso in both
journal modes, and the in-process Rust store all qualify at com-Orkut, 117
million edges, the largest graph in the set; LanceDB qualifies at 16.5 million;
two other stores at 88 thousand. Among same-machine pairs where both sides
passed, the in-process store leads on loading, hub fan-out, hot-node writes, cold
start and tail latency. The remaining advantage on the other side is memory, and
by the last cohort it was 4.9 GB against 5.4.

Those numbers moved during the measurement period, which is the point. Loading
under multi-version concurrency went from 1,500 to between 13,000 and 31,000
edges per second, and its peak memory from 15 GB to between 3 and 7, because
loads began running over several writer connections with a checkpoint between
rounds. The ledger keeps the earlier cells and names the run that superseded each
one, so the improvement is visible as a history rather than asserted as a state.

## Two boundaries, one discipline

The two graph experiments test different boundaries. One asks what must exist
when execution finishes: which arrays, how many entries, consumed by whom. The
other asks what must not have happened along the way: no lost write, no silent
truncation, no answer that arrives only because a gate was skipped.

Both refuse the same shortcut. Neither will let a faster number stand in for a
completed one, and neither pools measurements whose conditions differ — not
across machines, not across source revisions, not across execution classes that
do unequal work. When those distinctions are kept, an improvement can be
attributed to a change rather than to a mood, and a regression is as reportable
as a gain. That is the whole of the method, and it is why the numbers in this
chapter were allowed to move.
