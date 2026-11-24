# Polyglotta

A personal, local immersion journal with a separate dashboard, activity history, and flashcard deck for each language.

## Run locally

With Python 3.10 or newer, run these commands from the project directory.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn main:app
```

Open http://127.0.0.1:8000 and select **Add language**. For a YouTube video, paste its link in **Source URL** to fill the title and viewing time automatically. Adjust the minutes for a partial session. If the video details are unavailable, you can enter them manually. Use **Activity history** to edit a session or create a flashcard from its source.

SQLite stores your records in `data/polyglotta.sqlite3`. Set `POLYGLOTTA_DB` to use another database path. The active language is remembered in the current browser. This single-profile application is intended for loopback use.

Interactive API documentation is available at http://127.0.0.1:8000/docs.

## Explore the demo

Select **Explore demo** on the empty dashboard or in the language menu. Switch between **Spanish (demo)** and **Japanese (demo)** to compare their immersion calendars, browse sample reading and watching sessions, and practice four phrase cards in each language. Session dates are relative to the first time you open the demo. Reopening it keeps your edits and practice material.

## Backend architecture

`main:app` loads the FastAPI application factory from `polyglotta.application`. Routes handle HTTP validation and responses using Pydantic schemas. SQLAlchemy models describe the journal tables. Each request gets its own synchronous session, and the demo and statistics services contain the logic shared across multiple records. SQLite write transactions reserve the writer before checking existing records, including during concurrent demo requests.

Startup runs Alembic against the configured database. The baseline recognizes both original journal schemas, including the version created before demo support. Subsequent schema changes belong in a new revision under `migrations/versions`. Use `.venv/bin/alembic current` to inspect the revision and `.venv/bin/alembic revision --autogenerate -m "description"` to draft a migration after changing models. Review generated revisions before applying them.

Run the migration regression tests with `.venv/bin/python -m unittest discover -s tests`.
