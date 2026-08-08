"""Graphiti OSS adapter for MARCIANA-ADVERSARIAL-v1.

Maps the benchmark's behavioral contract onto graphiti-core with local
Ollama models (llama3.1 for knowledge-graph extraction, nomic-embed-text
for embeddings) over graphiti's embedded Kuzu driver — no external service.
Principals map to graphiti ``group_id`` partitions; storage, scoping, BM25
retrieval, and persistence are executed by graphiti/Kuzu, never by this
adapter. Retrieval uses graphiti's episode BM25 + RRF recipe over the raw
episode content; entity/edge extraction still runs on every remember
through the configured local LLM.

Two workarounds for graphiti-core 0.29.3's Kuzu backend, both documented in
the README: Kuzu full-text indexes must be created explicitly (its
``build_indices_and_constraints`` is a no-op), and ``KuzuDriver`` never
initializes ``_database``, which ``add_episode`` compares against the
requested group_id, so the sentinel is pinned before each write.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import sys
import warnings
from datetime import date, datetime, time as dtime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
logging.basicConfig(stream=sys.stderr, level=logging.ERROR)
warnings.filterwarnings("ignore", category=DeprecationWarning)

import kuzu
from graphiti_core import Graphiti
from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient
from graphiti_core.driver.driver import GraphProvider
from graphiti_core.driver.kuzu_driver import KuzuDriver
from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
from graphiti_core.graph_queries import get_fulltext_indices
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient
from graphiti_core.nodes import EpisodeType
from graphiti_core.search.search_config import (
    EpisodeReranker,
    EpisodeSearchConfig,
    EpisodeSearchMethod,
    SearchConfig,
)

from protocol import MemorySystem, run

OLLAMA = os.environ.get("MARCIANA_OLLAMA_URL", "http://localhost:11434").rstrip("/").removesuffix("/v1") + "/v1"
DATABASE = Path(__file__).resolve().parent / "data" / "kuzu-bench.db"
LLM = LLMConfig(api_key="ollama", model="llama3.1", small_model="llama3.1",
                base_url=OLLAMA, temperature=0)
EPISODES_BM25 = SearchConfig(
    episode_config=EpisodeSearchConfig(
        search_methods=[EpisodeSearchMethod.bm25],
        reranker=EpisodeReranker.rrf,
    ),
    limit=10,
)


def utc(day: date) -> datetime:
    return datetime.combine(day, dtime(0, 0), tzinfo=timezone.utc)


class GraphitiSystem(MemorySystem):
    name = "graphiti"
    version = "graphiti-core-0.29.3-kuzu"
    # Graphiti has no clearance/purpose/nonce/digest/derivation concepts, and
    # its bi-temporal edge dates come from LLM date extraction rather than a
    # caller-bound valid-time interval, so "temporal" is not claimed; see the
    # README. Episode BM25 returns nothing without lexical overlap, which is
    # graphiti's own abstention behavior under a first-class search recipe.
    capabilities = frozenset(
        {"retrieval", "isolation", "forget", "persistence", "abstention"}
    )

    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        self.generation = 0
        self.episodes: dict[tuple[str, str], str] = {}
        self.client: Graphiti | None = None

    def _connect(self) -> Graphiti:
        DATABASE.parent.mkdir(parents=True, exist_ok=True)
        driver = KuzuDriver(db=str(DATABASE))
        connection = kuzu.Connection(driver.db)
        connection.execute("INSTALL FTS; LOAD FTS;")
        for statement in get_fulltext_indices(GraphProvider.KUZU):
            try:
                connection.execute(statement)
            except RuntimeError:
                pass  # index already exists on a reopened database
        connection.close()
        return Graphiti(
            graph_driver=driver,
            llm_client=OpenAIGenericClient(config=LLM),
            embedder=OpenAIEmbedder(config=OpenAIEmbedderConfig(
                api_key="ollama", base_url=OLLAMA,
                embedding_model="nomic-embed-text", embedding_dim=768)),
            cross_encoder=OpenAIRerankerClient(config=LLM),
        )

    def _await(self, coroutine):
        return self.loop.run_until_complete(coroutine)

    def _close(self) -> None:
        if self.client is not None:
            self._await(self.client.close())
            self.client = None

    def _group(self, principal: str) -> str:
        return f"bench-{self.generation}-{principal}"

    def reset(self) -> None:
        self._close()
        shutil.rmtree(DATABASE, ignore_errors=True)
        self.generation += 1
        self.episodes = {}
        self.client = self._connect()

    def remember(self, memory_id, text, principal, valid_from=None,
                 valid_until=None, private=False, nonce=None, supersedes=None,
                 derived_from=()) -> bool:
        group = self._group(principal)
        self.client.driver._database = group
        result = self._await(self.client.add_episode(
            name=f"bench:{memory_id}",
            episode_body=text,
            source_description="adversarial benchmark seed",
            reference_time=utc(valid_from) if valid_from else utc(date(2026, 1, 15)),
            source=EpisodeType.text,
            group_id=group,
        ))
        self.episodes[(principal, memory_id)] = result.episode.uuid
        return True

    def recall(self, query, principal, as_of=None):
        result = self._await(self.client.search_(
            query, config=EPISODES_BM25, group_ids=[self._group(principal)]))
        ids = [episode.name[len("bench:"):]
               for episode in result.episodes
               if episode.name.startswith("bench:")]
        return tuple(dict.fromkeys(ids))

    def forget(self, memory_id, principal) -> bool:
        uuid = self.episodes.get((principal, memory_id))
        if uuid is None:
            return False
        self._await(self.client.remove_episode(uuid))
        return True

    def restart(self) -> None:
        self._close()
        self.client = self._connect()


if __name__ == "__main__":
    run(GraphitiSystem())
