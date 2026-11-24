from fastapi import APIRouter
from sqlalchemy import select

from .. import schemas
from ..dependencies import DB, LanguageID, scoped_entry
from ..models import Card

router = APIRouter(prefix="/{language_id}/cards", tags=["Cards"])


@router.get("", response_model=list[schemas.CardRead])
def list_cards(language_id: LanguageID, db: DB):
    query = select(Card).where(Card.language_id == language_id)
    return db.scalars(query.order_by(Card.id.desc())).all()


@router.post("", status_code=201, response_model=schemas.CardRead)
def create(language_id: LanguageID, item: schemas.Card, db: DB):
    entry = Card(language_id=language_id, **item.model_dump(mode="json"))
    db.add(entry)
    db.commit()
    return entry


@router.put("/{key}", response_model=schemas.CardRead)
def edit(language_id: LanguageID, key: int, item: schemas.Card, db: DB):
    entry = scoped_entry(db, Card, key, language_id)
    for field, value in item.model_dump(mode="json").items():
        setattr(entry, field, value)
    db.commit()
    return entry
