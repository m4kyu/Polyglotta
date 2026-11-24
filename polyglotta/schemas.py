from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, Field, HttpUrl, StringConstraints

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


class LanguageRead(Language):
    id: int


class ActivityRead(Activity):
    id: int
    language_id: int


class CardRead(Card):
    id: int
    language_id: int


class DailyMinutes(BaseModel):
    day: date
    video: int
    article: int


class Statistics(BaseModel):
    weekly: int
    total: int
    by_type: dict[str, int]
    days: list[DailyMinutes]
