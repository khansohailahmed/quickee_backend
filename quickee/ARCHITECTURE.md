# QuickEE Luxury Stylist Concierge – Architecture

## Folder Structure

```
quickeee/
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

## Data Journey (Request → Response)

```
User prompt (POST /api/v1/style-me)
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
                                                      │
                                          Store in cache (async)
                                                      │
        ◄─────────────────────────────────────────────┘
StyleMeResponse JSON
```

---

## State Management

LangGraph's `StateGraph` carries an `AgentState` TypedDict through each node.
Each node receives the full state and returns a partial update (spread operator pattern).
State is purely in-process (no Redis) – kept simple for single-instance deployment.

---

## Vector Database Schema (Qdrant)

### Collection: `clothing_catalog`
| Field | Type | Index | Notes |
|-------|------|-------|-------|
| item_id | keyword | no | Unique item identifier |
| name | text | no | Product name |
| brand | keyword | yes | "Zara" / "H&M" |
| category | keyword | yes | "tops" / "bottoms" |
| subcategory | keyword | no | "t-shirt" / "chinos" / etc. |
| color | keyword | yes | Normalised color string |
| price_inr | float | yes | Enables Range filter |
| description | text | no | Full text for embedding |
| image_url | text | no | CDN URL |
| product_url | text | no | Deep-link to product page |
| scraped_at | text | no | ISO datetime |

**Vector**: 384-dim COSINE (sentence-transformers all-MiniLM-L6-v2)
**Point ID**: `uuid.UUID(md5(item_id).hexdigest())` → valid UUID string

### Collection: `query_cache`
Same vector config. Payload: `original_query`, `response_json`, `created_at`.
Cache hit threshold: cosine ≥ **0.92** (configurable).

---

## Token / Cost Optimisation (Frugal Mindset)

1. **Semantic cache** – Identical/near-identical queries (≥ 0.92 cosine) return the
   cached response without any LLM call. Saves 100 % of tokens for repeat queries.

2. **Prompt compression** – `prompt_parser` uses `max_tokens=500` (structured JSON
   extraction is a short task). `fashion_evaluator` is capped at `1000` tokens.
   `stylist_note` is capped at `150` tokens (3 sentences max).

3. **Free-tier model** – `qwen2.5:7b-instruct running locally via Ollama provides
   strong reasoning at zero marginal cost during development.

4. **Batched embeddings** – `embed_batch()` sends all items in one `encode()` call
   instead of N individual calls, cutting embedding time ~60 %.

5. **Resource blocking** – Playwright aborts fonts, analytics pixels, and tracking
   scripts, reducing page-load time and network cost during scraping.

---

## Anti-bot / Rate-Limit Bypass Techniques

- Random user-agent rotation (3 modern browser strings)
- `navigator.webdriver` property overridden via `add_init_script`
- `--disable-blink-features=AutomationControlled` Chromium flag
- Realistic 1920×1080 viewport + `en-IN` locale + `Accept-Language` headers
- Random human-like delays between requests (1–3 s, uniform distribution)
- Gradual scroll (0.8× viewport height per step) to trigger lazy-load
- Non-essential resource blocking (fonts, analytics) to reduce fingerprint

---

## Running Locally

```bash
# 1. Start Qdrant
docker-compose up -d

# 2. Install dependencies
pip install -r requirements.txt
playwright install chromium

# 2b. Start Ollama + pull model (one-time)
ollama pull qwen2.5:7b-instruct

# 3. Scrape + ingest
python -m scraper.run_scrape          # scrape Zara + H&M
python pipeline/ingest.py             # embed + push to Qdrant

# 4. Start API
uvicorn api.main:app --reload --port 8000
# Swagger: http://localhost:8000/docs
```
