import pytest
from unittest.mock import MagicMock, patch
from pipeline.embedder import Embedder


class TestEmbedder:
    def test_embedder_initialization(self):
        embedder = Embedder()
        assert embedder.model == "nomic-embed-text"
        assert embedder.dimension == 768

    def test_cosine_similarity(self):
        embedder = Embedder()

        vec1 = [1.0, 0.0, 0.0]
        vec2 = [1.0, 0.0, 0.0]
        assert embedder.cosine_similarity(vec1, vec2) == pytest.approx(1.0)

        vec3 = [1.0, 0.0, 0.0]
        vec4 = [0.0, 1.0, 0.0]
        assert embedder.cosine_similarity(vec3, vec4) == pytest.approx(0.0)

        vec5 = [1.0, 1.0, 1.0]
        vec6 = [1.0, 1.0, 1.0]
        similarity = embedder.cosine_similarity(vec5, vec6)
        assert similarity == pytest.approx(1.0, rel=0.01)

    def test_normalize_vector(self):
        embedder = Embedder()

        vec = [3.0, 4.0, 0.0]
        normalized = embedder.normalize_vector(vec)
        norm = sum(x**2 for x in normalized) ** 0.5
        assert norm == pytest.approx(1.0, rel=0.01)

        zero_vec = [0.0, 0.0, 0.0]
        normalized_zero = embedder.normalize_vector(zero_vec)
        assert normalized_zero == zero_vec


class TestEmbedderBatch:
    def test_embed_batch_mock(self):
        with patch('pipeline.embedder.httpx.post') as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {"embedding": [0.1] * 768}
            mock_post.return_value = mock_response

            embedder = Embedder()
            texts = ["text1", "text2"]
            embeddings = embedder.embed_batch(texts)

            assert len(embeddings) == 2
            assert all(len(e) == 768 for e in embeddings)