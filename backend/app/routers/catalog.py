from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Blueprint, PrintProvider, VariantCatalog
from app.schemas import BlueprintOut, CategoryOut, PrintProviderOut, VariantCatalogOut
from app.services.catalog_parser import blueprint_summary, print_provider_summary, variant_catalog_summary
from app.services.printify_client import PrintifyClient, PrintifyError

router = APIRouter(prefix="/api/catalog", tags=["catalog"])


def _printify_error(exc: PrintifyError) -> HTTPException:
    return HTTPException(status_code=502, detail=f"Printify API error: {exc.body}")


@router.post("/sync")
def sync_catalog(db: Session = Depends(get_db)) -> dict:
    """Pulls the full blueprint list from Printify and upserts it. Print
    providers and variants are synced lazily, per-blueprint, when browsed --
    there are hundreds of blueprints and syncing every provider/variant
    combination up front would be thousands of API calls."""

    try:
        with PrintifyClient() as client:
            blueprints = client.list_blueprints()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PrintifyError as exc:
        raise _printify_error(exc) from exc

    synced = 0
    for raw in blueprints:
        summary = blueprint_summary(raw)
        existing = db.scalar(select(Blueprint).where(Blueprint.printify_id == summary["printify_id"]))
        if existing:
            existing.title = summary["title"]
            existing.brand = summary["brand"]
            existing.model = summary["model"]
            existing.category = summary["category"]
            existing.raw = raw
        else:
            db.add(
                Blueprint(
                    printify_id=summary["printify_id"],
                    title=summary["title"],
                    brand=summary["brand"],
                    model=summary["model"],
                    category=summary["category"],
                    raw=raw,
                )
            )
        synced += 1
    db.commit()
    return {"synced": synced}


@router.get("/blueprints", response_model=list[BlueprintOut])
def list_blueprints(
    q: str | None = Query(default=None, description="Case-insensitive title search"),
    category: str | None = Query(default=None, description="Exact match against a category from GET /api/catalog/categories"),
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> list[BlueprintOut]:
    stmt = select(Blueprint).order_by(Blueprint.title)
    if q:
        stmt = stmt.where(Blueprint.title.ilike(f"%{q}%"))
    if category:
        stmt = stmt.where(Blueprint.category == category)
    stmt = stmt.limit(limit).offset(offset)
    rows = db.scalars(stmt).all()
    if not rows and not q and not category:
        raise HTTPException(status_code=404, detail="Catalog is empty. Call POST /api/catalog/sync first.")
    return [BlueprintOut(**blueprint_summary(row.raw)) for row in rows]


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db)) -> list[CategoryOut]:
    """Categories are derived at sync time from blueprint titles (see
    `guess_category` in catalog_parser.py) since Printify's blueprint list
    doesn't carry a taxonomy field of its own."""

    rows = db.execute(
        select(Blueprint.category, func.count()).group_by(Blueprint.category).order_by(Blueprint.category)
    ).all()
    return [CategoryOut(category=category, count=count) for category, count in rows]


@router.get("/blueprints/{blueprint_id}/print-providers", response_model=list[PrintProviderOut])
def list_print_providers(blueprint_id: int, db: Session = Depends(get_db)) -> list[PrintProviderOut]:
    try:
        with PrintifyClient() as client:
            providers = client.list_print_providers(blueprint_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PrintifyError as exc:
        raise _printify_error(exc) from exc

    for raw in providers:
        summary = print_provider_summary(raw)
        existing = db.scalar(
            select(PrintProvider).where(
                PrintProvider.blueprint_printify_id == blueprint_id,
                PrintProvider.printify_id == summary["printify_id"],
            )
        )
        if existing:
            existing.title = summary["title"]
            existing.raw = raw
        else:
            db.add(
                PrintProvider(
                    printify_id=summary["printify_id"],
                    blueprint_printify_id=blueprint_id,
                    title=summary["title"],
                    raw=raw,
                )
            )
    db.commit()
    return [PrintProviderOut(**print_provider_summary(raw)) for raw in providers]


@router.get("/blueprints/{blueprint_id}/print-providers/{provider_id}/variants", response_model=VariantCatalogOut)
def get_variant_catalog(blueprint_id: int, provider_id: int, db: Session = Depends(get_db)) -> VariantCatalogOut:
    try:
        with PrintifyClient() as client:
            raw = client.get_variants(blueprint_id, provider_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PrintifyError as exc:
        raise _printify_error(exc) from exc

    existing = db.scalar(
        select(VariantCatalog).where(
            VariantCatalog.blueprint_printify_id == blueprint_id,
            VariantCatalog.print_provider_printify_id == provider_id,
        )
    )
    if existing:
        existing.raw = raw
    else:
        db.add(
            VariantCatalog(
                blueprint_printify_id=blueprint_id,
                print_provider_printify_id=provider_id,
                raw=raw,
            )
        )
    db.commit()

    return VariantCatalogOut(**variant_catalog_summary(raw))
