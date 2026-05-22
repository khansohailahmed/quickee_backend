from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Local LLM via Ollama (OpenAI-compatible endpoint) ────────────────────
    # Make sure Ollama is running:  ollama serve
    # Pull the model first:         ollama pull qwen2.5:7b-instruct
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "qwen2.5:7b-instruct"
    # Ollama's OpenAI-compat layer accepts any non-empty string as the key
    ollama_api_key: str = "ollama"

    # ── Qdrant ────────────────────────────────────────────────────────────────
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection_name: str = "clothing_catalog"
    qdrant_cache_collection_name: str = "query_cache"

    # ── Embeddings (sentence-transformers all-MiniLM-L6-v2, fully local) ─────
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dim: int = 384

    # ── Semantic cache ────────────────────────────────────────────────────────
    cache_threshold: float = 0.92
    cache_ttl_days: int = 7

    # ── Scraper ───────────────────────────────────────────────────────────────
    scraper_user_agents: list[str] = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    ]
    max_items_per_category: int = 50
    retrieval_limit: int = 5

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
