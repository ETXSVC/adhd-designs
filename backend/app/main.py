from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import Base, engine
from app.routers import catalog, designs, products

settings = get_settings()

Base.metadata.create_all(bind=engine)

app = FastAPI(title="adhd-designs API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(catalog.router)
app.include_router(designs.router)
app.include_router(products.router)

app.mount("/uploads", StaticFiles(directory=str(settings.upload_path)), name="uploads")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
