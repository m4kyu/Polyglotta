from alembic import context
from sqlalchemy import INTEGER, Table, event

from polyglotta.database import database_path, make_engine
from polyglotta.models import Base


def normalize_rowid(inspector, table, column):
    # SQLite reports legacy INTEGER PRIMARY KEY columns as nullable even though
    # the rowid always has a value. Normalize this during Alembic reflection.
    legacy_keys = {"activities": "id", "cards": "id", "languages": "id",
                   "demo_journals": "language_id"}
    if (inspector.bind.dialect.name == "sqlite"
            and column["name"] == legacy_keys.get(table.name)
            and column.get("primary_key") and type(column["type"]) is INTEGER):
        column["nullable"] = False


def run(connection):
    context.configure(connection=connection, target_metadata=Base.metadata,
                      transactional_ddl=True, render_as_batch=True)
    event.listen(Table, "column_reflect", normalize_rowid)
    try:
        with context.begin_transaction():
            context.run_migrations()
    finally:
        event.remove(Table, "column_reflect", normalize_rowid)


connection = context.config.attributes.get("connection")
if connection is not None:
    run(connection)
else:
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = make_engine(path)
    try:
        with engine.execution_options(sqlite_write=True).begin() as connection:
            run(connection)
    finally:
        engine.dispose()
