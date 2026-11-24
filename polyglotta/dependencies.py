from typing import Annotated

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from .db_session import DB
from .models import Activity, Card, Language
from .security import User


def active_language(language_id: int, db: DB, user: User):
    language = db.get(Language, language_id)
    if language is None or language.account_id != user.id:
        raise HTTPException(404, "Language not found.")
    return language_id


LanguageID = Annotated[int, Depends(active_language)]


def scoped_entry(db: Session, model: type[Activity] | type[Card], key: int, language_id: int):
    entry = db.get(model, key)
    if entry is None or entry.language_id != language_id:
        raise HTTPException(404, "Entry not found.")
    return entry
