from pydantic import BaseModel, Field
from typing import Optional


class StyleMeRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="Natural language style query")


class RecommendedItem(BaseModel):
    item_id: str
    name: str
    brand: str
    category: str
    price_inr: float
    color: str
    image_url: str
    product_url: str


class StyleMeResponse(BaseModel):
    recommended_items: list[RecommendedItem]
    total_price_inr: float
    stylist_note: str
    cache_hit: bool
    tokens_used: int
    processing_ms: int


class HealthResponse(BaseModel):
    status: str
    qdrant_connected: bool
    collections: dict
