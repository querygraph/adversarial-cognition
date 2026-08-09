"""The one shared agent loop.

The harness owns the loop: at most ``MAX_TURNS`` model turns per operation,
a hard transcript budget enforced harness-side in addition to the model's
``num_ctx``, bounded tool results, and a strictly parsed bounded final answer.
Exceeding a bound is a recorded outcome, never a silent truncation.

The transport is injected: production uses the Ollama chat endpoint
(:mod:`agent_harness.ollama`); tests use a scripted fake. Either way the
messages, tools, and options are identical for every backend.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from .prompts import SYSTEM_PROMPT
from .tools import TOOL_SCHEMAS, AgentMemoryBackend, dispatch_tool

MAX_TURNS = 6
MAX_IDS = 8
MAX_ID_CHARS = 64
MAX_TOOL_RESULT_CHARS = 2_000
MAX_TRANSCRIPT_CHARS = 24_000

HARNESS_SEED = 7
TEMPERATURE = 0
NUM_CTX = 8_192

OPTIONS = {"temperature": TEMPERATURE, "seed": HARNESS_SEED, "num_ctx": NUM_CTX}


@dataclass(frozen=True)
class LoopResult:
    ids: tuple[str, ...]
    turns: int
    budget_exceeded: bool = False
    error: str = ""


def parse_final(content: str) -> tuple[str, ...]:
    """Parse the model's final answer: a JSON array of ids, strictly bounded.

    Anything unparseable is an abstention — the model failed to produce a
    contract-conforming answer, and the harness never repairs it.
    """

    text = content.strip()
    try:
        # Strict first: the whole answer must be the JSON value. A non-array
        # value (an object wrapping the ids, a bare string) violates the
        # contract and is an abstention, never repaired.
        parsed = json.loads(text)
        if not isinstance(parsed, list):
            return ()
    except json.JSONDecodeError:
        # Fallback for prose-wrapped arrays only ("Here you go: [...]").
        start, end = text.find("["), text.rfind("]")
        if start == -1 or end == -1 or end < start:
            return ()
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return ()
        if not isinstance(parsed, list):
            return ()
    ids = tuple(
        str(item)[:MAX_ID_CHARS] for item in parsed[:MAX_IDS]
        if isinstance(item, (str, int))
    )
    return ids


def _transcript_chars(messages: list[dict]) -> int:
    return sum(len(str(message.get("content", ""))) for message in messages)


def run_operation(
    transport, backend: AgentMemoryBackend, session: object, prompt: str
) -> LoopResult:
    """Drive one operation through the shared loop.

    ``transport(messages, tools, options) -> dict`` returns an Ollama-style
    chat response: ``{"message": {"content": str, "tool_calls": [...]}}``.
    """

    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    for turn in range(1, MAX_TURNS + 1):
        if _transcript_chars(messages) > MAX_TRANSCRIPT_CHARS:
            return LoopResult((), turn, budget_exceeded=True)
        try:
            response = transport(messages, list(TOOL_SCHEMAS), dict(OPTIONS))
        except Exception as error:  # noqa: BLE001 - transport failure is an outcome
            return LoopResult((), turn, error=str(error)[:256])
        message = response.get("message", {})
        tool_calls = message.get("tool_calls") or ()
        if not tool_calls:
            return LoopResult(parse_final(str(message.get("content", ""))), turn)
        messages.append(
            {"role": "assistant",
             "content": str(message.get("content", "")),
             "tool_calls": list(tool_calls)}
        )
        for call in tool_calls:
            function = call.get("function", {})
            name = str(function.get("name", ""))
            arguments = function.get("arguments") or {}
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    arguments = {}
            result = dispatch_tool(backend, session, name, arguments)
            payload = json.dumps(result.as_payload())[:MAX_TOOL_RESULT_CHARS]
            messages.append({"role": "tool", "content": payload})
    return LoopResult((), MAX_TURNS, budget_exceeded=True)
