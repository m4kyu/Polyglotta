from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .models import Activity, Card, Language


def session(request: Request):
    with Session(request.app.state.engine, expire_on_commit=False) as db:
        db.connection(execution_options={"sqlite_write": request.method != "GET"})
        yield db


DB = Annotated[Session, Depends(session)]


def active_language(language_id: int, db: DB):
    if db.get(Language, language_id) is None:
        raise HTTPException(404, "Language not found.")
    return language_id


LanguageID = Annotated[int, Depends(active_language)]


def scoped_entry(db: Session, model: type[Activity] | type[Card], key: int, language_id: int):
    entry = db.get(model, key)
    if entry is None or entry.language_id != language_id:
        raise HTTPException(404, "Entry not found.")
    return entry
