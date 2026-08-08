"""Letta's archival passage store under the shared harness.

The v2 agent-memory row for Letta: the App Server's passage store supplies the
memory tool; the loop, model, and prompts are the harness's. This measures
Letta's *store* under the controlled loop — not Letta-as-shipped, whose native
agent loop was the (retired) v1 row.

Letta's server exposes no multi-identity authentication on the passage store,
so ``provision`` is empty and every authorization case is declined — the
adapter never routes principals to separate agents (see issue #1).
"""

from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_harness.tools import AgentMemoryBackend, Credential, ToolResult

REQUEST_TIMEOUT_SECONDS = 60


class LettaAgentBackend(AgentMemoryBackend):
    name = "letta-agent"
    version = "app-server-passages"
    capabilities = frozenset({"retrieval", "abstention", "forget", "persistence"})
    authorization_mechanism = "none"

    def __init__(self) -> None:
        self.base = os.environ.get(
            "LETTA_BASE_URL", "http://localhost:8283"
        ).rstrip("/")
        self.agent_id: str | None = None
        self.ids_by_passage: dict[str, str] = {}

    def _request(self, method: str, path: str, body: dict | None = None) -> object:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = urllib.request.Request(
            f"{self.base}{path}",
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            payload = response.read().decode("utf-8")
        return json.loads(payload) if payload else {}

    def _ensure_agent(self) -> str:
        if self.agent_id is None:
            created = self._request(
                "POST", "/v1/agents",
                {
                    "name": "marciana-adversarial-v2-store",
                    "agent_type": "memgpt_agent",
                    "model": os.environ.get(
                        "MARCIANA_LETTA_MODEL", "ollama/llama3.1:latest"
                    ),
                    "embedding": os.environ.get(
                        "MARCIANA_LETTA_EMBEDDING", "ollama/nomic-embed-text"
                    ),
                },
            )
            self.agent_id = str(created["id"])
        return self.agent_id

    def reset(self) -> None:
        if self.agent_id is not None:
            try:
                self._request("DELETE", f"/v1/agents/{self.agent_id}")
            except Exception:  # noqa: BLE001 - a fresh agent is created next
                pass
        self.agent_id = None
        self.ids_by_passage = {}

    def restart(self) -> None:
        # Passages are server-side durable; nothing volatile to rebuild.
        pass

    def provision(self) -> dict[str, str]:
        return {}

    def open_session(self, credential: Credential) -> object | None:
        # One shared store; no authentication surface to exercise.
        return credential.name

    def write(self, session, memory_id, text, valid_from=None,
              valid_until=None, private=False, derived_from=()) -> ToolResult:
        agent = self._ensure_agent()
        created = self._request(
            "POST", f"/v1/agents/{agent}/archival-memory",
            {"text": f"[{memory_id}] {text}"},
        )
        rows = created if isinstance(created, list) else [created]
        for row in rows:
            self.ids_by_passage[str(row.get("id", ""))] = memory_id
        return ToolResult(ok=True, ids=(memory_id,))

    def read(self, session, query, as_of=None) -> ToolResult:
        if not query.strip():
            return ToolResult(ok=True, results=(), ids=())
        agent = self._ensure_agent()
        encoded = urllib.parse.quote(query)
        found = self._request(
            "GET", f"/v1/agents/{agent}/archival-memory?search={encoded}&limit=8"
        )
        rows = found if isinstance(found, list) else found.get("results", [])
        results = []
        for row in rows:
            text = str(row.get("text", ""))
            memory_id = text.split("]", 1)[0].lstrip("[") if text.startswith("[") else ""
            if memory_id:
                results.append({"id": memory_id, "text": text[:200]})
        return ToolResult(
            ok=True,
            results=tuple(results),
            ids=tuple(row["id"] for row in results),
        )

    def delete(self, session, memory_id) -> ToolResult:
        agent = self._ensure_agent()
        passage_ids = [
            passage for passage, mapped in self.ids_by_passage.items()
            if mapped == memory_id
        ]
        if not passage_ids:
            return ToolResult(ok=False, error="not found")
        for passage in passage_ids:
            self._request(
                "DELETE", f"/v1/agents/{agent}/archival-memory/{passage}"
            )
            del self.ids_by_passage[passage]
        return ToolResult(ok=True, ids=(memory_id,))

    def list_ids(self, session) -> ToolResult:
        return ToolResult(ok=True, ids=tuple(sorted(set(self.ids_by_passage.values()))))
