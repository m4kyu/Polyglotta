"""Local Anki operator commands and single-host sync supervisor."""

import argparse
import base64
import fcntl
import hashlib
import os
from pathlib import Path
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import time

from sqlalchemy import delete, insert, select, update

from .database import make_engine
from .models import Account, AnkiCleanup, AnkiDeckMap, AnkiExport, AnkiGate, AnkiLink, Card, Language

ROOT = Path(os.environ.get("POLYGLOTTA_ANKI_DIR", "data/anki")).resolve()
DATABASE = Path(os.environ.get("POLYGLOTTA_DB", "data/polyglotta.sqlite3")).resolve()
PORT = int(os.environ.get("POLYGLOTTA_ANKI_PORT", "8081"))


def secret_path(uid, generation):
    return ROOT / "users" / f"p{uid}" / generation


def provision(engine, action, username):
    with engine.execution_options(sqlite_write=True).begin() as db:
        uid = db.scalar(select(Account.id).where(Account.username == username))
        if uid is None:
            raise SystemExit("Unknown profile.")
        link = db.execute(
            select(AnkiLink.generation, AnkiLink.paused).where(AnkiLink.account_id == uid)
        ).one_or_none()
        if action == "link" and link:
            raise SystemExit("Already linked. Use rotate to replace the credentials.")
        if action != "link" and not link:
            raise SystemExit("Profile has no Anki link.")
        if action == "resume":
            if not link.paused:
                raise SystemExit("This collection is not paused.")
            # A full download replaces only the worker replica. Keep the old database
            # and SQLite sidecars together until account cleanup.
            folder = secret_path(uid, link.generation).parent
            backup = folder / ("paused-" + secrets.token_hex(8))
            backup.mkdir()
            for file in folder.glob("collection.anki2*"):
                file.rename(backup / file.name)
            db.execute(update(AnkiLink).where(AnkiLink.account_id == uid)
                       .values(paused=0, updated=None, message=None))
            return
        if action == "revoke":
            languages = select(Language.id).where(Language.account_id == uid)
            cards = select(Card.id).where(Card.language_id.in_(languages))
            db.execute(delete(AnkiLink).where(AnkiLink.account_id == uid))
            db.execute(delete(AnkiDeckMap).where(AnkiDeckMap.language_id.in_(languages)))
            db.execute(delete(AnkiExport).where(AnkiExport.card_id.in_(cards)))
            return
        if db.scalar(select(AnkiCleanup.account_id).where(AnkiCleanup.account_id == uid)) is not None:
            raise SystemExit("Wait for revoked data to be removed before relinking.")
        password = secrets.token_urlsafe(32)
        salt = secrets.token_bytes(16)
        derived = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 210000)

        def encode(value):
            return base64.b64encode(value).decode().rstrip("=")

        phc = f"$pbkdf2-sha256$i=210000,l=32${encode(salt)}${encode(derived)}"
        generation = secrets.token_hex(16)
        path = secret_path(uid, generation)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(phc)
        if link:
            db.execute(update(AnkiLink).where(AnkiLink.account_id == uid).values(generation=generation))
        else:
            db.execute(insert(AnkiLink).values(account_id=uid, generation=generation))
    if link:
        secret_path(uid, link.generation).unlink(missing_ok=True)
    print(f"Sync username: p{uid}\nOne-time password: {password}")


def linked_profiles(db):
    query = select(AnkiLink.account_id, AnkiLink.generation).order_by(AnkiLink.account_id)
    return db.execute(query).all()


def serve(engine):
    from anki.buildinfo import version

    if version != "26.09.4":
        raise SystemExit("Install Anki 26.09.4 in the service environment.")
    from .anki_worker import refresh

    process = None
    configured = None
    next_check = {}

    def stop():
        if process is not None and process.poll() is None:
            process.terminate()
            process.wait()

    try:
        while True:
            with engine.connect() as db:
                links = linked_profiles(db)
                ready = db.scalar(select(AnkiGate.ready))
            if (
                links != configured
                or (links and not ready)
                or (process and process.poll() is not None)
            ):
                stop()
                process = None
                env = {k: v for k, v in os.environ.items() if not k.startswith("SYNC_")}
                env.update(
                    SYNC_HOST="0.0.0.0",
                    SYNC_PORT=str(PORT),
                    SYNC_BASE=str(ROOT / "server"),
                    PASSWORDS_HASHED="1",
                )
                for i, (uid, generation) in enumerate(links, 1):
                    path = secret_path(uid, generation)
                    try:
                        env[f"SYNC_USER{i}"] = f"p{uid}:" + path.read_text()
                    except FileNotFoundError:
                        break
                if any(f"SYNC_USER{i}" not in env for i in range(1, len(links) + 1)):
                    configured = None
                    time.sleep(1)
                    continue
                if links:
                    process = subprocess.Popen(
                        [sys.executable, "-m", "anki.syncserver"], env=env
                    )
                    for _ in range(100):
                        if process.poll() is not None:
                            raise RuntimeError(
                                "Anki sync server exited during startup."
                            )
                        try:
                            with socket.create_connection(
                                ("127.0.0.1", PORT), timeout=0.2
                            ):
                                break
                        except OSError:
                            time.sleep(0.1)
                    else:
                        raise RuntimeError("Anki sync server did not start.")
                with engine.execution_options(sqlite_write=True).begin() as db:
                    latest = linked_profiles(db)
                    db.execute(update(AnkiGate).values(ready=int(bool(links) and links == latest)))
                configured = links
                next_check.clear()
            with engine.connect() as db:
                pending_cleanup = db.scalars(select(AnkiCleanup.account_id)).all()
            for uid in pending_cleanup:
                if any(id_ == uid for id_, _ in configured):
                    continue
                for directory in (
                    ROOT / "users" / f"p{uid}",
                    ROOT / "server" / f"p{uid}",
                ):
                    if directory.exists():
                        shutil.rmtree(directory)
                with engine.begin() as db:
                    db.execute(delete(AnkiCleanup).where(AnkiCleanup.account_id == uid))
            for uid, generation in links:
                with engine.connect() as db:
                    link = db.execute(select(AnkiLink).where(
                        AnkiLink.account_id == uid, AnkiLink.generation == generation
                    )).mappings().one_or_none()
                    if not link or link["paused"]:
                        continue
                    jobs = db.execute(
                        select(AnkiExport).join(Card).join(Language)
                        .where(Language.account_id == uid, AnkiExport.state == "Queued")
                    ).mappings().all()
                if time.monotonic() < next_check.get(uid, 0) and not jobs:
                    continue
                next_check[uid] = time.monotonic() + 300
                try:
                    if not (ROOT / "server" / f"p{uid}" / "collection.anki2").exists():
                        next_check[uid] = time.monotonic() + 5
                        continue
                    refresh(engine, link, jobs, secret_path(uid, generation), PORT)
                except Exception as error:
                    next_check[uid] = time.monotonic() + 15
                    print(
                        f"Sync refresh p{uid}: {type(error).__name__}",
                        file=sys.stderr,
                        flush=True,
                    )
                    with engine.begin() as db:
                        db.execute(update(AnkiLink).where(
                            AnkiLink.account_id == uid, AnkiLink.generation == generation
                        ).values(message="Sync unavailable. Check the host or try again shortly."))
                    time.sleep(3)
            time.sleep(2)
    finally:
        stop()
        with engine.begin() as db:
            db.execute(update(AnkiGate).values(ready=0))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=["link", "rotate", "revoke", "resume", "serve"]
    )
    parser.add_argument("username", nargs="?")
    args = parser.parse_args()
    os.umask(0o077)
    ROOT.mkdir(parents=True, exist_ok=True)
    engine = make_engine(DATABASE, existing_only=True, timeout=15)
    try:
        if args.action == "serve":
            with (ROOT / "service.lock").open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
                serve(engine)
        else:
            provision(engine, args.action, args.username)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
