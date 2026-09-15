from alembic import context

from app.config import Settings
from app.db import (
    Base,
    make_engine,
    models,  # noqa: F401
)

target_metadata = Base.metadata
if context.is_offline_mode():
    context.configure(
        url=Settings().database_url, target_metadata=target_metadata, literal_binds=True
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    with make_engine(Settings().database_url).connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=connection.dialect.name == "sqlite",
        )
        with context.begin_transaction():
            context.run_migrations()
