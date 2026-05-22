import json
from typing import TypedDict

from agent.prompts.system_prompts import RESPONSE_BUILDER_SYSTEM, RESPONSE_BUILDER_USER


class ResponseBuilderOutput(TypedDict):
    recommended_items: list[dict]
    total_price_inr: float
    stylist_note: str
    cache_hit: bool
    tokens_used: int
    processing_ms: int


class ResponseBuilder:
    def build(self, state: dict) -> ResponseBuilderOutput:
        selected_items = state.get("selected_items", [])
        stylist_note = state.get("stylist_note", "")
        cache_hit = state.get("cache_hit", False)
        tokens_used = state.get("tokens_used", 0)
        processing_ms = state.get("processing_ms", 0)

        recommended_items = []
        total_price = 0.0

        for item in selected_items:
            if isinstance(item, dict):
                payload = item.get("payload", item)
                price = payload.get("price_inr", 0)
            else:
                price = 0

            total_price += price
            recommended_items.append(item)

        return ResponseBuilderOutput(
            recommended_items=recommended_items,
            total_price_inr=total_price,
            stylist_note=stylist_note,
            cache_hit=cache_hit,
            tokens_used=tokens_used,
            processing_ms=processing_ms,
        )


def response_builder_node(state: dict) -> dict:
    builder = ResponseBuilder()
    result = builder.build(state)

    return {
        **state,
        **result,
    }


def build_final_response(state: dict) -> dict:
    recommended_items = state.get("selected_items", [])
    stylist_note = state.get("stylist_note", "")
    cache_hit = state.get("cache_hit", False)
    tokens_used = state.get("tokens_used", 0)
    processing_ms = state.get("processing_ms", 0)

    formatted_items = []
    total_price = 0.0

    for item in recommended_items:
        if isinstance(item, dict):
            if "payload" in item:
                payload = item["payload"]
            else:
                payload = item

            formatted_items.append({
                "item_id": payload.get("item_id", "unknown"),
                "name": payload.get("name", "Unknown Item"),
                "brand": payload.get("brand", "Unknown"),
                "category": payload.get("category", "unknown"),
                "price_inr": payload.get("price_inr", 0),
                "color": payload.get("color", "N/A"),
                "image_url": payload.get("image_url", ""),
                "product_url": payload.get("product_url", ""),
            })
            total_price += payload.get("price_inr", 0)

    return {
        "recommended_items": formatted_items,
        "total_price_inr": total_price,
        "stylist_note": stylist_note,
        "cache_hit": cache_hit,
        "tokens_used": tokens_used,
        "processing_ms": processing_ms,
    }
