from sqlalchemy import ForeignKey, Index, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Language(Base):
    __tablename__ = "languages"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text(collation="NOCASE"), unique=True)


class DemoJournal(Base):
    __tablename__ = "demo_journals"

    language_id: Mapped[int] = mapped_column(ForeignKey("languages.id"), primary_key=True)


class Activity(Base):
    __tablename__ = "activities"
    __table_args__ = (Index("activity_history", "language_id", "day", "id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    language_id: Mapped[int] = mapped_column(ForeignKey("languages.id"))
    kind: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    day: Mapped[str] = mapped_column(Text)
    minutes: Mapped[int]
    url: Mapped[str | None] = mapped_column(Text)


class Card(Base):
    __tablename__ = "cards"

    id: Mapped[int] = mapped_column(primary_key=True)
    language_id: Mapped[int] = mapped_column(ForeignKey("languages.id"))
    front: Mapped[str] = mapped_column(Text)
    back: Mapped[str] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
