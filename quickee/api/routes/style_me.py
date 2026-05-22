import asyncio
import logging

from fastapi import APIRouter, HTTPException

from agent.graph import run_style_agent
from api.schemas import RecommendedItem, StyleMeRequest, StyleMeResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["style"])


@router.post("/style-me", response_model=StyleMeResponse)
async def style_me(request: StyleMeRequest):
    """
    Accept a natural-language style query and return a curated outfit recommendation.

    Example body:
        {"prompt": "I have dark navy chinos, what t-shirt and shoes should I wear
                    for a summer yacht party?"}
    """
    try:
        logger.info("Processing style query: %s", request.prompt)

        # FIX: run_style_agent is synchronous (blocking LLM + Qdrant calls).
        # Use asyncio.to_thread so it runs in a thread-pool instead of
        # blocking the uvicorn event loop.
        result = await asyncio.to_thread(run_style_agent, request.prompt)

        recommended_items = [
            RecommendedItem(**item) for item in result.get("recommended_items", [])
        ]

        return StyleMeResponse(
            recommended_items=recommended_items,
            total_price_inr=result.get("total_price_inr", 0.0),
            stylist_note=result.get("stylist_note", ""),
            cache_hit=result.get("cache_hit", False),
            tokens_used=result.get("tokens_used", 0),
            processing_ms=result.get("processing_ms", 0),
        )

    except Exception as e:
        logger.exception("Error processing style query")
        raise HTTPException(status_code=500, detail=str(e))
