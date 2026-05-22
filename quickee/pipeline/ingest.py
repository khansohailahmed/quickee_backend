import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from scraper.playwright_scraper import ZaraScraper, HnMScraper
from scraper.item_schema import ClothingItem, ScrapedData
from pipeline.embedder import get_embedder
from pipeline.qdrant_client import get_qdrant_client, QdrantClientWrapper


class IngestionPipeline:
    def __init__(self):
        self.embedder = get_embedder()
        self.qdrant: QdrantClientWrapper = get_qdrant_client()
        self.qdrant.connect()

    async def scrape_all(self) -> list[ClothingItem]:
        all_items = []

        print("Scraping Zara...")
        zara = ZaraScraper()
        zara_data = await zara.scrape_all()
        all_items.extend(zara_data.items)
        print(f"  -> {len(zara_data.items)} Zara items")

        print("Scraping H&M...")
        hnm = HnMScraper()
        hnm_data = await hnm.scrape_all()
        all_items.extend(hnm_data.items)
        print(f"  -> {len(hnm_data.items)} H&M items")

        return all_items

    def load_scraped_data(self) -> list[ClothingItem]:
        data_dir = Path(__file__).parent.parent / "data" / "scraped"
        all_items = []

        for json_file in data_dir.glob("*_items.json"):
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                items_data = data.get('items', [])
                for item_data in items_data:
                    try:
                        item = ClothingItem(**item_data)
                        all_items.append(item)
                    except Exception as e:
                        print(f"Error loading item: {e}")
                        continue

        print(f"Loaded {len(all_items)} items from scraped data")
        return all_items

    def embed_items(self, items: list[ClothingItem]) -> tuple[list[dict], list[list[float]]]:
        texts_to_embed = [item.to_embedding_text() for item in items]
        print(f"Embedding {len(texts_to_embed)} items...")

        embeddings = self.embedder.embed_batch(texts_to_embed)

        payloads = [item.to_payload() for item in items]

        print(f"Generated {len(embeddings)} embeddings")
        return payloads, embeddings

    def setup_collections(self, force_recreate: bool = False):
        print("Setting up Qdrant collections...")
        self.qdrant.create_clothing_collection(force_recreate=force_recreate)
        self.qdrant.create_cache_collection(force_recreate=force_recreate)

    def ingest_to_qdrant(
        self,
        payloads: list[dict],
        embeddings: list[list[float]],
    ):
        print(f"Ingesting {len(payloads)} items to Qdrant...")
        self.qdrant.upsert_items(
            collection_name=self.qdrant.settings.qdrant_collection_name,
            items=payloads,
            vectors=embeddings,
        )

    async def run_full_pipeline(
        self,
        use_existing_scraped: bool = True,
        force_recreate_collections: bool = False,
    ):
        print("=" * 50)
        print("QuickEE Ingestion Pipeline")
        print("=" * 50)

        if use_existing_scraped:
            items = self.load_scraped_data()
        else:
            items = await self.scrape_all()

        if not items:
            print("No items to ingest!")
            return

        self.setup_collections(force_recreate=force_recreate_collections)

        payloads, embeddings = self.embed_items(items)

        self.ingest_to_qdrant(payloads, embeddings)

        collection_info = self.qdrant.get_collection_info(
            self.qdrant.settings.qdrant_collection_name
        )
        print(f"\nCollection info: {collection_info}")

        print("\n" + "=" * 50)
        print("Ingestion complete!")
        print("=" * 50)


async def main():
    pipeline = IngestionPipeline()
    await pipeline.run_full_pipeline(
        use_existing_scraped=True,
        force_recreate_collections=False,
    )


if __name__ == "__main__":
    asyncio.run(main())
