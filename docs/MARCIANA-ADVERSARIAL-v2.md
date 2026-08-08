# MARCIANA-ADVERSARIAL-v2 — design

**Status:** implemented; first comparative run in progress. **Origin:** [issue #3](https://github.com/querygraph/adversarial-cognition/issues/3).
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
  (`adversarial_cognition/tracks.py`). *(done — render_v2 with a structural
  cross-track check; v1 rendering golden-tested byte-for-byte)*
- **v2.0-b — controlled agent-memory harness.** A shared runner that owns the
  model, loop, prompts, tool contract, and budget; backends supply only the
  memory tool. Migrate the agent-memory adapters onto it. *(done —
  `agent_harness/`; marciana-agent and memfs-agent rows, letta-agent declined
  with its reason until Letta's SDK exposes direct passage CRUD)*
- **v2.0-c — identity-based authorization.** Rework the isolation/clearance
  cases to use distinct authenticated identities; harden the "adapter enforces
  no gate" invariant with a check that fails a run whose adapter supplies a
  boundary. *(done — server-side identity registry with HMAC credentials;
  `protocol_v2` strips unauthenticated authorization claims and runs the
  negative-credential probe)*
- **v2.0 — cut the corpus.** Pin the v2 corpus digest, run both tracks, publish
  v2 results beside v1. *(corpus pinned:
  `sha256:9ea482f26144ee9a29f2fa3b9e99ae24bc84cdd31605a7d9c23c553e08c7f1fc`;
  comparative run and publication in progress)*

## Resolved decisions

- **Model and budget: one fixed configuration, not a matrix.** The harness runs
  one pinned model (`MARCIANA_HARNESS_MODEL`, default `llama3.1:latest` on
  Ollama), `temperature=0`, a fixed seed, `num_ctx=8192`, and a hard cap of six
  tool-call turns per operation — all recorded in a bounded `harness` block in
  the report. A model matrix would reintroduce a comparison axis (which model?)
  that invites exactly the cross-cell ordinal reads v2 exists to eliminate;
  model sensitivity is a separate v2.1 study, recoverable because the harness
  makes the model a config value.

- **The memory-store track keeps the exact v1 18-case intent set**, re-expressed
  through identity-based authorization under the new corpus version and digest.
  Changing case expectations in the same release would confound "the tracks
  split changed the numbers" with "the corpus changed the numbers"; keeping
  intent identical makes v1→v2 deltas attributable to the method changes alone.
  Tightening temporal/forget expectations is a clean v2.1.

- **Backends without native multi-identity authentication decline the
  authorization cases in both tracks.** No harness-supplied identity provider: a
  harness-held identity map is an adapter-supplied boundary at one remove — the
  exact failure mode change 3 eliminates. Declining is the benchmark's native
  honest mechanism, and it makes an isolation ✓ in either track mean the
  system's own gate held. (Under this rule, adapter-chosen `user_id`/`group_id`
  partitions no longer credit isolation — a v2 results note states that
  coverage moved, not correctness.)

- **The agent-memory track's case scope is harness-declared.** The shared tool
  contract cannot express provenance digests, nonces, idempotency keys, or
  LLM-independent reproducibility, so the harness declares one `EXPRESSIBLE_CASES`
  set, uniform for every backend in the track; inexpressible cases are
  track-unsupported for all. The expressibility map is part of the v2 corpus
  manifest, so the digest pins it.

- **The v2 Letta row measures Letta's store under the shared loop**, not
  Letta-as-shipped. The v1 native-loop row is retired as a ranked measurement
  (the v1 document remains the frozen record of it); the v2 rows are named so
  they cannot be misread as continuations.

- **What the no-adapter-gate check can and cannot catch.** The runtime check is
  three layers: a negative-credential probe (a corrupted credential must be
  rejected by the system, else all authorization claims are voided), denial
  evidence (a boundary denial must carry the system's own error surface, never
  a bare adapter `False`), and a published per-system
  `authorization_mechanism` attestation. This catches the issue-#1 class —
  honest adapter routing that manufactures isolation — and unauthenticated
  systems. It cannot catch an adapter that deliberately fabricates an auth
  surface; that is handled by in-repo adapter review, with the attestation
  making the claim explicit and falsifiable.

## v2.1 threads (observations from the first run)

- **Model sensitivity as a study, not a table.** The reference's 18/18-direct
  vs 5/10-through-the-loop delta is a property of `llama3.1:latest` as much as
  of the loop. Because the harness makes the model a config value
  (`MARCIANA_HARNESS_MODEL`), a v2.1 study can re-run the agent-memory track
  per model and report the delta as a function of model capability — each
  model's table separate, never a cross-model ordinal.
- **Akka + Fluree can win its isolation cases back on merit.** Its stripped
  claims are an adapter posture: the v1 adapter composed visibility into query
  text, which v2 refuses to credit. Reworking the adapter to authenticate
  distinct identities against Fluree's server-side policy surface would let
  the *ledger* hold the boundary — and pass the negative-credential probe.
- **Letta rows are one SDK release away.** Both `letta-direct` (memory-store)
  and `letta-agent` (agent-memory) are declined solely because Agent SDK 0.6.2
  reaches memory only through Letta's own agent turns; direct passage CRUD
  lights both up without any benchmark change.
- **Loop-cost taxonomy.** The reference's five agent-track failures are all
  contract failures by the model (unreported denials, non-JSON abstentions, an
  incomplete forget), not store failures. A v2.1 refinement could classify
  loop outcomes (store-denied/model-misreported vs store-failed) in the
  payload, making the delta's composition legible per case.
- **Tighten temporal/forget expectations** (carried from the resolved
  decisions) once the agent confound is measured separately.
