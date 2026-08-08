"""Ollama chat transport for the shared harness (stdlib only)."""

from __future__ import annotations

import json
import os
import urllib.request

DEFAULT_MODEL = "llama3.1:latest"
DEFAULT_URL = "http://localhost:11434"
REQUEST_TIMEOUT_SECONDS = 300


def harness_model() -> str:
    return os.environ.get("MARCIANA_HARNESS_MODEL", DEFAULT_MODEL)


def ollama_url() -> str:
    return os.environ.get("MARCIANA_OLLAMA_URL", DEFAULT_URL).rstrip("/")


def transport(messages: list[dict], tools: list[dict], options: dict) -> dict:
    """One non-streaming chat call with the harness's fixed options."""

    body = json.dumps(
        {
            "model": harness_model(),
            "messages": messages,
            "tools": tools,
            "options": options,
            "stream": False,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{ollama_url()}/api/chat",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))
