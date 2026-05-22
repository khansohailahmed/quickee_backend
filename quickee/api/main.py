from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from api.routes.style_me import router as style_me_router
from api.middleware import LoggingMiddleware, RateLimitMiddleware
from api.schemas import HealthResponse
from pipeline.qdrant_client import get_qdrant_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

app = FastAPI(
    title="QuickEE Stylist API",
    description="AI-powered fashion styling assistant using RAG and fashion reasoning",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(LoggingMiddleware)
app.add_middleware(RateLimitMiddleware, calls=10, period=60)

app.include_router(style_me_router)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    qdrant = get_qdrant_client()
    qdrant.connect()

    collections = {}
    try:
        clothing_info = qdrant.get_collection_info(qdrant.settings.qdrant_collection_name)
        collections["clothing_catalog"] = clothing_info
    except Exception as e:
        collections["clothing_catalog"] = {"error": str(e)}

    try:
        cache_info = qdrant.get_collection_info(qdrant.settings.qdrant_cache_collection_name)
        collections["query_cache"] = cache_info
    except Exception as e:
        collections["query_cache"] = {"error": str(e)}

    return HealthResponse(
        status="healthy",
        qdrant_connected=True,
        collections=collections,
    )


@app.get("/")
async def root():
    return {
        "message": "Welcome to QuickEE Stylist API",
        "docs": "/docs",
        "health": "/health",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
