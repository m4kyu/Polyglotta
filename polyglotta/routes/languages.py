from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .. import models, schemas
from ..dependencies import DB, User, LanguageID, scoped_entry
from ..services.demo import populate

router = APIRouter(tags=["Languages"])


@router.get("", response_model=list[schemas.LanguageRead])
def languages(db: DB, user: User):
    return db.scalars(select(models.Language).where(models.Language.account_id == user.id).order_by(models.Language.id)).all()


@router.post("", status_code=201, response_model=schemas.LanguageRead)
def add_language(item: schemas.Language, db: DB, user: User):
    language = models.Language(name=item.name, account_id=user.id)
    db.add(language)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(409, "You already track that language.") from error
    return language


@router.post("/demo")
def load_demo(today: Annotated[date, Query(ge=date(2, 1, 1))], db: DB, user: User):
    language_id = populate(db, today, user.id)
    db.commit()
    return {"language_id": language_id}


@router.delete("/{language_id}/{collection}/{key}", status_code=204)
def delete_entry(language_id: LanguageID, collection: Literal["activities", "cards"],
                 key: int, db: DB):
    model = models.Activity if collection == "activities" else models.Card
    db.delete(scoped_entry(db, model, key, language_id))
    db.commit()
    return Response(status_code=204)
