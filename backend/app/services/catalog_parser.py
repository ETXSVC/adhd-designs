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
        "images": raw.get("images", []),
    }


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
