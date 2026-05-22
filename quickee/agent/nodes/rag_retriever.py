from typing import Optional

from qdrant_client.models import FieldCondition, Filter, MatchAny, Range

from pipeline.embedder import get_embedder
from pipeline.qdrant_client import get_qdrant_client
from config.settings import get_settings


class RAGRetriever:
    def __init__(self):
        self.settings = get_settings()
        self.embedder = get_embedder()
        self.qdrant = get_qdrant_client()
        self.qdrant.connect()

    def retrieve(
        self,
        desired_categories: list[str],
        existing_items: list[str],
        color_preferences: list[str],
        max_budget: Optional[float] = None,
    ) -> tuple[list[float], dict[str, list[dict]]]:
        """Return (query_vector, {category: [hits]})."""

        # Build a rich semantic query from context
        query_parts = existing_items + color_preferences
        query_text = (
            " ".join(query_parts)
            if query_parts
            else " ".join(desired_categories) + " fashion clothing"
        )
        query_vector = self.embedder.embed_text(query_text)

        retrieved_items: dict[str, list[dict]] = {}

        for category in desired_categories:
            # --- Build filter chain ---
            must_conditions = []

            # Category filter (skip for "shoes" since we don't have that
            # collection; do a general search instead)
            if category in ("tops", "bottoms"):
                must_conditions.append(
                    FieldCondition(
                        key="category",
                        match=MatchAny(any=[category]),
                    )
                )

            # Price filter — FIX: use Range, not MatchText (price_inr is a float)
            if max_budget is not None:
                must_conditions.append(
                    FieldCondition(
                        key="price_inr",
                        range=Range(lte=max_budget),   # ← was broken MatchText
                    )
                )

            search_filter = Filter(must=must_conditions) if must_conditions else None

            results = self.qdrant.search(
                collection_name=self.settings.qdrant_collection_name,
                query_vector=query_vector,
                limit=self.settings.retrieval_limit,
                query_filter=search_filter,
            )

            retrieved_items[category] = [
                {"id": r["id"], "score": r["score"], "payload": r["payload"]}
                for r in results
            ]

        return query_vector, retrieved_items


def rag_retriever_node(state: dict) -> dict:
    retriever = RAGRetriever()

    query_vector, retrieved_items = retriever.retrieve(
        desired_categories=state.get("desired_categories", ["tops", "bottoms"]),
        existing_items=state.get("existing_items", []),
        color_preferences=state.get("color_preferences", []),
        max_budget=state.get("max_budget"),
    )

    return {
        **state,
        "retrieved_items": retrieved_items,
        "retrieval_query_vector": query_vector,
    }
