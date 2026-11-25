import os
from pathlib import Path

from sqlalchemy import URL, create_engine, event

ROOT = Path(__file__).resolve().parent.parent


def database_path():
    return Path(os.environ.get("POLYGLOTTA_DB", ROOT / "data" / "polyglotta.sqlite3"))


def make_engine(path, *, existing_only=False, timeout=5):
    if existing_only:
        url = URL.create("sqlite", database=Path(path).resolve().as_uri(),
                         query={"mode": "rw", "uri": "true"})
    else:
        url = URL.create("sqlite", database=str(path))
    engine = create_engine(url,
                           hide_parameters=True, connect_args={"check_same_thread": False, "timeout": timeout})

    @event.listens_for(engine, "connect")
    def configure(connection, _):
        connection.isolation_level = None
        connection.execute("PRAGMA foreign_keys = ON").close()

    @event.listens_for(engine, "begin")
    def begin(connection):
        # Reserve the SQLite writer before reading data used in a write decision.
        immediate = connection.get_execution_options().get("sqlite_write", False)
        connection.exec_driver_sql("BEGIN IMMEDIATE" if immediate else "BEGIN")

    return engine


def migrate(engine):
    from alembic import command
    from alembic.config import Config

    config = Config(str(ROOT / "alembic.ini"))
    with engine.execution_options(sqlite_write=True).begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
