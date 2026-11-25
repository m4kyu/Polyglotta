"""Read published snapshots and enqueue exports. Only the worker opens Anki collections."""
import json
import os
import time
import uuid
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy import text

from ..anki_provisioning import LinkConflict, request_link
from ..dependencies import DB, LanguageID, User, scoped_entry
from ..security import Credentials
from ..models import Card

router = APIRouter(prefix="/api", tags=["Anki"])


class DeckSelection(BaseModel):
    decks: list[int]


class Destination(BaseModel):
    deck: int


@router.get("/anki/ready", include_in_schema=False)
def proxy_gate(db: DB):
    ready = db.scalar(text("SELECT ready FROM anki_gate WHERE id=1"))
    return Response(status_code=204 if ready else 403)


def connection(db, user):
    return db.execute(text("SELECT * FROM anki_links WHERE account_id=:id"),
                      {"id": user.id}).mappings().first()


@router.get("/anki")
def status(db: DB, user: User):
    link = connection(db, user)
    return {"linked": bool(link), "username": (link["sync_username"] or f"p{user.id}") if link else None,
            "endpoint": os.getenv("POLYGLOTTA_ANKI_URL"), "message": link and link["message"]}


@router.post("/anki/connect", status_code=201)
def connect(db: DB, user: User, data: Credentials | None = None):
    endpoint = os.getenv("POLYGLOTTA_ANKI_URL")
    if not endpoint:
        raise HTTPException(503, "Anki sync is unavailable on this host.")
    uid = user.id
    db.close()  # Release the request's SQLite writer lock before provisioning.
    try:
        fields = {"sync_username": data.username, "password": data.password.get_secret_value()} if data else {}
        username, password = request_link(uid, **fields)
    except LinkConflict as error:
        raise HTTPException(409, str(error)) from None
    except (OSError, ValueError, KeyError) as error:
        raise HTTPException(503, "Anki sync is unavailable. Try again shortly.") from error
    return {"endpoint": endpoint, "username": username, **({"password": password} if password else {})}


def assignments(db, user, decks):
    rows = db.execute(text("""SELECT deck, language_id FROM anki_maps JOIN languages
        ON id=language_id WHERE account_id=:id"""), {"id": user.id})
    roots = dict(rows.all())
    names = {deck["name"]: deck["id"] for deck in decks}
    owners = {}
    for deck in decks:
        parts = deck["name"].split("::")
        for n in range(len(parts), 0, -1):
            root = names.get("::".join(parts[:n]))
            if root in roots:
                owners[deck["id"]] = roots[root]
                break
    return roots, owners


@router.get("/languages/{language_id}/anki")
def progress(language_id: LanguageID, user: User, db: DB, days: int = Query(7, ge=1, le=180)):
    link = connection(db, user)
    if not link:
        return {"linked": False}
    snap = json.loads(link["snapshot"] or "{}")
    decks = snap.get("decks", [])
    roots, owners = assignments(db, user, decks)
    mapped = [key for key, value in owners.items() if value == language_id]
    end = date.fromisoformat(snap["today"]) if snap else date.today()
    daily = {(end - timedelta(days=i)).isoformat(): [0]*5 for i in reversed(range(days))}
    for deck, day, rating, count, millis in snap.get("reviews", []):
        if deck in mapped and day in daily:
            daily[day][rating-1] += count
            daily[day][4] += millis
    jobs = db.execute(text("""SELECT card_id,state FROM anki_exports JOIN cards
        ON cards.id=card_id WHERE language_id=:id"""), {"id": language_id})
    return {"linked": True, "updated": link["updated"], "message": link["message"],
            "stale": bool(link["updated"] and time.time()-link["updated"] > 600),
            "decks": decks, "mapped": mapped, "roots": roots, "days": daily,
            "exports": dict(jobs.all())}


@router.put("/languages/{language_id}/anki/decks")
def map_decks(language_id: LanguageID, data: DeckSelection, user: User, db: DB):
    link = connection(db, user)
    decks = json.loads(link["snapshot"])["decks"] if link and link["snapshot"] else []
    names = {d["id"]: d["name"] for d in decks}
    roots, _ = assignments(db, user, decks)
    for key in data.decks:
        if key not in names:
            raise HTTPException(409, "Refresh the deck list.")
        for other, owner in roots.items():
            if owner == language_id or other not in names:
                continue
            a, b = names[key]+"::", names[other]+"::"
            if a.startswith(b) or b.startswith(a):
                raise HTTPException(409, "This deck or a related deck belongs to another language.")
    db.execute(text("DELETE FROM anki_maps WHERE language_id=:id"), {"id": language_id})
    for deck in set(data.decks):
        db.execute(text("INSERT INTO anki_maps VALUES(:id,:deck)"), {"id": language_id, "deck": deck})
    db.commit()
    return Response(status_code=204)


@router.post("/languages/{language_id}/cards/{card_id}/anki", status_code=202)
def send(language_id: LanguageID, card_id: int, data: Destination, user: User, db: DB):
    card = scoped_entry(db, Card, card_id, language_id)
    link = connection(db, user)
    if not link or not link["snapshot"] or link["paused"]:
        raise HTTPException(409, "Check your Anki connection before exporting.")
    decks = json.loads(link["snapshot"])["decks"]
    if assignments(db, user, decks)[1].get(data.deck) != language_id:
        raise HTTPException(409, "Select a mapped deck.")
    db.execute(text("""INSERT INTO anki_exports(card_id,guid,deck,front,back,url)
        VALUES(:id,:guid,:deck,:front,:back,:url) ON CONFLICT(card_id) DO UPDATE
        SET deck=excluded.deck,state='Queued' WHERE state='Check deck or note type'"""),
        {"id": card_id, "guid": uuid.uuid4().hex, "deck": data.deck,
         "front": card.front, "back": card.back, "url": card.url})
    state = db.scalar(text("SELECT state FROM anki_exports WHERE card_id=:id"), {"id": card_id})
    db.commit()
    return {"state": state}
