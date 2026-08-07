# Letta adapter — build notes

## Two interfaces, one adapter

Letta ships memory behind an agent loop, but it also has a passage/archival
store. To make the cost of the agent loop measurable rather than assumed, the
adapter runs in one of two modes, selected by `LETTA_ADAPTER_MODE`:

| Mode | `interface` | Claims | How memory is reached |
|------|-------------|--------|-----------------------|
| `agent-loop` (default) | `agent-loop` | retrieval, temporal, forget, persistence | one agent turn per operation |
| `direct-memory` | `direct-api` | retrieval, persistence | the passage store directly |

Both rows appear in the report — `letta` and `letta-direct` — so the delta
between them is exactly what the agent loop adds. The adapter enforces no gate
in either mode; principal→archive routing is **not** a Letta authorization
boundary (see PR #1), so `direct-memory` does **not** claim isolation.

## Running

- Agent loop (default): `MARCIANA_ADVERSARIAL_LETTA_CMD='adapters/letta/run.sh'`.
- Direct memory: point `MARCIANA_ADVERSARIAL_LETTA_DIRECT_CMD` at a command that
  sets `LETTA_ADAPTER_MODE=direct-memory` before the same `run.sh`, e.g.
  `env LETTA_ADAPTER_MODE=direct-memory adapters/letta/run.sh`.

## TODO — the direct-memory bridge path is a handoff

`bridge.js` currently implements only the agent-loop path. In `direct-memory`
mode it **fails loudly** on every memory op rather than silently falling back to
an agent turn (which would mislabel the interface). To complete it, implement
the memory ops against the Letta passage/archival API — create/list/delete on
the store, keyed by the principal's archive — and run against the live App
Server. The Python side (mode switch, declarations, registry entry) is already
in place; only the `bridge.js` `direct-memory` handlers and the live run remain.
