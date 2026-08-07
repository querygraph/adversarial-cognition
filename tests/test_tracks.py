"""Tests for the MARCIANA-ADVERSARIAL-v2 track model."""

from __future__ import annotations

import unittest

from adversarial_cognition.tracks import (
    AGENT_MEMORY,
    MEMORY_STORE,
    group_by_track,
    track_for_interface,
)


class TrackModelTests(unittest.TestCase):
    def test_interface_maps_to_track(self) -> None:
        self.assertEqual(track_for_interface("direct-api"), MEMORY_STORE)
        self.assertEqual(track_for_interface("agent-loop"), AGENT_MEMORY)

    def test_unknown_interface_defaults_to_memory_store(self) -> None:
        # A direct call is the conservative assumption; agent-loop must be explicit.
        self.assertEqual(track_for_interface("something-else"), MEMORY_STORE)

    def test_group_by_track_places_executed_systems(self) -> None:
        systems = {
            "marciana": {"status": "executed", "interface": "direct-api"},
            "letta": {"status": "executed", "interface": "agent-loop"},
            "mem0": {"status": "executed", "interface": "direct-api"},
            "zep": {"status": "unavailable"},
        }
        groups = group_by_track(systems)
        self.assertEqual(set(groups[MEMORY_STORE]), {"marciana", "mem0"})
        self.assertEqual(groups[AGENT_MEMORY], ["letta"])
        # Non-executed systems are not placed in any track.
        self.assertNotIn("zep", groups[MEMORY_STORE] + groups[AGENT_MEMORY])


if __name__ == "__main__":
    unittest.main()
