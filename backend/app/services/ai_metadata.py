"""Generates AI-suggested title/description/tags for a design or a product
listing, via the Anthropic API. Kept as a thin wrapper so the model and
prompt can change without touching the routers that call it.

Printify's product-create/update API doesn't accept custom tags (tags in
its schema are read-only/derived from the catalog) -- generated tags are
still returned and stored locally for the user's own reference, but only
`title`/`description` ever get sent to Printify."""

import base64

import anthropic
from pydantic import BaseModel, Field

from app.config import get_settings


class GeneratedMetadata(BaseModel):
    title: str = Field(description="A short, punchy, SEO-friendly title, under 70 characters")
    description: str = Field(description="A 4-6 sentence SEO optimized marketing description")
    tags: list[str] = Field(description="10-14 relevant lowercase SEO optimized search tags/keywords, no leading '#'")


def _client() -> anthropic.Anthropic:
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def _image_block(image_bytes: bytes, media_type: str) -> dict:
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": media_type,
            "data": base64.standard_b64encode(image_bytes).decode("ascii"),
        },
    }


def _generate(image_bytes: bytes, media_type: str, instruction: str) -> GeneratedMetadata:
    settings = get_settings()
    response = _client().messages.parse(
        model=settings.anthropic_model,
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": [_image_block(image_bytes, media_type), {"type": "text", "text": instruction}],
            }
        ],
        output_format=GeneratedMetadata,
    )
    return response.parsed_output


def generate_design_metadata(image_bytes: bytes, media_type: str) -> GeneratedMetadata:
    """Metadata describing the artwork itself, independent of any product
    it might end up printed on -- for organizing/searching an uploaded
    design library."""

    return _generate(
        image_bytes,
        media_type,
        "Look at this artwork and write metadata describing the design itself (not any "
        "product it might be printed on): a short punchy title, a 2-4 sentence description "
        "of its style/subject/mood, and 5-10 lowercase search tags.",
    )


def generate_product_metadata(image_bytes: bytes, media_type: str, blueprint_title: str) -> GeneratedMetadata:
    """Metadata for an e-commerce listing of this artwork printed on the
    given Printify blueprint (e.g. 'Unisex Heavy Cotton Tee')."""

    return _generate(
        image_bytes,
        media_type,
        f"This artwork is being printed on a '{blueprint_title}'. Write e-commerce listing "
        "metadata for the resulting product: an SEO-friendly title under 70 characters that "
        "names the product type, a 2-4 sentence marketing description, and 5-10 lowercase "
        "search tags/keywords a buyer might search for.",
    )
