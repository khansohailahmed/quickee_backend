"""
Playwright-based scraper for Zara India and H&M India.

Anti-detection measures used:
  • Random user-agent rotation
  • Realistic viewport (1920×1080)
  • Accept-Language / Accept headers to mimic a real browser
  • Abort heavy non-essential resources (fonts, analytics) for speed
  • Random human-like delays between requests
  • Slow-type / scroll behaviour to avoid bot fingerprinting
  • wait_for_selector before querying product cards

Fallback: if a site returns 0 items (blocked / DOM changed), generate_mock_data()
creates realistic synthetic items so the downstream pipeline always has data.
"""

import asyncio
import json
import random
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from config.settings import get_settings
from scraper.item_schema import ClothingItem, ScrapedData

# ---------------------------------------------------------------------------
# Blocked resource types – abort these to speed up scraping and reduce
# fingerprint surface (analytics pixels, web fonts, etc.)
# ---------------------------------------------------------------------------
_BLOCKED_RESOURCE_TYPES = {"font", "media"}
_BLOCKED_URL_PATTERNS = [
    "google-analytics.com",
    "googletagmanager.com",
    "hotjar.com",
    "facebook.net",
    "doubleclick.net",
]


def _should_block(url: str, resource_type: str) -> bool:
    if resource_type in _BLOCKED_RESOURCE_TYPES:
        return True
    return any(p in url for p in _BLOCKED_URL_PATTERNS)


# ---------------------------------------------------------------------------
# Base scraper
# ---------------------------------------------------------------------------

class BaseClothingScraper:
    def __init__(self, brand: str):
        self.brand = brand
        self.settings = get_settings()
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None

    async def setup(self):
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        ua = random.choice(self.settings.scraper_user_agents)
        self.context = await self.browser.new_context(
            user_agent=ua,
            viewport={"width": 1920, "height": 1080},
            locale="en-IN",
            extra_http_headers={
                "Accept-Language": "en-IN,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "DNT": "1",
            },
        )

        # Stealth: override navigator.webdriver flag
        await self.context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        # Abort unnecessary resources
        async def handle_route(route, request):
            if _should_block(request.url, request.resource_type):
                await route.abort()
            else:
                await route.continue_()

        await self.context.route("**/*", handle_route)

    async def teardown(self):
        if self.browser:
            await self.browser.close()

    async def random_delay(self, min_sec: float = 1.0, max_sec: float = 3.0):
        await asyncio.sleep(random.uniform(min_sec, max_sec))

    async def scroll_page(self, page: Page, scrolls: int = 5):
        """Gradually scroll to trigger lazy-loaded images."""
        for _ in range(scrolls):
            await page.evaluate("window.scrollBy(0, window.innerHeight * 0.8)")
            await asyncio.sleep(random.uniform(0.4, 0.9))
        # Scroll back to top
        await page.evaluate("window.scrollTo(0, 0)")
        await asyncio.sleep(0.5)

    def extract_price(self, price_text: str) -> float:
        """Extract the first numeric value from a price string."""
        numbers = re.findall(r"[\d,]+\.?\d*", price_text.replace(",", ""))
        if numbers:
            try:
                return float(numbers[0])
            except ValueError:
                pass
        return 0.0

    async def fetch_page(self, url: str) -> Optional[Page]:
        page = await self.context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=45_000)
            await self.random_delay()
            return page
        except Exception as e:
            print(f"[{self.brand}] Error fetching {url}: {e}")
            await page.close()
            return None

    async def save_items(self, items: list[ClothingItem], filename: str):
        data = ScrapedData(source=self.brand, items=items)
        out_dir = Path("data/scraped")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / filename
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data.model_dump(exclude={"scraped_at"}), f, indent=2, ensure_ascii=False)
        print(f"[{self.brand}] Saved {len(items)} items → {out_path}")


# ---------------------------------------------------------------------------
# Zara India scraper
# ---------------------------------------------------------------------------

class ZaraScraper(BaseClothingScraper):
    BASE_URL = "https://www.zara.com/in/en"

    # Zara uses React + a category-ID URL scheme.
    # These IDs are stable; verify at zara.com/in/en if the site changes.
    TOPS_URL = f"{BASE_URL}/woman-t-shirts-l1037.html"
    BOTTOMS_URL = f"{BASE_URL}/woman-trousers-l1056.html"

    def __init__(self):
        super().__init__("Zara")

    async def _scrape_category(
        self, url: str, category: str, id_prefix: str
    ) -> list[ClothingItem]:
        items: list[ClothingItem] = []
        page = await self.fetch_page(url)
        if not page:
            return items

        try:
            # Wait for the product grid to be rendered by React
            await page.wait_for_selector(
                "li.product-grid-product, li[class*='product-grid-product']",
                timeout=15_000,
            )
        except Exception:
            print(f"[Zara] Timeout waiting for product grid on {url}")
            await page.close()
            return items

        await self.scroll_page(page, scrolls=6)

        try:
            cards = await page.query_selector_all(
                "li.product-grid-product, li[class*='product-grid-product']"
            )
            print(f"[Zara] Found {len(cards)} cards for {category}")

            for idx, card in enumerate(cards[: self.settings.max_items_per_category]):
                try:
                    name_el = await card.query_selector(
                        "[class*='product-grid-product-info__name'],"
                        "[class*='product-grid-product-info'] a"
                    )
                    price_el = await card.query_selector(
                        "[class*='price__amount'],"
                        "[class*='money-amount'],"
                        "[class*='price-current']"
                    )
                    img_el = await card.query_selector("img")
                    link_el = await card.query_selector("a[href]")

                    name = (await name_el.inner_text()).strip() if name_el else f"Zara {category.title()} {idx+1}"
                    price_text = (await price_el.inner_text()).strip() if price_el else "₹0"
                    img_url = (await img_el.get_attribute("src") or "") if img_el else ""
                    href = (await link_el.get_attribute("href") or "") if link_el else ""
                    product_url = href if href.startswith("http") else f"{self.BASE_URL}{href}"

                    # Derive colour from name heuristics
                    color = self._guess_color(name)

                    subcategory = self._guess_subcategory(name, category)

                    item = ClothingItem(
                        item_id=f"zara_{id_prefix}_{idx+1:03d}",
                        name=name,
                        brand="Zara",
                        price_inr=self.extract_price(price_text),
                        category=category,
                        subcategory=subcategory,
                        color=color,
                        description=name,
                        image_url=img_url,
                        product_url=product_url,
                    )
                    items.append(item)
                except Exception as e:
                    print(f"[Zara] Card parse error {idx}: {e}")
                    continue
        except Exception as e:
            print(f"[Zara] Grid scrape error: {e}")

        await page.close()
        return items

    def _guess_color(self, name: str) -> str:
        name_lower = name.lower()
        for color in ["white", "black", "navy", "blue", "grey", "gray", "green",
                      "red", "pink", "beige", "cream", "brown", "yellow", "orange"]:
            if color in name_lower:
                return color
        return "multicolor"

    def _guess_subcategory(self, name: str, category: str) -> str:
        name_lower = name.lower()
        if category == "tops":
            if "shirt" in name_lower and "t-" not in name_lower:
                return "shirt"
            if "polo" in name_lower:
                return "polo"
            return "t-shirt"
        if category == "bottoms":
            if "chino" in name_lower:
                return "chinos"
            if "short" in name_lower:
                return "shorts"
            if "jean" in name_lower or "denim" in name_lower:
                return "jeans"
            return "trousers"
        return "unknown"

    async def scrape_tops(self) -> list[ClothingItem]:
        return await self._scrape_category(self.TOPS_URL, "tops", "top")

    async def scrape_bottoms(self) -> list[ClothingItem]:
        return await self._scrape_category(self.BOTTOMS_URL, "bottoms", "bottom")

    async def scrape_all(self) -> ScrapedData:
        await self.setup()
        try:
            tops = await self.scrape_tops()
            bottoms = await self.scrape_bottoms()

            # Fallback: generate mock data if scraping yielded nothing
            if len(tops) < 5:
                print("[Zara] Using mock tops (scraper returned insufficient results)")
                tops = generate_mock_items("Zara", "tops", 50)
            if len(bottoms) < 5:
                print("[Zara] Using mock bottoms (scraper returned insufficient results)")
                bottoms = generate_mock_items("Zara", "bottoms", 50)

            all_items = tops + bottoms
            await self.save_items(all_items, "zara_items.json")
            return ScrapedData(source=self.brand, items=all_items)
        finally:
            await self.teardown()


# ---------------------------------------------------------------------------
# H&M India scraper
# ---------------------------------------------------------------------------

class HnMScraper(BaseClothingScraper):
    # FIX: correct base URL is www2.hm.com, not www.hm.com
    BASE_URL = "https://www2.hm.com/en_in"
    TOPS_URL = f"{BASE_URL}/women/products/tops.html"
    BOTTOMS_URL = f"{BASE_URL}/women/products/trousers.html"

    def __init__(self):
        super().__init__("H&M")

    async def _scrape_category(
        self, url: str, category: str, id_prefix: str
    ) -> list[ClothingItem]:
        items: list[ClothingItem] = []
        page = await self.fetch_page(url)
        if not page:
            return items

        try:
            await page.wait_for_selector(
                "li.product-item, article.product-item, [class*='product-item']",
                timeout=15_000,
            )
        except Exception:
            print(f"[H&M] Timeout waiting for product grid on {url}")
            await page.close()
            return items

        await self.scroll_page(page, scrolls=6)

        try:
            cards = await page.query_selector_all(
                "li.product-item, article.product-item, [class*='product-item']:not([class*='product-item-image'])"
            )
            print(f"[H&M] Found {len(cards)} cards for {category}")

            for idx, card in enumerate(cards[: self.settings.max_items_per_category]):
                try:
                    name_el = await card.query_selector(
                        "[class*='item-heading'], [class*='product-title'], h2, h3, .item-link"
                    )
                    price_el = await card.query_selector(
                        "[class*='item-price'], [class*='price'], [data-value]"
                    )
                    img_el = await card.query_selector("img[src]")
                    link_el = await card.query_selector("a[href]")

                    name = (await name_el.inner_text()).strip() if name_el else f"H&M {category.title()} {idx+1}"
                    price_text = (await price_el.inner_text()).strip() if price_el else "₹0"
                    img_url = (await img_el.get_attribute("src") or "") if img_el else ""
                    href = (await link_el.get_attribute("href") or "") if link_el else ""
                    product_url = href if href.startswith("http") else f"{self.BASE_URL}{href}"

                    color = self._guess_color(name)
                    subcategory = self._guess_subcategory(name, category)

                    item = ClothingItem(
                        item_id=f"hm_{id_prefix}_{idx+1:03d}",
                        name=name,
                        brand="H&M",
                        price_inr=self.extract_price(price_text),
                        category=category,
                        subcategory=subcategory,
                        color=color,
                        description=name,
                        image_url=img_url,
                        product_url=product_url,
                    )
                    items.append(item)
                except Exception as e:
                    print(f"[H&M] Card parse error {idx}: {e}")
                    continue
        except Exception as e:
            print(f"[H&M] Grid scrape error: {e}")

        await page.close()
        return items

    def _guess_color(self, name: str) -> str:
        name_lower = name.lower()
        for color in ["white", "black", "navy", "blue", "grey", "gray", "green",
                      "red", "pink", "beige", "cream", "brown", "yellow", "orange", "olive"]:
            if color in name_lower:
                return color
        return "multicolor"

    def _guess_subcategory(self, name: str, category: str) -> str:
        name_lower = name.lower()
        if category == "tops":
            if "shirt" in name_lower and "t-shirt" not in name_lower:
                return "shirt"
            if "polo" in name_lower:
                return "polo"
            return "t-shirt"
        if category == "bottoms":
            if "chino" in name_lower:
                return "chinos"
            if "short" in name_lower:
                return "shorts"
            if "jean" in name_lower or "denim" in name_lower:
                return "jeans"
            return "trousers"
        return "unknown"

    async def scrape_tops(self) -> list[ClothingItem]:
        return await self._scrape_category(self.TOPS_URL, "tops", "top")

    async def scrape_bottoms(self) -> list[ClothingItem]:
        return await self._scrape_category(self.BOTTOMS_URL, "bottoms", "bottom")

    async def scrape_all(self) -> ScrapedData:
        await self.setup()
        try:
            tops = await self.scrape_tops()
            bottoms = await self.scrape_bottoms()

            if len(tops) < 5:
                print("[H&M] Using mock tops")
                tops = generate_mock_items("H&M", "tops", 50)
            if len(bottoms) < 5:
                print("[H&M] Using mock bottoms")
                bottoms = generate_mock_items("H&M", "bottoms", 50)

            all_items = tops + bottoms
            await self.save_items(all_items, "hm_items.json")
            return ScrapedData(source=self.brand, items=all_items)
        finally:
            await self.teardown()


# ---------------------------------------------------------------------------
# Mock-data fallback
# Used when a site blocks the scraper or its DOM has changed.
# Produces semantically-rich items so RAG + LLM recommendations still work.
# ---------------------------------------------------------------------------

_TOPS_TEMPLATES = [
    ("Classic White Crew-Neck T-Shirt", "white", "t-shirt", 799),
    ("Navy Slim-Fit Polo Shirt", "navy", "polo", 1299),
    ("Black Graphic Print Tee", "black", "t-shirt", 999),
    ("Sage Green Linen Shirt", "green", "shirt", 2499),
    ("Striped Cotton Casual Shirt", "multicolor", "shirt", 1799),
    ("Olive Washed-Cotton Tee", "olive", "t-shirt", 899),
    ("Cream Textured Knit Polo", "cream", "polo", 1599),
    ("Cobalt Blue Linen-Blend Shirt", "blue", "shirt", 2799),
    ("Blush Pink Essential T-Shirt", "pink", "t-shirt", 699),
    ("Beige Oversized Organic Cotton Tee", "beige", "t-shirt", 1099),
]

_BOTTOMS_TEMPLATES = [
    ("Dark Navy Slim Chinos", "navy", "chinos", 2499),
    ("Beige Tailored Trousers", "beige", "trousers", 3299),
    ("Black Slim-Fit Jeans", "black", "jeans", 2999),
    ("Khaki Cargo Shorts", "khaki", "shorts", 1799),
    ("Light Blue Straight-Leg Jeans", "blue", "jeans", 3499),
    ("Olive Linen Trousers", "olive", "trousers", 2999),
    ("Grey Slim Chinos", "grey", "chinos", 2299),
    ("Cream Wide-Leg Trousers", "cream", "trousers", 3799),
    ("Brown Corduroy Trousers", "brown", "trousers", 2799),
    ("White Cotton Bermuda Shorts", "white", "shorts", 1499),
]


def generate_mock_items(
    brand: str, category: str, count: int = 50
) -> list[ClothingItem]:
    """Generate synthetic clothing items for demo / fallback purposes."""
    templates = _TOPS_TEMPLATES if category == "tops" else _BOTTOMS_TEMPLATES
    brand_slug = brand.lower().replace("&", "and").replace(" ", "_")
    cat_slug = "top" if category == "tops" else "bottom"
    items = []
    for i in range(count):
        tpl = templates[i % len(templates)]
        name, color, subcat, base_price = tpl
        # Slight price variation per item
        price_variation = random.randint(-200, 500)
        price = max(499.0, base_price + price_variation)
        item = ClothingItem(
            item_id=f"{brand_slug}_{cat_slug}_{i+1:03d}",
            name=f"{brand} {name}",
            brand=brand,
            price_inr=float(price),
            category=category,
            subcategory=subcat,
            color=color,
            description=(
                f"Premium {color} {subcat} from {brand}. "
                f"Crafted for comfort and style, perfect for various occasions."
            ),
            image_url=f"https://placehold.co/400x500?text={brand}+{subcat}",
            product_url=f"https://www.{'zara' if brand=='Zara' else 'hm'}.com/in/en/placeholder-{i+1}",
        )
        items.append(item)
    return items


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def run_scraper():
    print("Starting Zara scraper...")
    zara = ZaraScraper()
    zara_data = await zara.scrape_all()
    print(f"Zara: {zara_data.total_items} items scraped/generated\n")

    print("Starting H&M scraper...")
    hnm = HnMScraper()
    hnm_data = await hnm.scrape_all()
    print(f"H&M: {hnm_data.total_items} items scraped/generated")

    return zara_data, hnm_data


if __name__ == "__main__":
    asyncio.run(run_scraper())
