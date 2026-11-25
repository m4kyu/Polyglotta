from sqlalchemy import ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str | None] = mapped_column(Text(collation="NOCASE"), unique=True)
    password_hash: Mapped[str | None] = mapped_column(Text)


class LoginSession(Base):
    __tablename__ = "login_sessions"

    digest: Mapped[str] = mapped_column(Text, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    expires: Mapped[int] = mapped_column(index=True)


class Attempt(Base):
    __tablename__ = "auth_attempts"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    expires: Mapped[int] = mapped_column(index=True)
    count: Mapped[int]


class Language(Base):
    __tablename__ = "languages"

    __table_args__ = (UniqueConstraint("account_id", "name"),)

    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text(collation="NOCASE"))


class DemoJournal(Base):
    __tablename__ = "demo_journals"

    language_id: Mapped[int] = mapped_column(ForeignKey("languages.id", ondelete="CASCADE"), primary_key=True)


class Activity(Base):
    __tablename__ = "activities"
    __table_args__ = (Index("activity_history", "language_id", "day", "id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    language_id: Mapped[int] = mapped_column(ForeignKey("languages.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    day: Mapped[str] = mapped_column(Text)
    minutes: Mapped[int]
    url: Mapped[str | None] = mapped_column(Text)


class Card(Base):
    __tablename__ = "cards"

    id: Mapped[int] = mapped_column(primary_key=True)
    language_id: Mapped[int] = mapped_column(ForeignKey("languages.id", ondelete="CASCADE"))
    front: Mapped[str] = mapped_column(Text)
    back: Mapped[str] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)


class AnkiLink(Base):
    __tablename__ = "anki_links"

    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True)
    generation: Mapped[str] = mapped_column(Text)
    snapshot: Mapped[str | None] = mapped_column(Text)
    updated: Mapped[int | None]
    message: Mapped[str | None] = mapped_column(Text)
    paused: Mapped[int] = mapped_column(server_default="0")


class AnkiDeckMap(Base):
    __tablename__ = "anki_maps"

    language_id: Mapped[int] = mapped_column(ForeignKey("languages.id", ondelete="CASCADE"), primary_key=True)
    deck: Mapped[int] = mapped_column(primary_key=True)


class AnkiExport(Base):
    __tablename__ = "anki_exports"

    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id", ondelete="CASCADE"), primary_key=True)
    guid: Mapped[str] = mapped_column(Text, unique=True)
    deck: Mapped[int]
    front: Mapped[str] = mapped_column(Text)
    back: Mapped[str] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str] = mapped_column(Text, server_default="Queued")


class AnkiGate(Base):
    __tablename__ = "anki_gate"

    id: Mapped[int] = mapped_column(primary_key=True)
    ready: Mapped[int]


class AnkiCleanup(Base):
    __tablename__ = "anki_cleanup"

    account_id: Mapped[int] = mapped_column(primary_key=True)
