"""Keep custom sync usernames reserved until hosted data cleanup completes."""
from alembic import op
import sqlalchemy as sa

revision = "0004_sync_username"
down_revision = "0003_anki"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("anki_links", "anki_cleanup"):
        op.add_column(table, sa.Column("sync_username", sa.Text(collation="NOCASE")))
    op.create_index("anki_username", "anki_links", ["sync_username"], unique=True)
    run = op.get_bind().exec_driver_sql
    run("DROP TRIGGER anki_remove")
    run("""CREATE TRIGGER anki_remove AFTER DELETE ON anki_links BEGIN
        INSERT OR IGNORE INTO anki_cleanup(account_id,sync_username)
        VALUES(OLD.account_id,OLD.sync_username); END""")


def downgrade():
    raise RuntimeError("Restore the backup made before upgrading.")
