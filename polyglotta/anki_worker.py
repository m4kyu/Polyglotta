"""Use a separate Anki client collection for review snapshots and outgoing notes."""
from datetime import datetime, timedelta
from hashlib import sha1
from html import escape
import json
import time

from anki.collection import Collection
from anki.sync_pb2 import SyncAuth
from sqlalchemy import bindparam, update

from .models import AnkiExport, AnkiLink


def snapshot(col):
    cutoff = datetime.fromtimestamp(col.sched.day_cutoff)
    today = cutoff.date() - timedelta(days=1)
    # Use local calendar midnights/rollover across daylight saving transitions.
    start = cutoff - timedelta(days=180)
    decks = [{"id": d.id, "name": d.name} for d in col.decks.all_names_and_ids(include_filtered=False)]
    rows = col.db.all("""SELECT COALESCE(NULLIF(c.odid,0),c.did),r.id,r.ease,r.time
        FROM revlog r JOIN cards c ON c.id=r.cid WHERE r.id>=? AND r.id<?
        AND r.ease BETWEEN 1 AND 4 AND r.type BETWEEN 0 AND 3""",
        int(start.timestamp()*1000), int(cutoff.timestamp()*1000))
    totals = {}
    for deck, stamp, rating, millis in rows:
        local = datetime.fromtimestamp(stamp/1000)
        day = local.date() - timedelta(days=int(local.time() < cutoff.time()))
        bucket = totals.setdefault((deck,day.isoformat(),rating),[0,0])
        bucket[0] += 1
        bucket[1] += millis
    return {"decks": decks, "today": today.isoformat(),
            "reviews": [[*key,*value] for key,value in totals.items()]}


def add_export(col, job):
    if col.db.scalar("SELECT id FROM notes WHERE guid=?",job["guid"]):
        return True
    deck = col.decks.get(job["deck"], default=False)
    model = next((m for m in col.models.all() if m["type"] == 0 and
                  [f["name"] for f in m["flds"]] == ["Front","Back"] and len(m["tmpls"]) == 1), None)
    if not deck or deck["dyn"] or not model:
        return False
    note = col.new_note(model)
    note.guid = job["guid"]
    note["Front"] = escape(job["front"]).replace("\n","<br>")
    note["Back"] = escape(job["back"]).replace("\n","<br>")
    if job["url"]:
        note["Back"] += '<br>' + escape(job["url"])
    col.add_note(note, job["deck"])
    return True


def refresh(engine, link, jobs, secret, port):
    uid = link["account_id"]
    # The pinned official server derives its sync bearer key from the configured
    # username:PHC string. Keep that credential exclusively in the service directory.
    key = sha1(f"p{uid}:{secret.read_text()}".encode()).hexdigest()
    auth = SyncAuth(hkey=key, endpoint=f"http://127.0.0.1:{port}/", io_timeout_secs=60)
    col = Collection(str(secret.parent/"collection.anki2"))
    try:
        if not link["updated"]:
            col.close_for_full_sync()
            col.full_upload_or_download(auth=auth, server_usn=None, upload=False)
            col.reopen(after_full_sync=True)
        out = col.sync_collection(auth, sync_media=False)
        states = []
        current_link = update(AnkiLink).where(
            AnkiLink.account_id == uid, AnkiLink.generation == link["generation"]
        )
        if out.required in (out.NORMAL_SYNC,out.NO_CHANGES):
            states = [
                {"job_guid": job["guid"],
                 "new_state": "Sent" if add_export(col, job) else "Check deck or note type"}
                for job in jobs
            ]
            if states:
                out = col.sync_collection(auth, sync_media=False)
        if out.required not in (out.NORMAL_SYNC,out.NO_CHANGES):
            with engine.begin() as db:
                db.execute(current_link.values(
                    paused=1, message="Full sync required. Ask the operator to reconcile your collection."
                ))
            return
        data = snapshot(col)
        with engine.begin() as db:
            if states:
                db.execute(update(AnkiExport).where(AnkiExport.guid == bindparam("job_guid"))
                           .values(state=bindparam("new_state")), states)
            db.execute(current_link.values(snapshot=json.dumps(data), updated=int(time.time()), message=None))
    finally:
        col.close()
