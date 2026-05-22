import json
import random
from pathlib import Path
from datetime import datetime

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


def generate_mock_items(brand, category, count=50):
    templates = _TOPS_TEMPLATES if category == "tops" else _BOTTOMS_TEMPLATES
    brand_slug = brand.lower().replace("&", "and").replace(" ", "_")
    cat_slug = "top" if category == "tops" else "bottom"
    domain = "zara" if brand == "Zara" else "hm"
    items = []
    for i in range(count):
        tpl = templates[i % len(templates)]
        name, color, subcat, base_price = tpl
        price_variation = random.randint(-200, 500)
        price = max(499.0, base_price + price_variation)
        item = {
            "item_id": f"{brand_slug}_{cat_slug}_{i+1:03d}",
            "name": f"{brand} {name}",
            "brand": brand,
            "price_inr": float(price),
            "category": category,
            "subcategory": subcat,
            "color": color,
            "description": f"Premium {color} {subcat} from {brand}. Crafted for comfort and style, perfect for various occasions.",
            "image_url": f"https://placehold.co/400x500?text={brand}+{subcat}",
            "product_url": f"https://www.{domain}.com/in/en/placeholder-{i+1}",
            "scraped_at": datetime.utcnow().isoformat(),
        }
        items.append(item)
    return items


def save_items(items, filename):
    data = {
        "source": items[0]["brand"] if items else "unknown",
        "items": items,
        "total_items": len(items),
    }
    out_dir = Path("data/scraped")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / filename
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(items)} items to {out_path}")


if __name__ == "__main__":
    zara_tops = generate_mock_items("Zara", "tops", 50)
    zara_bottoms = generate_mock_items("Zara", "bottoms", 50)
    save_items(zara_tops + zara_bottoms, "zara_items.json")

    hm_tops = generate_mock_items("H&M", "tops", 50)
    hm_bottoms = generate_mock_items("H&M", "bottoms", 50)
    save_items(hm_tops + hm_bottoms, "hm_items.json")

    print("Mock data generation complete!")