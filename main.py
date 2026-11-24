import os
import sqlite3
from contextlib import asynccontextmanager, contextmanager
from datetime import date, timedelta
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, HttpUrl, StringConstraints

from demo import populate

ROOT = Path(__file__).resolve().parent
DATABASE = Path(os.environ.get("POLYGLOTTA_DB", ROOT / "data" / "polyglotta.sqlite3"))
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
CardText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]


class Language(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


class Activity(BaseModel):
    kind: Literal["video", "article"]
    title: Title
    day: date
    minutes: Annotated[int, Field(strict=True, gt=0, le=1440)]
    url: HttpUrl | None = None


class Card(BaseModel):
    front: CardText
    back: CardText
    url: HttpUrl | None = None


@contextmanager
def connection():
    db = sqlite3.connect(DATABASE, check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    try:
        with db:
            yield db
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app):
    DATABASE.parent.mkdir(parents=True, exist_ok=True)
    with connection() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS languages (
                id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE COLLATE NOCASE);
            CREATE TABLE IF NOT EXISTS demo_journals (
                language_id INTEGER PRIMARY KEY REFERENCES languages(id));
            CREATE TABLE IF NOT EXISTS activities (
                id INTEGER PRIMARY KEY, language_id INTEGER NOT NULL REFERENCES languages(id),
                kind TEXT NOT NULL, title TEXT NOT NULL, day TEXT NOT NULL,
                minutes INTEGER NOT NULL, url TEXT);
            CREATE INDEX IF NOT EXISTS activity_history ON activities(language_id, day, id);
            CREATE TABLE IF NOT EXISTS cards (
                id INTEGER PRIMARY KEY, language_id INTEGER NOT NULL REFERENCES languages(id),
                front TEXT NOT NULL, back TEXT NOT NULL, url TEXT);
        """)
    yield


app = FastAPI(title="Polyglotta", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
base = "/api/languages"
scope = base + "/{language_id}"


@app.get("/")
def index():
    return FileResponse(ROOT / "static/index.html")


@app.get(base)
def languages():
    with connection() as db:
        return [dict(row) for row in db.execute("SELECT * FROM languages ORDER BY id")]


@app.post(base, status_code=201)
def add_language(item: Language):
    try:
        with connection() as db:
            key = db.execute("INSERT INTO languages(name) VALUES (?)", (item.name,)).lastrowid
            return {"id": key, "name": item.name}
    except sqlite3.IntegrityError:
        raise HTTPException(409, "You already track that language.")


@app.post(base + "/demo")
def load_demo(today: Annotated[date, Query(ge=date(2, 1, 1))]):
    with connection() as db:
        return {"language_id": populate(db, today)}


def language_db(language_id: int):
    with connection() as db:
        if not db.execute("SELECT 1 FROM languages WHERE id=?", (language_id,)).fetchone():
            raise HTTPException(404, "Language not found.")
        yield db


DB = Annotated[sqlite3.Connection, Depends(language_db)]


@app.get(scope + "/activities")
def activities(language_id: int, db: DB):
    return [dict(row) for row in db.execute(
        "SELECT * FROM activities WHERE language_id=? ORDER BY day DESC, id DESC", (language_id,))]


@app.get(scope + "/cards")
def cards(language_id: int, db: DB):
    return [dict(row) for row in db.execute(
        "SELECT * FROM cards WHERE language_id=? ORDER BY id DESC", (language_id,))]


def save(db, table, language_id, item, key=None):
    # Column names come exclusively from the validated model.
    fields = item.model_dump(mode="json")
    if key is None:
        columns = ", ".join(fields)
        marks = ", ".join("?" for _ in fields)
        key = db.execute(f"INSERT INTO {table}(language_id, {columns}) VALUES (?, {marks})",
                         (language_id, *fields.values())).lastrowid
    else:
        assignments = ", ".join(f"{field}=?" for field in fields)
        changed = db.execute(f"UPDATE {table} SET {assignments} WHERE language_id=? AND id=?",
                             (*fields.values(), language_id, key))
        if not changed.rowcount:
            raise HTTPException(404, "Entry not found.")
    return {"id": key, "language_id": language_id, **fields}


@app.post(scope + "/activities", status_code=201)
def add_activity(language_id: int, item: Activity, db: DB):
    return save(db, "activities", language_id, item)


@app.put(scope + "/activities/{key}")
def edit_activity(language_id: int, key: int, item: Activity, db: DB):
    return save(db, "activities", language_id, item, key)


@app.post(scope + "/cards", status_code=201)
def add_card(language_id: int, item: Card, db: DB):
    return save(db, "cards", language_id, item)


@app.put(scope + "/cards/{key}")
def edit_card(language_id: int, key: int, item: Card, db: DB):
    return save(db, "cards", language_id, item, key)


@app.delete(scope + "/{collection}/{key}", status_code=204)
def delete_entry(language_id: int, collection: Literal["activities", "cards"], key: int, db: DB):
    if not db.execute(f"DELETE FROM {collection} WHERE language_id=? AND id=?",
                      (language_id, key)).rowcount:
        raise HTTPException(404, "Entry not found.")
    return Response(status_code=204)


@app.get(scope + "/statistics")
def statistics(language_id: int, today: date, db: DB, days: int = Query(7, ge=1, le=30)):
    start = today - timedelta(days=days - 1)
    week = today - timedelta(days=6)
    buckets = {(start + timedelta(days=i)).isoformat(): {"video": 0, "article": 0}
               for i in range(days)}
    totals = {"video": 0, "article": 0}
    weekly = 0
    for row in db.execute("""SELECT day, kind, SUM(minutes) AS minutes FROM activities
                             WHERE language_id=? GROUP BY day, kind""", (language_id,)):
        day, kind, minutes = row
        totals[kind] += minutes
        if week.isoformat() <= day <= today.isoformat():
            weekly += minutes
        if day in buckets:
            buckets[day][kind] = minutes
    return {"weekly": weekly, "total": sum(totals.values()), "by_type": totals,
            "days": [{"day": day, **values} for day, values in buckets.items()]}
