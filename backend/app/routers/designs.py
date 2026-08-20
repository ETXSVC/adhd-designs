import uuid
from pathlib import Path

import anthropic
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Design
from app.schemas import DesignMetadataUpdate, DesignOut
from app.services.ai_metadata import generate_design_metadata
from app.services.image_processing import read_dimensions

router = APIRouter(prefix="/api/designs", tags=["designs"])

ALLOWED_CONTENT_TYPES = {"image/png", "image/jpeg", "image/webp"}
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


def _design_url(design: Design) -> str:
    return f"/uploads/{design.stored_filename}"


def _to_out(design: Design) -> DesignOut:
    return DesignOut(
        id=design.id,
        original_filename=design.original_filename,
        width=design.width,
        height=design.height,
        url=_design_url(design),
        ai_title=design.ai_title,
        ai_description=design.ai_description,
        ai_tags=design.ai_tags or [],
        created_at=design.created_at,
    )


@router.post("/upload", response_model=DesignOut)
async def upload_design(file: UploadFile, db: Session = Depends(get_db)) -> DesignOut:
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {file.content_type}")

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="File too large (25MB max)")

    try:
        width, height = read_dimensions(content)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Could not read image file") from exc

    settings = get_settings()
    extension = Path(file.filename or "").suffix or ".png"
    stored_filename = f"{uuid.uuid4().hex}{extension}"
    (settings.upload_path / stored_filename).write_bytes(content)

    design = Design(
        original_filename=file.filename or stored_filename,
        stored_filename=stored_filename,
        content_type=file.content_type,
        width=width,
        height=height,
    )
    db.add(design)
    db.commit()
    db.refresh(design)
    return _to_out(design)


@router.get("", response_model=list[DesignOut])
def list_designs(db: Session = Depends(get_db)) -> list[DesignOut]:
    rows = db.scalars(select(Design).order_by(Design.created_at.desc())).all()
    return [_to_out(d) for d in rows]


@router.get("/{design_id}", response_model=DesignOut)
def get_design(design_id: int, db: Session = Depends(get_db)) -> DesignOut:
    design = db.get(Design, design_id)
    if not design:
        raise HTTPException(status_code=404, detail="Design not found")
    return _to_out(design)


@router.post("/{design_id}/ai-metadata", response_model=DesignOut)
def generate_design_ai_metadata(design_id: int, db: Session = Depends(get_db)) -> DesignOut:
    design = db.get(Design, design_id)
    if not design:
        raise HTTPException(status_code=404, detail="Design not found")

    settings = get_settings()
    design_path = settings.upload_path / design.stored_filename
    if not design_path.exists():
        raise HTTPException(status_code=404, detail="Design file missing on disk")

    try:
        metadata = generate_design_metadata(design_path.read_bytes(), design.content_type)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except anthropic.APIStatusError as exc:
        raise HTTPException(status_code=502, detail=f"Anthropic API error: {exc.message}") from exc

    design.ai_title = metadata.title
    design.ai_description = metadata.description
    design.ai_tags = metadata.tags
    db.commit()
    db.refresh(design)
    return _to_out(design)


@router.patch("/{design_id}", response_model=DesignOut)
def update_design_metadata(design_id: int, payload: DesignMetadataUpdate, db: Session = Depends(get_db)) -> DesignOut:
    """Saves user edits to the AI-suggested (or manually typed) title/
    description/tags -- lets the generated copy be corrected before it's
    relied on elsewhere, rather than being stuck with whatever the model
    first produced."""

    design = db.get(Design, design_id)
    if not design:
        raise HTTPException(status_code=404, detail="Design not found")

    design.ai_title = payload.ai_title
    design.ai_description = payload.ai_description
    design.ai_tags = payload.ai_tags
    db.commit()
    db.refresh(design)
    return _to_out(design)
