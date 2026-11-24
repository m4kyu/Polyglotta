from fastapi import APIRouter
from sqlalchemy import select

from .. import schemas
from ..dependencies import DB, LanguageID, scoped_entry
from ..models import Activity

router = APIRouter(prefix="/{language_id}/activities", tags=["Activities"])


@router.get("", response_model=list[schemas.ActivityRead])
def list_activities(language_id: LanguageID, db: DB):
    query = select(Activity).where(Activity.language_id == language_id)
    return db.scalars(query.order_by(Activity.day.desc(), Activity.id.desc())).all()


@router.post("", status_code=201, response_model=schemas.ActivityRead)
def create(language_id: LanguageID, item: schemas.Activity, db: DB):
    entry = Activity(language_id=language_id, **item.model_dump(mode="json"))
    db.add(entry)
    db.commit()
    return entry


@router.put("/{key}", response_model=schemas.ActivityRead)
def edit(language_id: LanguageID, key: int, item: schemas.Activity, db: DB):
    entry = scoped_entry(db, Activity, key, language_id)
    for field, value in item.model_dump(mode="json").items():
        setattr(entry, field, value)
    db.commit()
    return entry
