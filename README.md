# Polyglotta

A private learner journal with a separate dashboard, activity history, and flashcard deck for each language.

## Run locally

With Python 3.10 or newer, run these commands from the project directory.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn main:app
```

Open http://127.0.0.1:8000 and create an account, then select **Add language**. For a YouTube video, paste its link in **Source URL** to fill the title and viewing time automatically. Adjust the minutes for a partial session. If the video details are unavailable, you can enter them manually. Use **Activity history** to edit a session or create a flashcard from its source.

SQLite stores your records in `data/polyglotta.sqlite3`. Set `POLYGLOTTA_DB` to use another database path. The browser remembers each profile’s active language. Open **Account** to sign out or permanently delete your profile with your current password. Use a password manager to retain your credentials. This release has no password reset flow.

## Hosting and existing journals

Run a single application host with persistent SQLite storage and restrict the database and backups to the service operator. Serve the UI and API on the same HTTPS origin behind a TLS reverse proxy. Set `POLYGLOTTA_ORIGIN` to the exact external origin (for example `https://journal.example.com`, without a trailing slash). Bind Uvicorn privately and set `--forwarded-allow-ips` to the proxy address. Configure the proxy to overwrite forwarded client IP headers, cap request bodies, and keep cookies and request bodies out of logs. Browser writes must include the matching Origin header. The default origin supports local development at the exact loopback URL above.

Before upgrading, stop the old server and use SQLite’s backup command to create a protected backup. Rehearse the upgrade against a copy using `POLYGLOTTA_DB`. Startup migrates the old journal to an inaccessible owner account. On the host, run the following against the intended database to choose the owner's username and password.

```sh
.venv/bin/python -m polyglotta.claim_journal
```

Sign in and check the original languages, sessions and cards before enabling public traffic. Fresh installations need no owner setup. To roll back, stop the new service and restore the pre-upgrade backup with the previous application version. Define a backup expiry policy and prevent restored backups from reactivating deleted accounts or previously issued sessions.

Interactive API documentation is available at http://127.0.0.1:8000/docs.

## Explore the demo

Select **Explore demo** on the empty dashboard or in the language menu. Switch between **Spanish (demo)** and **Japanese (demo)** to compare their immersion calendars, browse sample reading and watching sessions, and practice four phrase cards in each language. Session dates are relative to the first time you open the demo. Reopening it keeps your edits and practice material.

## Backend architecture

`main:app` loads the FastAPI application factory from `polyglotta.application`. Routes handle HTTP validation and responses using Pydantic schemas. SQLAlchemy models describe the journal tables. Each request gets its own synchronous session, and the demo and statistics services contain the logic shared across multiple records. SQLite write transactions reserve the writer before checking existing records, including during concurrent demo requests.

Startup runs Alembic against the configured database. The baseline recognizes both original journal schemas, including the version created before demo support. Subsequent schema changes belong in a new revision under `migrations/versions`. Use `.venv/bin/alembic current` to inspect the revision and `.venv/bin/alembic revision --autogenerate -m "description"` to draft a migration after changing models. Review generated revisions before applying them.

Run the migration regression tests with `.venv/bin/python -m unittest discover -s tests`.
