# QuickEE — AI Fashion Stylist Backend

> An AI-powered fashion styling API using Retrieval-Augmented Generation, a multi-node LangGraph agent, and a semantic vector cache — fully local with Ollama + Qdrant.

---

## What It Does

QuickEE accepts a natural-language styling request (e.g. *"I have dark navy chinos, what should I wear for a yacht party?"*) and returns a curated outfit recommendation with product links, prices, and a luxury stylist note — all powered by a local LLM with zero cloud API cost.

---

## Tech Stack

| Layer | Technology |
|---|---|
| API | FastAPI 0.111 + Uvicorn |
| Agent | LangGraph 0.1 (StateGraph) |
| LLM | Ollama — qwen2.5:7b-instruct (local) |
| Vector DB | Qdrant 1.9 |
| Embeddings | sentence-transformers all-MiniLM-L6-v2 (384-dim, local) |
| Scraper | Playwright 1.44 (Chromium, headless) |
| Validation | Pydantic v2 + pydantic-settings |
| Containerisation | Docker + Docker Compose |

---

## Architecture

### Folder Structure

```
quickee_backend/
├── scraper/
│   ├── playwright_scraper.py   # Zara + H&M scrapers with anti-bot measures & mock fallback
│   ├── item_schema.py          # ClothingItem / ScrapedData Pydantic models
│   └── run_scrape.py           # CLI entry-point for scraping
│
├── pipeline/
│   ├── embedder.py             # sentence-transformers all-MiniLM-L6-v2 (384-dim, local)
│   ├── qdrant_client.py        # Qdrant wrapper – collections, upsert, search
│   └── ingest.py               # Scrape → embed → upsert pipeline
│
├── agent/
│   ├── graph.py                # LangGraph StateGraph orchestration
│   ├── nodes/
│   │   ├── cache_lookup.py     # Semantic cache check (cosine ≥ 0.92 → HIT)
│   │   ├── prompt_parser.py    # LLM → structured JSON extraction
│   │   ├── rag_retriever.py    # Qdrant filtered semantic search
│   │   ├── fashion_evaluator.py# LLM scores items & selects best outfit
│   │   ├── stylist_note.py     # LLM writes luxury 2–3 sentence note
│   │   └── response_builder.py # Assembles final response dict
│   └── prompts/
│       └── system_prompts.py   # All LLM prompt templates
│
├── api/
│   ├── main.py                 # FastAPI app – CORS, logging, rate-limit middleware
│   ├── routes/style_me.py      # POST /api/v1/style-me
│   ├── schemas.py              # Request / Response Pydantic models
│   └── middleware.py           # LoggingMiddleware, RateLimitMiddleware
│
├── config/settings.py          # Pydantic-settings (env-file aware)
├── data/scraped/               # JSON output from scraper
├── tests/                      # pytest test suite
├── docker-compose.yml          # Qdrant service
├── Dockerfile                  # App container
├── requirements.txt
├── .env                        # Local secrets (gitignored)
└── ARCHITECTURE.md
```

---

### System Layers

**Scraper layer**
Playwright-powered headless Chrome scrapes Zara & H&M product catalogs. Falls back to bundled JSON mock data when scraping is unavailable.

**Pipeline layer**
Scraped items are embedded via `sentence-transformers/all-MiniLM-L6-v2` in a single batch call (~60% faster than serial) and upserted into Qdrant's `clothing_catalog` collection.

**Agent layer**
A 6-node LangGraph `StateGraph` carries an `AgentState` TypedDict through each node in-process (no Redis). A conditional edge short-circuits to `END` on a semantic cache hit.

**API layer**
FastAPI with CORS, structured logging, and a sliding-window rate limiter (10 req / 60 s per IP). Blocking LLM + Qdrant calls are offloaded via `asyncio.to_thread` to avoid stalling the event loop.

---

### Request → Response Data Journey

```
User prompt  (POST /api/v1/style-me)
        │
        ▼
[prompt_parser node]
  LLM extracts: existing_items, occasion, desired_categories,
                color_preferences, max_budget, season
        │
        ▼
[cache_lookup node]
  Embed query → search qdrant/query_cache → cosine ≥ 0.92?
   YES → return cached JSON (cache_hit=true)
   NO  ──────────────────────────────────────────────┐
                                                      ▼
                                          [rag_retriever node]
                                            Embed context text
                                            Per desired_category:
                                              Filter(category=X, price≤budget)
                                              Qdrant cosine search → top-5 hits
                                                      │
                                                      ▼
                                          [fashion_evaluator node]
                                            LLM scores each item 1-10
                                            Selects best outfit combo
                                                      │
                                                      ▼
                                          [stylist_note node]
                                            LLM writes 2-3 sentence
                                            luxury stylist note
                                                      │
                                                      ▼
                                          [response_builder node]
                                            Formats final JSON payload
                                            Stores result in cache (async)
                                                      │
        ◄─────────────────────────────────────────────┘
StyleMeResponse JSON
```

---

### Agent Node Reference

| Node | Model call | Token cap | Purpose |
|---|---|---|---|
| `prompt_parser` | qwen2.5:7b | 500 | Extracts structured fields from free-text prompt |
| `cache_lookup` | — (embedding only) | — | Checks semantic cache; short-circuits on HIT |
| `rag_retriever` | — (Qdrant search) | — | Per-category cosine search with price Range filter |
| `fashion_evaluator` | qwen2.5:7b | 1000 | Scores items 1–10, picks best outfit combo |
| `stylist_note` | qwen2.5:7b | 150 | Writes 2–3 sentence luxury stylist commentary |
| `response_builder` | — | — | Assembles final dict; stores in cache async |

---

## API Reference

### `POST /api/v1/style-me`

Accept a natural-language style query and return a curated outfit recommendation.

**Request body**

```json
{
  "prompt": "I have dark navy chinos, what t-shirt and shoes should I wear for a summer yacht party?"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `prompt` | string | yes | Natural-language style query (min 1 char) |

**Response — `StyleMeResponse`**

```json
{
  "recommended_items": [
    {
      "item_id": "zara-001",
      "name": "Slim-Fit Linen Shirt",
      "brand": "Zara",
      "category": "tops",
      "price_inr": 2999.0,
      "color": "white",
      "image_url": "https://...",
      "product_url": "https://zara.com/..."
    }
  ],
  "total_price_inr": 5498.0,
  "stylist_note": "This crisp white linen pairing against your navy chinos strikes the perfect nautical chord...",
  "cache_hit": false,
  "tokens_used": 842,
  "processing_ms": 3120
}
```

| Field | Type | Description |
|---|---|---|
| `recommended_items` | `RecommendedItem[]` | Curated outfit items with product links |
| `total_price_inr` | float | Sum of all recommended item prices |
| `stylist_note` | string | 2–3 sentence luxury stylist commentary |
| `cache_hit` | bool | `true` if served from semantic cache (0 LLM tokens used) |
| `tokens_used` | int | Total LLM tokens consumed |
| `processing_ms` | int | Wall-clock latency in milliseconds |

> Rate limit: 10 requests / 60 s per IP. Returns HTTP 429 on breach.

---

### `GET /health`

Returns API status and Qdrant collection info.

```json
{
  "status": "healthy",
  "qdrant_connected": true,
  "collections": {
    "clothing_catalog": { "vectors_count": 2400, "points_count": 2400 },
    "query_cache":      { "vectors_count": 18,   "points_count": 18   }
  }
}
```

### `GET /`

```json
{ "message": "Welcome to QuickEE Stylist API", "docs": "/docs", "health": "/health" }
```

### `GET /docs`

Auto-generated Swagger UI for interactive testing.

---

## Vector Database Schema (Qdrant)

### Collection: `clothing_catalog`

| Field | Type | Indexed | Notes |
|---|---|---|---|
| `item_id` | keyword | no | Unique item identifier |
| `name` | text | no | Product name |
| `brand` | keyword | yes | "Zara" / "H&M" |
| `category` | keyword | yes | "tops" / "bottoms" |
| `subcategory` | keyword | no | "t-shirt" / "chinos" / etc. |
| `color` | keyword | yes | Normalised color string |
| `price_inr` | float | yes | Enables Range filter for budget |
| `description` | text | no | Full text used for embedding |
| `image_url` | text | no | CDN URL |
| `product_url` | text | no | Deep-link to product page |
| `scraped_at` | text | no | ISO datetime |

**Vector:** 384-dim COSINE — `sentence-transformers/all-MiniLM-L6-v2`
**Point ID:** `uuid.UUID(md5(item_id).hexdigest())`

### Collection: `query_cache`

Same vector config. Payload fields: `original_query`, `response_json`, `created_at`.
Cache hit threshold: cosine ≥ **0.92** (configurable via `CACHE_THRESHOLD` env var).

---

## Cost & Performance Optimisations

1. **Semantic cache** — Near-identical queries (cosine ≥ 0.92) return the cached response with zero LLM calls. Saves 100% of tokens for repeat queries.

2. **Local LLM via Ollama** — `qwen2.5:7b-instruct` runs entirely on-device. Zero API cost and zero data leaving the machine during development.

3. **Tight token caps** — `prompt_parser`: 500 tokens. `fashion_evaluator`: 1000 tokens. `stylist_note`: 150 tokens (enforces 3-sentence max).

4. **Batched embeddings** — All items encoded in one `encode()` call instead of N serial calls, cutting embedding time ~60%.

5. **Playwright resource blocking** — Fonts, analytics pixels, and tracking scripts are aborted during scraping, reducing page-load time and network cost.

---

## Anti-bot / Scraper Bypass Techniques

- Random user-agent rotation (3 modern browser strings)
- `navigator.webdriver` property overridden via `add_init_script`
- `--disable-blink-features=AutomationControlled` Chromium flag
- Realistic 1920×1080 viewport + `en-IN` locale + `Accept-Language` headers
- Random human-like delays between requests (1–3 s, uniform distribution)
- Gradual scroll (0.8× viewport height per step) to trigger lazy-loaded content
- Non-essential resource blocking (fonts, analytics) to reduce browser fingerprint

---

## Getting Started

### Prerequisites

- Docker + Docker Compose
- Python 3.12+
- [Ollama](https://ollama.com) installed and running

### 1. Start Qdrant

```bash
docker-compose up -d
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 3. Pull the LLM (one-time)

```bash
ollama pull qwen2.5:7b-instruct
```

### 4. Scrape & ingest data

```bash
python -m scraper.run_scrape      # scrapes Zara + H&M (or uses mock fallback)
python pipeline/ingest.py         # embeds items and pushes to Qdrant
```

### 5. Start the API

```bash
uvicorn api.main:app --reload --port 8000
```

Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Environment Variables

Copy `.env.example` to `.env` and adjust as needed.

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | Ollama OpenAI-compatible endpoint |
| `OLLAMA_MODEL` | `qwen2.5:7b-instruct` | Model name |
| `QDRANT_HOST` | `localhost` | Qdrant host |
| `QDRANT_PORT` | `6333` | Qdrant port |
| `QDRANT_COLLECTION_NAME` | `clothing_catalog` | Main vector collection |
| `QDRANT_CACHE_COLLECTION_NAME` | `query_cache` | Semantic cache collection |
| `CACHE_THRESHOLD` | `0.92` | Cosine similarity threshold for cache hits |
| `CACHE_TTL_DAYS` | `7` | Cache entry TTL in days |
| `RETRIEVAL_LIMIT` | `5` | Top-K results per category from Qdrant |

---

## Running Tests

```bash
pytest tests/ -v
```

Test modules:
- `tests/test_api.py` — FastAPI endpoint integration tests
- `tests/test_rag.py` — RAG retrieval pipeline tests
- `tests/test_scraper.py` — Playwright scraper tests

---

## Demo Recording

A screen recording demonstrating the full API flow — prompt → agent pipeline → styled outfit response — is included in the repository as `Screen_Recording_2026-05-22.mp4`.

---

## License

MIT
