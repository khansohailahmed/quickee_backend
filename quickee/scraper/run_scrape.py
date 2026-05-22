import asyncio
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scraper.playwright_scraper import ZaraScraper, HnMScraper, run_scraper
from scraper.item_schema import ScrapedData
import json


def load_existing_data() -> list:
    data_dir = Path(__file__).parent.parent / "data" / "scraped"
    all_items = []

    for json_file in data_dir.glob("*_items.json"):
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            all_items.extend(data.get('items', []))

    return all_items


async def main():
    parser = argparse.ArgumentParser(description="Scrape clothing items from Zara and H&M")
    parser.add_argument("--brand", choices=["zara", "hm", "all"], default="all",
                        help="Which brand to scrape")
    parser.add_argument("--category", choices=["tops", "bottoms", "all"], default="all",
                        help="Which category to scrape")
    args = parser.parse_args()

    print("=" * 50)
    print("QuickEE Clothing Scraper")
    print("=" * 50)

    if args.brand in ["zara", "all"]:
        print("\n[1/2] Scraping Zara...")
        zara = ZaraScraper()
        zara_data = await zara.scrape_all()
        print(f"   -> {zara_data.total_items} items")

    if args.brand in ["hm", "all"]:
        print("\n[2/2] Scraping H&M...")
        hnm = HnMScraper()
        hnm_data = await hnm.scrape_all()
        print(f"   -> {hnm_data.total_items} items")

    if args.brand == "all":
        all_items = load_existing_data()
        print(f"\n{'=' * 50}")
        print(f"Total items scraped: {len(all_items)}")
        print(f"Data saved to: data/scraped/")
        print("=" * 50)

    print("\nScraping complete!")


if __name__ == "__main__":
    asyncio.run(main())
