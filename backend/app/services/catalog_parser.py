"""Turns raw Printify catalog JSON into the shapes the rest of the app uses.

Kept separate from the routers because this is the layer most likely to need
a fix if Printify changes field names — the DB always keeps the raw payload,
so a parsing fix here doesn't require a re-sync.
"""


def blueprint_summary(raw: dict) -> dict:
    return {
        "printify_id": raw["id"],
        "title": raw.get("title", ""),
        "brand": raw.get("brand", ""),
        "model": raw.get("model", ""),
        "category": guess_category(raw.get("title", "")),
        "images": raw.get("images", []),
    }


# Printify's `/catalog/blueprints.json` doesn't return a category/taxonomy
# field -- this list is the full flat catalog. `guess_category` buckets
# blueprints by matching keywords against the title text instead, since
# titles consistently name the product type (e.g. "11oz Accent Mug",
# "Unisex Heavy Cotton Tee"). It's a heuristic, not an authoritative
# taxonomy: order matters (more specific rules first, e.g. hoodies/
# sweatshirts before the generic shirts bucket, since "sweatshirt" also
# contains "shirt"), and anything that matches nothing falls into "Other".
CATEGORY_RULES: list[tuple[str, list[str]]] = [
    ("Hoodies & Sweatshirts", ["hoodie", "sweatshirt", "sweater", "crewneck", "fleece"]),
    (
        "Mugs & Drinkware",
        [
            "mug", "tumbler", "wine glass", "water bottle", "beer stein", "flask", "pint glass", "cup",
            "insulated bottle", "can cooler", "beverage holder", "can glass", "shot glass",
        ],
    ),
    (
        "Cases & Covers",
        ["phone case", "iphone", "samsung galaxy", "airpod", "laptop case", "laptop sleeve", "tablet case", "wallet case"],
    ),
    ("Bags", ["tote", "backpack", "fanny pack", "drawstring bag", " bag", "duffel", "pouch"]),
    (
        "Hats & Headwear",
        ["beanie", "bucket hat", "trucker", "flatbill", "snapback", "visor", "headband", "panel gramps", "-panel", " hat", " cap"],
    ),
    ("Posters & Wall Art", ["poster", "canvas", "wall art", "tapestry", "framed print", "wall decal", "acrylic print", "wall clock"]),
    ("Stickers & Decals", ["sticker", "decal", "magnet"]),
    (
        "Stationery & Office",
        ["notebook", "journal", "calendar", "planner", "greeting card", "sticky note", "mouse pad", "puzzle", "business card", "bookmark", "board book"],
    ),
    ("Jewelry & Accessories", ["necklace", "bracelet", "earring", "keychain", "engraved ring"]),
    (
        "Home & Living",
        [
            "pillow", "blanket", "towel", "rug", "doormat", "cutting board", "ornament", "candle", "coaster",
            "bath mat", "serving tray", "acrylic sign", "table sign", "bottle opener", "throw", "vase",
        ],
    ),
    ("Outerwear & Workwear", ["jacket", "vest", "jersey"]),
    ("Car Accessories", ["car mat", "car floor mat", "air freshener"]),
    ("Baby & Kids", ["baby", "onesie", "bodysuit", "toddler", "bib"]),
    ("Face Masks", ["face mask"]),
    ("Socks", ["sock"]),
    ("Dresses & Skirts", ["dress", "skirt"]),
    ("Bottoms & Loungewear", ["shorts", "sweatpants", "leggings", "pajama", "joggers"]),
    ("Pet Products", ["pet bandana", "dog bandana", "pet bowl"]),
    ("T-Shirts & Tops", ["tee", "t-shirt", "tank top", "shirt", "top", "polo"]),
]


def guess_category(title: str) -> str:
    lowered = f" {title.lower()} "
    for category, keywords in CATEGORY_RULES:
        if any(keyword in lowered for keyword in keywords):
            return category
    return "Other"


def print_provider_summary(raw: dict) -> dict:
    return {"printify_id": raw["id"], "title": raw.get("title", "")}


def variant_catalog_summary(raw: dict) -> dict:
    """`raw` is the /variants.json response: {id, title, variants: [...]}.
    Each variant carries its own `placeholders` (print areas in px) because
    different sizes can have different print areas. We surface variants
    flat, and a deduplicated list of print-area positions/sizes for the UI
    (picking the largest instance of each position, since that's the safest
    upper bound to preview against)."""

    variants = []
    print_areas: dict[str, dict] = {}

    for v in raw.get("variants", []):
        options = v.get("options", {})
        price_cents = v.get("cost")
        variants.append(
            {
                "id": v["id"],
                "title": v.get("title", ""),
                "price_cents": price_cents,
                "is_available": v.get("is_available", True),
                "options": options if isinstance(options, dict) else {},
            }
        )
        for ph in v.get("placeholders", []):
            position = ph.get("position")
            width = ph.get("width")
            height = ph.get("height")
            if not position or not width or not height:
                continue
            existing = print_areas.get(position)
            if not existing or width * height > existing["width_px"] * existing["height_px"]:
                print_areas[position] = {"position": position, "width_px": width, "height_px": height}

    return {"variants": variants, "print_areas": list(print_areas.values())}


def placeholders_for_variant(raw: dict, variant_id: int) -> list[dict]:
    """Print areas (position + exact px dims) for one specific variant, used
    when actually resizing artwork for a product being created."""

    for v in raw.get("variants", []):
        if v.get("id") == variant_id:
            return [ph for ph in v.get("placeholders", []) if ph.get("position") and ph.get("width") and ph.get("height")]
    return []
