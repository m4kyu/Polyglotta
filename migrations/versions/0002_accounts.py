"""Add private profiles and preserve the journal for local owner setup."""
from alembic import op

revision = "0002_accounts"
down_revision = "0001_journal"
branch_labels = depends_on = None


def upgrade():
    run = op.get_bind().exec_driver_sql
    run("""CREATE TABLE accounts (id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT COLLATE NOCASE UNIQUE, password_hash TEXT)""")
    run("""CREATE TABLE login_sessions (digest TEXT PRIMARY KEY NOT NULL,
        account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
        expires INTEGER NOT NULL)""")
    run("CREATE INDEX ix_login_sessions_expires ON login_sessions(expires)")
    run("""CREATE TABLE auth_attempts (key TEXT PRIMARY KEY NOT NULL,
        expires INTEGER NOT NULL, count INTEGER NOT NULL)""")
    run("CREATE INDEX ix_auth_attempts_expires ON auth_attempts(expires)")
    run("ALTER TABLE languages RENAME TO old_languages")
    run("""CREATE TABLE languages (id INTEGER PRIMARY KEY, name TEXT NOT NULL COLLATE NOCASE,
        account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
        UNIQUE(account_id, name))""")
    if run("SELECT 1 FROM old_languages LIMIT 1").first():
        owner = run("INSERT INTO accounts DEFAULT VALUES").lastrowid
        run("INSERT INTO languages SELECT id, name, ? FROM old_languages", (owner,))
    for table, columns in (
        ("activities", "id, language_id, kind, title, day, minutes, url"),
        ("cards", "id, language_id, front, back, url"),
        ("demo_journals", "language_id"),
    ):
        run(f"ALTER TABLE {table} RENAME TO old_{table}")
        fields = {
            "activities": "id INTEGER PRIMARY KEY, kind TEXT NOT NULL, title TEXT NOT NULL, day TEXT NOT NULL, minutes INTEGER NOT NULL, url TEXT,",
            "cards": "id INTEGER PRIMARY KEY, front TEXT NOT NULL, back TEXT NOT NULL, url TEXT,",
            "demo_journals": "",
        }[table]
        key = "PRIMARY KEY" if table == "demo_journals" else "NOT NULL"
        run(f"CREATE TABLE {table} ({fields} language_id INTEGER {key} REFERENCES languages(id) ON DELETE CASCADE)")
        run(f"INSERT INTO {table} ({columns}) SELECT {columns} FROM old_{table}")
        run(f"DROP TABLE old_{table}")
    run("DROP TABLE old_languages")
    run("CREATE INDEX activity_history ON activities(language_id, day, id)")


def downgrade():
    raise RuntimeError("Restore the pre-upgrade backup to recover the single-profile schema.")
