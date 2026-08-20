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


# (table, column, DDL type) for every column added after the initial
# `create_all`. Append here -- never edit an already-shipped row -- when a
# new column is added to an existing table.
_LIGHT_MIGRATIONS: list[tuple[str, str, str]] = [
    ("blueprints", "category", "VARCHAR DEFAULT ''"),
    ("designs", "ai_title", "VARCHAR"),
    ("designs", "ai_description", "VARCHAR"),
    ("designs", "ai_tags", "JSON"),
    ("products", "ai_tags", "JSON"),
]


def run_light_migrations() -> None:
    """`Base.metadata.create_all` only creates tables that don't exist yet --
    it won't add a column to a table that's already there. There's no
    Alembic in this project (SQLite, single small app), so new columns get a
    one-line guarded ALTER TABLE here instead of a migration framework."""

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    columns_by_table = {
        table: {col["name"] for col in inspector.get_columns(table)} for table in existing_tables
    }

    for table, column, ddl_type in _LIGHT_MIGRATIONS:
        if table not in existing_tables or column in columns_by_table.get(table, set()):
            continue
        with engine.begin() as conn:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}"))
