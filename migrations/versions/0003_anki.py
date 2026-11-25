"""Private Anki links, language mappings and durable exports."""
from alembic import op

revision = "0003_anki"
down_revision = "0002_accounts"
branch_labels = depends_on = None


def upgrade():
    run = op.get_bind().exec_driver_sql
    run("""CREATE TABLE anki_links (account_id INTEGER PRIMARY KEY, generation TEXT NOT NULL, snapshot TEXT, updated INTEGER,
        message TEXT, paused INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY(account_id) REFERENCES accounts(id) ON DELETE CASCADE)""")
    run("""CREATE TABLE anki_maps (language_id INTEGER NOT NULL, deck INTEGER NOT NULL,
        PRIMARY KEY(language_id,deck), FOREIGN KEY(language_id) REFERENCES languages(id) ON DELETE CASCADE)""")
    run("""CREATE TABLE anki_exports (card_id INTEGER PRIMARY KEY, guid TEXT UNIQUE NOT NULL, deck INTEGER NOT NULL, front TEXT NOT NULL,
        back TEXT NOT NULL, url TEXT, state TEXT NOT NULL DEFAULT 'Queued',
        FOREIGN KEY(card_id) REFERENCES cards(id) ON DELETE CASCADE)""")
    run("CREATE TABLE anki_gate (id INTEGER PRIMARY KEY, ready INTEGER NOT NULL)")
    run("INSERT INTO anki_gate VALUES(1,0)")
    run("CREATE TABLE anki_cleanup (account_id INTEGER PRIMARY KEY)")
    for event in ("INSERT", "UPDATE OF generation", "DELETE"):
        name = event.split()[0].lower()
        run(f"""CREATE TRIGGER anki_changed_{name} AFTER {event} ON anki_links
            BEGIN UPDATE anki_gate SET ready=0; END""")
    run("""CREATE TRIGGER anki_remove AFTER DELETE ON anki_links
        BEGIN INSERT OR IGNORE INTO anki_cleanup VALUES(OLD.account_id); END""")


def downgrade():
    raise RuntimeError("Restore the backup made before enabling Anki.")
