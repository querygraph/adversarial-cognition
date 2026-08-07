# Letta App Server adapter

Runs MARCIANA-ADVERSARIAL-v1 through Letta's current self-hosted
[App Server](https://docs.letta.com/self-hosting) and
`@letta-ai/letta-agent-sdk`. The integration uses Agent SDK 0.6.2 with Letta
Code/App Server 0.30.8. It does not use the deprecated V1 Python client,
archives, passages, or direct search endpoints.

Every benchmark operation goes through the agent loop:

- each principal is represented by a persistent Letta agent with MemFS;
- `remember` asks the agent to persist a bounded `[id:...]` fact with its
  memory tool;
- `recall` asks the agent to inspect memory and return matching bounded IDs;
- `forget` asks the agent to delete the marked memory;
- `restart` creates a new Agent SDK client while retaining server-side state.

The Python file remains a thin dependency-free protocol shim. Its Node bridge
and dependencies are isolated in this adapter directory.

## Setup

The default standalone command builds and starts the App Server container,
connects it to local Ollama, runs the adapter, and removes the container:

```sh
ollama pull gpt-oss:20b
MARCIANA_ADVERSARIAL_LETTA_CMD=adapters/letta/run.sh \
  python3 run_benchmark.py --systems marciana,letta --repeats 1
```

Override the agent model with `MARCIANA_LETTA_MODEL`. In compose mode the App
Server is a sibling service at `http://letta:4500`.
The non-loopback compose listener uses a capability token, passed to the SDK
through `MARCIANA_LETTA_TOKEN`; the default is scoped to the local benchmark
network and can be overridden.

## Capability scope

The adapter claims retrieval, temporal recall, forget, and persistence. It
does not claim isolation or authorization: choosing a principal's agent before
sending a turn is adapter routing, not differential permission enforcement by
Letta. Provenance, replay protection, idempotency, and derived-memory tracking
are likewise unclaimed.

No comparative score is published until a fresh bounded output from this
current agent-loop path is retained in `outputs/letta.json` and validated by
CI. Historical archive-search observations are not carried forward.
