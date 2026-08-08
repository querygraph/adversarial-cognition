"""Benchmark tracks for MARCIANA-ADVERSARIAL-v2.

See docs/MARCIANA-ADVERSARIAL-v2.md. v2 separates two abstraction layers that v1
reported in one table:

- the **memory-store** track: systems driven at their storage/retrieval API
  directly;
- the **agent-memory** track: systems driven through an agent loop under one
  shared model, prompt, tool contract, and context budget.

A system declares its track; results are compared only *within* a track, never
across. The ``interface`` field a v1 adapter already emits
(``direct-api`` | ``agent-loop``) determines the track, so no adapter needs a new
declaration — the track is a reporting axis derived from the interface.

This module is the v2 scaffold; it does not change v1 scoring or v1 rendering.
"""

from __future__ import annotations

MEMORY_STORE = "memory-store"
AGENT_MEMORY = "agent-memory"
TRACKS = (MEMORY_STORE, AGENT_MEMORY)

_INTERFACE_TRACK = {
    "direct-api": MEMORY_STORE,
    "agent-loop": AGENT_MEMORY,
}


def track_for_interface(interface: str) -> str:
    """Map an adapter's ``interface`` to its comparison track.

    Unknown interfaces default to the memory-store track — a direct call is the
    conservative assumption, and an adapter that reaches memory through an agent
    must say so explicitly (``agent-loop``) to be placed in the agent-memory
    track.
    """
    return _INTERFACE_TRACK.get(interface, MEMORY_STORE)


def group_by_track(systems: dict) -> dict[str, list[str]]:
    """Group executed system entries by track, for within-track comparison.

    ``systems`` is the report's ``{name: entry}`` mapping. Only executed systems
    are placed in a track; unavailable/error rows are the caller's to render
    separately. Ordering within a group is left to the caller.
    """
    groups: dict[str, list[str]] = {track: [] for track in TRACKS}
    for name, entry in systems.items():
        if entry.get("status") == "executed":
            groups[track_for_interface(entry.get("interface", "direct-api"))].append(name)
    return groups
