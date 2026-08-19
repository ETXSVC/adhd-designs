from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Design, Product
from app.schemas import Placement, ProductCreateRequest, ProductOut
from app.services.catalog_parser import placeholders_for_variant
from app.services.image_processing import fit_to_print_area
from app.services.printify_client import PrintifyClient, PrintifyError

router = APIRouter(prefix="/api/products", tags=["products"])


def _default_placements(raw_variant_catalog: dict, reference_variant_id: int) -> list[Placement]:
    """No placement given -> center the design, full scale, on the 'front'
    print area if the variant has one, otherwise its first available print
    area. Drag/scale/rotate positioning is a frontend feature to add later;
    the backend already accepts explicit x/y/scale/angle per position via
    ProductCreateRequest.placements."""

    areas = placeholders_for_variant(raw_variant_catalog, reference_variant_id)
    if not areas:
        raise HTTPException(status_code=400, detail="Selected variant has no print areas for this print provider")
    front = next((a for a in areas if a.get("position") == "front"), areas[0])
    return [Placement(position=front["position"])]


@router.post("", response_model=ProductOut, status_code=201)
def create_product(payload: ProductCreateRequest, db: Session = Depends(get_db)) -> ProductOut:
    design = db.get(Design, payload.design_id)
    if not design:
        raise HTTPException(status_code=404, detail="Design not found")
    if not payload.variant_ids:
        raise HTTPException(status_code=400, detail="At least one variant_id is required")

    settings = get_settings()
    design_path = settings.upload_path / design.stored_filename
    if not design_path.exists():
        raise HTTPException(status_code=404, detail="Design file missing on disk")
    source_bytes = Path(design_path).read_bytes()

    try:
        with PrintifyClient() as client:
            variant_catalog = client.get_variants(payload.blueprint_id, payload.print_provider_id)

            reference_variant_id = payload.variant_ids[0]
            placements = payload.placements or _default_placements(variant_catalog, reference_variant_id)
            area_by_position = {
                a["position"]: a for a in placeholders_for_variant(variant_catalog, reference_variant_id)
            }

            placeholders = []
            for placement in placements:
                area = area_by_position.get(placement.position)
                if not area:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Print area '{placement.position}' is not available for the selected variant",
                    )
                resized = fit_to_print_area(source_bytes, area["width"], area["height"])
                uploaded = client.upload_image(f"{design.original_filename}-{placement.position}.png", resized)
                placeholders.append(
                    {
                        "position": placement.position,
                        "images": [
                            {
                                "id": uploaded["id"],
                                "x": placement.x,
                                "y": placement.y,
                                "scale": placement.scale,
                                "angle": placement.angle,
                            }
                        ],
                    }
                )

            product_payload = {
                "title": payload.title,
                "description": payload.description,
                "blueprint_id": payload.blueprint_id,
                "print_provider_id": payload.print_provider_id,
                "variants": [
                    {"id": vid, "price": payload.price_cents, "is_enabled": True} for vid in payload.variant_ids
                ],
                "print_areas": [{"variant_ids": payload.variant_ids, "placeholders": placeholders}],
            }
            response = client.create_product(product_payload)
    except HTTPException:
        raise
    except (PrintifyError, RuntimeError) as exc:
        error_message = exc.body if isinstance(exc, PrintifyError) else str(exc)
        product = Product(
            title=payload.title,
            design_id=design.id,
            blueprint_printify_id=payload.blueprint_id,
            print_provider_printify_id=payload.print_provider_id,
            status="failed",
            error=error_message,
        )
        db.add(product)
        db.commit()
        raise HTTPException(status_code=502, detail=f"Printify API error: {error_message}") from exc

    product = Product(
        title=payload.title,
        design_id=design.id,
        blueprint_printify_id=payload.blueprint_id,
        print_provider_printify_id=payload.print_provider_id,
        printify_product_id=str(response.get("id")),
        status="created",
        raw=response,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return ProductOut.model_validate(product)


@router.get("", response_model=list[ProductOut])
def list_products(db: Session = Depends(get_db)) -> list[ProductOut]:
    rows = db.scalars(select(Product).order_by(Product.created_at.desc())).all()
    return [ProductOut.model_validate(p) for p in rows]


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db)) -> ProductOut:
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return ProductOut.model_validate(product)
