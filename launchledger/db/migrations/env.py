from alembic import context
from sqlalchemy import create_engine, text

from launchledger.db.models import ALL_SCHEMAS, Base
from launchledger.settings import get_settings

target_metadata = Base.metadata


def _include_name(name: str | None, type_: str, parent_names: object) -> bool:
    """Autogenerate only our schemas; never touch alembic's own version table."""
    if type_ == "schema":
        return name in ALL_SCHEMAS
    return not (type_ == "table" and name == "alembic_version")


def run_migrations_online() -> None:
    engine = create_engine(get_settings().database_url)
    with engine.begin() as connection:
        for schema in ALL_SCHEMAS:
            connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            include_name=_include_name,
        )
        with context.begin_transaction():
            context.run_migrations()
        connection.commit()


run_migrations_online()
