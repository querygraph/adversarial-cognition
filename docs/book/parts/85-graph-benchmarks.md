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
checkouts. Official Neo4j and GDS archives are downloaded separately and
checksum-verified. Base-image tags and transitive operating-system packages
are not immutable, so package and source receipts remain part of the record.

```sh
git clone https://github.com/querygraph/adversarial-graph-algorithms
cd adversarial-graph-algorithms
./docker/run.sh --full-path --algorithms dijkstra --families path \
  --sizes 16384 65536 --warmups 0 --repeats 1 --label reproduced-full-path
```

A useful comparison starts by saying what must exist when execution finishes,
what must have been consumed, and what the clock includes. The graph experiment
makes that discipline unusually concrete: two arrays, billions of entries,
and a completed run whose claims can be checked independently.
