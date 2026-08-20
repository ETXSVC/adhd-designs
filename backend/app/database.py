from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_light_migrations() -> None:
    """`Base.metadata.create_all` only creates tables that don't exist yet --
    it won't add a column to a table that's already there. There's no
    Alembic in this project (SQLite, single small app), so new columns get a
    one-line guarded ALTER TABLE here instead of a migration framework."""

    inspector = inspect(engine)
    if "blueprints" not in inspector.get_table_names():
        return
    existing_columns = {col["name"] for col in inspector.get_columns("blueprints")}
    if "category" not in existing_columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE blueprints ADD COLUMN category VARCHAR DEFAULT ''"))
