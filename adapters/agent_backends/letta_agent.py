"""Letta under the shared harness — currently declined, with the reason.

The v2 agent-memory row for Letta would drive Letta's *store* through the
shared loop. Agent SDK 0.6.2 against the self-hosted App Server exposes no
direct passage/file CRUD: memory (git-backed MemFS) is reachable only through
Letta's own agent turns (``createAgent``/``prompt``). Driving those from
inside the harness would nest Letta's loop within the shared loop — every
"tool call" would really be a second model run — violating the track's
one-loop premise and making the row incomparable.

Per the benchmark's constitution the row is therefore declined, not faked:
this backend refuses to construct, the run records an error row with this
reason, and the row becomes implementable the moment Letta's SDK exposes the
passage store directly (the same surface the memory-store track's
``letta-direct`` row is waiting on — see adapters/letta/BUILD_NOTES.md).
"""

from __future__ import annotations

REASON = (
    "letta store is not directly reachable via agent-sdk 0.6.2/app-server: "
    "memory is exposed only through Letta's own agent turns, which would nest "
    "a second loop inside the shared harness; declined rather than faked"
)


class LettaAgentBackend:
    name = "letta-agent"
    version = "declined"

    def __init__(self) -> None:
        raise SystemExit(REASON)
