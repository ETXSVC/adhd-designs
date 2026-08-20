import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


class Blueprint(Base):
    """A Printify product blueprint (e.g. 'Unisex Heavy Cotton Tee'). Cached from
    GET /catalog/blueprints.json. `raw` keeps the full Printify payload so new
    fields Printify adds don't require a migration to read."""

    __tablename__ = "blueprints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    printify_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    title: Mapped[str] = mapped_column(String, index=True)
    brand: Mapped[str] = mapped_column(String, default="")
    model: Mapped[str] = mapped_column(String, default="")
    category: Mapped[str] = mapped_column(String, default="", index=True)
    raw: Mapped[dict] = mapped_column(JSON)
    synced_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class PrintProvider(Base):
    """A print provider offering a given blueprint. Cached from
    GET /catalog/blueprints/{id}/print_providers.json."""

    __tablename__ = "print_providers"
    __table_args__ = (UniqueConstraint("blueprint_printify_id", "printify_id", name="uq_provider_per_blueprint"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    printify_id: Mapped[int] = mapped_column(Integer, index=True)
    blueprint_printify_id: Mapped[int] = mapped_column(Integer, index=True)
    title: Mapped[str] = mapped_column(String)
    raw: Mapped[dict] = mapped_column(JSON)
    synced_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class VariantCatalog(Base):
    """Cached response of GET /catalog/blueprints/{id}/print_providers/{id}/variants.json
    for one blueprint+provider pair. Holds the variants list AND the print-area
    placeholders (position name -> pixel width/height) that everything downstream
    depends on. Stored as raw JSON on purpose: this is the shape most likely to
    drift with a Printify API version bump, and re-syncing just overwrites it."""

    __tablename__ = "variant_catalogs"
    __table_args__ = (
        UniqueConstraint("blueprint_printify_id", "print_provider_printify_id", name="uq_variant_catalog"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    blueprint_printify_id: Mapped[int] = mapped_column(Integer, index=True)
    print_provider_printify_id: Mapped[int] = mapped_column(Integer, index=True)
    raw: Mapped[dict] = mapped_column(JSON)
    synced_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Design(Base):
    """An uploaded piece of artwork, stored on local disk."""

    __tablename__ = "designs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    original_filename: Mapped[str] = mapped_column(String)
    stored_filename: Mapped[str] = mapped_column(String, unique=True)
    content_type: Mapped[str] = mapped_column(String)
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    products: Mapped[list["Product"]] = relationship(back_populates="design")


class Product(Base):
    """A draft product we've asked Printify to create from a design + blueprint
    + print provider + chosen variants. `status` tracks our local flow, `raw`
    holds Printify's product response once created."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String)
    design_id: Mapped[int] = mapped_column(ForeignKey("designs.id"))
    blueprint_printify_id: Mapped[int] = mapped_column(Integer)
    print_provider_printify_id: Mapped[int] = mapped_column(Integer)
    printify_product_id: Mapped[str] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending")  # pending|created|failed
    error: Mapped[str] = mapped_column(String, nullable=True)
    raw: Mapped[dict] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    design: Mapped["Design"] = relationship(back_populates="products")
