"""Initialize a journal or adopt its original unversioned SQLite schema."""
from alembic import op
import sqlalchemy as sa

revision = "0001_journal"
down_revision = None
branch_labels = None
depends_on = None


def baseline():
    # Frozen definitions keep this revision independent of future ORM changes.
    metadata = sa.MetaData()
    sa.Table("languages", metadata,
             sa.Column("id", sa.Integer, primary_key=True),
             sa.Column("name", sa.Text(collation="NOCASE"), nullable=False, unique=True))
    for name, fields in (
        ("activities", [("kind", sa.Text), ("title", sa.Text),
                        ("day", sa.Text), ("minutes", sa.Integer)]),
        ("cards", [("front", sa.Text), ("back", sa.Text)]),
    ):
        sa.Table(name, metadata,
                 sa.Column("id", sa.Integer, primary_key=True),
                 sa.Column("language_id", sa.Integer, sa.ForeignKey("languages.id"), nullable=False),
                 *(sa.Column(key, dtype, nullable=False) for key, dtype in fields),
                 sa.Column("url", sa.Text))
    sa.Index("activity_history", metadata.tables["activities"].c.language_id,
             metadata.tables["activities"].c.day, metadata.tables["activities"].c.id)
    sa.Table("demo_journals", metadata,
             sa.Column("language_id", sa.Integer, sa.ForeignKey("languages.id"), primary_key=True))
    return metadata


def incompatible(detail):
    raise RuntimeError(f"Incompatible unversioned SQLite journal: {detail}")


def validate_legacy(connection, metadata, existing):
    required = {"languages", "activities", "cards"}
    if existing not in (required, required | {"demo_journals"}):
        incompatible(f"unexpected table set {sorted(existing)}")
    inspector = sa.inspect(connection)
    for name in existing:
        table = metadata.tables[name]
        columns = inspector.get_columns(name)
        if {c["name"] for c in columns} != set(table.columns.keys()):
            incompatible(f"{name} columns")
        for column in columns:
            expected = table.c[column["name"]]
            if (column["type"].__visit_name__.upper() != expected.type.__visit_name__.upper()
                    or (not expected.primary_key and column["nullable"] != expected.nullable)
                    or column.get("default") is not None or column.get("computed")):
                incompatible(f"{name}.{expected.name} definition")
        if inspector.get_pk_constraint(name)["constrained_columns"] != list(table.primary_key.columns.keys()):
            incompatible(f"{name} primary key")
        keys = inspector.get_foreign_keys(name)
        actual = [(fk["constrained_columns"], fk["referred_table"], fk["referred_columns"],
                   fk["options"]) for fk in keys]
        expected_keys = [] if name == "languages" else [(["language_id"], "languages", ["id"], {})]
        if actual != expected_keys:
            incompatible(f"{name} foreign keys")
        if inspector.get_check_constraints(name):
            incompatible(f"{name} check constraints")
        # SQLite reflection omits the collation on a unique constraint.
        # Its backing index records the effective collation and uniqueness.
        unique = []
        for index in connection.exec_driver_sql(f"PRAGMA index_list('{name}')").mappings():
            if index["unique"]:
                quoted = connection.dialect.identifier_preparer.quote_identifier(index["name"])
                entries = connection.exec_driver_sql(f"PRAGMA index_xinfo({quoted})").mappings()
                unique.append((index["partial"], [(r["name"], r["coll"]) for r in entries if r["key"]]))
        if unique != ([(0, [("name", "NOCASE")])] if name == "languages" else []):
            incompatible(f"{name} unique constraints")
    indexes = inspector.get_indexes("activities")
    if not any(i["name"] == "activity_history" and i["column_names"] == ["language_id", "day", "id"]
               and i["dialect_options"].get("sqlite_where") is None for i in indexes):
        incompatible("missing or incompatible activity_history index")


def upgrade():
    connection = op.get_bind()
    metadata = baseline()
    existing = set(sa.inspect(connection).get_table_names()) - {"alembic_version"}
    if existing:
        validate_legacy(connection, metadata, existing)
    for table in metadata.sorted_tables:
        if table.name not in existing:
            table.create(connection)


def downgrade():
    baseline().drop_all(op.get_bind())
