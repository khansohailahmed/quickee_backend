import pytest
import json
from pathlib import Path
from scraper.item_schema import ClothingItem, ScrapedData


class TestClothingItem:
    def test_clothing_item_creation(self):
        item = ClothingItem(
            item_id="test_001",
            name="Linen Shirt",
            brand="Zara",
            price_inr=2990.0,
            category="tops",
            subcategory="shirt",
            color="white",
            description="Classic white linen shirt",
            image_url="https://example.com/img.jpg",
            product_url="https://example.com/product",
        )

        assert item.item_id == "test_001"
        assert item.name == "Linen Shirt"
        assert item.brand == "Zara"
        assert item.price_inr == 2990.0
        assert item.category == "tops"
        assert item.subcategory == "shirt"
        assert item.color == "white"

    def test_to_embedding_text(self):
        item = ClothingItem(
            item_id="test_001",
            name="Linen Shirt",
            brand="Zara",
            price_inr=2990.0,
            category="tops",
            subcategory="shirt",
            color="white",
            description="Classic white linen shirt",
            image_url="https://example.com/img.jpg",
            product_url="https://example.com/product",
        )

        embedding_text = item.to_embedding_text()
        assert "Linen Shirt" in embedding_text
        assert "shirt" in embedding_text
        assert "white" in embedding_text
        assert "Classic white linen shirt" in embedding_text

    def test_to_payload(self):
        item = ClothingItem(
            item_id="test_001",
            name="Linen Shirt",
            brand="Zara",
            price_inr=2990.0,
            category="tops",
            subcategory="shirt",
            color="white",
            description="Classic white linen shirt",
            image_url="https://example.com/img.jpg",
            product_url="https://example.com/product",
        )

        payload = item.to_payload()
        assert payload["item_id"] == "test_001"
        assert payload["name"] == "Linen Shirt"
        assert payload["brand"] == "Zara"
        assert payload["price_inr"] == 2990.0
        assert "scraped_at" in payload


class TestScrapedData:
    def test_scraped_data_creation(self):
        items = [
            ClothingItem(
                item_id="test_001",
                name="Item 1",
                brand="Zara",
                price_inr=1000.0,
                category="tops",
                color="blue",
                image_url="",
                product_url="",
            ),
            ClothingItem(
                item_id="test_002",
                name="Item 2",
                brand="H&M",
                price_inr=2000.0,
                category="bottoms",
                color="black",
                image_url="",
                product_url="",
            ),
        ]

        data = ScrapedData(source="Zara", items=items)

        assert data.source == "Zara"
        assert len(data.items) == 2
        assert data.total_items == 2


class TestItemSchemaEdgeCases:
    def test_item_without_optional_fields(self):
        item = ClothingItem(
            item_id="test_001",
            name="Simple Item",
            brand="Zara",
            price_inr=1000.0,
            category="tops",
            color="blue",
            image_url="",
            product_url="",
        )

        assert item.description is None
        assert item.subcategory is None
        embedding_text = item.to_embedding_text()
        assert "Simple Item" in embedding_text
        assert "tops" in embedding_text
        assert "blue" in embedding_text

    def test_price_extraction(self):
        item = ClothingItem(
            item_id="test_001",
            name="Item",
            brand="Brand",
            price_inr=0.0,
            category="tops",
            color="blue",
            image_url="",
            product_url="",
        )

        assert item.price_inr == 0.0
