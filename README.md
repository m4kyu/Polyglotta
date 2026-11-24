# Polyglotta

A personal, local immersion journal with a separate dashboard, activity history, and flashcard deck for each language.

## Run locally

With Python 3.10 or newer, run these commands from the project directory.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn main:app
```

Open http://127.0.0.1:8000 and select **Add language**. Log the minutes you actually spent on an article or video. Use **Activity history** to edit a session or create a flashcard from its source.

SQLite stores your records in `data/polyglotta.sqlite3`. Set `POLYGLOTTA_DB` to use another database path. The active language is remembered in the current browser. This single-profile application is intended for loopback use.

Interactive API documentation is available at http://127.0.0.1:8000/docs.
