"""Adapter for the native Cognee Rust CLI (cognee-rs).

The CLI is an external, user-built Rust binary. This adapter does not emulate
Cognee: every remember/recall/reset operation invokes that binary and parses
its public JSON output. Dataset names provide storage partitioning only; they
are not claimed as authorization.
"""

from __future__ import annotations

import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from protocol import MemorySystem, Unsupported, run

ID_RE = re.compile(r"\[([A-Za-z0-9][A-Za-z0-9_-]{0,63})\]")


class CogneeRustSystem(MemorySystem):
    name = "cognee-rs"
    version = "native-cli"
    capabilities = frozenset({"retrieval", "persistence"})

    def __init__(self) -> None:
        binary = os.environ.get("COGNEE_RS_BIN", "cognee-cli")
        self.binary = shutil.which(binary) or (binary if Path(binary).is_file() else "")
        if not self.binary:
            raise RuntimeError("COGNEE_RS_BIN is not set and cognee-cli is not on PATH")
        self.root = Path(tempfile.mkdtemp(prefix="marciana-cognee-rs-"))
        self.env = os.environ.copy()
        model = os.environ.get("MARCIANA_OLLAMA_MODEL") or "gpt-oss:20b"
        ollama_url = os.environ.get("MARCIANA_OLLAMA_URL", "http://host.docker.internal:11434").rstrip("/")
        self.env.update({
            "COGNEE_CONFIG_HOME": str(self.root / "config"),
            "COGNEE_SYSTEM_ROOT_DIRECTORY": str(self.root / "system"),
            "COGNEE_DATA_ROOT_DIRECTORY": str(self.root / "data"),
            "COGNEE_LOG_FILE": "false",
            "RUST_LOG": "error",
            "LLM_PROVIDER": os.environ.get("LLM_PROVIDER") or "ollama",
            "LLM_MODEL": os.environ.get("LLM_MODEL") or model,
            "LLM_ENDPOINT": os.environ.get("LLM_ENDPOINT") or f"{ollama_url}/v1",
            "LLM_API_KEY": os.environ.get("LLM_API_KEY") or "ollama",
            "EMBEDDING_PROVIDER": os.environ.get("EMBEDDING_PROVIDER") or "ollama",
            "EMBEDDING_MODEL": os.environ.get("EMBEDDING_MODEL") or "nomic-embed-text",
            "EMBEDDING_ENDPOINT": os.environ.get("EMBEDDING_ENDPOINT") or f"{ollama_url}/api/embed",
            "EMBEDDING_DIMENSIONS": os.environ.get("EMBEDDING_DIMENSIONS") or "768",
        })

    def _call(self, *args: str, json_output: bool = False) -> str:
        command = [self.binary, *args]
        if json_output:
            command += ["--output-format", "json"]
        result = subprocess.run(command, env=self.env, capture_output=True,
                                text=True, timeout=600, check=False)
        if result.returncode:
            raise RuntimeError((result.stderr or result.stdout or "cognee-cli failed")[-512:])
        return result.stdout

    @staticmethod
    def _ids(output: str) -> tuple[str, ...]:
        found: list[str] = []
        for match in ID_RE.finditer(output):
            value = match.group(1)
            if value not in found and value in {"price-old", "price-current", "soil", "private-farm", "prompt-injection"}:
                found.append(value)
        return tuple(found[:8])

    def reset(self) -> None:
        # This only targets the adapter's private root, never a user's store.
        shutil.rmtree(self.root, ignore_errors=True)
        self.root.mkdir(parents=True)
        self.env["COGNEE_CONFIG_HOME"] = str(self.root / "config")
        self.env["COGNEE_SYSTEM_ROOT_DIRECTORY"] = str(self.root / "system")
        self.env["COGNEE_DATA_ROOT_DIRECTORY"] = str(self.root / "data")

    def remember(self, memory_id, text, principal, valid_from=None,
                 valid_until=None, private=False, nonce=None, supersedes=None,
                 derived_from=()) -> bool:
        if any(value is not None for value in (valid_from, valid_until, nonce, supersedes)) or derived_from:
            raise Unsupported("temporal, replay, supersession, and provenance metadata")
        dataset = f"marciana-{principal}"
        self._call("remember", f"[{memory_id}] {text}", "--dataset-name", dataset, "--no-improve")
        return True

    def recall(self, query, principal, as_of=None):
        if as_of is not None:
            raise Unsupported("temporal as-of query")
        output = self._call("recall", query, "--datasets", f"marciana-{principal}",
                            "--top-k", "15", json_output=True)
        return self._ids(output)

    def forget(self, memory_id, principal) -> bool:
        raise Unsupported("per-memory forget")

    def restart(self) -> None:
        # Each operation is already a fresh native process; storage is durable.
        return None


def main() -> None:
    system = CogneeRustSystem()
    buffer = io.StringIO()
    original = sys.stdout
    sys.stdout = buffer
    try:
        run(system)
    finally:
        sys.stdout = original
    for line in reversed(buffer.getvalue().splitlines()):
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and "cases" in parsed:
            print(line)
            return
    raise SystemExit("adapter produced no outcome payload")


if __name__ == "__main__":
    main()
