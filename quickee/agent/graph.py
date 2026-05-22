import time
from typing import Optional, TypedDict

from langgraph.graph import END, StateGraph

from agent.nodes.cache_lookup import cache_lookup_node
from agent.nodes.fashion_evaluator import fashion_evaluator_node
from agent.nodes.prompt_parser import prompt_parser_node
from agent.nodes.rag_retriever import rag_retriever_node
from agent.nodes.response_builder import build_final_response, response_builder_node
from agent.nodes.stylist_note import stylist_note_node
from pipeline.qdrant_client import get_qdrant_client


class AgentState(TypedDict):
    query: str
    existing_items: list[str]
    occasion: Optional[str]
    desired_categories: list[str]
    color_preferences: list[str]
    max_budget: Optional[float]
    season: Optional[str]
    cache_hit: bool
    cached_response: Optional[dict]
    retrieved_items: dict[str, list[dict]]
    retrieval_query_vector: Optional[list[float]]
    selected_items: list[dict]
    evaluation_reasoning: str
    stylist_note: str
    recommended_items: list[dict]
    total_price_inr: float
    tokens_used: int
    processing_ms: int


def create_style_agent() -> StateGraph:
    workflow = StateGraph(AgentState)

    workflow.add_node("prompt_parser", prompt_parser_node)
    workflow.add_node("cache_lookup", cache_lookup_node)
    workflow.add_node("rag_retriever", rag_retriever_node)
    workflow.add_node("fashion_evaluator", fashion_evaluator_node)
    workflow.add_node("generate_stylist_note", stylist_note_node)
    workflow.add_node("response_builder", response_builder_node)

    workflow.set_entry_point("prompt_parser")
    workflow.add_edge("prompt_parser", "cache_lookup")

    def should_retrieve(state: AgentState) -> str:
        return "cached" if state.get("cache_hit", False) else "retrieve"

    workflow.add_conditional_edges(
        "cache_lookup",
        should_retrieve,
        {"cached": END, "retrieve": "rag_retriever"},
    )

    workflow.add_edge("rag_retriever", "fashion_evaluator")
    workflow.add_edge("fashion_evaluator", "generate_stylist_note")
    workflow.add_edge("generate_stylist_note", "response_builder")
    workflow.add_edge("response_builder", END)

    return workflow.compile()


def setup_qdrant_collections():
    """Idempotent – safe to call on every startup."""
    qdrant = get_qdrant_client()
    qdrant.connect()
    qdrant.create_clothing_collection()
    qdrant.create_cache_collection()


def run_style_agent(query: str) -> dict:
    start_time = time.time()

    setup_qdrant_collections()

    agent = create_style_agent()

    initial_state: AgentState = {
        "query": query,
        "existing_items": [],
        "occasion": None,
        "desired_categories": ["tops", "bottoms"],
        "color_preferences": [],
        "max_budget": None,
        "season": None,
        "cache_hit": False,
        "cached_response": None,
        "retrieved_items": {},
        "retrieval_query_vector": None,
        "selected_items": [],
        "evaluation_reasoning": "",
        "stylist_note": "",
        "recommended_items": [],
        "total_price_inr": 0.0,
        "tokens_used": 0,
        "processing_ms": 0,
    }

    final_state = agent.invoke(initial_state)

    processing_ms = int((time.time() - start_time) * 1000)

    if final_state.get("cache_hit", False):
        # FIX: inject actual wall-clock processing_ms into cached response
        cached = dict(final_state["cached_response"])
        cached["processing_ms"] = processing_ms
        cached["cache_hit"] = True
        return cached

    result = build_final_response(final_state)
    result["processing_ms"] = processing_ms
    return result


# Pre-compiled agent (re-used across requests)
style_agent = create_style_agent()
