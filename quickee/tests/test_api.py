import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


@pytest.fixture
def client():
    with patch('api.main.get_qdrant_client'):
        from api.main import app
        with TestClient(app) as test_client:
            yield test_client


class TestHealthEndpoint:
    def test_health_check(self, client):
        with patch('api.main.get_qdrant_client') as mock_qdrant:
            mock_instance = MagicMock()
            mock_instance.connect.return_value = None
            mock_instance.get_collection_info.return_value = {
                "name": "test_collection",
                "vectors_count": 100,
                "points_count": 100,
                "status": "green",
            }
            mock_instance.settings.qdrant_collection_name = "clothing_catalog"
            mock_instance.settings.qdrant_cache_collection_name = "query_cache"
            mock_qdrant.return_value = mock_instance

            response = client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert "status" in data
            assert "qdrant_connected" in data


class TestRootEndpoint:
    def test_root(self, client):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert data["docs"] == "/docs"


class TestStyleMeEndpoint:
    def test_style_me_request_validation(self, client):
        response = client.post("/api/v1/style-me", json={})
        assert response.status_code == 422

    def test_style_me_request_empty_prompt(self, client):
        response = client.post("/api/v1/style-me", json={"prompt": ""})
        assert response.status_code == 422


class TestSchemas:
    def test_style_me_request_schema(self):
        from api.schemas import StyleMeRequest

        request = StyleMeRequest(prompt="I have dark navy chinos")
        assert request.prompt == "I have dark navy chinos"

    def test_recommended_item_schema(self):
        from api.schemas import RecommendedItem

        item = RecommendedItem(
            item_id="test_001",
            name="Linen Shirt",
            brand="Zara",
            category="tops",
            price_inr=2990.0,
            color="white",
            image_url="https://example.com/img.jpg",
            product_url="https://example.com/product",
        )

        assert item.item_id == "test_001"
        assert item.name == "Linen Shirt"

    def test_style_me_response_schema(self):
        from api.schemas import StyleMeResponse, RecommendedItem

        response = StyleMeResponse(
            recommended_items=[],
            total_price_inr=0.0,
            stylist_note="Test note",
            cache_hit=False,
            tokens_used=100,
            processing_ms=500,
        )

        assert response.total_price_inr == 0.0
        assert response.cache_hit is False
