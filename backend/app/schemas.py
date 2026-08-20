import datetime

from pydantic import BaseModel, Field, field_validator


class BlueprintOut(BaseModel):
    printify_id: int
    title: str
    brand: str
    model: str
    category: str = ""
    images: list[str] = Field(default_factory=list)

    model_config = {"protected_namespaces": ()}


class CategoryOut(BaseModel):
    category: str
    count: int


class PrintProviderOut(BaseModel):
    printify_id: int
    title: str


class VariantOut(BaseModel):
    id: int
    title: str
    price_cents: int | None = None
    is_available: bool = True
    options: dict = Field(default_factory=dict)


class PrintAreaOut(BaseModel):
    position: str
    width_px: int
    height_px: int


class VariantCatalogOut(BaseModel):
    variants: list[VariantOut]
    print_areas: list[PrintAreaOut]


class DesignOut(BaseModel):
    id: int
    original_filename: str
    width: int
    height: int
    url: str
    ai_title: str | None = None
    ai_description: str | None = None
    ai_tags: list[str] = Field(default_factory=list)
    created_at: datetime.datetime

    model_config = {"from_attributes": True}

    # `ai_tags` is a nullable JSON column (NULL until AI metadata is
    # generated) but the API contract always returns a list, never null.
    _default_tags = field_validator("ai_tags", mode="before")(lambda v: v or [])


class DesignMetadataUpdate(BaseModel):
    """User edits to AI-suggested (or manually entered) design metadata --
    always writes the full set, no partial-patch semantics, since the
    frontend form always has a value (even '') for every field."""

    ai_title: str = ""
    ai_description: str = ""
    ai_tags: list[str] = Field(default_factory=list)


class AIMetadataOut(BaseModel):
    title: str
    description: str
    tags: list[str]


class ProductAIMetadataRequest(BaseModel):
    design_id: int
    blueprint_id: int


class Placement(BaseModel):
    position: str
    x: float = 0.5  # 0..1, fraction of print-area width, center point
    y: float = 0.5  # 0..1, fraction of print-area height, center point
    scale: float = 1.0
    angle: float = 0.0


class ProductCreateRequest(BaseModel):
    title: str
    design_id: int
    blueprint_id: int
    print_provider_id: int
    variant_ids: list[int]
    price_cents: int
    placements: list[Placement] | None = None
    description: str = ""
    # Printify doesn't accept custom tags on product create/update -- these
    # are stored locally for reference only (see Product.ai_tags).
    tags: list[str] = Field(default_factory=list)


class ProductOut(BaseModel):
    id: int
    title: str
    design_id: int
    blueprint_printify_id: int
    print_provider_printify_id: int
    printify_product_id: str | None
    status: str
    error: str | None
    ai_tags: list[str] = Field(default_factory=list)
    created_at: datetime.datetime

    model_config = {"from_attributes": True}
    _default_tags = field_validator("ai_tags", mode="before")(lambda v: v or [])
