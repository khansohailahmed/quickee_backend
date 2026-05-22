"""
Embedder using sentence-transformers (local, no external API needed).
Model: all-MiniLM-L6-v2  →  384-dim vectors, fast and accurate.
"""
from typing import Optional
import numpy as np
from sentence_transformers import SentenceTransformer

from config.settings import get_settings


class Embedder:
    def __init__(self):
        self.settings = get_settings()
        # Local model – downloaded once, then cached at ~/.cache/huggingface
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        self.dimension = 384  # must match settings.embedding_dim

    def embed_text(self, text: str) -> list[float]:
        embedding = self.model.encode(text, normalize_embeddings=True)
        return embedding.tolist()

    def embed_batch(
        self, texts: list[str], batch_size: int = 64
    ) -> list[list[float]]:
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=True,
        )
        return embeddings.tolist()

    def cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        v1 = np.array(vec1)
        v2 = np.array(vec2)
        dot_product = np.dot(v1, v2)
        return float(dot_product / (np.linalg.norm(v1) * np.linalg.norm(v2)))

    def normalize_vector(self, vector: list[float]) -> list[float]:
        arr = np.array(vector)
        norm = np.linalg.norm(arr)
        if norm == 0:
            return vector
        return (arr / norm).tolist()


_embedder: Optional[Embedder] = None


def get_embedder() -> Embedder:
    global _embedder
    if _embedder is None:
        _embedder = Embedder()
    return _embedder
