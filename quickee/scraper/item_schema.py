from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ClothingItem(BaseModel):
    item_id: str = Field(..., description="Unique identifier for the item")
    name: str = Field(..., description="Product name")
    brand: str = Field(..., description="Brand name (Zara, H&M)")
    price_inr: float = Field(..., ge=0, description="Price in Indian Rupees")
    category: str = Field(..., description="Category: tops or bottoms")
    subcategory: Optional[str] = Field(None, description="Subcategory like t-shirt, shirt, trousers, chinos")
    color: str = Field(..., description="Primary color of the item")
    description: Optional[str] = Field(None, description="Product description")
    image_url: str = Field(..., description="URL to product image")
    product_url: str = Field(..., description="URL to product page")
    scraped_at: datetime = Field(default_factory=datetime.utcnow)

    def to_embedding_text(self) -> str:
        parts = [self.name, self.category, self.color]
        if self.description:
            parts.append(self.description)
        if self.subcategory:
            parts.insert(1, self.subcategory)
        return " ".join(parts)

    def to_payload(self) -> dict:
        return {
            "item_id": self.item_id,
            "name": self.name,
            "brand": self.brand,
            "price_inr": self.price_inr,
            "category": self.category,
            "subcategory": self.subcategory,
            "color": self.color,
            "description": self.description,
            "image_url": self.image_url,
            "product_url": self.product_url,
            "scraped_at": self.scraped_at.isoformat(),
        }


class ScrapedData(BaseModel):
    source: str
    items: list[ClothingItem]
    scraped_at: datetime = Field(default_factory=datetime.utcnow)
    total_items: int = Field(default=0)

    def model_post_init(self, __context):
        self.total_items = len(self.items)
