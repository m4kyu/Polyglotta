from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Activity


def immersion_statistics(db: Session, language_id: int, today: date, days: int):
    start = today - timedelta(days=days - 1)
    week = today - timedelta(days=6)
    buckets = {(start + timedelta(days=i)).isoformat(): {"video": 0, "article": 0}
               for i in range(days)}
    totals = {"video": 0, "article": 0}
    weekly = 0
    query = (select(Activity.day, Activity.kind, func.sum(Activity.minutes))
             .where(Activity.language_id == language_id)
             .group_by(Activity.day, Activity.kind))
    for day, kind, minutes in db.execute(query):
        totals[kind] += minutes
        if week.isoformat() <= day <= today.isoformat():
            weekly += minutes
        if day in buckets:
            buckets[day][kind] += minutes
    return {"weekly": weekly, "total": sum(totals.values()), "by_type": totals,
            "days": [{"day": day, **values} for day, values in buckets.items()]}
