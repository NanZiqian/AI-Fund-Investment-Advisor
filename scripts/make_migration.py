"""Developer helper: generate a frozen migration from the current database schema."""

import sys
from pathlib import Path

from alembic.autogenerate import produce_migrations, render_python_code
from alembic.migration import MigrationContext

from app.config import Settings
from app.db import (
    Base,
    make_engine,
    models,  # noqa: F401
)


def main():
    revision, previous = sys.argv[1:3]
    with make_engine(Settings().database_url).connect() as conn:
        migration = produce_migrations(MigrationContext.configure(conn), Base.metadata)
        upgrade = render_python_code(migration.upgrade_ops, user_module_prefix="app.db.")
        downgrade = render_python_code(migration.downgrade_ops, user_module_prefix="app.db.")
    source = (
        "from alembic import op\nimport sqlalchemy as sa\nimport app.db\n\n"
        f"revision = {revision!r}\ndown_revision = {previous!r}\n"
        "branch_labels = None\ndepends_on = None\n\n"
        f"def upgrade():\n{upgrade}\n\ndef downgrade():\n{downgrade}\n"
    )
    Path(f"migrations/versions/{revision}_schema.py").write_text(source, encoding="utf-8")


if __name__ == "__main__":
    main()
