"""The memory tool contract — the only surface a backend supplies.

The model sees exactly these four tools, identically for every backend. The
harness dispatches a tool call to the backend's implementation and returns the
bounded JSON result as a tool message. Authorization is the system's: a session
comes from ``open_session`` with a credential the system itself issued at
``provision`` time, and the driver — never the backend — chooses which
principal's session an operation runs under.
"""

from __future__ import annotations

from dataclasses import dataclass, field

TOOL_CONTRACT_VERSION = "marciana-agent-tools-v1"


@dataclass(frozen=True)
class Credential:
    """A principal name and the secret the system issued for it."""

    name: str
    secret: str


@dataclass(frozen=True)
class ToolResult:
    """Bounded result of one memory tool call."""

    ok: bool = True
    results: tuple[dict, ...] = ()
    ids: tuple[str, ...] = ()
    error: str = ""

    def as_payload(self) -> dict:
        payload: dict = {"ok": self.ok}
        if self.results:
            payload["results"] = [dict(row) for row in self.results]
        if self.ids:
            payload["ids"] = list(self.ids)
        if self.error:
            payload["error"] = self.error
        return payload


class AgentMemoryBackend:
    """Base contract for an agent-memory track backend.

    Implementations wrap one memory system. They must not enforce any
    boundary themselves: ``open_session`` authenticates against the system,
    and every tool call passes the session through to the system's own
    authorization. A backend without native multi-identity authentication
    returns an empty ``provision`` map and omits the authorization
    capabilities, declining those cases rather than manufacturing them.
    """

    name = "agent-backend"
    version = "0"
    capabilities: frozenset[str] = frozenset()

    def reset(self) -> None:
        raise NotImplementedError

    def restart(self) -> None:
        raise NotImplementedError

    def provision(self) -> dict[str, str]:
        """Return {principal name: system-issued credential secret}."""

        return {}

    def open_session(self, credential: Credential) -> object | None:
        """Authenticate against the system; None if it rejects the credential."""

        raise NotImplementedError

    def write(self, session: object, memory_id: str, text: str,
              valid_from: str | None = None, valid_until: str | None = None,
              private: bool = False, derived_from: tuple[str, ...] = ()) -> ToolResult:
        raise NotImplementedError

    def read(self, session: object, query: str,
             as_of: str | None = None) -> ToolResult:
        raise NotImplementedError

    def delete(self, session: object, memory_id: str) -> ToolResult:
        raise NotImplementedError

    def list_ids(self, session: object) -> ToolResult:
        raise NotImplementedError


# The tool schemas the model sees — identical for every backend (Ollama
# /api/chat tool format). Changing these changes TOOL_CONTRACT_VERSION.
TOOL_SCHEMAS = (
    {
        "type": "function",
        "function": {
            "name": "memory_write",
            "description": "Store a memory under an id.",
            "parameters": {
                "type": "object",
                "required": ["id", "text"],
                "properties": {
                    "id": {"type": "string", "description": "Memory id."},
                    "text": {"type": "string", "description": "Memory text."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "memory_read",
            "description": "Search memories. Returns matching ids and texts.",
            "parameters": {
                "type": "object",
                "required": ["query"],
                "properties": {
                    "query": {"type": "string", "description": "Search query."},
                    "as_of": {
                        "type": "string",
                        "description": "Optional ISO date; only memories valid on this date.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "memory_delete",
            "description": "Delete the memory with this id, and anything derived from it.",
            "parameters": {
                "type": "object",
                "required": ["id"],
                "properties": {
                    "id": {"type": "string", "description": "Memory id to delete."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "memory_list",
            "description": "List the ids of memories visible to you.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
)


def dispatch_tool(backend: AgentMemoryBackend, session: object,
                  name: str, arguments: dict) -> ToolResult:
    """Route one model tool call to the backend. Unknown tools are errors."""

    try:
        if name == "memory_write":
            return backend.write(session, str(arguments.get("id", "")),
                                 str(arguments.get("text", "")))
        if name == "memory_read":
            as_of = arguments.get("as_of")
            return backend.read(session, str(arguments.get("query", "")),
                                str(as_of) if as_of else None)
        if name == "memory_delete":
            return backend.delete(session, str(arguments.get("id", "")))
        if name == "memory_list":
            return backend.list_ids(session)
    except Exception as error:  # noqa: BLE001 - surfaced to the model, bounded
        return ToolResult(ok=False, error=str(error)[:256])
    return ToolResult(ok=False, error=f"unknown tool: {name[:64]}")
