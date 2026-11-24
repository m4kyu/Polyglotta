from datetime import date

from fastapi import APIRouter, Query

from ..dependencies import DB, LanguageID
from ..schemas import Statistics
from ..services.statistics import immersion_statistics

router = APIRouter(tags=["Statistics"])


@router.get("/{language_id}/statistics", response_model=Statistics)
def statistics(language_id: LanguageID, today: date, db: DB, days: int = Query(7, ge=1, le=30)):
    return immersion_statistics(db, language_id, today, days)
