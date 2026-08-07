# MARCIANA-ADVERSARIAL-v2 — design

**Status:** in progress. **Origin:** [issue #3](https://github.com/querygraph/adversarial-cognition/issues/3).
**Predecessor:** MARCIANA-ADVERSARIAL-v1 (published; unchanged and still valid).

v1 attacks a governed memory boundary across a field of systems, scores only
declared capabilities, and keeps safety in hard gates. v2 keeps all of that and
fixes one methodological gap: v1 places systems driven through a full agent loop
(model + tool calls + a response parser) in the same table as systems whose
storage API is called directly. Even with the configuration documented, one
table invites an ordinal read of unlike measurements. v2 makes the abstraction
layer a first-class part of the method rather than a footnote.

Everything about v1 that does not concern the mixing of layers carries over
unchanged: the threat model, the eighteen-case corpus intent, the nine hard
gates, capability-declared scoring, digest-pinned corpora, bounded reports, and
the `interface` field v1 adapters already emit.

## The three changes

### 1. Two tracks, compared only within a track

Every system runs in exactly one **track**, which it declares:

- **memory-store** — the system's storage, retrieval, deletion, temporal, and
  authorization APIs are called directly.
- **agent-memory** — memory is reached through an agent loop.

The `interface` field an adapter already reports determines the track
(`direct-api → memory-store`, `agent-loop → agent-memory`). Results are grouped
by track and compared **only within a track**; the report never presents a
cross-track ordinal, and the renderer enforces this rather than relying on a
caption. A product that ships both layers (e.g. Letta: a passage store and an
agent loop) appears as one row per track, so the cost of the agent loop is the
delta between its two rows — a measurement, not an assertion.

### 2. A controlled agent-memory harness

For the agent-memory track, comparability requires more than a label. Every
backend in that track runs under **one shared harness**: the same model, the same
agent loop, the same system and per-operation prompts, the same tool contract,
and the same context budget. Only the memory backend varies. This isolates the
memory system's contribution from the model's instruction-following and
formatting behavior — the confound that makes a raw agent-loop number
incomparable today.

The harness owns the loop and the prompts; a backend adapter supplies only the
memory tool implementation (write / read / delete / list, and whatever scope or
temporal operations it enforces). The shared model and budget are recorded in
the run configuration and stamped into the report.

### 3. Identity-based authorization

Isolation and clearance are exercised through **distinct authenticated
identities**, never adapter-selected partitions. This is the same failure mode
[#1](https://github.com/querygraph/adversarial-cognition/issues/1) caught: an
adapter that routes each principal to its own store *manufactures* an isolation
the system does not enforce. The hard invariant, made explicit in v2:

> The adapter enforces no gate. Every authorization boundary must be held by the
> system under test, exercised through the system's own authenticated identities.
> A system without that boundary declines the case; it is never credited by
> adapter routing.

Systems that expose real authenticated identities (the reference, a ledger with
a policy engine) are tested through them; systems that scope only by an
adapter-supplied key decline isolation and clearance rather than being scored on
a boundary the adapter would be supplying.

## Versioning and compatibility

- New corpus version `marciana-adversarial-v2` with its **own digest**. v2 is a
  separate benchmark, not a patch to v1's digest.
- **v1 results stay published as v1** — in the repo, on adversari.al, and in the
  book's companion report. v2 arrives alongside; it never silently overwrites v1.
- **The book needs no rewrite.** It describes systems and the *why*, not the
  numbers, so v2 only adds a section to the companion results report.
- Reports carry the benchmark version; the renderer selects flat (v1) or
  track-grouped (v2) presentation from it, so v1 output is byte-for-byte stable.

## Staged roadmap

- **v2.0-a — tracks in the report.** Promote `interface` to a first-class
  `track`; group and compare within track in the renderer, gated on the v2
  version so v1 rendering is untouched. Land the `track` model in code
  (`adversarial_cognition/tracks.py`). *(begun)*
- **v2.0-b — controlled agent-memory harness.** A shared runner that owns the
  model, loop, prompts, tool contract, and budget; backends supply only the
  memory tool. Migrate the agent-memory adapters onto it.
- **v2.0-c — identity-based authorization.** Rework the isolation/clearance
  cases to use distinct authenticated identities; harden the "adapter enforces
  no gate" invariant with a check that fails a run whose adapter supplies a
  boundary.
- **v2.0 — cut the corpus.** Pin the v2 corpus digest, run both tracks, publish
  v2 results beside v1.

## Open questions

- The shared agent-memory model and budget: fixed constants, or a small matrix
  (one small, one mid model) reported per cell?
- Whether the memory-store track keeps the exact v1 case set or tightens the
  temporal/forget expectations now that the agent confound is gone.
- Identity substrate for the agent-memory track: how backends without native
  multi-identity auth participate in the isolation cases (decline vs. a shared
  identity provider the harness supplies to the *model*, not the memory).
