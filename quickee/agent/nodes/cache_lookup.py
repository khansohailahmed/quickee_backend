from typing import TypedDict, Optional
import json

from pipeline.embedder import get_embedder
from pipeline.qdrant_client import get_qdrant_client
from config.settings import get_settings


class CacheLookupOutput(TypedDict):
    cache_hit: bool
    cached_response: Optional[dict]
    cache_query_vector: Optional[list[float]]


class CacheLookup:
    def __init__(self):
        self.settings = get_settings()
        self.embedder = get_embedder()
        self.qdrant = get_qdrant_client()
        self.qdrant.connect()

    def check_cache(self, query: str) -> tuple[bool, Optional[dict]]:
        query_vector = self.embedder.embed_text(query)

        results = self.qdrant.search(
            collection_name=self.settings.qdrant_cache_collection_name,
            query_vector=query_vector,
            limit=1,
            score_threshold=self.settings.cache_threshold,
        )

        if results and len(results) > 0:
            hit = results[0]
            if hit["score"] >= self.settings.cache_threshold:
                cached_payload = hit["payload"]
                try:
                    cached_response = json.loads(cached_payload["response_json"])
                    return True, cached_response
                except (json.JSONDecodeError, KeyError):
                    pass

        return False, None


def cache_lookup_node(state: dict) -> dict:
    lookup = CacheLookup()
    query = state.get("query", "")

    cache_hit, cached_response = lookup.check_cache(query)

    return {
        **state,
        "cache_hit": cache_hit,
        "cached_response": cached_response,
    }
